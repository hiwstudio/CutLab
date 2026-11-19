# PROGRESS — Current interface work (September 2026)

- 2026-09-30: First production ecosystem adapter implemented: complete MixFix
  MIX/FIX import through durable jobs, copied/ingested media, editable footage,
  narration and captions, scene provenance and source alternatives. Engines
  inspector prepares isolated visual-update proposals with Preview/Accept/Reject;
  source metadata participates in revisions and undo. Regeneration saves a
  downloadable operator handoff; automatic dispatch/generation remains pending.
  Source approval gates are unchanged. Added transactional head checks to prevent
  worker/editor races. Media-backed import checks exposed a frame-rounding bug
  on held footage; the fix uses the engine renderer with a guard frame.
  Verification: 248 fast server tests pass (24 slow deselected), TypeScript passes,
  browser import, playback, proposal preview and rejection verified. The
  integration suite uses synthetic media and verifies scene-linked edits.
  Scope and remaining adapters: `docs/ENGINE-INTEGRATION.md`.

- 2026-09-22: Fixed initial editor loading by resolving route params and
  fetching the saved project on the server, seeding the interactive editor
  with its EDL, revision and assets. Completed same-origin media/WS routing
  and allowed the local development origin. Browser verification confirms the
  editor loads saved tracks, clip selection opens Lens, and playback advances.

- [x] Four interactive interface concepts created (2026-09-11).
- [x] **D / Spine** selected as the editor layout (2026-09-13).
- [x] Preserve A/B for a possible future public editor; original comparison
      archived in `docs/ui-concepts/archive/2026-09-11/`.
- [x] Refine D with Media, precise timing, compact audio controls and history
      using the existing sample model.
- [x] Update design spec and record `docs/SPINE-IMPLEMENTATION.md`.
- [x] Refinement checks: four Node tests pass; browser verified Media → Lens,
      precise trim, Music gain, History and undo restoration; visual inspection.
- [x] Migrate Studio to the Spine rail, preview, Lens/Audio/History tabs and inline Director.
- [x] Saved scene ranges, approval/review invalidation, linked scene reorder,
      named tracks, role/mute/solo/lock/gain and precise clip/caption properties.
- [x] Live audio on separate media tracks, additive clip/track gain, mute/solo
      semantics shared with export; frame stepping, scene band and timeline fit.
- [x] Verification: 205 existing fast server tests, six new Spine tests, Director
      server tests; frontend type/lint checks; browser ingest/edit/undo/render,
      compositor/segment preview, proposals, palette, analysis and Spine workflow.
      Populated layouts inspected at 1440×900 and 1100×760.
- [x] D fidelity pass: bundled the approved Hanken Grotesk, Bricolage Grotesque
      and JetBrains Mono faces; matched the 50px shell, compact scene rail,
      640px preview, segmented scrubber, centred transport, Lens hierarchy,
      amber playhead and compact role-coloured timeline.
- [x] Verified resumable MixFix MIX/FIX import through the durable asset and EDL
      APIs. Integration checks cover scene timing, footage, narration, captions,
      provenance, undo, proposals, resume and source immutability. Importers can
      read user-supplied projects; production media is not included here.
- [x] Professional editor controls: opacity/source replacement, crop/transform,
      speed, clip/track volume, audio and video fades, visual adjustments,
      caption templates, beat snapping, mirror, transitions, reverse, freeze
      frame, named overlay/sticker tracks, and project background colour. Each
      is a revisioned EDL operation shared by the Studio preview and FFmpeg
      export. Focused server tests and Studio type checks pass; live API
      apply/undo checks restored the clean test project after each control.
- [x] Circle mask: a non-destructive clip effect with matching browser alpha
      clipping and FFmpeg alpha compositing. Its export passed a real smoke
      render, and its live API apply/undo check restored the test project.
- [x] Still-image background cutout: durable local U2-Net/ONNX job adapted
      from Mirage Studio, configurable model path, transparent PNG derivative,
      EDL asset registration, and a Media-panel action. Verified with a real
      four-channel cutout (alpha 0–254), live job completion, and Studio UI.
- [x] Automatic music ducking: the Audio inspector now splits a selected music
      track at padded voiceover boundaries and applies an exact ducked gain to
      the overlapping regions. The cuts remain editable and use the normal EDL
      revision, undo, preview and export paths. Render checks cover overlapping
      voice and music, and confirm stereo AAC output.
- [x] Built-in Sounds library: the Media panel exposes configured local music
      and sound-effect cues with in-place audition, category filters, and project
      import through normal durable ingest. The cue catalog remains local and
      is populated by the user.
      Follow-up workflow fix: Add now waits for ingest and places the sound at
      the playhead, then marks the library card ready for direct timeline drag.
      UI verification covers adding at the playhead and dragging an imported
      sound onto an audio lane.
- [x] Auto Lyrics: analyzed vocal audio can now generate a dedicated lyric
      track with short phrases, source-to-timeline timing, and a Karaoke Lyrics
      template shared by browser preview and ASS export. Timed lyric preview
      and export were verified on a test voice sample.
