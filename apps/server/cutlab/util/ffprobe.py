"""ffprobe wrapper: media introspection."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import config


class ProbeError(Exception):
    pass


@dataclass
class ProbeResult:
    duration_ms: int | None
    width: int | None
    height: int | None
    fps: float | None
    has_video: bool
    has_audio: bool
    raw: dict[str, Any]


def probe(path: str | Path) -> ProbeResult:
    cmd = [
        config.FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise ProbeError(f"ffprobe failed for {path}: {proc.stderr[-500:]}")
    raw = json.loads(proc.stdout)

    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in raw.get("streams", []) if s.get("codec_type") == "audio"), None)

    duration_ms: int | None = None
    dur_s = raw.get("format", {}).get("duration")
    if dur_s is None and video:
        dur_s = video.get("duration")
    if dur_s is None and audio:
        dur_s = audio.get("duration")
    if dur_s is not None:
        duration_ms = int(round(float(dur_s) * 1000))

    fps: float | None = None
    if video:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if rate and rate != "0/0":
            f = Fraction(rate)
            if f > 0:
                fps = float(f)

    return ProbeResult(
        duration_ms=duration_ms,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        fps=fps,
        has_video=video is not None,
        has_audio=audio is not None,
        raw=raw,
    )
