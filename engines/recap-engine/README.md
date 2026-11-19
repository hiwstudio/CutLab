# Recap Engine

Recap Engine turns long-form footage into a narrated story recap. It downloads
or reads the source, transcribes it, detects scenes, builds a story outline,
matches beats to footage, creates narration, validates coverage, and assembles
an MP4. Cached stages let a run resume after a pause or failure.

## Run

    scripts\engine.ps1 recap "C:\Videos\documentary.mp4"
    scripts\engine.ps1 recap "C:\Videos\documentary.mp4" --minutes 7

The default agent mode is **manual**: the engine writes prompts into its output
folder, and the agent supplies the response files before resuming. It does not
need an LLM key. Set LLM_BACKEND=openrouter only for standalone automatic
analysis and provide OPENROUTER_API_KEY in a local .env.

Recap rendering needs narration. The default Piper backend needs the `piper-tts`
package and a licensed `.onnx` voice model with its matching `.onnx.json` file.
Install it into CutLab's shared engine environment with
`engines/.venv/Scripts/python -m pip install piper-tts` on Windows or
`engines/.venv/bin/python -m pip install piper-tts` on macOS/Linux. Place the
voice files under `engines/recap-engine/voices/` and set `PIPER_VOICE` in a
local `.env`. Fish Audio is optional and requires a key. Keep remote voice
generation off unless the user explicitly asks for a connected provider.

The rendered output and cached stages are under output/<source-name>/.
Import recap.mp4 into a CutLab project through **Media Library → Import
media** to trim scenes, adjust audio, or add titles.

## Data and source boundaries

The bundled package contains engine code and its dependencies, not source
videos, model weights, API keys, voice models, or prior production outputs.
Project files and renders are ignored by Git.
