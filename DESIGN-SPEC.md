# CutLab Studio — Project Design Spec

Per the UI-library decision engine (file 15). All Studio UI work follows this.

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
