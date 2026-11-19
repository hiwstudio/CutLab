"""Matching funnel — Stage A: rank candidate windows by transcript similarity.

Lexical TF-IDF cosine over sliding transcript windows (stdlib only, offline).
An optional embeddings backend (sentence-transformers) can slot in behind
rank_windows() later; lexical is the default pre-filter — the active brain
(Stage B vision) and the user's review are the real judges.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9']+")
_STOP = set("the a an and or of to in on for with is are was were be been it this "
            "that as at by from we you they he she its it's their our your".split())


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP]


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def rank_windows(scene_text: str, visual_intent: str, transcript: list[dict],
                 target_ms: int, top_k: int = 3) -> list[dict]:
    """Slide windows over transcript segments sized to fit the scene duration.

    Returns top_k windows: [{start_ms, end_ms, score, text}] sorted by score.
    Window duration band: [target, target*2.5] with 1.5s pad each side, snapped
    to segment boundaries (clip-scoring conventions: never cut mid-segment).
    """
    if not transcript:
        return []
    query = Counter(_tokens(scene_text) + _tokens(visual_intent))
    lo, hi = target_ms, int(target_ms * 2.5) + 3000
    windows = []
    for i in range(len(transcript)):
        text_parts, j = [], i
        while j < len(transcript):
            text_parts.append(transcript[j]["text"])
            dur = transcript[j]["end_ms"] - transcript[i]["start_ms"]
            if dur >= lo:
                windows.append({
                    "start_ms": max(0, transcript[i]["start_ms"] - 1500),
                    "end_ms": transcript[j]["end_ms"] + 1500,
                    "text": " ".join(text_parts),
                })
            if dur >= hi:
                break
            j += 1
    if not windows:  # video shorter than the scene — offer its full span
        windows = [{"start_ms": max(0, transcript[0]["start_ms"] - 1500),
                    "end_ms": transcript[-1]["end_ms"] + 1500,
                    "text": " ".join(t["text"] for t in transcript)}]
    for w in windows:
        w["score"] = round(_cosine(query, Counter(_tokens(w["text"]))), 4)
    windows.sort(key=lambda w: -w["score"])
    # non-max suppression: drop windows overlapping a better one by >50%
    kept: list[dict] = []
    for w in windows:
        if all(_overlap(w, k) <= 0.5 for k in kept):
            kept.append(w)
        if len(kept) == top_k:
            break
    return kept


def _overlap(a: dict, b: dict) -> float:
    inter = min(a["end_ms"], b["end_ms"]) - max(a["start_ms"], b["start_ms"])
    if inter <= 0:
        return 0.0
    return inter / min(a["end_ms"] - a["start_ms"], b["end_ms"] - b["start_ms"])


# A captionless candidate scores off its TITLE, which is a weaker signal than a
# transcript window, so it is discounted rather than trusted equally. Only matters
# when both kinds compete for one scene; among themselves the discount cancels.
CAPTIONLESS_WEIGHT = 0.6


def positional_windows(title: str, scene_text: str, visual_intent: str,
                       duration_s: float, target_ms: int,
                       top_k: int = 2) -> list[dict]:
    """Windows for footage that has NO transcript.

    B-roll mostly has no captions — a drone pass over a street, stadium footage,
    a walking tour. `rank_windows` returns nothing for those, which silently
    discarded every candidate for an illustrative cutaway (measured: 4 of 4
    perfect Sixth Street results, all captionless, all dropped).

    Relevance therefore comes from the title, and the window is chosen by
    POSITION: skip the intro card and the outro, then offer a couple of points in
    the body. Nothing here claims to find a specific moment — for illustrative
    footage any representative stretch does the job.
    """
    if duration_s <= 0:
        return []
    dur_ms = int(duration_s * 1000)
    want = max(target_ms, 4000)
    if dur_ms <= want + 2000:
        picks = [0]
        want = min(want, dur_ms)
    else:
        lead = min(int(dur_ms * 0.15), 30_000)   # titles, intros, sponsor cards
        tail = min(int(dur_ms * 0.10), 20_000)   # outros, end screens
        span = max(0, (dur_ms - tail) - lead - want)
        picks = sorted({lead + int(span * f) for f in (0.2, 0.55)})
    score = round(_cosine(Counter(_tokens(scene_text) + _tokens(visual_intent)),
                          Counter(_tokens(title))) * CAPTIONLESS_WEIGHT, 4)
    return [{"start_ms": st, "end_ms": min(st + want, dur_ms),
             "score": score, "text": title} for st in picks][:top_k]


def rank_candidates(scene: dict, candidates: list[dict],
                    transcripts: dict[str, list[dict]], top_k: int = 3,
                    allow_captionless: bool = False) -> list[dict]:
    """Rank (video, window) pairs across all candidate videos for one scene.

    `allow_captionless` decides what happens to a candidate with no transcript.
    Off (the default) it is dropped, which is right when the scene must show the
    EVENT being described and the transcript is how that is confirmed. On, it is
    ranked by title with a positional window — right when the scene merely has to
    ILLUSTRATE something that was named, where most usable footage is captionless.
    """
    target_ms = scene["end_ms"] - scene["start_ms"]
    ranked = []
    for cand in candidates:
        windows = rank_windows(
            scene.get("text", ""), scene["visual_intent"],
            transcripts.get(cand["video_id"], []), target_ms, top_k=2)
        if not windows and allow_captionless:
            windows = positional_windows(
                cand.get("title", ""), scene.get("text", ""),
                scene["visual_intent"], cand.get("duration_s", 0), target_ms)
        for w in windows:
            ranked.append({**cand, "clip_start_ms": w["start_ms"],
                           "clip_end_ms": w["end_ms"], "score": w["score"],
                           "matched_text": w["text"][:200]})
    # Fetch reliability is a real ranking factor: yt-dlp must seek to the offset,
    # and deep offsets in long videos are measurably slower and far more likely to
    # time out or hit an expired CDN URL. Demote depth so a shallow, nearly-as-good
    # window wins — a clip we can actually fetch beats a marginally better one we
    # can't. A much stronger match can still outrank a shallow one.
    for r in ranked:
        depth_min = r["clip_start_ms"] / 60000
        r["fetch_score"] = r["score"] / (1 + 0.06 * depth_min)
    ranked.sort(key=lambda r: -r["fetch_score"])
    return ranked[:top_k]
