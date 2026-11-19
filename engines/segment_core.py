"""Shared YouTube authentication and section-integrity checks for local editors."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


MAX_AUDIO_GAP_S = 1.0
VIDEO_TOLERANCE_S = 0.75


def cookie_args(browser: str | None, cookiefile: Path) -> list[str]:
    """Use one source: the live browser first, then a saved export if needed."""
    browser = (browser or "").strip().lower()
    if browser:
        return ["--cookies-from-browser", browser]
    if cookiefile.exists():
        return ["--cookies", str(cookiefile)]
    return []


def stream_durations(path: Path, ffprobe: str) -> dict[str, float] | None:
    """Return real video/audio stream durations, or None for an invalid file."""
    try:
        if not path.is_file():
            return None
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,duration:stream_disposition=attached_pic",
             "-of", "json", str(path)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if proc.returncode != 0:
            return None
        streams = json.loads(proc.stdout).get("streams", [])
        durations: dict[str, float] = {}
        for stream in streams:
            kind = stream.get("codec_type")
            if kind not in ("video", "audio"):
                continue
            if kind == "video" and int(stream.get("disposition", {}).get("attached_pic", 0)):
                continue
            duration = stream.get("duration")
            if duration not in (None, "N/A"):
                durations[kind] = max(durations.get(kind, 0.0), float(duration))
        return durations
    except (OSError, ValueError, TypeError, KeyError):
        return None


def has_video(path: Path, ffprobe: str, *, min_bytes: int = 0) -> bool:
    try:
        if path.stat().st_size < min_bytes:
            return False
    except OSError:
        return False
    durations = stream_durations(path, ffprobe)
    return durations is not None and durations.get("video", 0) > 0


def audio_gap_s(path: Path, ffprobe: str) -> float:
    durations = stream_durations(path, ffprobe) or {}
    if "audio" not in durations or "video" not in durations:
        return 0.0
    return max(0.0, durations["video"] - durations["audio"])


def media_covers(path: Path, required_ms: int, ffprobe: str, *,
                 require_audio: bool = False, min_bytes: int = 0) -> bool:
    """Reject truncated video, missing audio, and audio that ends early."""
    try:
        if path.stat().st_size < min_bytes:
            return False
    except OSError:
        return False
    durations = stream_durations(path, ffprobe)
    if not durations or "video" not in durations:
        return False
    video_s = durations["video"]
    if video_s + VIDEO_TOLERANCE_S < required_ms / 1000:
        return False
    audio_s = durations.get("audio")
    if require_audio and audio_s is None:
        return False
    if audio_s is not None and video_s - audio_s > MAX_AUDIO_GAP_S:
        return False
    return True
