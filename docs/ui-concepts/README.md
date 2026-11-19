# CutLab interface concepts

**Selected: D / Spine**, product decision 2026-09-13. A / Studio and B / Bay
remain available as references for CutLab's interface.

Run from the repository root:

```powershell
python -m http.server 8790 --bind 127.0.0.1 --directory docs/ui-concepts
```

- Refined Spine: `http://127.0.0.1:8790/#D`
- Compare all four: `http://127.0.0.1:8790/#overview`
- Original comparison: `http://127.0.0.1:8790/archive/2026-09-11/index.html`

The archive contains the full original eight HTML/JS files and has no dependency
on the new Spine enhancement. A/B/C/D source files and shared core/ui/paint were
verified byte-for-byte identical to the archive after refinement. D is extended
only by `spine-enhancements.js`, loaded after the original scripts.

## Refined D

- Scenes/Media switch: thumbnail project media plus voiceover/music/SFX browsing.
- Lens: exact clip start, duration and source-in; bounds/overlap/lock validation.
- Audio: relative gain adjustment across each track's clips, mute/solo/lock.
- History: readable edits and undo/redo.

These are in-memory sample controls. Reload resets edits. Video frames are
generated illustrations; audio is not rendered. Export/effects/transitions remain
layout placeholders. The real Studio migration is tracked in
`../SPINE-IMPLEMENTATION.md` and `../../PROGRESS.md`.

## Checks (2026-09-13)

`node --test docs/ui-concepts/tests/spine.test.cjs`: 4 passing tests for timing
validation, review invalidation, atomic rejection, relative gain and history.
Browser verified: Media selection opens Lens; exact trim updates the timeline;
Music gain updates both music clips; History records both edits; two undos restore
the original project and approvals. Scenes/Lens and Media/Audio inspected visually.
