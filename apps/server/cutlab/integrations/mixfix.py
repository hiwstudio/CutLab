"""Read MixFix's existing timeline/timing contract; source files stay external.

The adapter preserves source provenance and uses MixFix's own segment renderer
only when a clip needs its established last-frame hold to cover a scene slot.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

from .. import config


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def project_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
        raise ValueError("invalid MixFix project name")
    root = (config.MIXFIX_ROOT / "projects").resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_dir():
        raise ValueError("MixFix project not found")
    return path


def discover() -> list[dict]:
    root = config.MIXFIX_ROOT / "projects"
    items = []
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if not path.is_dir() or not (path / "timeline/timeline.json").is_file():
                continue
            try:
                tl = read_json(path / "timeline/timeline.json")
                items.append({"name": path.name, "scene_count": len(tl.get("scenes", [])),
                              "duration_ms": tl.get("total_ms", 0)})
            except (ValueError, OSError):
                continue
    return items


def snapshot(name: str, mode: str, canvas: dict) -> dict:
    if mode not in ("mix", "fix"):
        raise ValueError("This adapter supports MIX and FIX; other modes need their own layout adapter")
    root = project_path(name)
    tl = read_json(root / "timeline/timeline.json")
    timing = read_json(root / "timing/timing_map.json")
    total = int(tl["total_ms"])
    scenes = sorted(tl["scenes"], key=lambda s: s["start_ms"])
    if not scenes or total <= 0:
        raise ValueError("MixFix timeline has no scenes or duration")
    ids = [s["id"] for s in scenes]
    if len(ids) != len(set(ids)):
        raise ValueError("MixFix scene IDs must be unique")
    previous_end = 0
    for i, scene in enumerate(scenes):
        start = int(scene["start_ms"])
        end = int(scenes[i + 1]["start_ms"]) if mode == "mix" and i + 1 < len(scenes) else (
            total if mode == "mix" else int(scene["end_ms"]))
        if mode == "mix" and i == 0:
            start = 0  # matches MixFix assemble.render's coverage contract
        if not previous_end <= start < end <= total:
            raise ValueError(f"invalid/overlapping scene range: {scene['id']}")
        previous_end = end
        scene["slot_start_ms"], scene["slot_end_ms"] = start, end
        visual = scene.get("visual")
        if mode == "mix" and not visual:
            raise ValueError(f"MIX scene {scene['id']} has no ready visual")
        if visual:
            if visual.get("kind") not in ("clip", "image"):
                raise ValueError(f"unsupported visual kind in {scene['id']}")
            path = Path(visual["path"])
            path = path if path.is_absolute() else root / path
            if not path.is_file():
                raise ValueError(f"missing visual file for {scene['id']}: {path.name}")
            visual["path"] = str(path.resolve())
            visual["file_signature"] = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
            if int(visual.get("trim_in_ms", 0)) < 0:
                raise ValueError("visual trim must be nonnegative")
    voice = root / "voiceover/voice.mp3"
    source = root / "input/source.mp4"
    if mode == "mix" and not voice.is_file():
        raise ValueError("MIX project needs voiceover/voice.mp3")
    if mode == "fix" and not source.is_file():
        raise ValueError("FIX project needs local input/source.mp4; resolve source before importing")
    manifest = {"contract_version": "1.0", "engine": "mixfix", "source_project": name,
                "source_dir": str(root), "mode": mode, "canvas": canvas,
                "total_ms": total, "scenes": scenes, "words": timing.get("words", []),
                "voice": str(voice) if mode == "mix" else None,
                "base_video": str(source) if mode == "fix" else None,
                "warnings": ["MIX scene boundaries use hard cuts in this adapter; engine crossfades are not yet translated."] if mode == "mix" else []}
    manifest["snapshot_hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return manifest


def module(name: str):
    """Use the bundled MixFix engine, rather than duplicating its logic."""
    root = str(config.MIXFIX_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    mod = importlib.import_module(f"mixfix.{name}")
    if not Path(mod.__file__).resolve().is_relative_to(config.MIXFIX_ROOT):
        raise RuntimeError("loaded MixFix module belongs to a different installation")
    return mod
