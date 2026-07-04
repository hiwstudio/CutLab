# CUTLAB — CLAUDE CODE BUILD HANDOFF
## Full Architecture Spec + Phase 0 Build Instructions

You (Claude Code) are building **CutLab**: a personal-first, professional, AI-native video editing system. This document is the complete spec. Read all of it before writing any code. Part A tells you what the system is. Part B tells you exactly what to build right now. Do not build anything outside Part B's scope.

---

# PART A — THE SYSTEM

## A1. What CutLab is

A professional, timeline-based video editor with an AI director inside it. A human can edit fully manually (timeline, trims, layers, captions, audio, effects, export). The AI director accepts natural-language commands ("remove silence", "crop this for TikTok", "turn this 10-minute video into 2 minutes") and performs real edits.

Three engines share one core:
- **Editor** — human-driven, AI-assisted
- **Compaction Engine** — saliency-driven; shortens any video (long → short)
- **Recap Engine** — script-spine-driven; retells long story content as narrated recaps

Built personal-first for the owner's brands (SystemLab, Warriors at War, SeatPass); a SaaS subset may be extracted much later. Runs locally on Windows now; deploys to Railway later with no rewrite (hosting change only).

## A2. Non-negotiable principles

1. **The EDL is the only source of truth.** One JSON document per project describes the entire edit. The UI renders it, the AI mutates it, the render engine executes it. Nothing edits media directly.
2. **The AI emits operations, never pixels and never raw JSON edits.** A closed, validated operation vocabulary is the only mutation path — for humans (via UI) and AI alike.
3. **Every mutation creates a revision.** Undo/redo, diffs, and AI proposals are revision pointers. Proposals are revisions in a `proposed` state that the user accepts or rejects.
4. **All heavy work is durable jobs.** SQLite-backed queue, checkpointed stages, crash-resumable. A render that dies at minute 38 resumes; it never restarts.
5. **All times are integer milliseconds.** No frames, no floats in the EDL. Frame math happens only inside the render compiler against `canvas.fps`.
6. **Capabilities are registry entries.** Effects, transitions, caption styles, export presets = manifest + handler. Core code never changes to add one.
7. **Determinism.** Same EDL + same assets → byte-stable output structure (same cuts, timings, layout) every render.

## A3. Architecture overview

```
┌─ apps/studio (Next.js) ────────────────────────────────┐
│ timeline UI · media library · L0 preview compositor    │
│ AI chat panel · proposal/diff viewer                   │
└──────────────┬─────────────────────────────────────────┘
               │  REST + WebSocket (JSON)
┌─ apps/server (Python / FastAPI) ───────────────────────┐
│ edl/            schema, validation, ops engine, revs   │
│ director/       command → plan → ops (LATER PHASE)     │
│ understanding/  whisper, scenes, silence (LATER PHASE) │
│ engines/        compaction, recap (LATER PHASE)        │
│ render/         ffmpeg graph compiler, ladder          │
│ jobs/           sqlite queue, checkpoints, recovery    │
│ gates/          telegram approvals (LATER PHASE)       │
└──────────────┬─────────────────────────────────────────┘
               │
   SQLite (truth) · filesystem (media/proxies/renders)
   FFmpeg (render core) · Remotion (overlay pass, LATER)
```

Final render strategy (for context; only the FFmpeg core is Phase 0): FFmpeg executes all structural work (cuts, concat, speed, crop, audio mix). Remotion later renders styled caption/motion-graphic layers as transparent overlays that FFmpeg composites in a final pass.

Preview strategy (for context; NOT Phase 0): three-level fidelity ladder — L0 instant proxy playback in-browser, L1 backend-rendered segment previews, L2 full render.

## A4. EDL v1.0 — complete specification

One file per project: `data/projects/{project_id}/edl.json`. Persisted per-revision in SQLite (full snapshot per revision; snapshots are small because media is referenced, never embedded).

### Root

