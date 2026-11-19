"""ASSEMBLY's own config defaults and project template.

Registered into the core on import (see assembly/__init__.py), so `mixfix/`
holds no assembly-specific settings.
"""
from __future__ import annotations

from mixfix.config import DEFAULTS
from mixfix.templates import EXTRA

from .pipeline import ASSEMBLY_STAGES

ASSEMBLY_DEFAULTS = {
    # The published band for this format. Enforced in the plan schema, so a
    # plan that would produce a 4-minute video or a 50-minute one is rejected
    # before anything is downloaded.
    "min_total_s": 15 * 60,
    "max_total_s": 25 * 60,
    # Below this a window is a soundbite. Many short windows make the audio
    # feel chopped, which is the difference between an assembly and a montage.
    "min_window_s": 45,

    # --- the hook: a moment lifted from inside the section and played first ---
    # Under ~8s does not land; over ~35s it stops being a teaser and the video
    # simply starts twice.
    "hook_min_s": 8,
    "hook_max_s": 35,
    # How deep into the BODY the hook must sit. The hook plays twice, so pulled
    # from the first minute it repeats almost immediately and reads as a stutter
    # rather than a callback.
    "hook_min_depth_s": 120,

    # --- cutaways: scaled to runtime ---
    # A flat 4-10 put the same handful of cutaways on a 12-minute cut and a
    # 25-minute one, so the long cuts felt unedited. The count now follows the
    # runtime at `inserts_per_min`, clamped to the band below. At the 8s ceiling
    # in `fix`, 12-20 inserts alter roughly 10-17% of a 15-25 minute runtime.
    "inserts_per_min": 0.9,
    "min_inserts": 12,
    "max_inserts": 20,
    # --- how many cutaways may be SOURCED from YouTube ---
    # Sourcing is the slow, failure-prone half: every sourced cutaway is a search
    # plus a range-fetch, and range-fetches are what stall under throttling.
    # Generated visuals cost no YouTube bandwidth at all, so the plan is capped —
    # a few sourced clips where real footage genuinely matters, everything else
    # generated. Fewer but LONGER is the trade: a handful of 10-20s clips reads
    # better than a dozen 4s flashes and costs far less network than either.
    "max_sourced": 4,
    "sourced_min_s": 10.0,
    "sourced_max_s": 20.0,
    # Per-channel cutaway doctrine, free text, read by insert_plan. This is the
    # knob that makes one engine serve several channels: a comedy channel wants
    # fast literal cutaways on references and punchlines, an informational one
    # wants slower inserts on claims. Same code, different instruction.
    "channel_style": "",
}

ASSEMBLY_INPUTS = [
    {"key": "source", "label": "Episode URL", "path": "input/source.txt",
     "hint": "YouTube URL of ONE podcast episode."},
    {"key": "theme", "label": "Theme (optional)", "path": "input/theme.txt",
     "hint": "The thread to build around. Leave empty to let the plan stage "
             "pick the strongest one in the episode."},
]

ASSEMBLY_TEMPLATE = {
    "name": "assembly",
    "title": "ASSEMBLY — themed long-form cut from one podcast episode",
    "mode": "assembly", "builtin": True, "inputs": ASSEMBLY_INPUTS,
    "stages": [{"name": s} for s in ASSEMBLY_STAGES],
}


def install() -> None:
    """Add ASSEMBLY's defaults and template to the core registries."""
    DEFAULTS.setdefault("assembly", ASSEMBLY_DEFAULTS)
    if not any(t.get("name") == "assembly" for t in EXTRA):
        EXTRA.append(ASSEMBLY_TEMPLATE)
