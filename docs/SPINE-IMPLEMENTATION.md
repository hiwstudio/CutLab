# Spine — implementation handoff

D / Spine is CutLab's selected editor layout. A/B remain preserved as
alternative interface concepts in docs/ui-concepts/archive/2026-09-11.
Follow DESIGN-SPEC.md and docs/HANDOFF.md. No further design selection is needed.

## Implemented in the real editor — 2026-09-13

Studio now uses Scenes/Media at left, the compositor in the center,
Lens/Audio/History at right, and Director/proposals above the timeline.
Existing uploads, understanding, jobs, keyboard edits, proposals, exact preview
and final renders remain connected. A/B originals and their archive are unchanged.

### Existing systems retained

- Editor.tsx / useEditor.ts: API calls, revision handling, jobs and selection.
- Preview.tsx: live compositor, exact segment preview and final render status.
- Timeline.tsx / WaveStrip.tsx: move/trim, thumbnails and real waveform strips.
- MediaLibrary.tsx: upload, ingest and analysis in the Media tab.
- DirectorPanel.tsx / ProposalReview.tsx: real backend/manual fallback and review.
- RevisionStrip.tsx: read-only historical inspection in the History tab.
- EDL schema/ops/engine: the same database and transactional revision engine.

### Scene contracts

Scenes are explicit, non-overlapping timeline ranges saved in EDL revisions.
Legacy projects load with no scenes; Scenes → Create scenes from video cuts is
an explicit starting point, not automatic story detection. Ordinary clip edits
retain scene boundaries, including intentional gaps. An all-track ripple range
delete maps scene boundaries through the deletion.

Reordering requires adjacent scene ranges and partitions crossing clips/captions
so their portions move together. Tracks marked Music retain absolute placement.
A locked track prevents operations that would change it, including scene moves.

Approval is saved in normal history. Contributing clip/asset changes, timing,
canvas, audio settings or title edits reset affected scene approvals. Undo restores
both content and review state. Approval is a human review flag, not a render gate.

### Mixer and preview contracts

Track gain is a true offset added to clip gain. Mute removes visuals/captions and
audio from preview and export. Solo affects media audio only, retaining other
visible video layers. Browser playback uses separate media elements and Web Audio
gain nodes; exact previews and final files continue to use the FFmpeg planner.
There are no synthetic live meters. L0 remains an approximate compositor for
effects; use exact preview/final render to judge supported output effects.

### Editing and Director

Lens saves timing atomically and edits captions, clip gain and scene titles.
History viewing guards edits and stays stable during background job refreshes.
The Director brief includes scene ranges/names and track mix/lock settings. It
still proposes changes for explicit acceptance. Timeline has a scene band and
fit control; preview has frame stepping and preserves the canvas aspect ratio.

## Verification

- Existing 205 fast server tests pass. Six new Spine tests cover review/undo,
  crossing-layer reorder, locked transactions, timing bounds, export mixing and
  legacy compatibility. Director tests pass after context changes.
- Browser checks cover upload/edit/undo/render, compositor/segment preview,
  analysis, command palette and proposal review. The new Spine workflow checks
  rename/reorder, review invalidation, mix/playback, locks, history and persistence.
- Populated views inspected at 1440×900 and 1100×760, with no horizontal overflow.
- TypeScript and lint pass for the changed editor/preview/state hook/Spine panels.
- Browser tests explicitly force the manual Director in isolated test data.

## D fidelity and engine import demonstration (2026-09-13)

The live editor now uses the approved prototype's bundled typefaces and its
actual layout proportions instead of an approximation: a 50px header, compact
54px story rows, 640px preview stack, segmented story scrubber, centred playback
controls, narrative-first Lens and compact role-coloured timeline. Responsive
rules retain the same hierarchy in the narrower in-app browser.

`scripts/import_mixfix_demo.py` demonstrates the generated-project boundary
with user-supplied inputs. It reads a MixFix project and a licensed music file
without changing source or approval state, prepares an excerpt, ingests each
asset through CutLab's durable job API, and commits scenes, footage, narration,
timed captions and music as normal EDL operations. The script records a reminder
to verify and document the licenses of supplied media. No demo project or music
is included in the repository.

## Next work

Refine scene range-authoring and selected-scene/clip Director command scoping.
Then turn the demonstrated resumable import into the validated durable contract
for generated scenes, media, narration, captions and audio. Keep MixFix Review
unchanged. Transitions,
effects and other later-phase operations remain subject to actual backend support;
prototype placeholders do not imply implemented capabilities.