| Field | Type | Req | Rules |
|---|---|---|---|
| `edl_version` | string | ✓ | must be `"1.0"` |
| `project` | Project | ✓ | |
| `assets` | map<AssetId, Asset> | ✓ | may be empty; keys match `^ast_[a-z0-9]{2,12}$` |
| `tracks` | Track[] | ✓ | may be empty; render order = array order (index 0 = bottom) |

### Project

| Field | Type | Req | Rules |
|---|---|---|---|
| `id` | string | ✓ | `^proj_[a-z0-9]{4,12}$` |
| `name` | string | ✓ | 1–120 chars |
| `profile` | string | — | profile id; default `"default"` |
| `canvas.width` | int | ✓ | 16–7680, even |
| `canvas.height` | int | ✓ | 16–7680, even |
| `canvas.fps` | number | ✓ | one of 24, 25, 30, 50, 60 |
| `duration_ms` | int | derived | server-computed on every mutation = max clip end across tracks; never client-supplied |

### Asset

| Field | Type | Req | Rules |
|---|---|---|---|
| `kind` | enum | ✓ | `video` \| `audio` \| `image` |
| `src` | string | ✓ | path relative to project dir; must exist at validation |
| `proxy` | string | — | set by ingest job (video only) |
| `duration_ms` | int | ✓ for video/audio | probed at ingest, > 0 |
| `width`,`height` | int | ✓ for video/image | probed at ingest |
| `understanding` | string | — | path to understanding JSON (later phase) |

### Track

| Field | Type | Req | Rules |
|---|---|---|---|
| `id` | string | ✓ | `^trk_[a-z0-9]{2,12}$`, unique |
| `kind` | enum | ✓ | `video` \| `audio` \| `caption` \| `text` |
| `clips` | Clip[] | ✓ | sorted by `start_ms`; **no overlaps within a track** |

### Clip (video/audio kinds)

| Field | Type | Req | Rules |
|---|---|---|---|
| `id` | string | ✓ | `^clp_[a-z0-9]{2,12}$`, unique project-wide |
| `asset` | AssetId | ✓ | must exist; asset.kind compatible with track.kind (image allowed on video tracks) |
| `in_ms` / `out_ms` | int | ✓ | `0 ≤ in < out ≤ asset.duration_ms` (images: use `out_ms − in_ms` as display duration, `in_ms` = 0) |
| `start_ms` | int | ✓ | ≥ 0; timeline position |
| `speed` | number | — | 0.1–10.0, default 1.0. Timeline length = `(out_ms − in_ms) / speed`, rounded to int |
| `gain_db` | number | — | audio/video, −60 to +12, default 0 |
| `transform` | object | — | `{scale:0.1–10 (1), x:int px (0), y:int px (0), rotate:−360–360 (0)}` |
| `crop` | object | — | `{mode: "none"\|"center"\|"manual", rect?: {x,y,w,h} source px}` — `manual` requires `rect`. (`reframe_auto` is a later-phase mode; reject it in v1.0 validation) |
| `effects` | EffectRef[] | — | `{cap: string, params: object}` — Phase 0 validates shape only; capability resolution is a later phase. Unknown `cap` = validation **warning**, not error |
| `transition_out` | object | — | `{cap, duration_ms 50–2000}` — same warning rule |

### Clip (caption/text kinds)

| Field | Type | Req | Rules |
|---|---|---|---|
| `id`, `start_ms` | | ✓ | as above; plus `end_ms` int > start_ms |
| `text` | string | ✓ | 1–500 chars |
| `cap_style` | string | — | capability id; warning if unknown |
| `source` | object | — | provenance: `{kind:"transcript", asset, words:[int,int]}` — optional, opaque in Phase 0 |

### Validation contract

`validate(edl) → {valid: bool, errors: Issue[], warnings: Issue[]}` where `Issue = {code, path, message}`. Codes are stable strings (`E_OVERLAP`, `E_RANGE`, `E_REF`, `E_SCHEMA`, `W_UNKNOWN_CAP`, ...). Errors block apply; warnings don't. Cross-checks required: id uniqueness, asset references resolve, clip ranges within asset duration, no intra-track overlap, canvas legal, `duration_ms` recomputed.

