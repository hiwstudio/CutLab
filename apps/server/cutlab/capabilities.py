"""Capability registry (P6, A2.6): effects, transitions, caption styles and
export presets are manifest + handler — adding one never changes core code.

Manifests live in `capabilities/*.json` at the repo root:
  {"id": "...", "kind": "effect|transition|caption_style|export_preset",
   "name": "...", ...kind-specific fields...}

Handlers by kind:
  effect         -> ffmpeg video filter template (`filter` field, {param}
                    placeholders filled from the clip's EffectRef params,
                    falling back to manifest `defaults`)
  transition     -> outgoing-edge filter template with {duration_s} and
                    {start_s} placeholders (applied to the clip's tail)
  caption_style  -> CaptionStyle fields (render/captions.py merges them)
  export_preset  -> encoder args for the final render

Built-ins are registered here so a fresh checkout works with no manifest
files; repo manifests extend/override by id.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

log = logging.getLogger("cutlab.capabilities")

CAPS_DIR = REPO_ROOT / "capabilities"

_BUILTINS: list[dict[str, Any]] = [
    # effects — safe, param-checked ffmpeg filter templates
    {"id": "grayscale", "kind": "effect", "name": "Grayscale", "filter": "hue=s=0",
     "defaults": {}},
    {"id": "blur", "kind": "effect", "name": "Blur",
     "filter": "boxblur={radius}:{passes}", "defaults": {"radius": 8, "passes": 2}},
    {"id": "vignette", "kind": "effect", "name": "Vignette",
     "filter": "vignette=PI/{angle_div}", "defaults": {"angle_div": 5}},
    {"id": "brightness", "kind": "effect", "name": "Brightness/Contrast",
     "filter": "eq=brightness={brightness}:contrast={contrast}",
     "defaults": {"brightness": 0.0, "contrast": 1.0}},
    # transitions — outgoing edge only (A4 transition_out)
    {"id": "fade", "kind": "transition", "name": "Fade to black",
     "filter": "fade=t=out:st={start_s}:d={duration_s}"},
    {"id": "fade-white", "kind": "transition", "name": "Fade to white",
     "filter": "fade=t=out:st={start_s}:d={duration_s}:c=white"},
    # caption styles — merged into render/captions.py's CaptionStyle
    {"id": "default", "kind": "caption_style", "name": "Clean"},
    {"id": "bold-pop", "kind": "caption_style", "name": "Bold Pop"},
    {"id": "boxed", "kind": "caption_style", "name": "Boxed"},
    {"id": "top-title", "kind": "caption_style", "name": "Top Title"},
    # export presets — final encode args
    {"id": "h264-archive", "kind": "export_preset", "name": "H.264 archive",
     "video": ["-c:v", "libx264", "-preset", "medium", "-crf", "20"],
     "audio": ["-c:a", "aac", "-b:a", "192k"]},
    {"id": "h264-social", "kind": "export_preset", "name": "H.264 social",
     "video": ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
               "-maxrate", "8M", "-bufsize", "12M"],
     "audio": ["-c:a", "aac", "-b:a", "160k"]},
]


@dataclass(frozen=True)
class Capability:
    id: str
    kind: str
    name: str
    data: dict[str, Any]


@lru_cache(maxsize=1)
def registry() -> dict[str, Capability]:
    caps: dict[str, Capability] = {}

    def add(manifest: dict[str, Any], source: str) -> None:
        cid, kind = manifest.get("id"), manifest.get("kind")
        if not cid or kind not in ("effect", "transition", "caption_style", "export_preset"):
            log.warning("ignoring invalid capability manifest from %s: %s", source, manifest)
            return
        caps[str(cid)] = Capability(id=str(cid), kind=str(kind),
                                    name=str(manifest.get("name", cid)),
                                    data=manifest)

    for m in _BUILTINS:
        add(m, "builtin")
    if CAPS_DIR.is_dir():
        for f in sorted(CAPS_DIR.glob("*.json")):
            try:
                loaded = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                log.warning("capability manifest %s unreadable: %s", f.name, e)
                continue
            for m in loaded if isinstance(loaded, list) else [loaded]:
                add(m, f.name)
    return caps


def known_cap_ids() -> frozenset[str]:
    return frozenset(registry().keys())


def get(cap_id: str, kind: str | None = None) -> Capability | None:
    cap = registry().get(cap_id)
    if cap and kind and cap.kind != kind:
        return None
    return cap


def list_caps(kind: str | None = None) -> list[Capability]:
    return [c for c in registry().values() if kind is None or c.kind == kind]


def _fmt_value(v: Any) -> str:
    """Only plain numbers survive into filter strings — nothing injectable."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return f"{v:.6g}"
    raise ValueError(f"effect param must be numeric, got {type(v).__name__}")


def effect_filter(cap_id: str, params: dict[str, Any]) -> str | None:
    """Instantiate an effect's filter template. Unknown cap or bad params ->
    None (the render skips it with a warning, matching the validator's
    warn-don't-fail contract)."""
    cap = get(cap_id, "effect")
    if cap is None:
        return None
    values = {**cap.data.get("defaults", {}), **(params or {})}
    try:
        return str(cap.data["filter"]).format(
            **{k: _fmt_value(v) for k, v in values.items()})
    except (KeyError, ValueError, IndexError) as e:
        log.warning("effect %s: bad params %s (%s)", cap_id, params, e)
        return None


def transition_filter(cap_id: str, start_s: float, duration_s: float) -> str | None:
    cap = get(cap_id, "transition")
    if cap is None:
        return None
    return str(cap.data["filter"]).format(
        start_s=f"{start_s:.3f}", duration_s=f"{duration_s:.3f}")


def export_args(preset_id: str | None) -> tuple[list[str], list[str]] | None:
    """(video_args, audio_args) for an export preset, or None if unknown."""
    cap = get(preset_id or "", "export_preset")
    if cap is None:
        return None
    return list(cap.data.get("video", [])), list(cap.data.get("audio", []))
