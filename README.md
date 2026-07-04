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
optimistic locking), undo/redo, revisions, asset upload + ingest jobs, render
jobs, `/media/{project}/...` file serving, and `WS /ws` for job/revision
events. See `docs/HANDOFF.md` §A7 for the full surface.

## Status

Phase 0. See [PROGRESS.md](PROGRESS.md) for the module checklist and
[DECISIONS.md](DECISIONS.md) for spec-ambiguity resolutions. Later phases
(AI director, understanding layer, compaction/recap engines, Remotion caption
overlays) are specified in the handoff doc and intentionally not built yet.
