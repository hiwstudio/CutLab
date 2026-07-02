# DECISIONS

Ambiguity resolutions, per B3's instruction to choose the simplest interpretation
consistent with A2 and keep moving.

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
