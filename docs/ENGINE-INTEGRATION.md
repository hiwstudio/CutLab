# Production engine connections

Reusable engine source lives under `engines/`; project data, API keys, source
media, databases, model weights, and renders remain local and Git-ignored.
Existing engine pipeline logic remains the reference implementation; CutLab
owns editing and revision review.

The engine launcher runs MixFix, Clipinn, Viral Clip Engine, Recap Engine, and
HIW Studio from the bundled source. MixFix MIX/FIX has a direct project
adapter. Other engines currently import their rendered output through CutLab's
normal media-ingest flow.

## Working milestone

- Home → Bring in an engine project → select MixFix project and MIX/FIX mode →
  Open in CutLab. Uses the selected canvas. Opens the editor after the durable
  job finishes assembling a complete timeline, not after copying the first file.
- MIX imports the full narrated film with separate footage, narration, and
  caption tracks and explicit scene ranges. Gaps between spoken scenes are
  covered to the next boundary, matching MixFix assembly.
- FIX imports the full original video/audio plus bounded visual replacements;
  gaps retain the original video. Original audio is editable on its own track.
- Media is copied into CutLab, content-addressed, and ingested through the
  existing probe/proxy/waveform/thumbnail pipeline. Engine source files are not
  modified. Unsupported modes and missing visuals fail before creating a project.
- Short sources use MixFix's own last-frame hold renderer. Encodes include a
  guard frame, because millisecond endpoints can round down at 30 fps. CutLab
  still keeps the intended exact scene duration in its EDL.
- Engines inspector shows source identity, visual intent, provenance and
  alternative count. Move the playhead into a scene to select its connection.
- Prepare scene update ingests the latest source visual, then creates a
  **proposal**, preserving the clip's timeline position, duration, speed, gain,
  transform, opacity, effects and other scene layers. It never commits the new
  picture automatically. Preview, then Accept/Reject via the existing review UI.
- Source metadata belongs to the proposed revision. Undo restores the old
  provenance as well as the old picture. Concurrent editor/worker changes use a
  transactional head check; a selected clip changed during preparation fails
  instead of overwriting it. Frozen clips require unfreezing before replacement.
- Prepare regeneration request saves a durable downloadable operator handoff
  with source scene, instructions and MixFix's `regen` review flag. Status is
  **awaiting operator**. It does not run generation or approve a MixFix gate.
  Complete the scene in the existing engine, then Prepare scene update.

## Contract

`CUTLAB_MIXFIX_ROOT` overrides the installed engine directory. Discovery reads
`projects/*/timeline/timeline.json`. MIX also needs `voiceover/voice.mp3`;
FIX needs `input/source.mp4`. Both read `timing/timing_map.json` for word times.
The adapter normalizes scene slots, validates source paths/coverage, and saves
the full source snapshot, provenance and alternatives under the CutLab
project's `integration/` directory. `project.engine_source` references the
revision's link artifact. Scene-to-clip IDs are deterministic for resume.

HTTP endpoints:

- `GET /api/v1/engines/mixfix/projects`
- `POST /api/v1/engines/mixfix/import` (`source_project`, `mode`, `canvas`)
- `GET /api/v1/projects/{id}/engine-link` (optional `rev`)
- `POST /api/v1/projects/{id}/engine-scenes/{scene}/refresh` (`base_rev`)
- `POST /api/v1/projects/{id}/engine-scenes/{scene}/request` (`base_rev`, `note`)
- `GET /api/v1/projects/{id}/engine-requests/{job}` (completed handoff download)

Durable job kinds: `engine_import`, `engine_refresh`, `engine_request`. Available
in both embedded and standalone workers. Existing job status/cancel APIs apply.

## Explicit limits and subsequent milestones

MIX imports use hard cuts: MixFix crossfades are not translated yet. Caption
word timing/text is retained, but engine-specific typography is not translated.
Visual replacement does not resynchronize changed narration, scene layout, or
captions; those require a separate whole-project reconciliation adapter. It
updates the surviving imported clip ID; independently created/split clips stay
as edited. Alternative metadata is retained; selecting engine candidates from
CutLab is not implemented. Regeneration requests are files awaiting operator
execution, not automatic dispatch to engine review or remote generation.

The other bundled engines are standalone producers today: CutLab imports their
rendered media, but does not map their source manifests into scene-linked EDLs.
Potential follow-up adapters could preserve Clipinn candidate provenance, Viral
Clip segment choices, Recap beat/source links, and HIW scene ranges. MixFix
SPLIT/ASSEMBLY import, automatic operator-task dispatch, crossfade/animation
translation, and conflict-aware two-way synchronization are also open.

## Verification

`tests/test_engine_integration.py` covers full MIX/FIX ingest, source trace,
resume, scene-update proposal isolation, retained opacity/transform, accepted
provenance and undo, handoff persistence without source writes, malformed source
rejection, worker/editor concurrency and real MixFix held-frame rounding.
