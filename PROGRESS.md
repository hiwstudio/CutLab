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

**Phase 0 complete — all nine acceptance tests pass.**

---

# PROGRESS — Phase 1 (Understanding Layer)

Scope (A11): produce per-asset understanding data. Consuming ops (remove_silence,
caption_from_transcript, reframe) remain P2 and stay `E_NOT_IMPLEMENTED`.
See DECISIONS.md "Phase 1" for the resolutions and reuse map (CLAUDE.md).

- [x] P1.1 understanding/schema.py — per-asset artifact (transcript/scenes/silence/
      active_ranges/beats/tempo/saliency/provenance), integer ms
- [x] P1.2 understanding/scenes.py — ffmpeg scene filter (from recap-engine) —
      `tests/test_understanding_av.py`
- [x] P1.3 understanding/silence.py — ffmpeg silencedetect + active ranges (from
      viral-clip-engine) — `tests/test_understanding_av.py`
- [x] P1.4 understanding/transcribe.py — faster-whisper (from both engines),
      injectable model — `tests/test_transcribe.py` (fake + real model)
- [x] P1.5 understanding/beats.py — librosa (installed on py3.14) w/ numpy fallback —
      `tests/test_beats.py`
- [x] P1.6 understanding/saliency.py + profiles.py — per-profile weighted saliency —
      `tests/test_saliency.py`
- [x] P1.7 jobs/understanding.py — durable 6-stage job + set_understanding op +
      assets.understanding migration — `tests/test_understanding_job.py` (incl. crash-resume)
- [x] P1.8 API (analyze / understanding endpoints) + Studio UI (Analyze button,
      progress, Insights panel) — `tests/test_understanding_api.py`,
      `apps/studio/tests/understanding.spec.ts`

## Phase 1 acceptance (analogous to B5)

- [x] Scene detection — hard-cut fixture yields 3 scenes at the true boundaries
- [x] Silence detection — tone/silence/tone yields one middle span + two active ranges
- [x] Transcription — faster-whisper schema conversion (fake model) + real run
- [x] Beats — 120-BPM click track recovered (~500ms spacing, tempo ~120)
- [x] Saliency — per-profile weights reorder speech-vs-montage windows correctly
- [x] Understanding job — full 6-stage pipeline writes valid artifact + registers in EDL
- [x] Crash-resume — rewind after silence stage; scenes/silence not re-run
- [x] API — analyze enqueues job; understanding fetch returns artifact; asset lists path
- [x] UI (Playwright) — `apps/studio/tests/understanding.spec.ts` (analyze → Insights panel)
- [x] Live check on owner's real footage — proj_8pl41d6l / ast_0sfvy9db (43s clip):
      4 scenes, en transcript ("So we got those fun inside Linkington."), 53 beats @86 BPM,
      22 saliency windows, registered in the EDL as understanding/ast_0sfvy9db.understanding.json

**Phase 1 complete.** Server suite: 146 tests pass (128 fast + 18 slow). Studio:
smoke + understanding Playwright specs pass.

---

# PROGRESS — Phase 2 (AI Director)

Scope (A11): AI Director v1 (context compiler, plan→propose→accept loop, first
smart ops: remove_silence, caption_from_transcript, reframe). Built the
deterministic foundation first (needs no LLM), then the director on top.

- [x] P2.1 OpContext plumbing — engine loads asset understanding artifacts and
      passes them to op.apply (keeps ops pure) — regression-covered
- [x] P2.2 remove_silence — pure planner (silence→delete_range) + op — `tests/test_smartops.py`
- [x] P2.3 caption_from_transcript — phrase grouping + timed caption clips — `tests/test_smartops.py`
- [x] P2.4 reframe — center-crop via canvas + set_crop; renders 1080×1920 — `tests/test_smartops.py`
- [x] P2.5 propose→accept/reject loop — engine + API + Studio review panel +
      smart-op propose triggers — `tests/test_proposals.py`, `apps/studio/tests/proposals.spec.ts`
- [x] P2.6 AI Director (LLM) — context compiler + pluggable backend (default
      manual, + openrouter/anthropic) + command→plan→propose loop + Studio command
      box — `tests/test_director.py`, `apps/studio/tests/director.spec.ts`

## Phase 2 acceptance so far

- [x] Smart ops golden + engine tests (remove_silence/captions/reframe)
- [x] reframe renders at true 9:16 (slow test)
- [x] propose/accept/reject (engine + API)
- [x] UI: propose a smart edit → review → accept (Playwright)
- [x] Live on owner's footage: proposed captions from the real transcript on
      proj_8pl41d6l/ast_0sfvy9db, accepted (2 caption clips), then undone to
      restore baseline (head r14).

- [x] AI Director: context compiler, plan parsing (bare/fenced/prose JSON),
      command→propose loop (fake + manual backends), API surface — `tests/test_director.py`
- [x] UI: NL command → manual prompt → paste plan → proposal → accept (Playwright)
- [x] Live on owner's footage: "make this vertical for tiktok" → director prompt →
      reframe plan → proposed → accepted (canvas 1080×1920) → undone to restore.

**Phase 2 complete.** Server suite: 163 fast tests pass (+ slow). Studio: smoke,
understanding, proposals, director Playwright specs pass. The director proposes;
the human always accepts/rejects. Automatic backends (openrouter/anthropic) work
by adding a key to the env; manual is the default and needs none. Next phase (P3:
L0 compositor + Remotion caption styles) starts only on the owner's request.