- [x] Text layers and templates: the + menu and Command Palette open a proper
      playhead-aware text composer with editable duration and reusable Title
      Card, Lower Third, Top Title, Boxed Callout and Clean Text templates.
      Layers use dedicated text lanes and remain editable in Lens. Export frames
      were visually checked for placement, scale and readability.
- [x] Drawing annotations: the + menu and Command Palette open a transparent
      canvas with colour, brush size, opacity, eraser, undo, clear and duration
      controls. Saving ingests a transparent PNG and places it on a dedicated
      overlay lane at the playhead. Revision 63 contains a yellow checkmark;
      an exact four-second render visually confirms that its alpha is preserved
      over the source video and captions. Still-image RGBA preservation now has
      a renderer regression test.
- [x] Expansion QA gate: all 238 fast server tests pass, Studio TypeScript
      passes, and all seven Playwright workflows pass (compositor/exact preview,
      Director, palette, proposals, ingest/edit/render, Spine, understanding).
      The proposal check also restored a compact live canvas-size indicator in
      the D header so accepted reframes visibly confirm their output format.
- [ ] Next product work: refine scene-range authoring and selected-scene AI
      scoping, then formalize the demonstrated generated-project import contract.

Historical P0–P7 below records engine work, not completion of the Spine migration.

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

Tests 7–9 were confirmed on 2026-07-04.

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
- [x] Media-backed analyze check: scenes, transcript, beats, saliency windows,
      and the registered understanding artifact were verified end to end.

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
- [x] Proposed captions from an analyzed transcript, accepted the proposal, and
      undid it to restore the baseline revision.

- [x] AI Director: context compiler, plan parsing (bare/fenced/prose JSON),
      command→propose loop (fake + manual backends), API surface — `tests/test_director.py`
- [x] UI: NL command → manual prompt → paste plan → proposal → accept (Playwright)
- [x] Tested the Director's vertical reframe proposal, acceptance and undo flow.

**Phase 2 complete.** Server suite: 163 fast tests pass (+ slow). Studio: smoke,
understanding, proposals, director Playwright specs pass. The director proposes;
the human always accepts/rejects. Automatic backends (openrouter/anthropic) work
by adding a key to the env; manual is the default and needs none.

---

# PROGRESS — Phases 3–7 (full build-out, 2026-07-05)

## P3 — Preview ladder + captions
- [x] P3.1 add_emphasis (saliency-driven punch-in) — `tests/test_smartops.py`
- [x] P3.2 L1 segment previews (window_plan + fast encode + /preview) — `tests/test_preview.py`
- [x] P3.3 L0 browser compositor (layered live preview, media-clock transport,
      caption overlays) — `apps/studio/tests/compositor.spec.ts`
- [x] P3.4 Captions burn into renders (ASS/libass per chunk, 4 styles;
      registry-ready; Remotion deferred — see DECISIONS) — `tests/test_captions_render.py`

## P4 — Compaction Engine + Telegram gate
- [x] Deterministic clip-scoring rubric core + compact op — `tests/test_compaction.py`
- [x] Durable compaction job (candidates → propose → gate) + report contract
- [x] Telegram gate (thin bot on proposal accept/reject; round-tripped with an
      injected transport) — `tests/test_telegram_gate.py`. LIVE round-trip
      pending optional Telegram credentials in the local environment.

## P5 — Recap Engine
- [x] Outline/script prompts (adapted from recap-engine), pluggable LLM,
      manual file hand-off inside the durable job
- [x] Piper TTS (real synthesis in tests), loudnorm, measured durations
- [x] Time-prior + dialogue matching with coverage extension (CLIP visual
      matching deferred — weight slot kept)
- [x] EDL assembly as one transactional proposal — `tests/test_recap.py`

## P6 — Capability registry + brand profiles
- [x] Registry (manifest+handler): effects, transitions, caption styles,
      export presets; validator/planner/ffgraph/captions/mux all resolve
      through it — `tests/test_capabilities.py` (incl. rendered-grayscale proof)
- [x] Profiles with speech-heavy, montage and vertical short-form defaults are
      selectable per project.

## P7 — Pro polish
- [x] DESIGN-SPEC.md (S2 Dark Hi-Tech per ui-library decision engine)
- [x] Design tokens (globals.css), focus-visible rings, reduced-motion,
      shimmer skeletons, selection glow, thin scrollbars
- [x] ⌘K command palette — `apps/studio/tests/palette.spec.ts`
- [x] Job-outcome toasts (WS-driven, aria-live)
- [x] Full QA gate: complete server suite + complete Playwright suite (results
      in the final report)

Remaining known deferrals (each logged in DECISIONS.md with its upgrade path):
Remotion caption backend, CLIP visual matching in recap, cross-clip xfade
transitions, LLM judgment pass in clip scoring, live Telegram round-trip
(needs optional Telegram credentials).

