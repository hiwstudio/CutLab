# DECISIONS

Ambiguity resolutions, per B3's instruction to choose the simplest interpretation
consistent with A2 and keep moving.

## Phase 1 — Understanding Layer

A11 specifies P1 as one line ("faster-whisper, PySceneDetect, silencedetect,
librosa beats, saliency v1 with per-profile weights") — no Part-B-style detailed
build spec. Resolutions:

- **Scope boundary**: P1 builds the layer that *produces* understanding data only.
  The ops that *consume* it (`remove_silence`, `caption_from_transcript`, `reframe`)
  are explicitly P2 in A11 and stay `E_NOT_IMPLEMENTED`. No AI/LLM (P2), no Remotion,
  no compaction. Minimal UI surfacing (an Analyze trigger + status/counts) so the
  data is observable without building P2's consumption.
- **Scene detection uses the ffmpeg `scene` filter, not PySceneDetect.** The owner's
  recap-engine (the reuse source per CLAUDE.md) already detects scenes with
  `select='gt(scene,thr)',showinfo` — classical, deterministic, zero extra
  dependency — and it's proven in production. A2.7 (determinism) and the reuse
  principle both favour it over adding PySceneDetect. Same thresholds as recap-engine
  (SCENE_THRESHOLD 0.30, SCENE_MIN_LEN 1.5s).
- **Silence** reuses viral-clip-engine's `silencedetect=noise=-30dB:d=0.6` approach
  verbatim (spec literally names `silencedetect`), plus its active-range
  padding/merge logic, exposed as data (spans + active ranges) — no cutting here
  (cutting is `remove_silence`, a P2 op).
- **Transcription** reuses both engines' faster-whisper config (model `small`, device
  `auto`, compute `auto`, `word_timestamps=True, vad_filter=True`, audio pre-extracted
  as 16 kHz mono pcm_s16le). Model id/device overridable via `CUTLAB_WHISPER_*` env.
- **Beats**: librosa (with numba) **did** install cleanly on Python 3.14, so
  `librosa.beat.beat_track` is the primary path. The numpy-only onset-strength +
  autocorrelation-tempo tracker is kept as an automatic fallback (used if librosa
  is absent or raises), and it's independently tested on a click track — so beats
  never hard-fail on a thinner environment. The numpy tempo estimate needed a
  log-normal 120-BPM prior to fix pulse-train octave ambiguity (60 vs 120 BPM),
  and the reported tempo is derived from detected beat spacing for self-consistency.
- **Understanding artifacts are content, not deterministic renders.** A2.7's
  byte-stability rule targets render output; whisper/VAD results are not byte-stable.
  The artifact carries the model id + parameters used, for provenance.
- **Understanding enters the EDL via an op**, mirroring ingest's `add_asset`: a new
  `set_understanding` op sets `asset.understanding` to the artifact path (A2.2 — ops
  are the only mutation path). It is a Phase-1 op, not one of A5's later-phase enum
  entries.

## Phase 2 — AI Director (in progress)

A11 scopes P2 as: AI Director v1 (context compiler, plan→propose→accept loop,
first smart ops incl. remove_silence, caption_from_transcript, reframe). Build
order chosen: the deterministic foundation first (smart ops + accept/reject loop,
neither needs an LLM), then the LLM director on top.

- **Smart ops consume understanding via an `OpContext`, not file I/O in apply.**
  Ops must stay pure (A2). The three smart ops need Phase-1 understanding data,
  which lives in `asset.understanding` files. Resolution: the *logic* is pure
  planner functions `(edl, understanding) → mutations`, and op `apply` gains an
  optional `OpContext` (an in-memory `{asset_id: Understanding}` map) that the
  engine populates by loading the referenced artifacts before apply. Purity is
  preserved (apply is a pure function of edl + ctx); tests pass ctx directly.
