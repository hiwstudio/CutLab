"""Shared helpers: ffmpeg wrappers, logging, time formatting.

Ported from Viral Clip Engine (stable) — same ffmpeg resolution logic so the
modern WinGet build wins over any ancient bundled ffmpeg on PATH.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Resolve the shared segment helper from the engine-pack root.
_engines_root = str(Path(__file__).resolve().parents[2])
if _engines_root not in sys.path:
    sys.path.insert(0, _engines_root)
import segment_core


def _resolve(tool: str) -> str:
    """Locate ffmpeg/ffprobe, preferring FFMPEG_BIN env, then WinGet Gyan
    build, then PATH (some machines have an ancient ffmpeg first on PATH)."""
    env = os.getenv(f"{tool.upper()}_BIN")
    if env and Path(env).exists():
        return env
    local = os.getenv("LOCALAPPDATA", "")
    if local:
        base = Path(local) / "Microsoft" / "WinGet" / "Packages"
        hits = sorted(base.glob(f"Gyan.FFmpeg*/**/{tool}.exe")) if base.exists() else []
        if hits:
            return str(hits[-1])
    return shutil.which(tool) or tool


FFMPEG = _resolve("ffmpeg")
FFPROBE = _resolve("ffprobe")

# Windows: piped stdio defaults to cp1252 — emoji crash stdout and piped-in
# text arrives mojibake'd. Force UTF-8; stdin absorbs a BOM via utf-8-sig.
for _stream, _enc in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"),
                      (sys.stderr, "utf-8")):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding=_enc, errors="replace")
        except (ValueError, OSError):
            pass


def log(msg: str) -> None:
    print(f"[clipinn] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"[clipinn] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def check_ffmpeg() -> None:
    if not (Path(FFMPEG).exists() or shutil.which(FFMPEG)) \
            or not (Path(FFPROBE).exists() or shutil.which(FFPROBE)):
        die("ffmpeg not found. Windows: winget install Gyan.FFmpeg "
            "(then restart the terminal)")


def run_ffmpeg(args: list, desc: str = "", cwd: Path | None = None) -> None:
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({desc}):\n{result.stderr[-2000:]}")


def probe_duration(video: Path) -> float:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "json", str(video)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    return float(json.loads(result.stdout)["format"]["duration"])


def probe_size(video: Path) -> tuple:
    cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", str(video)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    st = json.loads(result.stdout)["streams"][0]
    return int(st["width"]), int(st["height"])


def has_video(path: Path) -> bool:
    """True if the file has a real (moving) video stream, not just cover art."""
    return segment_core.has_video(path, FFPROBE)


# A clean section's audio and video end within a frame or two of each other.
MAX_AUDIO_GAP_S = segment_core.MAX_AUDIO_GAP_S


def audio_gap_s(path: Path) -> float:
    """Seconds by which the audio track ends before the video.

    yt-dlp can lose audio fragments partway through a section and still exit 0:
    the video runs to the end, the sound stops mid-clip, and the render copies
    that faithfully. 0.0 when there is no audio stream or nothing to compare.
    """
    return segment_core.audio_gap_s(path, FFPROBE)


def media_covers(path: Path, required_ms: int, *, require_audio: bool = False) -> bool:
    return segment_core.media_covers(path, required_ms, FFPROBE,
                                     require_audio=require_audio)


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def ass_ts(seconds: float) -> str:
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def safe_slug(text: str, max_len: int = 40) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return "-".join(keep.lower().split())[:max_len].strip("-") or "clip"


def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
