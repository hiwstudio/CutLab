"""Split MixFix — the split-screen engine.

Its own workflow, living under the MixFix system and sharing its core rather
than forking it: intake, timing, research, timeline, QA and export are the
same code MIX and FIX run, so a fix to any of them lands here for free.

What is genuinely SPLIT's own:
    pipeline.py  the split_plan stage and the stage list
    render.py    the vstack renderer and seam captions
    schema.py    the split_plan result contract
    prompt.py    the operator doctrine for planning the bottom pane

Importing this package registers SPLIT with the core, so `mixfix/` itself
contains no split-specific code.

    python -m split run --project <name>
"""
from mixfix import modes

from . import defaults, prompt, schema  # noqa: F401 — import registers these
from .pipeline import SPLIT_KNOBS, SPLIT_STAGES, SplitPipeline
from .render import render_split

modes.register("split", SPLIT_STAGES, render_split, SPLIT_KNOBS)
modes.CLI["split"] = "python -m split"
defaults.install()

__all__ = ["SplitPipeline", "SPLIT_STAGES", "render_split"]