## A5. Operation API — full vocabulary

Mutations are applied as a **plan**: `apply(project_id, base_rev, ops[], mode)` where mode = `commit` (user action) or `propose` (AI/engine action, later). Apply is transactional: all ops validate against the working copy in sequence, or the whole plan rejects. Result: new revision (or proposal), plus a human-readable diff summary.

**Phase 0 implements these ops** (engine + tests; no AI involved — the UI and tests call them directly):

| Op | Params | Semantics / edge rules |
|---|---|---|
| `add_track` | kind, index? | insert track |
| `remove_track` | track | and its clips |
| `add_clip` | track, asset, in_ms, out_ms, start_ms, (speed?, transform?...) | rejects on overlap |
| `remove_clip` | clip, ripple: bool=false | ripple shifts later clips on that track left by removed timeline length |
| `trim` | clip, new_in_ms? , new_out_ms?, edge_mode: "hold_start"\|"hold_end"="hold_start" | hold_start keeps `start_ms` fixed; hold_end keeps clip end fixed and moves `start_ms` |
| `split` | clip, at_ms (timeline coords) | must fall strictly inside clip; produces two clips, ids `{orig}` + new; source ranges partitioned respecting speed |
| `move` | clip, to_start_ms, to_track? | rejects on overlap at destination; cross-track requires kind compatibility |
| `delete_range` | tracks[] \| "all", from_ms, to_ms, ripple: bool=true | clips fully inside → removed; straddling → trimmed/split as needed; ripple closes gap on affected tracks |
| `set_speed` | clip, speed | recomputes timeline length; rejects if new length overlaps next clip (unless ripple:true param shifts) |
| `set_gain` | clip, gain_db | |
| `set_transform` | clip, transform partial | merge semantics |
| `set_crop` | clip, crop | |
| `set_canvas` | width, height, fps | project-level |
| `add_caption` | track, text, start_ms, end_ms, cap_style? | caption/text tracks only |
| `set_project` | name? , profile? | metadata |

**Later-phase ops — define the enum now, return `E_NOT_IMPLEMENTED`:** `caption_from_transcript`, `remove_silence`, `duck`, `denoise`, `fade`, `apply_effect`, `add_transition`, `reframe`, `find`, `compact`, `add_emphasis`, `apply_style`, `reorder`.

Every applied plan stores: `{rev, parent_rev, ops_json, summary, created_at}`. `undo` = re-point project head to `parent_rev`; `redo` = forward pointer. Head pointer lives in the projects table.

## A6. SQLite schema (Phase 0, complete)

One DB: `data/cutlab.db`, WAL mode.

```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  head_rev INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE revisions (
  project_id TEXT NOT NULL REFERENCES projects(id),
  rev INTEGER NOT NULL, parent_rev INTEGER,
  state TEXT NOT NULL CHECK(state IN ('committed','proposed','rejected')),
  ops_json TEXT NOT NULL,          -- the plan that produced this rev
  edl_json TEXT NOT NULL,          -- full snapshot
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, rev)
);
CREATE TABLE assets (
  project_id TEXT NOT NULL, asset_id TEXT NOT NULL,
  kind TEXT NOT NULL, src TEXT NOT NULL, proxy TEXT,
  duration_ms INTEGER, width INTEGER, height INTEGER,
  probe_json TEXT,                 -- raw ffprobe output
  status TEXT NOT NULL CHECK(status IN ('ingesting','ready','failed')),
  PRIMARY KEY (project_id, asset_id)
);
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,             -- job_{uuid}
  kind TEXT NOT NULL,              -- 'ingest' | 'render' | (later: 'understanding','segment',...)
  project_id TEXT, input_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('queued','running','done','failed','cancelled')),
  stage TEXT,                      -- current checkpoint stage name
  progress REAL NOT NULL DEFAULT 0,
  artifacts_json TEXT NOT NULL DEFAULT '{}',  -- stage → artifact paths
  error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_jobs_state ON jobs(state);
```

