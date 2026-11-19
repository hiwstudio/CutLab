# CutLab

CutLab is a local video editing workspace for creating, reviewing, and finishing
edits from several production engines. It combines a scene based timeline, media
library, preview, revisions, undo and redo, and an AI director that proposes
editable changes.

## What you can do

- Create a timeline and edit video, audio, images, captions, and text.
- Use CutLab's built in compaction and recap workflows.
- Bring MixFix MIX/FIX projects into CutLab with their scene timing and source
  history preserved.
- Run Clipinn, Viral Clip Engine, Recap Engine, and HIW Studio from the bundled
  engine pack, then bring their rendered media into the CutLab timeline.
- Add your own effects, workflows, profiles, and engine adapters.

CutLab runs on your computer. Source files, project databases, model downloads,
and renders stay local unless you choose a remote AI backend or external media
source.

## Quick start

Requirements: Git, Python 3.11+, Node.js 20+, npm, and FFmpeg with `ffprobe`.
On Windows, install FFmpeg with `winget install Gyan.FFmpeg` and reopen the
terminal.

```powershell
git clone <repository-url>
cd CutLab
scripts\setup.ps1
scripts\dev.ps1
```

Open `http://localhost:3000`. The first setup installs the CutLab app and the
bundled Python and Remotion engine dependencies. Transcription models download
the first time you use them.

On macOS or Linux, use `bash scripts/setup.sh` and `bash scripts/dev.sh`.

## Start with the editor

1. Choose **New project** and give it a name.
2. Select a landscape, vertical, HD, or 4K canvas.
3. In the editor, open **Media Library → Upload**, choose a video, audio file,
   or image, then add it to the timeline.
4. Drag clips to arrange them. Use the preview, inspector, and revision history
   to shape and review the edit.
5. Export from the project toolbar when the cut is ready.

The home screen also lets you open a MixFix MIX/FIX project directly. For any
other engine, use the engine launcher below, then import its output through the
Media Library.

## Run a production engine

After setup, run the desired workflow from the repository root:

```powershell
scripts\engine.ps1 mixfix run --mode mix --project my-film
scripts\engine.ps1 clipinn run "https://www.youtube.com/watch?v=VIDEO_ID" --style blur
scripts\engine.ps1 viral --mode clip "C:\Videos\interview.mp4"
scripts\engine.ps1 recap "C:\Videos\documentary.mp4"
scripts\engine.ps1 hiw create-project "Why We Procrastinate"
```

The Linux/macOS launcher is `bash scripts/engine.sh <engine> <arguments...>`.
The [engine guide](engines/README.md) explains each workflow and how to bring
its result into CutLab. Each engine can also be used directly from its folder.

## AI and API keys

The default agent workflows use operator/manual mode and do not need an API
key. Optional API keys belong in a local, ignored `.env` file for the engine
that uses them. Never put a real key in source control. See
[`apps/server/.env.example`](apps/server/.env.example) and each engine's
`.env.example` for variable names.

## Agent support

Start with [`AGENTS.md`](AGENTS.md), then follow the engine-specific guide in
[`engines/README.md`](engines/README.md). Agents can operate the same engine
CLIs, inspect task files, and use CutLab's API and editor. The EDL remains the
source of truth for edits; engines produce source media and CutLab owns the
reviewed timeline.

## More documentation

- [Getting started and troubleshooting](docs/GETTING-STARTED.md)
- [Engine connections and current support](docs/ENGINE-INTEGRATION.md)
- [Architecture and build contract](docs/HANDOFF.md)
- [Progress checklist](PROGRESS.md)
- [Product direction](docs/VISION.md)
- [Design decisions](DECISIONS.md)
- [Known production fixes](LESSONS.md)

## License

CutLab and its bundled, project-authored engine code are licensed under the MIT
License; see [LICENSE](LICENSE). Third-party dependencies and assets retain their
own license terms. The bundled font files include their respective OFL notices.

## Development

```powershell
cd apps\server
.venv\Scripts\python -m pytest -m "not slow"
cd ..\studio
npm run build
npx playwright test
```

The full server suite includes slower FFmpeg media checks. See
[`AGENTS.md`](AGENTS.md) for architecture and machine-independent development
rules.
