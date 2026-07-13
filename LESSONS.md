# LESSONS

Durable fixes worth carrying into later phases. One entry per lesson; update in
place rather than duplicating.

## Mutated pydantic models skip shape validation — always re-validate the serialized snapshot
In-place mutations of parsed models (`clip.out_ms = 0`) bypass field/model
validators; only a full re-parse re-runs them. The engine therefore validates
`json.loads(model_dump_json())` — the exact bytes to be persisted — before
committing any revision (engine.py). Any future code that mutates EDL models
(director plans, engines) must go through `Engine.apply`, never write snapshots
directly.

## Floor, don't round, when deriving source lengths from timeline lengths
`round()` on `(timeline_ms × speed)` can overshoot by 1ms and create overlaps or
degenerate ranges after trims/splits/deletes. Rule: source spans are computed
with `floor(timeline_ms × speed)`, guaranteeing the resulting timeline length
never exceeds the target (ops.py `_src_len_for_timeline`). Also: a trim can
still floor a remnant to zero source length — degenerate remnants must be
dropped, not kept (found by the hypothesis property test at final acceptance).

## Property-based tests catch what golden tests can't — keep them in the gate
The only post-module bug in Phase 0 (degenerate `delete_range` remnant) was
found by the random-plan hypothesis test, not by 30+ golden tests. Every future
op (remove_silence, compact, reorder…) must be added to the property test's
generator, not just given golden cases.

## ffmpeg on PATH is a lie on this machine
ImageMagick ships ffmpeg 4.2.3 which shadows the real 8.1 install. Resolve
ffmpeg from ffprobe's directory (ffprobe isn't shadowed), with env overrides —
`cutlab/config.py._resolve_ff`. Replicate in any script that shells out to
ffmpeg (the Playwright global-setup already does).

## `fps=1/N` can emit zero frames on short inputs
Thumbnail extraction with `fps=1/5` produced no output on a ~2s video (ffmpeg 8).
Use `select=isnan(prev_selected_t)+gte(t-prev_selected_t\,5)` + `-fps_mode vfr`
semantics (we pass `-vsync vfr`) to guarantee the first frame is always taken.

## Chunked renders: put audio inside each chunk, mux with concat-demux `-c copy`
Per-chunk video+audio encoding with identical codec settings lets the final mux
be a pure stream-copy — fast, and resume-safe because each chunk is an
independent checkpointed artifact. Never re-encode at mux time.

## A silently-dead backend looks like a broken frontend
The studio kept rendering its last-loaded state after the API server died; every
action failed quietly and the app "didn't work." Any UI over the API needs an
explicit unreachable-server state with auto-reconnect (useEditor `serverDown` +
3s probe). Assume later surfaces (Telegram gate, dashboards) need the same.

## Custom pointer-event drag needs `touch-action: none` + `pointercancel`
Mouse-only drag logic breaks under touch/pen: the browser turns the gesture into
a scroll and fires `pointercancel`, leaving drag state stuck. Every draggable
element gets `touch-action: none` and every drag state machine handles
`pointercancel` (Timeline, Editor asset drag).

## The AI never mutates state directly — it proposes ops the human accepts
The director turns NL into a plan of ops, applied in `propose` mode only; the
engine validates it, so a bad LLM plan becomes a reported rejection, never a
broken EDL, and the human always accepts/rejects (A2.2/A2.3). Keep this invariant
for every future AI surface: model output → validated ops → proposal, never a
direct snapshot write or an auto-commit.

## Smart ops that need derived data take it via an injected context, staying pure
remove_silence/caption_from_transcript read Phase-1 understanding through an
OpContext the engine populates, not by reading files in apply(). Logic lives in
pure planner functions (edl+data → primitive-op plan) so it's unit-testable; the
op just expands into primitives. Reuse this shape for any data-driven op.

## LLM plan parsing must tolerate prose and ```json fences
Models wrap JSON in explanation or code fences. parse_plan tries bare JSON, then a
fenced block, then the first {...} span, and validates it's `{"ops":[...]}` with
op objects — anything else is a clean LLMError, not a crash. Always parse
defensively; never `json.loads` a raw completion and assume success.

## The engines are integration layers over the EDL, never parallel pipelines
Compaction and recap don't run their own ffmpeg or mutate media: they compute a
plan (pure functions over understanding data) and emit ONE transactional
proposal of ordinary ops. Everything downstream (render, undo, diffs, gates,
Studio review) works on them for free. Any future engine (P-whatever) must
follow this shape.

## rAF is not a clock — media elements are
requestAnimationFrame freezes in hidden tabs; a transport clock built on it
stalls while videos keep playing. Drive playback time from the playing media
element's currentTime (interval-corrected), and A/V sync becomes structural
instead of chased.

## Filtergraph parameters are an injection surface
Anything templated into an ffmpeg -filter_complex string must be validated to
numerics first (capabilities.effect_filter rejects strings). A "radius" of
"8,evil=1" would otherwise splice arbitrary filters into the graph.

## Don't round-trip UTF-8 text through PowerShell 5.1 cmdlets
`Get-Content -Raw | Set-Content -Encoding utf8` on BOM-less UTF-8 misreads it as
ANSI and double-encodes non-ASCII (em-dashes → mojibake). Use the file tools or
Python for text edits; keep PS to process/port management.

## SQLite job claiming: order by `rowid`, not timestamps
`created_at` has millisecond resolution; two enqueues in the same ms tie and
break FIFO. `rowid` is insertion order and free.

## Injectable-dependency defaults must resolve at call time, not def time
`def f(load_model=_real_loader)` binds the default once at definition, so
monkeypatching the module attribute later has no effect — the understanding job
kept running real whisper despite a fake being patched in. Use `load_model=None`
and resolve `(load_model or _real_loader)()` inside the body (name lookup at call
time). Applies to any injected-for-testability heavy dependency.

## Tempo estimation needs an octave prior
A regular pulse train's autocorrelation peaks equally at the period and its
multiples, so naive argmax picks 60 BPM for a 120 BPM track. Fix: weight the
autocorrelation by a log-normal prior centered at 120 BPM, and derive the final
tempo from the median detected beat spacing for self-consistency (beats.py).

## Additive SQLite migrations for a shipped DB
Adding a column (assets.understanding) to a DB real projects already use needs a
guarded `ALTER TABLE ADD COLUMN` on connect (PRAGMA table_info check), not just a
new CREATE — existing rows must gain the column without data loss (db.py `_migrate`).

## Prefer the owner's proven ffmpeg approach over a heavier named dependency
The spec named PySceneDetect, but recap-engine already does scene detection with
the classical ffmpeg `scene` filter — deterministic, zero extra dependency, and
production-proven. Reuse principle + A2.7 favored it. Check the existing engines
before pulling a new library the spec merely names.

## Playwright starts webServers before globalSetup
Global setup cannot wipe a data dir the API webServer already holds open
(SQLite lock). Treat webServer-owned state as append-only from setup code.
