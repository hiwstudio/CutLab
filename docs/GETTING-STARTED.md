# Getting started with CutLab

## Install

Install Git, Python 3.11+, Node.js 20+, npm, and FFmpeg (`ffmpeg` and
`ffprobe` must both run from a terminal). Windows users can install FFmpeg
with `winget install Gyan.FFmpeg`, then open a new terminal.

From the repository root:

```powershell
scripts\setup.ps1
scripts\dev.ps1
```

Open `http://localhost:3000`. The server listens on `127.0.0.1:8787`. To skip
heavy production-engine Python dependencies, use `scripts\setup.ps1 -CoreOnly`;
rerun setup without that option when you want the bundled Python engines.

For macOS or Linux, use:

```bash
bash scripts/setup.sh
bash scripts/dev.sh
```

The setup checks prerequisites and reports what is missing. It does not install
system packages or request admin privileges.

## Make an edit

Choose **New project**, name it, and select the target canvas. In the editor,
open **Media Library → Upload** to add video, audio, or image files. Add media
to the timeline, arrange scenes, and inspect the result in Preview. Edits are
versioned, so you can undo or return to a previous revision.

## Use a production engine

The included engines cover different jobs:

- **MixFix** makes narrated films and video overlays. MIX/FIX imports become
  separate editable CutLab tracks with scene provenance.
- **Clipinn** selects spoken moments from captions and downloads selected
  ranges only.
- **Viral Clip Engine** finds and reframes clips, then adds subtitles and
  hook overlays.
- **Recap Engine** makes a narrated story recap from long-form footage.
- **HIW Studio** creates deterministic animated videos from scene manifests.

Run an engine with `scripts/engine.ps1` (Windows) or `scripts/engine.sh`
(macOS/Linux). Each engine README gives the mode-specific steps. After an
engine renders, create or open a CutLab project, upload the MP4 through the
Media Library, and continue editing.

MixFix's direct CutLab import supports MIX and FIX. Its separate SPLIT workflow
is included as a standalone engine; split project import and automatic
cross-engine synchronization remain future adapters.

## Agent workflows

Agents should use operator/manual mode so they do the selection and reasoning
work themselves without sending content to an LLM service. Clipinn and Viral
Clip Engine are launched in operator mode by the engine launcher. MixFix uses
its operator brain by default. Recap uses its manual handoff. HIW Studio has no
AI calls in its render pipeline.

An agent should:

1. Read the root `AGENTS.md` and the chosen engine's README.
2. Start or resume the engine with the launcher.
3. Fulfill its task files and review gates as described by that engine.
4. Import the final output into CutLab for timeline edits and export.

## Optional services and local files

- API keys are optional. Store them in ignored `.env` files or environment
  variables; keep the `.env.example` files blank.
- Whisper models download on first transcription and are cached locally.
- MixFix may need browser cookies for YouTube media access. Configure the
  browser supported by your system; do not copy browser databases into the
  repository.
- The optional still-image cutout model can be placed at
  `data/models/u2netp.onnx` or selected with `CUTLAB_CUTOUT_MODEL`.
- Text to Sound uses Fish Audio when configured; otherwise it needs `piper-tts`
  and a licensed Piper voice model at `data/voices/en_US-lessac-medium.onnx`
  (or the path in `CUTLAB_PIPER_VOICE`).
- Add your own licensed music, voiceover, and sound effects. The repository
  contains no source projects or generated media.

## Project data and Git

Project databases and media are under `data/`. Engine-specific runtime state,
source downloads, and renders live in their engine folders and are ignored by
Git. Only source code, documentation, tests, and safe examples belong in a
public commit.

## Troubleshooting

- **CutLab reports missing FFmpeg:** confirm `ffmpeg -version` and
  `ffprobe -version` work in a new shell.
- **The Studio cannot reach the server:** start both processes with
  `scripts/dev.ps1` or `scripts/dev.sh`; keep ports 3000 and 8787 free.
- **An engine says dependencies are missing:** rerun the full setup script,
  without `-CoreOnly`.
- **A source is not found by MixFix import:** use the bundled path
  `engines/mixfix/projects`, or set `CUTLAB_MIXFIX_ROOT` to another MixFix
  installation.
- **A YouTube download fails:** confirm the source is available to your
  browser session and that `yt-dlp`, FFmpeg, and browser-cookie settings match
  the selected engine's README.
