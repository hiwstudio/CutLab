"""Reframe a whole video into 9:16 portrait (blur fill or center crop) with
burned-in subtitles and a persistent top caption.

In blur mode the video sits in a band of config.BLUR_VIDEO_PCT of the frame
height (25/50/25 by default); the caption is auto-sized to fit the blurred band
above it, never on the video. Portrait sources are fitted instead and keep the
config.CAPTION_BAND_MIN reserve.

Used by the 'reframe' and 'cut-reframe' modes. If the video has little/no
detected speech, the caller provides a caption (asked from the user)."""
from pathlib import Path

import config
from engine import fonts, styles
from engine.subtitles import build_ass
from engine.utils import has_video, log, probe_duration, run_ffmpeg


def ask_split_image() -> "Path | None":
    """Ask the user whether to provide a custom bottom image for split style."""
    print()
    print("  Split style: bottom panel image")
    print("    1. Let the engine pick a frame automatically")
    print("    2. I'll provide my own image")
    try:
        ans = input("  Pick 1-2 (Enter for 1): ").strip()
    except EOFError:
        ans = ""
    if ans == "2":
        try:
            path = input("  Image path: ").strip().strip('"')
        except EOFError:
            path = ""
        p = Path(path) if path else None
        if p and p.exists():
            log(f"Using custom split image: {p}")
            return p
        log("Image not found, auto-picking instead.")
    return None


