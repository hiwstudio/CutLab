# CutLab

A personal-first, professional, AI-native video editing system. Phase 0 builds
the spine: **ingest real footage → build an EDL → apply ops with revisions and
undo → render correct output with FFmpeg → survive crashes.**

- **EDL is the only source of truth** — one JSON document per project; the UI
  renders it, ops mutate it, the render compiler executes it.
- **Every mutation is a revision** — undo/redo are head-pointer moves.
- **All heavy work is durable jobs** — SQLite-backed queue, checkpointed
  stages, crash-resumable renders (a render that dies at minute 38 resumes).
- **All times are integer milliseconds.**

## Layout

```
apps/server   Python 3.11+ / FastAPI — EDL engine, jobs, FFmpeg render pipeline
apps/studio   Next.js / TypeScript — media library, preview, timeline, revisions
capabilities/ registry (later phases)
profiles/     brand profiles (stub)
data/         gitignored: cutlab.db + per-project media/proxies/renders
scripts/      dev.ps1 / dev.sh — start server + studio together
```

## Setup (Windows)

Prereqs: Python 3.11+, Node 20+, FFmpeg + ffprobe on PATH
(`winget install Gyan.FFmpeg`).

```powershell
# Server
python -m venv apps\server\.venv
apps\server\.venv\Scripts\pip install fastapi "uvicorn[standard]" pydantic python-multipart
# (+ for tests: pytest httpx hypothesis numpy)

# Studio
cd apps\studio; npm install
```

> If another tool (e.g. ImageMagick) shadows ffmpeg on PATH, CutLab resolves
> ffmpeg from ffprobe's directory automatically; override with the
> `CUTLAB_FFMPEG` / `CUTLAB_FFPROBE` env vars.

## Run

```powershell
scripts\dev.ps1     # server on http://127.0.0.1:8787, studio on http://localhost:3000
```

Or individually:

```powershell
cd apps\server; .venv\Scripts\python -m cutlab.main
cd apps\studio; npm run dev
```

## Test

```powershell
cd apps\server
.venv\Scripts\python -m pytest              # full suite (includes slow media tests)
.venv\Scripts\python -m pytest -m "not slow"  # fast suite

cd ..\studio
npx playwright test                         # UI smoke (starts both servers itself)
```

## API

Base `http://127.0.0.1:8787/api/v1` — projects, apply (ops plans with
optimistic locking), undo/redo, revisions + proposals (accept/reject), asset
upload + ingest, analyze (understanding), compact, recap, render + L1 segment
previews, director command/answer, `/media/{project}/...` file serving, and
`WS /ws` for job/revision events. See `docs/HANDOFF.md` §A7 for the core
surface; later-phase endpoints follow the same conventions.

## Status

**All phases (P0–P7) built and tested.**

- **P0 spine** — EDL + ops/revisions/undo, durable jobs, chunked crash-resuming
  FFmpeg renders, Studio editor.
- **P1 understanding** — faster-whisper transcript, scenes, silence, beats,
  per-profile saliency, as a resumable per-asset job.
- **P2 AI director** — smart ops (remove_silence, caption_from_transcript,
  reframe), propose→accept/reject loop, NL commands via pluggable LLM backend
  (manual file hand-off by default; OpenRouter/Anthropic via env keys).
- **P3 preview ladder + captions** — L0 live browser compositor, L1 exact
  segment previews, add_emphasis, captions burned via ASS/libass (4 styles).
- **P4 compaction** — clip-scoring rubric engine, compact op, durable job,
  Telegram approval gate (@AlltronzBot; enable with `CUTLAB_TELEGRAM_*` env).
- **P5 recap** — story outline → original narration (LLM) → Piper TTS → scene
  matching → recap timeline as one proposal (adapted from recap-engine).
- **P6 capabilities** — registry (effects/transitions/caption styles/export
  presets) + brand profiles (systemlab, warriors-at-war, seatpass).
- **P7 polish** — S2 design tokens (see DESIGN-SPEC.md), ⌘K command palette,
  job toasts, a11y (focus rings, reduced motion).

See [PROGRESS.md](PROGRESS.md) for the checklist, [DECISIONS.md](DECISIONS.md)
for ambiguity resolutions and deliberate deferrals, [LESSONS.md](LESSONS.md)
for hard-won fixes.
