"""Synthetic deterministic test media via ffmpeg testsrc2/sine (no real
footage needed for CI)."""
from __future__ import annotations

from pathlib import Path

from cutlab.util.ffrun import run_ffmpeg


def make_video(path: Path, seconds: float, tone_hz: int = 440,
               size: str = "320x180", fps: int = 30) -> Path:
    """H.264+AAC test clip: testsrc2 picture + a pure sine tone."""
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=48000:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(path),
    ])
    return path


def make_audio(path: Path, seconds: float, tone_hz: int = 440) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=48000:duration={seconds}",
        "-c:a", "aac", "-b:a", "128k", str(path),
    ])
    return path


def make_image(path: Path, size: str = "320x180") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=1:duration=1",
        "-frames:v", "1", str(path),
    ])
    return path
