"""Compaction Engine (P4): saliency-driven long -> short.

Implements the deterministic core of the owner's clip-scoring rubric over the
Phase-1 understanding data (the rubric's judgment scores — hook strength,
self-containment, payoff — are an optional LLM pass that adds to these
subscores; the deterministic engine must stand alone, per the rubric's tuning
rule: one rubric, per-brand weights).

Pipeline (pure functions):
  candidates()  — sliding windows over transcript segments (active ranges when
                  no speech), snapped to scene/silence boundaries, deduped by
                  non-max suppression (>50% overlap)
  score()       — weighted subscores: saliency, density, duration_fit, silence
  select()      — top candidates by score, chronological, until target reached
  plan_compact()— ops plan that keeps the selected source spans and deletes the
                  rest (ripple), for one asset's clips on the timeline

Output contract per the clip-scoring skill: every candidate carries
{clip_id, start_ms, end_ms, score, subscores, rationale, hook_text,
 suggested_title} and the full report is checkpointed by the compaction job.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..understanding.schema import Understanding

# Platform bands (ms). Defaults per the rubric; profiles override.
DEFAULT_BAND = (15_000, 58_000)
DEFAULT_SWEET = (25_000, 40_000)

# Deterministic weights (rubric weights for the signals we can compute without
# an LLM; judgment scores add on top when a scorer backend is configured).
DEFAULT_WEIGHTS = {
    "saliency": 3.0,      # stands in for emotional charge/hook until LLM pass
    "density": 1.0,
    "duration_fit": 1.0,
    "silence": 2.0,       # penalty weight
}


@dataclass
class Candidate:
    clip_id: str
    start_ms: int          # source time
    end_ms: int
    score: float = 0.0
    subscores: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    hook_text: str = ""
    suggested_title: str = ""

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id, "start_ms": self.start_ms, "end_ms": self.end_ms,
            "score": round(self.score, 3),
            "subscores": {k: round(v, 3) for k, v in self.subscores.items()},
            "rationale": self.rationale, "hook_text": self.hook_text,
            "suggested_title": self.suggested_title,
        }


def _snap(t: int, anchors: list[int], tolerance_ms: int = 700) -> int:
    """Snap a boundary to the nearest scene/silence anchor within tolerance."""
    best = min(anchors, key=lambda a: abs(a - t), default=None)
    return best if best is not None and abs(best - t) <= tolerance_ms else t


def _overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def candidates(
    u: Understanding,
    band: tuple[int, int] = DEFAULT_BAND,
) -> list[Candidate]:
    """Sliding windows over transcript segments (or active ranges), snapped and
    deduplicated. Boundaries never cut words: they land on segment edges."""
    lo, hi = band
    segs: list[tuple[int, int, str]] = []
    if u.transcript and u.transcript.segments:
        segs = [(s.start_ms, s.end_ms, s.text) for s in u.transcript.segments]
    elif u.active_ranges:
        segs = [(r.start_ms, r.end_ms, "") for r in u.active_ranges]
    if not segs:
        return []

    anchors = sorted({0, u.duration_ms}
                     | {s.start_ms for s in u.scenes}
                     | {sp.end_ms for sp in u.silence} | {sp.start_ms for sp in u.silence})

    out: list[Candidate] = []
    n = 0
    for i in range(len(segs)):
        for j in range(i, len(segs)):
            start, end = segs[i][0], segs[j][1]
            dur = end - start
            if dur < lo:
                continue
            if dur > hi:
                break
            snapped_start = min(_snap(start, anchors), start)  # never cut into a word
            snapped_end = max(_snap(end, anchors), end)
            text = " ".join(t for _, _, t in segs[i : j + 1] if t).strip()
            hook = " ".join(text.split()[:12])
            n += 1
            out.append(Candidate(
                clip_id=f"cand_{n:03d}",
                start_ms=max(0, snapped_start),
                end_ms=min(u.duration_ms, snapped_end),
                hook_text=hook,
                suggested_title=(hook[:60] or f"Clip {n}"),
            ))

    # Non-max placeholder ordering happens after scoring; here just dedupe exact.
    seen: set[tuple[int, int]] = set()
    uniq = []
    for c in out:
        key = (c.start_ms, c.end_ms)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def score(
    cands: list[Candidate],
    u: Understanding,
    sweet: tuple[int, int] = DEFAULT_SWEET,
    weights: dict[str, float] | None = None,
) -> list[Candidate]:
    """Deterministic subscores (each 0-10) + weighted sum, in place."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    sal_windows = u.saliency.windows if u.saliency else []
    word_spans: list[tuple[int, int]] = []
    if u.transcript:
        for s in u.transcript.segments:
            word_spans += [(wd.start_ms, wd.end_ms) for wd in s.words]

    for c in cands:
        dur = c.duration_ms
        # Saliency: coverage-weighted mean of window scores over the candidate.
        if sal_windows:
            num = sum(win.score * _overlap(c.start_ms, c.end_ms, win.start_ms, win.end_ms)
                      for win in sal_windows)
            sal = 10.0 * num / dur
        else:
            sal = 5.0
        # Density: words per second, 3+ w/s ~= 10.
        words_in = sum(1 for s0, s1 in word_spans if c.start_ms <= s0 and s1 <= c.end_ms)
        density = min(10.0, (words_in / (dur / 1000)) / 3.0 * 10.0) if word_spans else 5.0
        # Duration fit: 10 inside the sweet spot, linear falloff outside.
        s_lo, s_hi = sweet
        if s_lo <= dur <= s_hi:
            fit = 10.0
        else:
            dist = (s_lo - dur) if dur < s_lo else (dur - s_hi)
            fit = max(0.0, 10.0 - 10.0 * dist / s_lo)
        # Silence penalty: fraction of the window that is silent.
        silent = sum(_overlap(c.start_ms, c.end_ms, sp.start_ms, sp.end_ms)
                     for sp in u.silence) / dur
        c.subscores = {"saliency": sal, "density": density,
                       "duration_fit": fit, "silence_frac": round(silent * 10, 3)}
        c.score = (w["saliency"] * sal + w["density"] * density
                   + w["duration_fit"] * fit - w["silence"] * silent * 10)
        c.rationale = (
            f"saliency {sal:.1f}, {words_in} words ({density:.1f} density), "
            f"fit {fit:.1f}, silent {silent:.0%}"
        )
    return cands


