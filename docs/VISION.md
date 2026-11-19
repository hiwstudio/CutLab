# CutLab — product direction (September 2026)

Written after pausing the build to reset the interface direction. `docs/HANDOFF.md`
stays the engine spec; this document says what the product must become and in what
order.

## What CutLab is

A real, AI-native video editor — CapCut's usability with Premiere's capability. Open a
project, watch it, inspect its scenes and elements, and edit it directly: video/audio
tracks, cut/trim/split/delete/move/reorder, clip duration, multiple layers, volume and
mute, real-time preview, undo/redo, basic transitions and effects, text/captions, and
AI-assisted editing. It must read as a professional editing application, not a dashboard
with buttons added.

## Where it sits: the editing layer for every engine

```
Video engines (MixFix, Clipinn, Viral Clip, Recap Engine, HIW Studio, …)
        ↓  generated project (scenes, footage, voiceover, captions, audio)
      CutLab  —  review → edit → refine → approve → export
        ↓
    final video
```

Engines generate; CutLab is the shared editing surface. Each engine may keep
the production gates its workflow depends on; CutLab owns the final timeline
review and export.

## Build order (strict)

1. Redesign CutLab — **D / Spine selected on 2026-09-13**; implement with useful
   controls from A and B (see `DESIGN-SPEC.md`).
2. Make the editing experience polished.
3. Implement the core editing interactions.
4. Make the AI editing interface work properly.
5. Make CutLab open generated projects (engine → CutLab import contract).
6. Connect MixFix and the other engines through a stable import contract.

**The MixFix Review dashboard stays exactly as it is until step 6.**

## Engine pack status — 2026-11-19

CutLab packages the production engines. MixFix MIX/FIX projects have a direct
scene-linked import. Clipinn, Viral Clip,
Recap Engine, and HIW Studio are bundled and run through the engine launcher;
their rendered media enters CutLab through normal asset ingest. Source
manifest import for those engines remains a separate follow-up adapter.

The home screen introduces the editor and its bundled workflows. The selected
Spine layout remains in place, with direct MixFix import and an engine library
that explains each workflow.

## Interface principles

### Approved direction — 2026-09-13

Spine is CutLab's selected editing workspace: its scene-based arrangement
supports the production engine workflow. Preserve that arrangement and borrow
A's visual media drawer plus B's precise properties, compact audio controls,
and history. Original concepts: `docs/ui-concepts/archive/2026-09-11/`.
Implementation sequence: `docs/SPINE-IMPLEMENTATION.md`.

Clean, sharp, modern, premium, minimal, professional, easy to understand, well organized,
visually balanced, fast to navigate. Every panel, button, control and piece of information
has a clear purpose — otherwise it goes.

- **Timeline is a real timeline:** select, drag, trim, split, delete, rearrange, zoom,
  playhead, multiple layers, audio tracks visible.
- **Audio has real controls:** volume, mute, levels, track selection, waveforms,
  voiceover / music / SFX separated.
- **Scenes are first-class.** Selecting a scene shows immediately what it contains, how
  long it is, its footage, audio, voiceover, captions, and where it sits on the timeline.
- **AI is part of the editor, not a chatbot beside it.** Compact and purposeful; it
  proposes edits the user applies or dismisses (already the engine's model:
  proposed revisions → accept/reject).

## Process

Explore → compare → choose → build → polish. Concepts live in `docs/ui-concepts/`
(open `index.html` via the `ui-concepts` launch config). They are interactive
prototypes on one shared sample project, so they compare feel, not screenshots.

## Engine gaps any chosen direction will need

Found while designing the concepts (verified against `apps/server` on 2026-09-11):

- The EDL has **no scene entity** — scenes exist only inside per-asset understanding
  artifacts. Scene-based review needs `scenes[]` in the EDL (id, title, range, status,
  source metadata) plus ops to move/approve scenes.
- Tracks carry only `id/kind/clips` — no name, mute, solo, lock or volume.
- `reorder`, `fade`, `add_transition`, `duck` and `apply_effect` still return
  `E_NOT_IMPLEMENTED`.
- No import endpoint for an engine-generated project (step 5).
