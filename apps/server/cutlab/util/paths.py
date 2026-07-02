"""Project directory layout. Everything media-related lives under the
project dir; the EDL references paths relative to it."""
from __future__ import annotations

from pathlib import Path

SUBDIRS = ("media", "proxies", "understanding", "thumbs", "renders")


def ensure_project_layout(project_dir: Path) -> None:
    for sub in SUBDIRS:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)


def media_dir(project_dir: Path) -> Path:
    return project_dir / "media"


def proxy_path(project_dir: Path, asset_id: str) -> Path:
    return project_dir / "proxies" / f"{asset_id}.mp4"


def peaks_path(project_dir: Path, asset_id: str) -> Path:
    return project_dir / "understanding" / f"{asset_id}.peaks.json"


def probe_path(project_dir: Path, asset_id: str) -> Path:
    return project_dir / "understanding" / f"{asset_id}.probe.json"


def thumbs_dir(project_dir: Path, asset_id: str) -> Path:
    return project_dir / "thumbs" / asset_id


def renders_dir(project_dir: Path) -> Path:
    return project_dir / "renders"


def safe_join(root: Path, relative: str) -> Path:
    """Resolve `relative` under `root`, refusing traversal outside it."""
    target = (root / relative).resolve()
    root = root.resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes project dir: {relative}")
    return target
