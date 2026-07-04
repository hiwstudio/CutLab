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

## Don't round-trip UTF-8 text through PowerShell 5.1 cmdlets
`Get-Content -Raw | Set-Content -Encoding utf8` on BOM-less UTF-8 misreads it as
ANSI and double-encodes non-ASCII (em-dashes → mojibake). Use the file tools or
Python for text edits; keep PS to process/port management.

## SQLite job claiming: order by `rowid`, not timestamps
`created_at` has millisecond resolution; two enqueues in the same ms tie and
break FIFO. `rowid` is insertion order and free.

## Playwright starts webServers before globalSetup
Global setup cannot wipe a data dir the API webServer already holds open
(SQLite lock). Treat webServer-owned state as append-only from setup code.
