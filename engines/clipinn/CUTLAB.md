# Clipinn in CutLab

Clipinn is bundled as a standalone, resumable short-clipping engine. Run it
with `scripts\engine.ps1 clipinn run <YouTube URL> --style blur`. Its selected
segments and finished clips stay under `engines/clipinn/projects/<name>/`.

To continue editing in CutLab, create a project, open **Media Library → Import
media**, and add the finished clip files. The Clipinn selection rubric and
segment-only download behavior remain owned by Clipinn; CutLab's native
compaction workflow remains a separate editable option.

Agent runs should use operator mode. The agent scores the saved candidate task
and writes the result file; API scoring is optional for standalone use.
