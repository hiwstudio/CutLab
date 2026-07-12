"""Profile loading (P1 use: saliency weights).

Profiles live in `profiles/{id}.json` at the repo root. Phase 0 shipped a stub;
P1 adds the `saliency` block (window + per-signal weights). Unknown profiles fall
back to `default`, and a missing `saliency` block falls back to the built-in
DEFAULT_WEIGHTS — the analyzer never fails because a profile is thin.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import REPO_ROOT
from .understanding.saliency import DEFAULT_WEIGHTS, DEFAULT_WINDOW_MS

PROFILES_DIR = REPO_ROOT / "profiles"


@lru_cache(maxsize=16)
def load_profile(profile_id: str) -> dict:
    path = PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        path = PROFILES_DIR / "default.json"
    if not path.exists():
        return {"id": "default"}
    return json.loads(path.read_text(encoding="utf-8"))


def saliency_config(profile_id: str) -> tuple[int, dict[str, float]]:
    """Return (window_ms, weights) for a profile, with safe fallbacks."""
    prof = load_profile(profile_id)
    block = prof.get("saliency", {})
    window_ms = int(block.get("window_ms", DEFAULT_WINDOW_MS))
    weights = {**DEFAULT_WEIGHTS, **(block.get("weights", {}))}
    return window_ms, weights


def export_preset(profile_id: str) -> str | None:
    """The profile's default export_preset capability id (None = engine default)."""
    return load_profile(profile_id).get("export_preset")


def caption_style(profile_id: str) -> str | None:
    """The profile's default caption style capability id."""
    return load_profile(profile_id).get("caption_style")
