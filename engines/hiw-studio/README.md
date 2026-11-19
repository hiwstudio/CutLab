# HIW Studio engine

This is the reusable source for the deterministic React/SVG animation engine.
It turns a scene manifest into a repeatable Remotion render. It does not make
video with an AI generator and it does not include episode projects, voiceovers,
music, sound effects, generated footage, or finished renders.

## Install and create a project

Run the CutLab setup once from the repository root, then:

```powershell
scripts\engine.ps1 hiw create-project "Why We Procrastinate"
```

Create or edit the generated `manifest.json`, add your own media, then validate
and render:

```powershell
scripts\engine.ps1 hiw validate .\projects\why-we-procrastinate\manifest.json
scripts\engine.ps1 hiw render --quality draft .\projects\why-we-procrastinate\manifest.json
scripts\engine.ps1 hiw render --quality final .\projects\why-we-procrastinate\manifest.json
```

The engine expects Node.js 18+ and downloads Chromium through Remotion on its
first render. Audio is optional; add voiceover and any properly licensed music
or sound effects to your project. Bring the finished MP4 into CutLab through
**Media Library → Import media** for further timeline edits.

## Engine contract

The scene manifest is the interface. The CLI validates the manifest before
rendering, and the same manifest produces the same animation. Read
`src/engine/manifest/schema.ts` for the schema and `src/cli/index.ts` for the
available commands.

The original HIW channel's episode files, image style library, voiceovers,
music, sound effects, and generated scene assets are intentionally absent.
Bring your own media and adapt the engine's registered components for your
own projects.
