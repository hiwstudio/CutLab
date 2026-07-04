"""Scene / shot-boundary detection (P1).

Adapted from the owner's recap-engine `engine/scenes.py` (the reuse source per
CLAUDE.md): the classical ffmpeg `scene` filter, no model or extra dependency,
deterministic. See DECISIONS.md for why this stands in for PySceneDetect.

Emits integer-ms `Scene` objects; merges shots shorter than `min_len_ms` so the
timeline isn't littered with flicker cuts.
"""
from __future__ import annotations

import os
import re
import subprocess

from .. import config
from .schema import Scene, seconds_to_ms

SCENE_THRESHOLD = float(os.environ.get("CUTLAB_SCENE_THRESHOLD", "0.30"))
SCENE_MIN_LEN_MS = int(float(os.environ.get("CUTLAB_SCENE_MIN_LEN", "1.5")) * 1000)

_PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def detect_cut_times_s(video: str, threshold: float = SCENE_THRESHOLD) -> list[float]:
    """Sorted timestamps (seconds) where a hard visual cut occurs."""
    cmd = [
        config.FFMPEG, "-hide_banner", "-nostats", "-i", str(video),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return sorted({round(float(t), 3) for t in _PTS_RE.findall(res.stderr)})


def detect_scenes(
    video: str,
    duration_ms: int,
    threshold: float = SCENE_THRESHOLD,
    min_len_ms: int = SCENE_MIN_LEN_MS,
) -> list[Scene]:
    cuts_ms = [
        seconds_to_ms(t)
        for t in detect_cut_times_s(video, threshold)
        if 50 < seconds_to_ms(t) < duration_ms
    ]
    boundaries = [0, *cuts_ms, duration_ms]

    scenes: list[Scene] = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        if e <= s:
            continue
        if e - s < min_len_ms and scenes:
            scenes[-1].end_ms = e  # merge tiny shot into previous
        else:
            scenes.append(Scene(index=len(scenes), start_ms=s, end_ms=e))
    for i, sc in enumerate(scenes):
        sc.index = i
    return scenes


def provenance(threshold: float = SCENE_THRESHOLD, min_len_ms: int = SCENE_MIN_LEN_MS) -> dict[str, str]:
    return {
        "tool": "ffmpeg scene filter",
        "threshold": str(threshold),
        "min_len_ms": str(min_len_ms),
    }
