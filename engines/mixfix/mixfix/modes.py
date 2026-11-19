"""Mode registry — how a workflow plugs into the core without the core
knowing about it.

MixFix owns MIX and FIX. SPLIT lives in its own engine folder (`split/`) and
registers itself here on import, so `mixfix/` contains no split-specific code
and the two can be worked on independently. A mode contributes its stage list,
its renderer, and (via the ai registries) its task schema and prompt.
"""
from __future__ import annotations

from typing import Callable

# mode -> ordered stage names
STAGES: dict[str, list[str]] = {}
# mode -> renderer(project_dir, timeline, timing_map, cfg, source) -> Path.
# None means 'use the core renderer' — MIX and FIX do.
RENDERERS: dict[str, Callable | None] = {}
# mode -> {stage_name: [config sections it reads]}, for the node editor
KNOBS: dict[str, dict[str, list[str]]] = {}


def register(mode: str, stages: list[str],
             renderer: Callable | None = None,
             knobs: dict[str, list[str]] | None = None) -> None:
    STAGES[mode] = list(stages)
    RENDERERS[mode] = renderer
    KNOBS[mode] = dict(knobs or {})


def stages_for(mode: str) -> list[str]:
    if mode not in STAGES:
        raise KeyError(
            f"unknown mode {mode!r}. Known: {sorted(STAGES)}. "
            "SPLIT lives in the split/ engine — run it with `python -m split`.")
    return STAGES[mode]


# mode -> the command that drives it. MIX and FIX are this package's CLI; an
# engine registering from outside sets its own, so a paused run tells the
# operator the command that will actually resume it.
CLI: dict[str, str] = {"mix": "python -m mixfix.cli", "fix": "python -m mixfix.cli"}


def cli_for(mode: str) -> str:
    return CLI.get(mode, "python -m mixfix.cli")
