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


def make_hardcut_video(path: Path, seg_seconds: float = 2.0,
                       size: str = "320x180", fps: int = 30) -> Path:
    """Three visually-distinct segments concatenated -> two hard scene cuts at
    ~seg and ~2*seg seconds. Deterministic input for scene detection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sources = [
        f"testsrc2=size={size}:rate={fps}:duration={seg_seconds}",
        f"color=c=red:size={size}:rate={fps}:duration={seg_seconds}",
        f"color=c=blue:size={size}:rate={fps}:duration={seg_seconds}",
    ]
    inputs: list[str] = []
    for src in sources:
        inputs += ["-f", "lavfi", "-i", src]
    filt = "".join(f"[{i}:v]" for i in range(len(sources))) + \
        f"concat=n={len(sources)}:v=1:a=0,format=yuv420p[v]"
    run_ffmpeg([
        *inputs, "-filter_complex", filt, "-map", "[v]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", str(path),
    ])
    return path


def make_tone_silence_tone(path: Path, seg_seconds: float = 2.0,
                           tone_hz: int = 440, with_video: bool = True,
                           size: str = "320x180", fps: int = 30) -> Path:
    """tone -> silence -> tone: exactly one silent span in the middle.
    Deterministic input for silence detection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    a = (
        f"sine=frequency={tone_hz}:sample_rate=48000:duration={seg_seconds}[a0];"
        f"anullsrc=r=48000:cl=mono,atrim=0:{seg_seconds}[a1];"
        f"sine=frequency={tone_hz}:sample_rate=48000:duration={seg_seconds}[a2];"
        f"[a0][a1][a2]concat=n=3:v=0:a=1[a]"
    )
    total = seg_seconds * 3
    args: list[str]
    if with_video:
        args = [
            "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={total}",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-filter_complex", a, "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(path),
        ]
    else:
        args = [
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-filter_complex", a, "-map", "[a]",
            "-c:a", "aac", "-b:a", "128k", str(path),
        ]
    run_ffmpeg(args)
    return path


def make_black_video(path: Path, seconds: float, size: str = "320x180",
                     fps: int = 30) -> Path:
    """Pure black + silent audio — the canvas for caption-burn luminance tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=black:size={size}:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono",
        "-t", str(seconds),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "aac", "-b:a", "96k", str(path),
    ])
    return path


def make_click_track(path: Path, bpm: int = 120, seconds: float = 8.0) -> Path:
    """A metronome click at a fixed BPM — deterministic input for beat tracking.
    Clicks are short sine bursts at `bpm` beats/min."""
    path.parent.mkdir(parents=True, exist_ok=True)
    period = 60.0 / bpm
    n = int(seconds / period)
    # Each beat: 40ms 1kHz burst, then silence to fill the period.
    parts = []
    for i in range(n):
        parts.append(f"sine=frequency=1000:duration=0.04[c{i}]")
        parts.append(f"anullsrc=r=48000:cl=mono,atrim=0:{period - 0.04:.4f}[s{i}]")
    labels = "".join(f"[c{i}][s{i}]" for i in range(n))
    chain = ";".join(parts) + f";{labels}concat=n={2 * n}:v=0:a=1[a]"
    run_ffmpeg([
        "-filter_complex", chain, "-map", "[a]",
        "-c:a", "pcm_s16le", str(path),
    ])
    return path