- **remove_silence** deletes the silent timeline ranges of a target asset's clips
  using the understanding silence spans (mapped from source time to timeline time,
  respecting each clip's in/out/speed), via the existing delete_range semantics
  (ripple to close gaps). It does not re-cut media — it edits the EDL, and the
  Phase-0 render realizes it.
- **caption_from_transcript** groups transcript words into phrase clips (reusing
  viral-clip-engine's grouping: ≤N words, break on sentence punctuation) and adds
  them to a caption track, timed to where the asset actually plays on the timeline.
  It creates EDL caption clips; burning them is P3 (Remotion), so Phase-0 render
  still skips caption tracks with a warning.
- **reframe** is the basic center reframe: set the target canvas and set the
  affected clips' `crop.mode="center"`. The Phase-0 render compiler already
  center-crops to the canvas aspect, so no new render code is needed.
  `reframe_auto` (face/subject tracking) stays later-phase (needs vision), per A4.
- **LLM backend: pluggable, default manual** (owner's decision, 2026-07-04). Like
  recap-engine: `CUTLAB_LLM_BACKEND` selects `manual` (default — writes the prompt
  to `director/{rid}.prompt.txt`, a human/Claude drops the answer back, it resumes;
  free, no key, crash-resumable via the files), `openrouter`, or `anthropic`. Keys
  come from the env (`OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY`) and are never
  stored or logged. Auto backends fall back to manual if their key is absent.
- **The director never commits — it only proposes** (A2.3). Every plan, whichever
  backend produced it, is applied in `propose` mode; the human accepts/rejects.
  The system prompt constrains the model to a safe op subset (the smart ops +
  primitive edits); the engine validates the plan, so a bad plan becomes a
  reported rejection, never a broken EDL.
- **Director v1 is request/response, not a durable job.** A2.4 ("heavy work is a
  durable job") targets minutes-long media work; an LLM call is seconds and its
  result is already a persisted proposal revision. Automatic calls are offloaded
  to a thread (`asyncio.to_thread`) so they don't block the event loop; manual
  request state lives in files (resumable). Moving the director onto the job queue
  is a later option if calls get heavier (e.g. multi-step planning).

## Environment

- **ffmpeg resolution**: ImageMagick ships an ancient ffmpeg 4.2.3 that shadows the
  real ffmpeg 8.1 on this machine's PATH. `config.py` resolves ffmpeg from ffprobe's
  directory (ffprobe is not shadowed), with `CUTLAB_FFMPEG` / `CUTLAB_FFPROBE` env
  overrides. Startup verifies both run.

## Validation

- **Issue codes**: A4 names `E_OVERLAP, E_RANGE, E_REF, E_SCHEMA, W_UNKNOWN_CAP, ...`
  — the ellipsis is filled with: `E_KIND` (kind incompatibility), `E_DUP` (duplicate
  ids), `E_ORDER` (clips unsorted), `E_SRC` (asset source file missing), `E_DURATION`
  (stored duration_ms ≠ recomputed), `E_NOT_IMPLEMENTED` (later-phase ops),
  `E_CONFLICT` (optimistic-lock failure, HTTP 409). Numeric out-of-range from shape
  checking maps to E_RANGE; type/pattern/enum/missing/unknown-field errors map to E_SCHEMA.
- **Unknown fields are rejected** (`extra="forbid"`): catches typos early; the EDL is
  a strict contract.
- **src existence** is checked only when a project base dir is supplied (server always
  supplies it; pure unit tests may omit it).
- **duration_ms**: value `0` is always accepted (fresh/client EDLs); the engine
  recomputes and stores the derived value on every mutation. A nonzero mismatch is
  `E_DURATION`.
- **Audio tracks accept video assets** (a video's audio stream), mirroring
  "image allowed on video tracks".

## Ops

- **`add_asset` internal op**: A5 has no op that registers an asset in the EDL, but
  A2.2 says ops are the only mutation path. Ingest completion therefore applies an
  internal `add_asset` op (also callable via the API).
- **Rounding**: timeline length = round-half-up((out−in)/speed). Trim/split/delete_range
  compute source lengths with floor(timeline·speed) so rounding can never create a 1ms
  overlap; a split's right piece starts where the left piece ends (continuity), which can
  differ from `at_ms` by <1ms at extreme speeds.
- **split on caption clips** is allowed (partitions the time window, duplicates text).
- **split keeps `transition_out` on the right piece only** (it's an *outgoing* edge
  transition).
- **Explicit ids**: `add_track`/`add_clip`/`add_caption`/`split` accept an optional
  client-chosen id (pattern-validated) so tests and optimistic UIs can pin ids;
  generated when absent.
- **redo** follows the highest-numbered committed child of the current head (after
  undo + new edits create a branch, redo prefers the newest branch).

## Jobs

- **Attempts semantics**: `attempts` increments on crash recovery *and* on handler
  exception; reaching 3 → `failed`. Stage artifacts store absolute paths; non-path
  artifact values (logged commands) are ignored by the integrity check.
- **Render stages**: A8 lists plan/video/audio/mux but also mandates ≤60s chunking with
  `video_chunk_{n}` checkpoints. Implemented as: `plan` → `chunk_{n}` (each chunk
  compiles video+audio together into one intermediate mp4) → `mux` (concat demux +
  faststart). This is what makes resume real; audio is inside each chunk.
