# Clipinn

Turn a YouTube video into short-form clips (Shorts / TikTok / Reels) **without
ever downloading the full video**.

The workflow is inverted vs. classic clippers:

```
Analyze (captions only) → Score & select moments → Download ONLY those
segments → Whisper each segment → Render 9:16 clips
```

A 2-hour podcast costs a few KB of caption fetches plus ~40s of video per
selected clip — not a multi-GB download and an hour of transcription.

## Quick start

```
pip install -r requirements.txt        # plus ffmpeg (winget install Gyan.FFmpeg)
python -m clipinn run https://www.youtube.com/watch?v=VIDEO
python -m clipinn status
```

Everything not given as a flag is asked interactively: output style
(blur/center/split/face), font, caption placement, subtitle placement.
Caption and subtitles each go top / middle / bottom and can never collide —
once one zone is taken it isn't offered for the other.

Non-interactive:

```
python -m clipinn run URL --style blur --font Impact --captions top --subtitles bottom --clips 8
```

## How selection works

Explainable rubric scoring (clip-scoring skill), not vibes: candidate windows
over the caption Timing Map, each scored 0–10 on hook, self-containment,
payoff, emotion, quotability, density, duration fit — weighted numerically in
`config.RUBRIC_WEIGHTS`, hard disqualifiers enforced, overlaps removed by
non-max suppression, quality bar `CLIP_QUALITY_BAR` (default 6.5).

Clips run **30s to 180s**. For every starting moment the engine generates
several candidate lengths (30/45/60/90/120/180s, clamped to the band), so a
tight 30-second cut and a 3-minute treatment of the *same* moment compete
against each other. `duration_fit` scores whether a clip **earns** its length —
padding and rambling lose points, length alone never does. Boundaries snap to
**sentence** ends, so a clip never opens or closes mid-sentence — segment ends
are not enough, because auto-caption segments break on timing, not syntax. A
window may also open on a `>>` speaker turn. Transcripts with no punctuation
at all fall back to raw segment boundaries (logged when it happens).

**Adaptive visual analysis**: the scorer flags candidates it can't judge from
words alone (`needs_visual`) — reactions, physical comedy, "look at this"
moments. Only those clips get a cheap 360p sample + a few extracted frames
and a vision review that confirms, rescores, or rejects them. Straightforward
videos never touch this path.

Two intelligence layers, exactly one active:

- **Operator mode** (enabled by CutLab's engine launcher, and default under
  supported agent harnesses): the run pauses and writes
  `projects/<name>/select_task.json`; the operator scores candidates and
  writes `moments.json`, then reruns. Zero LLM API calls.
- **Standalone**: set `OPENROUTER_API_KEY` in `.env` and the engine scores
  candidates itself via the rubric prompt.

## Project layout (per run)

```
projects/<name>/
  info.json          video metadata
  timing_map.json    canonical ms Timing Map (captions or whisper)
  select_task.json   operator task (operator mode)
  moments.json       selected clips with subscores + rationale
  segments/          the ONLY video ever downloaded (one small file per clip)
  clips/             final 9:16 mp4s (+ per-clip word maps)
  clips.json         full metadata: scores, hooks, titles, captions, hashtags
  posting-plan.txt   human-readable plan
```

State lives in `clipinn.db` (SQLite, pipeline-state schema: runs / stages /
assets / events). Every stage is idempotent — rerun the same command after
any crash or pause and done work is never redone.

## Config

Env vars (or `.env`): `CLIP_MIN_SECONDS`/`CLIP_MAX_SECONDS` (15/58),
`CLIP_QUALITY_BAR`, `MAX_CLIPS`, `DL_MAX_RES`, `WHISPER_MODEL`,
`SUB_STYLE` (word|phrase), `STYLE`, `LLM_CONCURRENCY` (8 — candidates are
scored in parallel; they're independent by design).

`YT_BROWSER` defaults to **firefox**. Set it to a browser available on your
system if Firefox is not configured. Downloading is a direct port of MixFix
Engine's `YtDlpSource`: one cookie source, no
`--extractor-args`, no `--ffmpeg-location`, and a format selector that prefers
H.264 with no bare `/b` fallback. Every one of those is load-bearing — read
[`lessons/ytdlp-download-port-2026-07.md`](lessons/ytdlp-download-port-2026-07.md)
before changing any of it, and `tests/test_smoke.py` guards the contract. A
`cookies.txt` in this folder takes precedence if present.

### FFmpeg and downloads

Clipinn uses yt-dlp for selected source ranges and its own FFmpeg path for
rendering. The download selector is constrained to video-plus-audio formats,
and every downloaded segment is probed before use because yt-dlp can report
success when a stream is incomplete. Avoid forcing a separate `--ffmpeg-location`
for downloads unless a tested platform-specific issue requires it. Set
`FFMPEG_BIN` if Clipinn's renderer needs an explicit FFmpeg binary.

## Future

The pipeline is a plain Python API (`clipinn.pipeline.run`) over a SQLite
state DB — a web dashboard can drive it exactly like the CLI does.
