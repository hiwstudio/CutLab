"""SPLIT's own config defaults and project template.

Registered into the core on import (see split/__init__.py), so `mixfix/` holds
no split-specific settings. Anything here can still be overridden per-run by
config.yaml or by node parameters, exactly as the core sections are.
"""
from __future__ import annotations

from mixfix.config import DEFAULTS
from mixfix.templates import EXTRA, FIX_INPUTS

from .pipeline import SPLIT_STAGES

SPLIT_DEFAULTS = {
        "top_fraction": 0.5,      # share of frame height held by the speaker pane
        "word_captions": True,    # one word at a time, pinned to the seam
    }

SPLIT_TEMPLATE = {"name": "split",
         "title": "SPLIT — speaker on top, reference footage below",
         "mode": "split", "builtin": True, "inputs": FIX_INPUTS,
         # portrait by default: this format is made for shorts
         "stages": [{"name": s, **({"params": {"render": {"width": 1080,
                                                          "height": 1920}}}
                                   if s == "assemble" else {})}
                    for s in SPLIT_STAGES]}


def install() -> None:
    """Add SPLIT's defaults and template to the core registries."""
    DEFAULTS.setdefault("split", SPLIT_DEFAULTS)
    if not any(t.get("name") == "split" for t in EXTRA):
        EXTRA.append(SPLIT_TEMPLATE)
