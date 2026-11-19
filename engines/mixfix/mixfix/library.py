"""Visual library — content-addressed, append-only clip/image store.

library/clips/<sha1>.mp4, library/images/<sha1>.<ext>; manifest rows live in the
main SQLite assets table (kind=clip|image) with provenance in meta_json.
Duplicate extraction is structurally impossible: same content → same hash → hit.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from .tools import FFMPEG, FFPROBE
from .state import State


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clip_duration_ms(path: Path) -> int:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return int(round(float(out.stdout.strip()) * 1000))


# Below this a clip is mush once scaled into a 1080-wide pane. It lives here,
# not in pipeline.py, because the DOWNLOADER must honour the same floor: a
# fetch selector that can return 240p while the gate rejects 240p guarantees a
# wasted download and a burned candidate. Measured on an ultra-wide (1920x720)
# upload where the retry selector fell back to `worst` and produced 640x240.
MIN_SOURCE_HEIGHT = 360


def clip_height(path: Path) -> int:
    """Vertical resolution of the first video stream, 0 if unreadable."""
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return int(out.stdout.strip() or 0)


def sample_frames(video: Path, out_dir: Path, fps: float = 1.0,
                  max_frames: int = 12) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-i", str(video),
         "-vf", f"fps={fps}", "-frames:v", str(max_frames),
         str(out_dir / "frame_%03d.jpg")],
        check=True, capture_output=True, text=True)
    return sorted(out_dir.glob("frame_*.jpg"))


class Library:
    def __init__(self, state: State, root: Path):
        self.state = state
        self.root = Path(root)
        (self.root / "clips").mkdir(parents=True, exist_ok=True)
        (self.root / "images").mkdir(parents=True, exist_ok=True)
        self.dedup_hits = 0

    def ingest_clip(self, tmp_file: Path, run_id: str, provenance: dict) -> dict:
        """Move an extracted clip into the library. Returns {asset_id, path, duplicate}."""
        digest = sha1_file(tmp_file)
        dest = self.root / "clips" / f"{digest}.mp4"
        existing = self.state.get_asset(digest)
        if existing or dest.exists():
            self.dedup_hits += 1
            tmp_file.unlink(missing_ok=True)
            return {"asset_id": digest, "path": str(dest), "duplicate": True}
        shutil.move(str(tmp_file), str(dest))  # append-only: never overwrite
        self.state.add_asset(digest, run_id, "research_extract", "clip",
                             str(dest), provenance)
        return {"asset_id": digest, "path": str(dest), "duplicate": False}
