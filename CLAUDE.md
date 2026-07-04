# CutLab — development principles

## Reuse existing engines — never rebuild what already works

Several capabilities CutLab needs in later phases **already exist as working,
tested systems on this machine**. They are the source of truth. Before building
any feature, follow this workflow:

1. Check whether the feature already exists as one of the owner's engines (map below).
2. If it does, locate it and understand how it works (each has its own README/CLAUDE.md).
3. Integrate or adapt it to CutLab's architecture (EDL ops, durable jobs, capabilities).
4. Build from scratch **only** if nothing suitable exists or adaptation is impossible —
   and say so explicitly before doing it.

## Existing engine map (verified 2026-07-03)

| Capability (CutLab phase) | Existing system | Location |
|---|---|---|
| Compaction / viral clipping, silence removal, 9:16 reframe, burned subtitles, hooks/titles/captions (P4, parts of P1–P2) | **viral-clip-engine** — download → faster-whisper transcribe → LLM moment-finding via OpenRouter → cut/center-crop 1080×1920 → word-group subtitles + hook overlay → clips.json + posting plan + preview dashboard. Modes: Clip, Reframe, Cut+Reframe. | `C:\Users\ALLTRON\content\creathor\viral-clip-engine` |
| Recap Engine (P5) | **recap-engine** — download → transcribe → scene detect → story outline → footage index → recap script → beat/scene matching → Piper TTS voiceover (local, not ElevenLabs) → length reconcile → coverage validation → assemble. Stage-cached/resumable; LLM backend pluggable (manual or OpenRouter). Production milestone reached; see its CLAUDE.md for design decisions. | `C:\Users\ALLTRON\content\creathor\recap-engine` |
| Transcription (P1 understanding layer) | faster-whisper integration lives inside both engines above | same dirs |

Other potentially relevant repos in `C:\Users\ALLTRON`: `HIWstudio`, `miragestudio`,
`shortvidcreate`, `SystemLab`, `voice-to-text`, `AntiSystem` — survey before building
anything adjacent (Remotion craft, TTS, pipelines). `content\creathor\Recapsystem`
appeared empty at last check.

Integration means adapting these engines to emit **EDL operations and durable jobs**
(per the handoff spec's principles), not shelling out to them blindly — but their
pipeline logic, prompts, tuning, and hard-won fixes are the reference implementation.

## Phase discipline

The build spec is `docs/HANDOFF.md`. Phase 0 is complete. Do not start
a later phase without the owner asking. Ambiguity resolutions go in `DECISIONS.md`,
module status in `PROGRESS.md`.

## Environment quirks

- ffmpeg on PATH is shadowed by ImageMagick's ancient 4.2.3; the server resolves the
  real ffmpeg 8.1 from ffprobe's directory (`cutlab/config.py`). Do the same in any
  new script.
- Server tests: `cd apps/server; .venv\Scripts\python -m pytest` (`-m "not slow"` for fast runs).
- UI smoke: `cd apps/studio; npx playwright test` (needs ports 3000/8787 free).
