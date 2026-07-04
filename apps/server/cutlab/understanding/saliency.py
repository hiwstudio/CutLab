"""Saliency v1 with per-profile weights (P1).

A pure function that folds the other understanding signals (speech, scene change,
beats, silence) into a normalized per-window saliency curve — "how likely is this
window to matter in a shortened cut". The Compaction Engine (P4) consumes this;
P1 only produces it.

Per-profile weights let each brand tune what counts as salient (a talking-head
channel weights speech; a montage channel weights scene change / beats). Weights
come from the project profile; `DEFAULT_WEIGHTS` is the fallback.
"""
from __future__ import annotations

from .schema import (
    ActiveRange,
    Saliency,
    SaliencyWindow,
    Scene,
    SilenceSpan,
    Transcript,
)

DEFAULT_WINDOW_MS = 2000
DEFAULT_WEIGHTS = {
    "speech": 1.0,     # fraction of the window covered by transcribed words
    "scene": 0.4,      # a visual cut opening in the window
    "beat": 0.3,       # musical beat density
    "silence": 0.8,    # penalty for silent coverage
}


def _overlap_ms(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def compute_saliency(
    duration_ms: int,
    profile: str,
    weights: dict[str, float],
    transcript: Transcript | None,
    scenes: list[Scene],
    silence: list[SilenceSpan],
    beats_ms: list[int],
    window_ms: int = DEFAULT_WINDOW_MS,
) -> Saliency:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    windows: list[SaliencyWindow] = []
    if duration_ms <= 0 or window_ms <= 0:
        return Saliency(profile=profile, window_ms=window_ms, windows=windows, weights=w)

    # Precompute word spans (fall back to segment spans when word timings absent).
    word_spans: list[tuple[int, int]] = []
    if transcript:
        for seg in transcript.segments:
            if seg.words:
                word_spans += [(wd.start_ms, wd.end_ms) for wd in seg.words]
            else:
                word_spans.append((seg.start_ms, seg.end_ms))

    scene_starts = [s.start_ms for s in scenes if s.start_ms > 0]

    t = 0
    while t < duration_ms:
        end = min(t + window_ms, duration_ms)
        wlen = end - t

        speech = sum(_overlap_ms(t, end, s, e) for s, e in word_spans) / wlen
        speech = min(1.0, speech)
        silent = sum(_overlap_ms(t, end, s.start_ms, s.end_ms) for s in silence) / wlen
        silent = min(1.0, silent)
        scene_hit = 1.0 if any(t <= cut < end for cut in scene_starts) else 0.0
        # Beat density: normalize against a musically busy ceiling of ~4 beats/window.
        beat_ct = sum(1 for b in beats_ms if t <= b < end)
        beat = min(1.0, beat_ct / 4.0)

        raw = (
            w["speech"] * speech
            + w["scene"] * scene_hit
            + w["beat"] * beat
            - w["silence"] * silent
        )
        pos_max = w["speech"] + w["scene"] + w["beat"]
        score = 0.0 if pos_max <= 0 else max(0.0, min(1.0, raw / pos_max))
        windows.append(SaliencyWindow(start_ms=t, end_ms=end, score=round(score, 4)))
        t = end

    return Saliency(profile=profile, window_ms=window_ms, windows=windows, weights=w)
