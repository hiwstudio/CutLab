"""Assembly MixFix — select a section of a long episode, then FIX it.

Its own workflow, living under the MixFix system and sharing its core rather
than forking it. The back half of this mode IS FIX: `timing_map`, `fix_shots`,
`research_extract`, `generate_visuals`, `timeline`, `assemble` (render_fix),
`render_qa` and `export` are the same code, so a fix to any of them lands here
for free. There is no renderer of its own — `render_fix` already plays a video
and replaces the picture for planned windows while stream-copying the original
audio, which is exactly what this format wants.

What is genuinely ASSEMBLY's own:
    pipeline.py  captions-first intake, window selection, extraction, the cut,
                 and the sparse cutaway plan
    cut.py       joins the windows behind a hook lifted from inside the section
    schema.py    the assembly_plan and insert_plan result contracts
    prompt.py    the operator doctrine for both plan stages

Importing this package registers ASSEMBLY with the core, so `mixfix/` itself
contains no assembly-specific code.

    python -m assembly run --project <name>
"""
from mixfix import assemble as _assemble
from mixfix import modes

from . import defaults, prompt, schema  # noqa: F401 — import registers these
from .pipeline import ASSEMBLY_KNOBS, ASSEMBLY_STAGES, AssemblyPipeline

# render_fix, unmodified: original plays, planned windows replace the picture,
# original audio stream-copied. `assembly_cut` has already written the file it
# renders from to input/source.mp4, which is where render_fix looks.
modes.register("assembly", ASSEMBLY_STAGES, _assemble.render_fix, ASSEMBLY_KNOBS)
modes.CLI["assembly"] = "python -m assembly"
defaults.install()

__all__ = ["AssemblyPipeline", "ASSEMBLY_STAGES"]
