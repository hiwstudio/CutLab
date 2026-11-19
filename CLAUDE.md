# CutLab — development principles

## Reuse existing engines — never rebuild what already works

Several capabilities CutLab needs in later phases **already exist as working,
tested systems**. Their bundled sources are the source of truth. Before building
any feature, follow this workflow:

1. Check whether the feature already exists in a bundled engine (map below).
2. If it does, locate it and understand how it works (each has its own README/CLAUDE.md).
3. Integrate or adapt it to CutLab's architecture (EDL ops, durable jobs, capabilities).
4. Build from scratch **only** if nothing suitable exists or adaptation is impossible —
   and say so explicitly before doing it.

## Existing engine map (verified 2026-07-03)

| Capability (CutLab phase) | Existing system | Location |
|---|---|---|
| Compaction / viral clipping, silence removal, 9:16 reframe, burned subtitles, hooks/titles/captions (P4, parts of P1–P2) | **Viral Clip Engine** — download → faster-whisper transcribe → operator/API moment selection → vertical reframing → subtitles and hooks. Modes: Clip, Reframe, Cut+Reframe. | `engines/viral-clip-engine` |
| Recap Engine (P5) | **Recap Engine** — download → transcribe → scene detect → story outline → footage index → recap script → beat/scene matching → voiceover → coverage validation → assemble. Stage-cached/resumable; the LLM backend supports manual or optional API mode. | `engines/recap-engine` |
| Transcription (P1 understanding layer) | faster-whisper integration lives inside both engines above | same dirs |

The bundled engine sources live under `engines/`. Read the relevant engine guide
before adding an overlapping pipeline or adapting its outputs.

Integration means adapting these engines to emit **EDL operations and durable jobs**
(per the handoff spec's principles), not shelling out to them blindly — but their
pipeline logic, prompts, tuning, and hard-won fixes are the reference implementation.

## Phase discipline

The build spec is `docs/HANDOFF.md`. Phase 0 is complete. Do not start
a later phase without a user request. Ambiguity resolutions go in `DECISIONS.md`,
module status in `PROGRESS.md`.

## Environment quirks

- Resolve FFmpeg through the shared helper in `cutlab/config.py`; use the same
  helper in any new script so every workflow selects the same executable.
- Server tests: `cd apps/server; .venv\Scripts\python -m pytest` (`-m "not slow"` for fast runs).
- UI smoke: `cd apps/studio; npx playwright test` (needs ports 3000/8787 free).