Job recovery rule: on worker startup, every job in `running` is reset to `queued` with `attempts += 1`; execution begins at the first stage whose artifact (per `artifacts_json`) is missing or fails an integrity check (file exists + size > 0). Max 3 attempts → `failed`.

## A7. HTTP + WebSocket API (Phase 0, complete)

Base `http://127.0.0.1:8787/api/v1`. JSON everywhere. Errors: `{error: {code, message, issues?}}`.

```
POST   /projects                          {name, canvas}            → project + rev 0 (empty EDL)
GET    /projects                                                    → list
GET    /projects/{id}                                               → project meta + head_rev
GET    /projects/{id}/edl?rev=            (default head)            → EDL snapshot
POST   /projects/{id}/apply               {base_rev, ops[], mode}   → {rev, summary, edl} | 409 if base_rev ≠ head | 422 with issues
POST   /projects/{id}/undo                                          → {rev}
POST   /projects/{id}/redo                                          → {rev}
GET    /projects/{id}/revisions                                     → [{rev, summary, state, created_at}]

POST   /projects/{id}/assets              multipart file OR {path}  → asset (status:ingesting) + ingest job id
GET    /projects/{id}/assets                                        → list with status
GET    /media/{project}/{...path}         static file serving (source, proxies, renders)

POST   /projects/{id}/render              {rev?, output?: name}     → job id     (L2 full render)
GET    /jobs/{id}                                                   → job row
POST   /jobs/{id}/cancel                                            → ok

WS     /ws                                subscribe {project_id}    → events:
       {type:"job", job}                  every state/progress change (throttle ≥ 250ms)
       {type:"revision", project_id, rev, summary}
```

Concurrency: `apply` uses optimistic locking on `base_rev` (409 → client refetches head and retries). Single-writer per project enforced with a per-project async lock in the server.

## A8. Render pipeline (Phase 0 scope)

**Ingest job** (`kind='ingest'`), stages, each checkpointed in `artifacts_json`:
1. `probe` — ffprobe → duration/width/height/codecs → assets row updated
2. `proxy` — video only: 540p (preserve AR, `scale=-2:540`), H.264 `-preset veryfast -crf 28`, AAC 128k, keyframe interval 1s (`-g fps`) for clean scrubbing → `proxies/{asset}.mp4`
3. `waveform` — audio/video: peaks JSON (1000 buckets via ffmpeg astats or raw PCM decimation) → `understanding/{asset}.peaks.json`
4. `thumbs` — video: 1 frame / 5s, 160px wide, JPEG strip dir → `thumbs/{asset}/`

**Render job** (`kind='render'`) — the FFmpeg graph compiler, the heart of Phase 0:
1. `plan` — load EDL rev → normalize into a segment plan per track
2. `video` — compile filtergraph: per clip `trim` → `setpts` (speed) → `crop` (if any) → `scale/pad` to canvas → transform via `scale`+`overlay` offsets; images via `loop`; gaps become black `color` segments; concat per video track; multiple video tracks composite bottom-up with `overlay` (Phase 0: rectangular overlay only, honoring transform x/y/scale)
3. `audio` — per clip `atrim` → `atempo` chain (factor decomposition for speed outside 0.5–2.0) → `volume` (gain_db) → `adelay` to position → `amix` across all audio-bearing clips; silence-fill via `anullsrc`
4. `mux` — H.264 `-preset medium -crf 20`, AAC 192k, `-movflags +faststart` → `renders/{project}_{rev}.mp4`
Caption/text tracks: **skipped with a logged warning in Phase 0** (Remotion overlay pass is a later phase). Effects/transitions refs: skipped with warning.
Long renders: chunk the timeline into ≤60s pieces rendered to intermediates (`stage: video_chunk_{n}`), concat-demux at mux — this is what makes resume real, and each chunk completion updates `progress`.

