# Clipinn download contract

Clipinn's selected-range downloader shares the tested approach in MixFix's
`YtDlpSource`. Keep these behaviors aligned with `tests/test_smoke.py`:

- Use one configured browser-cookie source when authentication is needed.
- Avoid extractor overrides that can return unsupported or incomplete formats.
- Constrain format fallbacks by height and require a video-plus-audio result.
- Keep bounded retries for transient network errors.
- Do not pass `--ffmpeg-location` to yt-dlp by default; Clipinn selects its
  render binary separately through `FFMPEG_BIN`.
- Probe every downloaded segment and reject it if it has no video stream.

When changing format selection or download arguments, test a section well into
a long source, then use `ffprobe` to confirm the result includes video and audio.
This catches partial-download cases that a successful process exit can hide.
