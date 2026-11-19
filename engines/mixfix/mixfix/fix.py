"""FIX mode helpers — audio extraction, source fetch, shot detection, face presence.

Thin wrappers around ffmpeg/ffprobe (subprocess), yt_dlp (subprocess), scenedetect
0.7, and opencv-python. Stdlib + already-installed deps only.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .tools import FFMPEG, FFPROBE


def extract_audio(video: Path, out_mp3: Path) -> Path:
    """Extract the first audio stream from video to mp3 (128k)."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-y", "-i", str(video), "-vn", "-map", "0:a:0",
         "-c:a", "libmp3lame", "-b:a", "128k", str(out_mp3)],
        check=True, capture_output=True,
    )
    return out_mp3


def fetch_source(spec: str, out_mp4: Path,
                 cookies_from_browser: str | None = None) -> Path:
    """Fetch a video from a URL (yt_dlp) or local path (copy) into out_mp4."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    if spec.startswith("http://") or spec.startswith("https://"):
        cookie_args = (["--cookies-from-browser", cookies_from_browser]
                       if cookies_from_browser else [])
        subprocess.run(
            ["python", "-m", "yt_dlp", *cookie_args, spec, "-f",
             "bv*[height<=720]+ba/b[height<=720]",
             # h264+m4a first: Opus/AV1 streams can fail to mux into mp4
             "-S", "res:720,vcodec:h264,acodec:m4a",
             "--merge-output-format", "mp4", "-o", str(out_mp4)],
            check=True, capture_output=True,
        )
    else:
        shutil.copy2(spec, out_mp4)
    if not out_mp4.exists():
        raise RuntimeError(f"fetch_source: expected output not found: {out_mp4}")
    return out_mp4


def _probe_duration_ms(video: Path) -> int:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        check=True, capture_output=True, text=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def detect_shots(video: Path) -> list[dict]:
    """Detect shot boundaries. Falls back to one full-length shot if no cuts found."""
    from scenedetect import ContentDetector, detect

    scenes = detect(str(video), ContentDetector())
    if not scenes:
        return [{"start_ms": 0, "end_ms": _probe_duration_ms(video)}]
    return [
        {"start_ms": round(start.get_seconds() * 1000), "end_ms": round(end.get_seconds() * 1000)}
        for start, end in scenes
    ]


def face_presence(video: Path, every_s: float = 1.0) -> list[dict]:
    """Sample frames every every_s seconds and count faces. Advisory only."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        return []

    cap = cv2.VideoCapture(str(video))
    results: list[dict] = []
    t_ms = 0.0
    step_ms = every_s * 1000
    try:
        while True:
            cap.set(cv2.CAP_PROP_POS_MSEC, t_ms)
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.1, 5)
            results.append({"t_ms": round(t_ms), "faces": len(faces)})
            t_ms += step_ms
    finally:
        cap.release()
    return results