Determinism rule: the compiler is a pure function `(edl, paths) → ffmpeg command list`; log the full command per stage into `artifacts_json`.

## A9. Studio UI (Phase 0 scope — minimal but real)

Next.js app, dark UI, three panes:
- **Media library** (left): asset list with status/thumbs, upload button (file → POST /assets), ingest progress via WS.
- **Preview** (center): plain `<video>` element playing the **proxy of the clip under the playhead** — honest placeholder, not the L0 compositor. Plus a "Render" button → render job → progress → playable result link when done.
- **Timeline** (bottom): tracks as horizontal lanes; clips as blocks (asset name + duration) with thumbnails/waveform strip; playhead; zoom; **interactions: select, drag-move (→ `move` op), drag edges (→ `trim`), S to split at playhead, Del to remove, Ctrl+Z/Y undo/redo**. Every interaction is an `apply` call — the UI never mutates local EDL state except optimistically pending server ack.
- **Revision strip**: last N revision summaries; click = view (read-only) that rev.

No AI chat panel yet (render the pane with a "Phase 2" placeholder). No effects browser. No caption editor beyond `add_caption` via a simple dialog.

## A10. Repo structure

```
cutlab/
├── apps/
│   ├── studio/                    # Next.js 14+, TypeScript, Tailwind
│   │   └── src/{app,components/{timeline,library,preview,revisions},lib/api.ts,lib/types.ts}
│   └── server/                    # Python 3.11+, FastAPI, uv or venv
│       ├── cutlab/
│       │   ├── edl/{schema.py, validate.py, ops.py, engine.py, diff.py}
│       │   ├── render/{planner.py, ffgraph.py, audio.py, runner.py}
│       │   ├── jobs/{queue.py, worker.py, ingest.py}
│       │   ├── db.py  api.py  ws.py  config.py  main.py
│       │   └── util/{ids.py, ffprobe.py, paths.py}
│       └── tests/                 # pytest — see acceptance tests
├── capabilities/                  # empty + README (later phases)
├── profiles/default.json          # minimal stub
├── data/                          # gitignored: cutlab.db, projects/
├── scripts/{dev.ps1, dev.sh}      # start server + studio together
└── README.md
```

## A11. Later phases (context only — DO NOT BUILD NOW)

P1 Understanding Layer (faster-whisper, PySceneDetect, silencedetect, librosa beats, saliency v1 with per-profile weights) → P2 AI Director v1 (context compiler, plan→propose→accept loop, first smart ops incl. remove_silence, caption_from_transcript, reframe) → P3 L0 browser compositor + L1 segment renders + emphasis ops + first Remotion caption styles → P4 Compaction Engine + Telegram gate (@AlltronzBot) → P5 Recap Engine (story pass → script gate → ElevenLabs VO → WhisperX timing map → scene retrieval → dress) → P6 capability registry at depth + 3 brand profiles → P7 pro polish. Ecosystem reuse when those phases come: faster-whisper (CLIPFORGE), Timing Map + WhisperX (VB Studio), Remotion craft (ad system / HIW), SQLite durability + approval gates (Agent OS / FLOWDECK patterns).

---

# PART B — BUILD INSTRUCTIONS (PHASE 0)

## B1. Mission

Build the spine: **ingest real footage → hand-write or UI-build an EDL → apply ops with revisions/undo → render correct output with FFmpeg → survive crashes.** When Phase 0 passes its tests, CutLab exists as a machine; everything after is organs.

## B2. Environment

- Windows 11, user `ALLTRON`. Develop Windows-native (PowerShell scripts; use `pathlib` everywhere, no hardcoded separators). Keep everything Railway-portable: no Windows-only APIs.
- Python 3.11+, Node 20+, FFmpeg + ffprobe on PATH (verify at server startup; fail loud with install instructions if missing).
- Ports: server 8787, studio 3000. SQLite WAL. All state under `./data/`.

## B3. Build order (strict)

