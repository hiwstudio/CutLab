# MixFix

MixFix is a resumable production engine for narrated films and video overlays.
Its outputs can be reviewed in MixFix, then MIX and FIX projects can be opened
as editable CutLab timelines.

## Modes

- **MIX** builds a narrated film from a topic, voiceover, timing map, scene
  plan, sourced or generated visuals, review, render, and quality checks.
- **FIX** adds visual overlays to an existing video while keeping the original
  audio intact.
- **SPLIT** creates a split-screen short. It is included as a standalone
  workflow; direct CutLab import currently covers MIX and FIX.

## Run

    scripts\engine.ps1 mixfix run --mode mix --project my-first-film
    scripts\engine.ps1 mixfix run --mode fix --project my-existing-video
    scripts\engine.ps1 mixfix status

MixFix runs in operator mode by default. It writes requests for an agent or
human to complete and resumes from saved stages. To create a MIX project, add
projects/<name>/input/topic.json with a topic string. The voiceover stage
will request a finished voice file. For FIX, place a source video at
projects/<name>/input/source.mp4.

Review the result in the MixFix board before importing it. Keep project names
simple (letters, digits, dot, underscore, hyphen). The CLI and local review
board use project data under this engine folder.

## CutLab connection

CutLab discovers projects under engines/mixfix/projects by default. The
home screen's **Bring in an engine project** action imports MIX or FIX to a
durable CutLab job. Imported video, narration, captions, scene ranges, and
source identity become editable EDL data.

Set CUTLAB_MIXFIX_ROOT if you keep a separate MixFix checkout. For details,
see [CUTLAB.md](CUTLAB.md) and [the engine integration guide](../../docs/ENGINE-INTEGRATION.md).

## Optional settings

- Set MIXFIX_IMAGE_TOOL to an image-generation tool that accepts the
  MixFix prompt contract. Leave it blank to keep image generation as an
  explicit operator hand-off.
- Set MIXFIX_GRID_ROOT only if you have the separate GRID canvas installed.
- Keep ANTHROPIC_API_KEY or another configured key in an ignored .env
  file. Manual operator mode does not require an API key.

FFmpeg and ffprobe must be available on PATH. Transcription downloads the
selected faster-whisper model on first use.

## Developer checks

    python -m pytest tests
    python -m pytest split\tests

The bundled MixFix source includes the engine code and tests. It does not
include private production projects, project databases, downloaded footage,
or generated media.
