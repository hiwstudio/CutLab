"""Silence detection + active-range derivation (P1).

Adapted from the bundled Viral Clip Engine's `engine/silence.py`. P1 only *detects*
and exposes silence as data (spans + the complementary active/spoken ranges);
actually removing silence is the P2 `remove_silence` op. The active-range
padding/merge logic is carried over so a later cut has clean boundaries.
"""
from __future__ import annotations

import os
import re
import subprocess

from .. import config
from .schema import ActiveRange, SilenceSpan, seconds_to_ms

SILENCE_NOISE_DB = int(os.environ.get("CUTLAB_SILENCE_NOISE_DB", "-30"))
SILENCE_MIN_LEN_S = float(os.environ.get("CUTLAB_SILENCE_MIN_LEN", "0.6"))
SILENCE_PAD_S = float(os.environ.get("CUTLAB_SILENCE_PAD", "0.10"))
SILENCE_MIN_KEEP_S = float(os.environ.get("CUTLAB_SILENCE_MIN_KEEP", "0.4"))
SILENCE_MERGE_GAP_S = 0.25

_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silences_s(
    video: str, noise_db: int = SILENCE_NOISE_DB, min_silence_s: float = SILENCE_MIN_LEN_S
) -> list[tuple[float, float | None]]:
    """[(start_s, end_s|None), ...] silent intervals via ffmpeg silencedetect.
    A trailing None means silence runs to the end of the media."""
    cmd = [
        config.FFMPEG, "-hide_banner", "-nostats", "-i", str(video),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    starts = [float(x) for x in _START_RE.findall(res.stderr)]
    ends = [float(x) for x in _END_RE.findall(res.stderr)]
    out: list[tuple[float, float | None]] = []
    for i, s in enumerate(starts):
        out.append((max(0.0, s), ends[i] if i < len(ends) else None))
    return out


def silence_spans(
    video: str, duration_ms: int, noise_db: int = SILENCE_NOISE_DB,
    min_silence_s: float = SILENCE_MIN_LEN_S,
) -> list[SilenceSpan]:
    spans: list[SilenceSpan] = []
    for s, e in detect_silences_s(video, noise_db, min_silence_s):
        start_ms = seconds_to_ms(s)
        end_ms = duration_ms if e is None else seconds_to_ms(e)
        if end_ms > start_ms:
            spans.append(SilenceSpan(start_ms=start_ms, end_ms=min(end_ms, duration_ms)))
    return spans


def active_ranges(
    duration_ms: int,
    silences: list[SilenceSpan],
    pad_ms: int = seconds_to_ms(SILENCE_PAD_S),
    min_keep_ms: int = seconds_to_ms(SILENCE_MIN_KEEP_S),
    merge_gap_ms: int = seconds_to_ms(SILENCE_MERGE_GAP_S),
) -> list[ActiveRange]:
    """Complement of the silent intervals = the parts worth keeping, padded so
    the first/last syllable isn't clipped, then merged and de-fragmented."""
    keep: list[list[int]] = []
    cursor = 0
    for span in silences:
        if span.start_ms > cursor:
            keep.append([cursor, span.start_ms])
        cursor = max(cursor, span.end_ms)
    if cursor < duration_ms:
        keep.append([cursor, duration_ms])

    padded = [[max(0, s - pad_ms), min(duration_ms, e + pad_ms)] for s, e in keep]

    merged: list[list[int]] = []
    for r in padded:
        if merged and r[0] - merged[-1][1] <= merge_gap_ms:
            merged[-1][1] = max(merged[-1][1], r[1])
        else:
            merged.append(list(r))

    ranges = [ActiveRange(start_ms=s, end_ms=e) for s, e in merged if e - s >= min_keep_ms]
    if not ranges and duration_ms > 0:
        ranges = [ActiveRange(start_ms=0, end_ms=duration_ms)]
    return ranges


def provenance(noise_db: int = SILENCE_NOISE_DB, min_silence_s: float = SILENCE_MIN_LEN_S) -> dict[str, str]:
    return {
        "tool": "ffmpeg silencedetect",
        "noise_db": str(noise_db),
        "min_silence_s": str(min_silence_s),
    }