## Professional editor expansion — 2026-09-22

- [x] Audio cleanup is revisioned per clip: steady-noise reduction, low cut,
      and high cut. Low/high cut audition in the browser; all three run through
      the exact segment-preview and final-export FFmpeg path.
- [x] Duplicate-clip operation accepts and preserves the current audio cleanup,
      fade, reverse, freeze, and visual animation fields.
- [x] Validation: 17 focused server tests pass; Studio TypeScript passes; a real
      FFmpeg filter smoke passes; test-project revision 12 produced the exact
      preview `renders/preview_r12_0_3000.mp4`.
- [x] Audio-effect presets are revisioned per clip: Voice Enhance, Telephone,
      Echo, and None. Voice/telephone have browser audition; all presets use
      the exact FFmpeg preview/export path. Three filter-chain smoke renders
      and 20 focused server tests pass. Test-project revision 13 contains Voice
      Enhance and rendered `renders/preview_r13_0_3000.mp4` successfully.
- [x] Direct microphone recording is available in the Media panel. It requests
      a microphone only when Record is pressed, records with browser echo/noise
      controls, uploads the take, and feeds the normal durable ingest pipeline.
- [x] Fixed browser `audio/webm` classification: multipart MIME now overrides
      the ambiguous `.webm` extension. Ten fast API tests and Studio TypeScript
      pass; a generated Opus/WebM test take ingested as ready audio.
- [x] Fixed browser MediaRecorder WebM takes with no container duration. Ingest
      now measures missing duration from decoded PCM, stores it in waveform
      metadata and the asset row, then registers the audio normally. Fifteen
      ingest/API tests pass. Missing duration is recovered from decoded audio,
      allowing browser-recorded takes to resume correctly.
- [x] Extract Audio is available on ready video assets. A durable job selects
      the first audio stream, encodes a standalone 192 kbps AAC/M4A asset,
      builds its waveform, and registers it in the EDL. Ten API tests and
      Studio TypeScript pass. Extraction was verified on a long-form test source.
- [x] Video Quality controls now include Reduce Noise, Stabilize, Remove
      Flicker, Enhance Detail, and Motion Blur as revisioned capability effects.
      All five passed direct FFmpeg processing; 30 focused server tests and
      Studio TypeScript pass. Video noise reduction was applied to the test
      clip and exact preview `preview_r33_0_2000.mp4` rendered successfully.
- [x] Project format controls expose Landscape 16:9, Vertical 9:16, Square
      1:1, landscape 4K, vertical 4K, and 24/25/30/50/60 fps. They use the
      revisioned canvas operation and preserve background color. Twenty-one
      focused server tests and Studio TypeScript pass. A live exact preview was
      probed at 3840x2160/24 fps, then the temporary format revision was undone.
- [x] Text to Sound is available in Media. It reuses the recap engine's local
      Piper voice and loudness-normalization path, runs as a durable job,
      generates waveform peaks, and registers a normal editable audio asset.
      Eleven fast API tests and Studio TypeScript pass. Local synthesis and
      normal asset registration are verified.
- [x] Text to Sound supports Fish Audio when configured, with Piper as a local
      fallback. Output is normalized to a 48 kHz stereo master. Thirteen tests
      and Studio TypeScript pass.
- [x] Caption workflow now exposes Whisper language selection (Auto, English,
      Spanish, French, German, Portuguese, Italian, Japanese, Korean, Chinese),
      words-per-caption, and Clean/Bold Pop/Boxed/Top Title templates. Explicit
      language re-analysis invalidates transcript-dependent checkpoints.
- [x] Generated and extracted audio now persist probe metadata so Analyze does
      not mistake them for silent assets. Twenty-seven focused tests and Studio
      TypeScript pass. Analysis was verified on generated audio with timed
      captions and an exact preview render.
## Engine pack and new-user onboarding — 2026-11-19

- [x] Bundled MixFix, Clipinn, Viral Clip Engine, Recap Engine, and HIW Studio
      source under engines/, excluding engine projects, credentials, databases,
      model weights, downloads, and finished media.
- [x] Added one setup path and a cross-platform launcher for the bundled engines.
- [x] Made CutLab discover the bundled MixFix path by default, while retaining
      CUTLAB_MIXFIX_ROOT for alternate installs.
- [x] Added a home-screen engine library and clearer first-project guidance.
- [x] Verification: 248 fast CutLab server tests, 23 Spine tests, 10 MixFix
      adapter tests, one complete browser smoke test, and the Studio production
      build pass. MixFix source tests pass 157/157 runnable cases; one case was
      skipped because SceneDetect is not installed in the CutLab test venv, and
      SceneDetect is declared in the bundled engine requirements. Python sources
      compile and PowerShell setup/launcher scripts parse. The full optional
      engine dependency installation was not run on the development checkout.
- [ ] Choose and add a project/engine license before granting broad public reuse;
      HIW Studio and MixFix motion package metadata currently say `UNLICENSED`.
