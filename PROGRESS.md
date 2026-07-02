# PROGRESS — Phase 0

- [x] B3.1 db.py + schema + jobs/queue.py (enqueue, claim, checkpoint, recover-on-start) + worker — tests passing
- [x] B3.2 edl/schema.py + validate.py — table-driven tests passing
- [ ] B3.3 edl/ops.py + engine.py + diff.py — ops, transactional apply, revisions, undo/redo
- [ ] B3.4 util/ffprobe.py + jobs/ingest.py — 4-stage checkpointed ingest
- [ ] B3.5 render/ — planner, ffgraph, audio, runner (60s chunks + resume)
- [ ] B3.6 api.py + ws.py — full A7 surface
- [ ] B3.7 apps/studio — library, preview, timeline, revision strip
- [ ] B3.8 scripts/dev.*, README, acceptance pass

## Acceptance tests (B5)

- [ ] 1 Validator coverage
- [ ] 2 Ops engine golden + property + undo/redo round-trip
- [ ] 3 Render correctness (duration ±1 frame, tone order spectral check)
- [ ] 4 Crash resume (SIGKILL mid-chunks, completed chunks not re-rendered)
- [ ] 5 Optimistic locking (200 + 409)
- [ ] 6 UI smoke (Playwright)
- [ ] 7–9 Manual (human)
