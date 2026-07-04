# PROGRESS — Phase 0

- [x] B3.1 db.py + schema + jobs/queue.py (enqueue, claim, checkpoint, recover-on-start) + worker — tests passing
- [x] B3.2 edl/schema.py + validate.py — table-driven tests passing
- [x] B3.3 edl/ops.py + engine.py + diff.py — ops, transactional apply, revisions, undo/redo
- [x] B3.4 util/ffprobe.py + jobs/ingest.py — 4-stage checkpointed ingest
- [x] B3.5 render/ — planner, ffgraph, audio, runner (60s chunks + resume)
- [x] B3.6 api.py + ws.py — full A7 surface
- [x] B3.7 apps/studio — library, preview, timeline, revision strip
- [x] B3.8 scripts/dev.*, README, acceptance pass

## Acceptance tests (B5)

- [x] 1 Validator coverage — `tests/test_validate.py` (37 cases, one per rule/code)
- [x] 2 Ops engine golden + property + undo/redo round-trip — `tests/test_ops.py`, `tests/test_ops_property.py`
- [x] 3 Render correctness — `tests/test_render.py::test_render_correctness_three_clips`
      (8.0s ±1 frame; spectral tone order 440→660→880; −12dB gain ratio)
- [x] 4 Crash resume — `tests/test_render.py::test_crash_resume_kills_worker_mid_chunks`
      (SIGKILL mid-chunks; completed chunk mtimes unchanged; output valid)
- [x] 5 Optimistic locking — `tests/test_api.py::test_optimistic_locking_concurrent` (200 + 409)
- [x] 6 UI smoke (Playwright) — `apps/studio/tests/smoke.spec.ts`
      (create → upload → ingest → drag → split → trim → undo → render → file exists)
- [x] 7 Manual: ingest a real long video → proxy scrubs, waveform + thumbs visible
- [x] 8 Manual: 3-clip cut in the UI, render, cuts land exactly
- [x] 9 Manual: kill server mid-render, restart, render resumes and completes

Tests 7–9 run and confirmed by the owner on 2026-07-04.

**Phase 0 complete — all nine acceptance tests pass.** Next phase starts only on
the owner's request (P1 understanding layer; see docs/HANDOFF.md §A11 and the
engine-reuse map in CLAUDE.md).
