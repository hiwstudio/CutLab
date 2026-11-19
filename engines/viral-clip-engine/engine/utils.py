"""Shared helpers: ffmpeg wrappers, logging, time formatting."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve(tool: str) -> str:
    """Locate ffmpeg/ffprobe, preferring a modern build over an old bundled one.

    Some machines have an ancient ffmpeg first on PATH (e.g. ImageMagick ships
    4.2.3, which decodes AV1 at a crawl). Prefer, in order: an explicit
    FFMPEG_BIN/FFPROBE_BIN env, a WinGet Gyan.FFmpeg build, then PATH.
    """
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

# Windows: piped stdio defaults to cp1252 - emoji in captions/hooks crash
# stdout, and piped-in captions arrive mojibake'd. Force UTF-8 everywhere.
# stdin uses utf-8-sig so a BOM from piped input is absorbed by the codec
for _stream, _enc in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"),
                      (sys.stderr, "utf-8")):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding=_enc, errors="replace")
        except (ValueError, OSError):
            pass  # detached/closed stream (e.g. pythonw)


def log(msg: str) -> None:
    print(f"[clip-engine] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"[clip-engine] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def check_ffmpeg() -> None:
    if not (Path(FFMPEG).exists() or shutil.which(FFMPEG)) \
            or not (Path(FFPROBE).exists() or shutil.which(FFPROBE)):
        die(
            "ffmpeg not found. Install it and make sure it is on your PATH.\n"
            "  Windows:  winget install Gyan.FFmpeg   (then restart the terminal)\n"
            "  Mac:      brew install ffmpeg\n"
            "  Linux:    sudo apt install ffmpeg"
        )


def run_ffmpeg(args: list, desc: str = "", cwd: Path | None = None) -> None:
    """Run an ffmpeg command, raising on failure with stderr shown."""
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({desc}):\n{result.stderr[-2000:]}")


def probe_duration(video: Path) -> float:
    """Video duration in seconds."""
    cmd = [
        FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    return float(json.loads(result.stdout)["format"]["duration"])


def fmt_ts(seconds: float) -> str:
    """Seconds -> HH:MM:SS for human-readable output."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def ass_ts(seconds: float) -> str:
    """Seconds -> ASS subtitle timestamp H:MM:SS.cc"""
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def safe_slug(text: str, max_len: int = 40) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return "-".join(keep.lower().split())[:max_len].strip("-") or "clip"


def probe_size(video: Path) -> tuple:
    """Return (width, height) of the first video stream."""
    cmd = [
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    st = json.loads(result.stdout)["streams"][0]
    return int(st["width"]), int(st["height"])


def has_video(video: Path) -> bool:
    """True if the file has a real (moving) video stream, not just cover art."""
    cmd = [
        FFPROBE, "-v", "error", "-select_streams", "v",
        "-show_entries", "stream_disposition=attached_pic",
        "-of", "json", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        return False
    for st in streams:
        disp = st.get("disposition", {})
        if int(disp.get("attached_pic", 0)) == 0:
            return True
    return False


def next_version_n(workdir: Path, label: str, suffix: str = ".mp4") -> int:
    """Next free N for files named '{label} vN{suffix}' in workdir (1 if none)."""
    pat = re.compile(rf"^{re.escape(label)} v(\d+){re.escape(suffix)}$", re.I)
    highest = 0
    if not workdir.exists():
        return 1
    for p in workdir.iterdir():
        m = pat.match(p.name)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def archive_output(path: Path, label: str | None = None) -> Path | None:
    """If `path` exists, rename it to '{label} vN{suffix}' (never delete).

    Also renames a matching '{stem}.caption.txt' sidecar to
    '{label} vN.caption.txt' when present. Returns the archive path, or None
    if there was nothing to archive.
    """
    path = Path(path)
    if not path.exists():
        return None
    label = label or path.stem
    n = next_version_n(path.parent, label, path.suffix)
    dest = path.parent / f"{label} v{n}{path.suffix}"
    path.rename(dest)
    cap = path.parent / f"{path.stem}.caption.txt"
    if cap.exists():
        cap.rename(path.parent / f"{label} v{n}.caption.txt")
    log(f"Archived previous version -> {dest.name}")
    return dest


def prepare_rerender(workdir: Path, current: str, label: str,
                     legacy: list[str] | None = None) -> None:
    """Archive any existing current/legacy deliverables so a fresh render can
    write `current` without overwriting history.

    Order: archive the preferred current name first, then any legacy filenames
    (each becomes the next sequential version under the same label).
    """
    workdir = Path(workdir)
    for name in [current, *(legacy or [])]:
        archive_output(workdir / name, label=label)
