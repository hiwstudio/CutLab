"""Smart ops (P2 first tier): remove_silence, caption_from_transcript, reframe.

These are real ops in the vocabulary that consume Phase-1 understanding data
(provided via OpContext) and mutate the EDL through the same primitives a human
would use. The heavy lifting is in pure planner functions so it is unit-testable
without the engine; the op classes are thin wrappers.

Design notes in DECISIONS.md (Phase 2). Import-cycle note: this module is imported
by ops.py at the bottom, so it imports names from ops.py lazily inside methods.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import ConfigDict, Field

from ..util import ids
from .schema import CaptionClip, MediaClip, Track, timeline_len_ms

if TYPE_CHECKING:
    from ..understanding.schema import Understanding, Word
    from .ops import OpContext


# -- source<->timeline mapping ------------------------------------------------


def source_ms_to_timeline(clip: MediaClip, src_ms: int) -> int | None:
    """Map a point in the asset's source time to this clip's timeline time.
    Returns None if the source point falls outside the clip's [in,out) window."""
    if src_ms < clip.in_ms or src_ms >= clip.out_ms:
        return None
    return clip.start_ms + int(round((src_ms - clip.in_ms) / clip.speed))


def overlap_source_span(clip: MediaClip, s0: int, s1: int) -> tuple[int, int] | None:
    """Intersect a source-time span [s0,s1) with the clip's window, mapped to
    timeline time. Returns (tl_start, tl_end) or None if no overlap."""
    lo = max(s0, clip.in_ms)
    hi = min(s1, clip.out_ms)
    if lo >= hi:
        return None
    tl_start = clip.start_ms + int(round((lo - clip.in_ms) / clip.speed))
    tl_end = clip.start_ms + int(round((hi - clip.in_ms) / clip.speed))
    return (tl_start, tl_end) if tl_end > tl_start else None


# -- remove_silence -----------------------------------------------------------


def plan_remove_silence(
    edl, understanding: "Understanding", asset_id: str,
    tracks: list[str] | None, min_ms: int, ripple: bool,
) -> list[dict]:
    """Pure planner: emit delete_range op dicts for the timeline ranges where the
    given asset's clips play silent source. Ranges are merged and applied
    right-to-left so earlier ripples don't invalidate later coordinates."""
    silent_source = [(s.start_ms, s.end_ms) for s in understanding.silence
                     if s.end_ms - s.start_ms >= min_ms]
    if not silent_source:
        return []

    target_tracks = edl.tracks if tracks is None else [
        t for t in edl.tracks if t.id in set(tracks)
    ]

    tl_ranges: list[tuple[int, int]] = []
    for track in target_tracks:
        for clip in track.clips:
            if not isinstance(clip, MediaClip) or clip.asset != asset_id:
                continue
            for s0, s1 in silent_source:
                span = overlap_source_span(clip, s0, s1)
                if span:
                    tl_ranges.append(span)

    if not tl_ranges:
        return []

    # Merge overlapping/adjacent timeline ranges.
    tl_ranges.sort()
    merged: list[list[int]] = []
    for s, e in tl_ranges:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    track_ids = [t.id for t in target_tracks]
    # Delete right-to-left so ripple shifts don't move not-yet-processed ranges.
    ops: list[dict] = []
    for s, e in reversed(merged):
        ops.append({
            "op": "delete_range", "tracks": track_ids,
            "from_ms": s, "to_ms": e, "ripple": ripple,
        })
    return ops


# -- caption_from_transcript --------------------------------------------------


def group_words_into_phrases(
    words: list["Word"], max_words: int, max_gap_ms: int
) -> list[tuple[int, int, str]]:
    """Group consecutive words into caption phrases. A group closes at max_words,
    on sentence punctuation, or when the gap to the next word is large. Returns
    (start_ms, end_ms, text) in the asset's SOURCE time."""
    phrases: list[tuple[int, int, str]] = []
    group: list["Word"] = []

    def flush() -> None:
        if not group:
            return
        text = " ".join(w.word for w in group if w.word).strip()
        if text:
            phrases.append((group[0].start_ms, group[-1].end_ms, text))

    for i, w in enumerate(words):
        group.append(w)
        ends_sentence = w.word.rstrip().endswith((".", "?", "!"))
        big_gap = (
            i + 1 < len(words) and words[i + 1].start_ms - w.end_ms > max_gap_ms
        )
        if len(group) >= max_words or ends_sentence or big_gap:
            flush()
            group = []
    flush()
    return phrases


def plan_caption_from_transcript(
    edl, understanding: "Understanding", asset_id: str, track_id: str,
    max_words: int, max_gap_ms: int, cap_style: str | None,
) -> list[dict]:
    """Emit add_caption op dicts for the asset's transcript, timed to where the
    asset actually plays on the timeline (each phrase clipped to the media clips
    that show that source span)."""
    if not understanding.transcript:
        return []
    all_words: list["Word"] = []
    for seg in understanding.transcript.segments:
        all_words.extend(seg.words)
    if not all_words:
        return []

    phrases = group_words_into_phrases(all_words, max_words, max_gap_ms)

    media_clips = [
        c for t in edl.tracks for c in t.clips
        if isinstance(c, MediaClip) and c.asset == asset_id
    ]

    ops: list[dict] = []
    for s0, s1, text in phrases:
        # Place the caption wherever this source span is visible on the timeline.
        for clip in media_clips:
            span = overlap_source_span(clip, s0, s1)
            if not span:
                continue
            start, end = span
            if end <= start:
                continue
            ops.append({
                "op": "add_caption", "track": track_id, "text": text[:500],
                "start_ms": start, "end_ms": end,
                **({"cap_style": cap_style} if cap_style else {}),
            })
    # Sort by start and drop overlaps (a caption track allows no overlap).
    ops.sort(key=lambda o: o["start_ms"])
    deduped: list[dict] = []
    for o in ops:
        if deduped and o["start_ms"] < deduped[-1]["end_ms"]:
            continue
        deduped.append(o)
    return deduped
