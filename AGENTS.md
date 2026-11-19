# CutLab — development principles

## Reuse existing engines — never rebuild what already works

Several capabilities CutLab needs **already exist as working systems in the
bundled engine pack**. Reuse them instead of rebuilding their pipeline logic.
Before building an adjacent feature, follow this workflow:

1. Check whether the feature already exists in a bundled engine (map below).
2. If it does, locate it and understand how it works (each has its own README/AGENTS.md).
3. Integrate or adapt it to CutLab's architecture (EDL ops, durable jobs, capabilities).
4. Build from scratch **only** if nothing suitable exists or adaptation is impossible —
   and say so explicitly before doing it.

## Bundled engine map

| Capability | Existing system | Location |
|---|---|---|
| Narrated film and overlay production | **MixFix** — resumable MIX/FIX pipelines, with SPLIT available as a standalone workflow. MIX/FIX projects open as editable CutLab timelines. | `engines/mixfix` |
| Short-form clipping from caption windows | **Clipinn** — scores candidates, downloads selected sections, then renders vertical clips. | `engines/clipinn` |
| Reframe and viral moment production | **Viral Clip Engine** — transcription, moment review, vertical reframing, subtitles, and hooks. | `engines/viral-clip-engine` |
| Narrated story recaps | **Recap Engine** — transcript, outline, footage matching, narration, coverage validation, and assembly. | `engines/recap-engine` |
| Deterministic animation | **HIW Studio** — Remotion renderer driven by scene manifests. | `engines/hiw-studio` |
| Timeline editing and built-in workflows | CutLab EDL editor, understanding pipeline, compaction, and recap. | `apps/server/cutlab` |

The engine source is part of this repository. Runtime projects, local databases,
models, cookies, downloaded media, and renders stay out of Git. Read
`engines/README.md` and the engine's nested `AGENTS.md` before running or
changing one.

MixFix MIX/FIX projects use CutLab's durable import and revision paths.
Clipinn, Viral Clip, Recap, and HIW Studio run through the engine launcher;
their rendered media enters CutLab through the normal asset-ingest flow.
Do not describe those outputs as scene-linked imports until an adapter provides it.

## Phase discipline

The build spec is `docs/HANDOFF.md`. Phase 0 is complete. Do not start
a later phase without the requester asking. Ambiguity resolutions go in `DECISIONS.md`,
module status in `PROGRESS.md`.

## Environment quirks

- Use the configured `FFMPEG` and `FFPROBE` paths from `cutlab.config` in new server
  code; do not assume the first `ffmpeg` executable on PATH is the intended binary.
- Server tests: `cd apps/server; .venv\Scripts\python -m pytest` (`-m "not slow"` for fast runs).
- UI smoke: `cd apps/studio; npx playwright test` (needs ports 3000/8787 free).
