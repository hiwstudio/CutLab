# CutLab — Spine design specification

Owner-approved direction, 2026-09-13. **D / Spine** is selected for the personal
CutLab workspace. This supersedes the July S2/violet specification below.
The owner authorized borrowing useful controls from A and B while preserving
those separate concepts for a possible future public editor.

## Approved product and arrangement

CutLab is the owner's daily review and editing workspace for scene-based video
projects. Personality: **clear, precise, composed**. D's arrangement resonates
with the owner's operating system and existing engine workflow.

1. Header: project/source, real review progress and saved revision, undo/redo,
   export. Production status must reflect actual saved data and jobs.
2. Left rail: Scenes by default, Media on demand. Scene number, title, duration,
   layer presence and approval remain visible. Media replaces the rail contents
   temporarily rather than adding another permanent panel.
3. Center: large preview, current scene, segmented scrubber, transport and
   previous/next scene and frame stepping.
4. Right: contextual Lens; Audio, Director and History available as tabs.
   A scene exposes its narration and layers; a clip exposes exact properties.
5. Bottom: multitrack timeline, scene band, track headers, waveforms/thumbnails,
   visible editing tools, zoom/fit and the compact AI command line. Proposed
   changes appear in context and require explicit accept/dismiss.

## Approved visual system

| Role | Value |
|---|---|
| Background | Warm charcoal `#0F0F0E` |
| Panel / raised / hover | `#161614` / `#1F1F1C` / `#292925` |
| Text / secondary / quiet | `#EDEBE5` / `#9C998F` / `#65635C` |
| Border | `rgba(255,248,230,.07)` |
| Selection, playhead, primary action | Amber `#FFB547`, dark ink `#1D1405` |
| AI / approval | Lavender `#A79BFF` / green `#7FD6A4` |
| Body | Hanken Grotesk, system sans-serif fallback |
| Wordmark and scene numbers | Bricolage Grotesque, system sans-serif fallback |
| Timecode / numerical controls | JetBrains Mono, Consolas, monospace |
| Density / shape | Compact 12–14px body; 6–8px control radii, quiet borders |

Use one SVG icon family, visible focus and labeled controls. Approval is conveyed
with text/icon as well as color. Respect reduced motion. Production must remain
usable with local fonts/system fallbacks when offline. The 1440×860 prototype is
a visual reference, not a required viewport: resize panes, contain timeline width,
and collapse secondary panels when needed rather than scaling the entire real app.

## Useful additions from A and B

| Source | Adopt | Purpose |
|---|---|---|
| A / Studio | Thumbnail media browser, short labels, one drawer at a time | Fast browsing without losing scene structure |
| A / Studio | Discoverable split/delete, trim handles, zoom and fit | Make common edits easy to find |
| B / Bay | Exact start/source-in/duration fields in Lens | Precise editing without relying on dragging |
| B / Bay | Compact Audio tab, separate voice/music/SFX, mute/solo/lock | Control the mix without a permanent mixer panel |
| B / Bay | Edit history and explicit revision | Confidence while experimenting |

Do not transplant B's dense panel layout into D. Live meters must eventually show
measured audio; the animated sample meters in B are not a production feature.

## Preservation and integration

A and B stay intact for a possible later public video editor. The entire original
comparison is frozen in `docs/ui-concepts/archive/2026-09-11/`. Current A/B/C are
unchanged; D's added behavior lives in `docs/ui-concepts/spine-enhancements.js`.

All real changes must use the existing EDL, operations, revisions and durable
jobs. Scene moves must keep linked layers synchronized; continuous music needs
an explicit policy. Changed scenes require review again; undo restores review
state. Validate timing against bounds, speed and overlaps. Track locks must be
enforced server-side; mute/solo/gain must agree in preview and final renders.
The real Director keeps its propose/accept model and its pluggable backend.

The comparison remains a sample prototype. The first live Studio migration is
implemented; `docs/SPINE-IMPLEMENTATION.md` records its contracts, checks and
remaining range-authoring/import work. The design choice is
approved; another direction-selection confirmation is not required.

## Superseded July specification — historical reference only

```
Product: CutLab Studio      Category: dev-grade creator tool (daily-driver editor)
Style: S2 Dark Hi-Tech (upgrade of existing zinc-dark, not a replacement)
Accent: electric violet #7C6AEF (ramp via color-mix); semantic greens/reds unchanged
Neutrals: cool near-black ramp — bg #0A0A0B / surface #141416 / elevated #1C1C1F
Fonts: heading+body Inter (system fallback) / mono JetBrains Mono, Consolas (timecodes, ids)
Radius: soft (8px surfaces, 6px controls)   Density: compact (editor = information-dense tool)
Motion personality: precise, spring-less, 150–250ms, ease-out in / faster out;
                    respects prefers-reduced-motion
Shell layout: three-pane editor (library | preview | director+revisions) over timeline —
              canonical "workbench" layout from file 03
Voice (3 adjectives): precise, calm, capable
Reference structure: Linear (shell + ⌘K)   Reference surface: S2 recipe tokens
Reference motion: Raycast (instant, exact)
```

Rules in force (core doctrine): tokens only — no hardcoded colors/durations in
components; accent used surgically (primary action + focus + selection);
depth = surface lightening + 1px inside borders, not shadows; every async
action acknowledged <100ms (optimistic apply already does this); all
interactive elements get focus-visible rings and 44px-equivalent hit areas
where touch matters; one icon set (inline SVG/unicode, no mixed packs).