def nms(cands: list[Candidate], max_overlap: float = 0.5) -> list[Candidate]:
    """Non-max suppression: keep highest-scoring, drop others overlapping >50%."""
    kept: list[Candidate] = []
    for c in sorted(cands, key=lambda x: -x.score):
        ok = True
        for k in kept:
            ov = _overlap(c.start_ms, c.end_ms, k.start_ms, k.end_ms)
            if ov / min(c.duration_ms, k.duration_ms) > max_overlap:
                ok = False
                break
        if ok:
            kept.append(c)
    return kept


def select(cands: list[Candidate], target_ms: int) -> list[Candidate]:
    """Best non-overlapping candidates within the target budget, in
    chronological order (story order is preserved in the compacted cut)."""
    chosen: list[Candidate] = []
    total = 0
    for c in nms(cands):
        if total + c.duration_ms > target_ms and chosen:
            continue
        chosen.append(c)
        total += c.duration_ms
        if total >= target_ms * 0.9:
            break
    chosen.sort(key=lambda c: c.start_ms)
    return chosen


def plan_compact(edl, asset_id: str, keep: list[Candidate]) -> list[dict]:
    """Ops plan: delete every timeline range of `asset_id`'s clips that is NOT
    covered by the kept candidates (source-time), ripple to close gaps.
    Reuses the remove_silence mapping helpers."""
    from ..edl.schema import MediaClip
    from ..edl.smartops import overlap_source_span

    if not keep:
        return []
    keep_src = sorted((c.start_ms, c.end_ms) for c in keep)
    # Complement of kept spans in source time.
    drop_src: list[tuple[int, int]] = []
    cursor = 0
    for s, e in keep_src:
        if s > cursor:
            drop_src.append((cursor, s))
        cursor = max(cursor, e)
    drop_src.append((cursor, 1 << 60))

    tl_ranges: list[tuple[int, int]] = []
    track_ids: list[str] = []
    for track in edl.tracks:
        for clip in track.clips:
            if not isinstance(clip, MediaClip) or clip.asset != asset_id:
                continue
            if track.id not in track_ids:
                track_ids.append(track.id)
            for s, e in drop_src:
                span = overlap_source_span(clip, s, min(e, clip.out_ms))
                if span and span[1] > span[0]:
                    tl_ranges.append(span)

    if not tl_ranges:
        return []
    tl_ranges.sort()
    merged: list[list[int]] = []
    for s, e in tl_ranges:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [
        {"op": "delete_range", "tracks": track_ids, "from_ms": s, "to_ms": e, "ripple": True}
        for s, e in reversed(merged)  # right-to-left so ripple math stays valid
    ]