def ask_top_caption(cli_choice: str = None) -> bool:
    """Ask whether to burn the top caption onto the video.
    cli_choice: 'yes' | 'no' | None."""
    if cli_choice in ("yes", "on", "true"):
        return True
    if cli_choice in ("no", "off", "false"):
        return False
    try:
        ans = input("\n  Add the top caption text ON the video? [Y/n]: ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("", "y", "yes")


def get_caption(transcript: dict, workdir: Path, interactive: bool = True) -> str:
    """Return a top caption. Always shows the suggested caption (when speech is
    usable) and asks whether to use it; if not, asks the user to type one. For
    audio/no-speech videos it asks directly."""
    cap_file = workdir / "caption.txt"
    if cap_file.exists():
        saved = cap_file.read_text(encoding="utf-8-sig").strip()
        if saved:
            log(f'Using saved caption: "{saved}"')
            return saved

    text = " ".join(s["text"] for s in transcript.get("segments", [])).strip()
    suggested = ""
    if len(text) >= 40 and config.LLM_ENABLED:
        try:
            from engine.analyze import suggest_caption
            suggested = suggest_caption(text)
        except Exception as e:
            log(f"Could not auto-generate a caption ({e}).")

    caption = ""
    if suggested:
        log(f'Suggested caption: "{suggested}"')
        if interactive:
            print()
            print(f'  Suggested caption:  "{suggested}"')
            try:
                ans = input("  Use this caption? [Y/n]: ").strip().lower()
            except EOFError:
                ans = ""
            if ans in ("", "y", "yes"):
                caption = suggested
            else:
                try:
                    typed = input("  Type the caption to use: ").strip("\ufeff\ufffd \t")  # piped stdin can carry a BOM/garbage
                except EOFError:
                    typed = ""
                caption = typed or suggested  # empty -> keep the suggestion
        else:
            caption = suggested

    if not caption:
        if interactive:
            print()
            print("  No clear speech was detected, so I could not suggest a caption.")
            try:
                caption = input("  Type the caption to show on the video: ").strip("\ufeff\ufffd \t")  # piped stdin can carry a BOM/garbage
            except EOFError:
                caption = ""
        if not caption:
            caption = "Watch this 👀"
            log(f'No caption given, using default: "{caption}"')

    cap_file.write_text(caption, encoding="utf-8")
    log(f'Caption set to: "{caption}"')
    return caption

def reframe_video(video: Path, transcript: dict, workdir: Path, caption: str,
                  out_name: str, duration: float = None,
                  subtitles_on: bool = True, caption_overlay: bool = True,
                  split_image: Path = None) -> Path:
    """Render the entire `video` to a single 9:16 portrait mp4 with subtitles
    and a persistent top caption locked inside the top blurred band.
    subtitles_on=False renders only the caption (no word subtitles)."""
    if duration is None:
        duration = probe_duration(video)

    out_file = workdir / out_name
    if out_file.exists():
        log(f"{out_name} already exists, skipping render (use --redo to rerun)")
        return out_file
    ass_file = workdir / (out_file.stem + ".ass")
    segments = transcript.get("segments", [])
    fonts.install_into(workdir)
    top = caption if caption_overlay else ""
    log(f"Subtitles: {'on' if subtitles_on else 'off'}  |  Top caption: {'on' if caption_overlay else 'off'}")

    # Audio-only input (music/podcast with no video): make a vertical audio card.
    if not has_video(video):
        log("No video stream found - building a vertical audio card instead.")
        return _render_audio_card(video, segments, workdir, top,
                                  out_file, ass_file, duration, subtitles_on)

    r = styles.build(video, ass_file.name, start=0.0, end=duration,
                     boxed=True, workdir=workdir, split_image=split_image)
    build_ass(segments, 0.0, duration, top, ass_file,
              hook_persist=True, hook_box=r.hook_box, subtitles_on=subtitles_on)

    log(f"Reframing whole video ({duration:.0f}s, style: {config.STYLE})...")
    run_ffmpeg(
        [
            "-i", str(video), *r.inputs,
            "-filter_complex", r.fc,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", *r.out_args,
            out_file.name,
        ],
        desc=out_name,
        cwd=workdir,
    )
    ass_file.unlink(missing_ok=True)
    for tmp in r.temp:
        Path(tmp).unlink(missing_ok=True)
    fonts.remove_from(workdir)
    log(f"Reframed video -> {out_file}")
    return out_file


def _render_audio_card(video, segments, workdir, caption, out_file, ass_file,
                       duration, subtitles_on):
    """Render audio-only input to a 9:16 card: solid background + persistent
    caption (top) + live subtitles, over the original audio."""
    W, H = config.OUT_WIDTH, config.OUT_HEIGHT
    top_band = int(H * 0.30)  # caption sits in the upper third
    build_ass(segments, 0.0, duration, caption, ass_file,
              hook_persist=True, hook_box=top_band, subtitles_on=subtitles_on)
    bg = config.AUDIO_CARD_BG
    fc = (f"[1:v]format=yuv420p,ass={ass_file.name}{fonts.fontsdir_suffix()}[v]")
    run_ffmpeg(
        [
            "-i", str(video),
            "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r=30",
            "-filter_complex", fc,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            out_file.name,
        ],
        desc=out_file.name,
        cwd=workdir,
    )
    ass_file.unlink(missing_ok=True)
    fonts.remove_from(workdir)
    log(f"Audio card -> {out_file}")
    return out_file


def assess_subtitle_clarity(transcript: dict, duration: float) -> tuple:
    """Judge how clear/usable the auto-subtitles are.
    Returns (is_clear: bool, message: str)."""
    segments = transcript.get("segments", [])
    words = [w for s in segments for w in s.get("words", [])]
    n = len(words)
    if duration <= 0:
        duration = max(1.0, transcript.get("duration", 1.0))

    if n == 0:
        return False, "No speech was detected in this video."

    wpm = n / duration * 60.0

    # use Whisper confidence if the transcript has it (newer runs do)
    lps = [s["avg_logprob"] for s in segments if "avg_logprob" in s]
    nsp = [s["no_speech_prob"] for s in segments if "no_speech_prob" in s]
    if lps:
        mean_lp = sum(lps) / len(lps)
        mean_ns = (sum(nsp) / len(nsp)) if nsp else 0.0
        clear = mean_lp > -1.0 and mean_ns < 0.5 and wpm >= 25
        quality = ("confident" if mean_lp > -0.7 else
                   "okay" if mean_lp > -1.0 else "low-confidence")
        msg = f"~{wpm:.0f} words/min, transcription confidence {quality}."
        return clear, msg

    # fallback heuristic when confidence isn't stored
    clear = wpm >= 40
    if wpm < 15:
        msg = f"Very little speech detected (~{wpm:.0f} words/min)."
    else:
        msg = f"~{wpm:.0f} words/min detected."
    return clear, msg


def ask_subtitles(transcript: dict, duration: float, cli_choice: str = None) -> bool:
    """Tell the user whether the subtitles look clear and ask whether to add
    them. cli_choice: 'yes' | 'no' | 'auto' | None."""
    clear, msg = assess_subtitle_clarity(transcript, duration)
    verdict = "CLEAR" if clear else "UNCLEAR / messy"
    log(f"Subtitle check: {msg}  ->  subtitles look {verdict}.")

    if cli_choice in ("yes", "on", "true"):
        return True
    if cli_choice in ("no", "off", "false"):
        return False
    if cli_choice == "auto":
        return clear

    default_yes = clear
    prompt = ("  Add subtitles to the video? [Y/n]: " if default_yes
              else "  The speech isn't clear, so subtitles may look messy.\n"
                   "  Add subtitles anyway? [y/N]: ")
    try:
        ans = input("\n" + prompt).strip().lower()
    except EOFError:
        ans = ""
    if ans == "":
        return default_yes
    return ans in ("y", "yes")
