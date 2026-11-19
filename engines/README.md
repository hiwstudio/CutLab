# CutLab engine pack

CutLab is the shared editing and review workspace. This folder contains the
production engines that create or prepare footage, plus the CutLab adapter that
opens MixFix MIX/FIX projects as editable timelines.

## Included engines

| Engine | Best for | Start here |
|---|---|---|
| MixFix | Narrated films (MIX), video overlays (FIX), and split layouts | [mixfix/README.md](mixfix/README.md) |
| Clipinn | Transcript-led short clips without downloading the full source | [clipinn/README.md](clipinn/README.md) |
| Viral Clip Engine | Moment selection, reframing, subtitles, hooks, and short-form exports | [viral-clip-engine/README.md](viral-clip-engine/README.md) |
| Recap Engine | Narrated story recaps from long-form footage | [recap-engine/README.md](recap-engine/README.md) |
| HIW Studio | Deterministic Remotion animation from scene manifests | [hiw-studio/README.md](hiw-studio/README.md) |

CutLab also has its own AI director, timeline editor, compaction workflow, and
recap workflow. Use an engine that fits the story, then bring its output into
CutLab for scene-level review and editing.

## First run

From the CutLab repository root:

```powershell
scripts\setup.ps1
scripts\dev.ps1
```

Then open `http://localhost:3000`. The first setup installs the CutLab app and
the bundled engines' dependencies. Whisper models download the first time a
transcription workflow needs them. Install FFmpeg before setup; Windows users
can use `winget install Gyan.FFmpeg` and reopen the terminal.

Run a bundled engine through the launcher, which selects the shared engine
environment and sets the correct working directory:

```powershell
scripts\engine.ps1 mixfix run --mode mix --project my-first-film
scripts\engine.ps1 clipinn run "https://www.youtube.com/watch?v=VIDEO_ID" --style blur
scripts\engine.ps1 viral --mode clip "C:\Videos\interview.mp4"
scripts\engine.ps1 recap "C:\Videos\documentary.mp4"
scripts\engine.ps1 hiw create-project "Why We Procrastinate"
```

Each engine keeps its own resumable state and output under its folder. These
runtime paths are ignored by Git. When you have a rendered output, create a
CutLab project and use **Media Library → Import media** to add it to the
timeline. MixFix MIX/FIX projects can also be opened directly from the CutLab
home screen, preserving their scene layout and source provenance.

## Local settings and privacy

- Put API keys in the engine's ignored `.env` file or the environment. Never
  commit a real key.
- Use `CUTLAB_MIXFIX_ROOT` only when MixFix lives outside this bundle.
- User projects, source videos, databases, model files, downloaded segments,
  logs, and renders do not ship with this source package.
- `engines/segment_core.py` is shared by MixFix and Clipinn for source range
  validation and download integrity.

See [the getting-started guide](../docs/GETTING-STARTED.md) for installation,
agent setup, supported workflows, and troubleshooting.