1. `db.py` + schema + `jobs/queue.py` (enqueue, claim, checkpoint, recover-on-start) — **with tests first**: recovery test = mark job running with 2 of 4 stage artifacts, restart worker, assert stages 3–4 only run.
2. `edl/schema.py` + `validate.py` — every rule in A4; table-driven tests (valid fixtures + one fixture per error code).
3. `edl/ops.py` + `engine.py` + `diff.py` — every Phase 0 op incl. edge rules (split-inside-speed-clip, ripple math, overlap rejection, trim edge modes); transactional plan apply; revision write; undo/redo; summary generation.
4. `util/ffprobe.py` + `jobs/ingest.py` — 4-stage checkpointed ingest.
5. `render/` — planner → ffgraph (video) → audio → runner with 60s chunking + resume. Test against generated fixtures (use ffmpeg `testsrc2`/`sine` to synthesize deterministic test media in a fixture script — do not require real footage for CI).
6. `api.py` + `ws.py` — full A7 surface; optimistic locking; per-project write lock.
7. `apps/studio` — library → preview → timeline interactions → revision strip, in that order.
8. `scripts/dev.*`, README (setup, run, test), final acceptance pass.

Commit per module with passing tests before moving on. If a spec detail is ambiguous, choose the simplest interpretation consistent with A2 principles, note it in `DECISIONS.md`, and continue — do not stall, do not invent scope.

## B4. DO NOT BUILD (Phase 0 exclusions — hard)

No AI director, no LLM calls anywhere. No understanding layer (whisper/scenes/silence). No Remotion; captions render nowhere (warning only). No effects/transitions execution (validate shape, warn, skip). No L0 compositor or L1 segments (preview = proxy `<video>` only). No Telegram. No compaction/recap. No auth/multi-user. No capability registry logic beyond the unknown-cap warning. No export preset matrix (single H.264 output). Later-phase ops return `E_NOT_IMPLEMENTED`.

## B5. Acceptance tests (definition of done)

Automated (pytest + one Playwright smoke):
1. **Validator** — all A4 rules covered; malformed EDLs produce the right `Issue.code`.
2. **Ops engine** — golden tests per op; property test: any random valid plan sequence never yields an invalid EDL; undo/redo round-trips restore exact snapshots.
3. **Render correctness** — synthesize 3 test clips (testsrc2 + distinct sine tones); EDL cuts them 3s/2s/4s with one 2× speed clip and one gain change; render; assert output duration 8.0s ±1 frame via ffprobe, and audio tone sequence matches expected order (spectral check on 3 sample windows).
4. **Crash resume** — start a chunked render on a 3-minute synthetic timeline, SIGKILL the worker mid-chunks, restart, assert completed chunks are not re-rendered (mtimes unchanged) and final output is valid.
5. **Optimistic locking** — two concurrent applies from same base_rev: one 200, one 409.
6. **UI smoke (Playwright)** — create project → upload fixture video → wait ingest → drag to timeline → split → trim → undo → render → assert job reaches `done` and output file exists.

Manual (the human will run):
7. Ingest a real long video → proxy scrubs smoothly, waveform + thumbs visible.
8. Build a 3-clip cut in the UI, render, watch it — cuts land exactly where placed.
9. Kill the server mid-render, restart, render resumes and completes.

Phase 0 is done when all nine pass. Then stop and report — do not start Phase 1.

## B6. Working conventions

- Type hints + pydantic models throughout the server; TypeScript strict in studio; shared types mirrored in `lib/types.ts` (hand-mirrored is fine in Phase 0).
- Every ffmpeg invocation logged in full. Every job failure captures stderr tail into `jobs.error`.
- Stable error codes only (no free-text matching in tests).
- Keep functions pure where the spec says pure (validator, ops, graph compiler); side effects live in runners/workers only.
- Maintain `DECISIONS.md` (ambiguity resolutions) and `PROGRESS.md` (module checklist) at repo root.

Begin with step B3.1.
