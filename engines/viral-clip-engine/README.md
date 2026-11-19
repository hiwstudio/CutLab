# Viral Clip Engine (MVP)

Turn a long video (podcast, interview, livestream, commentary, education) into
export-ready vertical short-form clips with subtitles, hooks, titles, captions,
and hashtags — for TikTok, YouTube Shorts, Instagram Reels, and Facebook Reels.

## What it does

1. Extracts audio from your video (ffmpeg)
2. Transcribes locally with faster-whisper (free, offline)
3. Finds strong moments and writes hooks/titles/captions/hashtags. The bundled
   agent launcher uses operator hand-off by default; standalone mode can use an
   LLM via OpenRouter.
4. Cuts each moment to 9:16 (1080x1920) in your chosen output style
   (see below) and burns in live subtitles plus a hook overlay
5. Writes `clips.json` + `posting-plan.txt` with everything you need to post
6. Serves a local dashboard to preview, copy text, and download clips

## Setup (once)

1. **Install Python 3.11+** and **ffmpeg**
   - Windows: `winget install Gyan.FFmpeg` then restart the terminal
2. **Install dependencies**
   ```
   cd viral-clip-engine
   pip install -r requirements.txt
   ```
3. **Optional standalone API mode:** copy `.env.example` to `.env` and set
   `OPENROUTER_API_KEY`. The CutLab launcher uses operator mode and works
   without this key.

From the CutLab repository root, the bundled launcher is the easiest way to
run it:

```powershell
scripts\engine.ps1 viral --mode clip "C:\Videos\interview.mp4"
```

## Output styles

Every mode asks which layout to use (or pass `--style`):

1. **blur** — video centered in a 50%-height band, blurred zoomed copy above and
   below (default). Tune the split with `BLUR_VIDEO_PCT` (0.5 = 25/50/25);
   portrait sources are fitted to width instead of cropped.
2. **center** — static center crop to 9:16
3. **split** — video plays in the top half, a still frame from the video fills the bottom
4. **face** — full-frame 9:16 crop that smoothly follows the main face
   (needs `pip install opencv-python`; falls back to center crop if no face is found)

Adding a style later = one function + one registry entry in `engine/styles.py`.

## Three modes

When you run the tool it asks what you want to do:

1. **Clip** — find the viral moments in a long video and cut them into shorts
   (subtitles, hooks, titles, captions, hashtags). The original feature.
2. **Reframe** — take the WHOLE video and turn it into one 9:16 portrait short:
   blurred-background style + subtitles + a caption that stays on screen the
   whole time. If the video has little/no speech, it asks you what caption to use.
3. **Cut+Reframe** — turn a long video into a short YouTube-Shorts-style edit:
   find the strongest moments (same LLM analysis as clip mode), assemble the best
   ones into a ~90-180s highlight reel, then reframe that reel to 9:16. Not a
   silence trimmer — it keeps what *matters*, not just what has sound. Tune the
   length with `REEL_MIN_SECONDS` / `REEL_MAX_SECONDS`.

## Usage

```
python run.py
```

It shows the 3-mode menu, then asks for a video link or file path.

You can also skip the prompts:

```
python run.py --mode clip        "C:\path\video.mp4"
python run.py --mode reframe      https://youtu.be/...
python run.py --mode cut-reframe  "C:\path\video.mp4"
```

First run downloads the Whisper model (~500MB for "small"). A 1-hour video
takes roughly 10–30 min to transcribe on CPU.

Then review your clips:

```
python dashboard.py
```

Open http://localhost:5000 — preview clips, copy captions/hashtags, download.

Everything is also on disk under `output/<video-name>/`:

- `clips/*.mp4` — ready-to-post vertical clips
- `clips.json` — machine-readable metadata for every clip
- `posting-plan.txt` — human-readable titles, captions, hashtags, reasons
- `transcript.json`, `moments.json` — cached intermediate steps

## Useful options

```
python run.py video.mp4 --clips 10    # keep at most 10 clips
python run.py video.mp4 --redo        # ignore cache, redo everything
```

Steps are cached: if a run fails halfway, rerun the same command and it
resumes. Transcription, analysis, silence detection, and finished renders
(clips, reframed/compacted video) are never repeated unless you pass `--redo`.

### Intelligence layer: two modes, never both

There is always exactly **one** brain deciding what to clip and caption. The
engine picks it automatically:

- **Operator mode** — when Claude Code (or another agent harness) is driving the
  system, *it* is the intelligence layer and the engine will **not** call the
  LLM API. Auto-detected via the `CLAUDECODE` env var Claude Code sets. Here the
  operator reads `output/<video-name>/transcript.json`, writes
  `output/<video-name>/moments.json` (and `caption.txt` for reframe modes), then
  re-runs to render. The engine stops with a clear instruction when the seed is
  missing.
- **Standalone mode** — when you run the system on your own, the configured LLM
  API (`LLM_MODEL` via OpenRouter) is the intelligence layer and does the
  analysis automatically.

Overrides: `AGENT_OPERATOR=1` forces operator mode, `AGENT_OPERATOR=0` forces
standalone, and prefixing `LLM_MODEL` with `~` in `.env` hard-disables the LLM
(pure seed-it-yourself workflow). The active layer is printed at the top of
every run.

Tune `config.py`: Whisper model size, LLM model, clip length limits, minimum
viral score, font/size for subtitles.

## Costs

- Transcription: free (local)
- LLM analysis: ~$0.05–0.30 per video depending on length and model

## Roadmap (v2+)

- Recap mode (see RECAP_ENGINE_DESIGN.md)
- Animated/karaoke subtitle styles
- Batch processing, queue
- Web app with upload + accounts (SaaS)
- Direct posting / scheduling integrations
