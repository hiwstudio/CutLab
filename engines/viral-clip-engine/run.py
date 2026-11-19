"""Viral Clip Engine - turn a long video into short-form content.

Three modes:
  1. Clip         - find the viral moments and cut them into shorts (subtitles,
                    hooks, titles, captions, hashtags).
  2. Reframe      - turn the WHOLE video into a 9:16 short: blurred portrait
                    style + subtitles + a caption that stays on screen.
  3. Cut+Reframe  - remove silent/dead parts, compact the video, then reframe.

Usage:
    python run.py                                  # full menu
    python run.py --mode reframe --font Wargod --subtitles auto <video|url>
    python run.py <video> --clips 10               # clip mode target count
    python run.py <video> --redo                   # ignore cached steps
"""
import argparse
import shutil
import time
from pathlib import Path

import config
from engine import fonts, styles
from engine.analyze import find_moments, suggest_social_caption
from engine.cut import cut_clips
from engine.metadata import write_caption_file, write_metadata
from engine.reframe import ask_split_image, ask_subtitles, ask_top_caption, get_caption, reframe_video
from engine.silence import compact_video, reel_ranges, remap_segments
from engine.source import resolve_input
from engine.transcribe import transcribe
from engine.utils import check_ffmpeg, log, prepare_rerender, probe_duration, safe_slug

MODES = {"1": "clip", "2": "reframe", "3": "cut-reframe"}

# User-facing deliverable names. On revision, the current file is archived as
# "{label} vN.ext" and the new render is written back to the unversioned name.
REFRAME_OUT = "Reframe.mp4"
REFRAME_LEGACY = ["reframed.mp4"]
CUT_REFRAME_OUT = "Cut reframe.mp4"
CUT_REFRAME_LEGACY = ["cut-reframed.mp4"]
CUT_REFRAME_SOURCE = "Cut reframe source.mp4"
CUT_REFRAME_SOURCE_LEGACY = ["cut-reframed-source.mp4"]


def choose_mode(cli_mode: str | None) -> str:
    if cli_mode:
        m = cli_mode.strip().lower().replace("_", "-")
        if m in ("clip", "reframe", "cut-reframe"):
            return m
        if m in MODES:
            return MODES[m]
    print()
    print("  What do you want to do?")
    print("    1. Clip        - find viral moments and cut them into shorts")
    print("    2. Reframe     - turn the whole video into a 9:16 short + caption")
    print("    3. Cut+Reframe - remove dead/silent parts, then reframe to 9:16")
    print()
    while True:
        choice = input("  Pick 1, 2 or 3: ").strip()
        if choice in MODES:
            return MODES[choice]
        print("  Please type 1, 2 or 3.")


def choose_style(cli_style: str | None) -> str:
    """Pick the output layout style; ask when not given via --style."""
    options = styles.describe()
    if cli_style:
        s = cli_style.strip().lower()
        if s in styles.STYLES:
            return s
        print(f'  Style "{cli_style}" not found; pick one below.')
    print()
    print("  Which output style?")
    for i, (name, desc) in enumerate(options, 1):
        print(f"    {i}. {name:<7}- {desc}")
    print()
    while True:
        choice = input(f"  Pick 1-{len(options)} (Enter for 1): ").strip()
        if choice == "":
            return options[0][0]
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1][0]
        print(f"  Please type a number 1-{len(options)}.")


def _reframe_metadata(video, out_file, workdir, caption, duration):
    """Write clips.json/posting-plan for a single reframed video so it shows
    up in the dashboard just like clips do."""
    moment = {
        "file": out_file.name,
        "start": 0.0,
        "end": round(duration, 2),
        "score": None,
        "hook": caption,
        "title": caption,
        "caption": caption,
        "hashtags": [],
        "reason": "Whole video reframed to 9:16 with a persistent caption.",
    }
    write_metadata(video, [moment], workdir)



def _social_for_reframe(transcript, fallback):
    """One universal social caption for reframe outputs."""
    text = " ".join(s["text"] for s in transcript.get("segments", [])).strip()
    if len(text) >= 40 and config.LLM_ENABLED:
        try:
            return suggest_social_caption(text)
        except Exception as e:
            log(f"Could not generate a social caption ({e}).")
    return fallback


def run_clip(video, workdir, overlay_on, split_img=None, remotion=False,
             subtitles_on=True):
    transcript = transcribe(video, workdir)
    moments = find_moments(transcript, workdir)
    moments = cut_clips(video, transcript, moments, workdir,
                        overlay_on=overlay_on, split_image=split_img,
                        no_text=remotion, subtitles_on=subtitles_on)
    if remotion:
        from engine.remotion_render import render_with_remotion
        clips_dir = workdir / "clips"
        for m in moments:
            clean = clips_dir / Path(m["file"]).name
            out = clips_dir / clean.name.replace(".mp4", "_remotion.mp4")
            render_with_remotion(clean, m, transcript, out)
            m["file_remotion"] = f"clips/{out.name}"
    write_metadata(video, moments, workdir)
    return len(moments), "clips"


def run_reframe(video, workdir, subs_choice, overlay_on, split_img=None):
    transcript = transcribe(video, workdir)
    duration = probe_duration(video)
    subs_on = ask_subtitles(transcript, duration, subs_choice)
    caption = get_caption(transcript, workdir, interactive=overlay_on)
    social = _social_for_reframe(transcript, caption)
    # Archive any prior deliverable so we never overwrite history.
    prepare_rerender(workdir, REFRAME_OUT, "Reframe", legacy=REFRAME_LEGACY)
    write_caption_file(workdir / "Reframe.caption.txt", caption, social, overlay_on)
    out_file = reframe_video(video, transcript, workdir, caption, REFRAME_OUT,
                             duration, subtitles_on=subs_on, caption_overlay=overlay_on,
                             split_image=split_img)
    _reframe_metadata(video, out_file, workdir, caption, duration)
    return 1, "reframed video"


def run_cut_reframe(video, workdir, subs_choice, overlay_on, split_img=None):
    """Intelligent editor: find the strongest moments (LLM/agent, same engine as
    clip mode), assemble the best ones into a 90-180s highlight reel, then
    reframe that reel to 9:16 - not a silence-trimmed copy of the whole video."""
    transcript = transcribe(video, workdir)
    moments = find_moments(transcript, workdir)
    ranges = reel_ranges(moments)
    if not ranges:
        raise SystemExit("No moments qualified for the highlight reel.")
    total = sum(e - s for s, e in ranges)
    log(f"Highlight reel: {len(ranges)} moment(s), {total:.0f}s "
        f"(target {config.REEL_MIN_SECONDS}-{config.REEL_MAX_SECONDS}s).")
    # Archive current deliverable + compacted source (never delete prior cuts).
    prepare_rerender(workdir, CUT_REFRAME_OUT, "Cut reframe",
                     legacy=CUT_REFRAME_LEGACY)
    prepare_rerender(workdir, CUT_REFRAME_SOURCE, "Cut reframe source",
                     legacy=CUT_REFRAME_SOURCE_LEGACY)
    compacted = compact_video(video, ranges, workdir, out_name=CUT_REFRAME_SOURCE)
    new_duration = probe_duration(compacted)
    new_transcript = {"segments": remap_segments(transcript.get("segments", []), ranges),
                      "duration": new_duration}
    subs_on = ask_subtitles(new_transcript, new_duration, subs_choice)
    caption = get_caption(transcript, workdir, interactive=overlay_on)
    social = _social_for_reframe(transcript, caption)
    write_caption_file(workdir / "Cut reframe.caption.txt", caption, social, overlay_on)
    out_file = reframe_video(compacted, new_transcript, workdir, caption,
                             CUT_REFRAME_OUT, new_duration,
                             subtitles_on=subs_on, caption_overlay=overlay_on,
                             split_image=split_img)
    _reframe_metadata(video, out_file, workdir, caption, new_duration)
    return 1, "cut + reframed video"


def main() -> None:
    parser = argparse.ArgumentParser(description="Viral Clip Engine")
    parser.add_argument("video", nargs="?", default=None,
                        help="video file path or YouTube/video URL")
    parser.add_argument("--mode", default=None,
                        help="clip | reframe | cut-reframe (else you'll be asked)")
    parser.add_argument("--style", default=None,
                        help="output layout: blur | center | split | face "
                             "(else you'll be asked)")
    parser.add_argument("--font", default=None,
                        help="caption font name (else you'll be asked)")
    parser.add_argument("--subtitles", default=None,
                        help="reframe modes: yes | no | auto (else you'll be asked)")
    parser.add_argument("--caption", default=None,
                        help="burn top caption on video: yes | no (else you'll be asked)")
    parser.add_argument("--clips", type=int, default=config.MAX_CLIPS,
                        help="clip mode: max number of clips to keep")
    parser.add_argument("--redo", action="store_true",
                        help="delete cached results and rerun everything")
    parser.add_argument("--remotion", action="store_true",
                        help="use Remotion for animated text instead of burning ASS subtitles")
    args = parser.parse_args()

    config.MAX_CLIPS = args.clips
    check_ffmpeg()
    log(f"Intelligence layer: {config.intelligence_layer()}")

    mode = choose_mode(args.mode)
    config.STYLE = choose_style(args.style)
    fonts.apply_font(fonts.choose_font(args.font))
    video = resolve_input(args.video)

    workdir = config.OUTPUT_DIR / safe_slug(video.stem, 60)
    if args.redo and workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    log(f"Mode: {mode}  |  Style: {config.STYLE}  |  Font: {config.SUB_FONT}  |  Project: {workdir}")

    subs_choice = args.subtitles.strip().lower() if args.subtitles else None
    cap_choice = args.caption.strip().lower() if args.caption else None
    overlay_on = ask_top_caption(cap_choice)
    split_img = ask_split_image() if config.STYLE == "split" else None
    t0 = time.time()
    if mode == "clip":
        clip_subs = (subs_choice in ("yes", "on", "true")) if subs_choice in ("yes", "no", "on", "off", "true", "false") else True
        n, what = run_clip(video, workdir, overlay_on, split_img=split_img,
                           remotion=args.remotion, subtitles_on=clip_subs)
    elif mode == "reframe":
        n, what = run_reframe(video, workdir, subs_choice, overlay_on, split_img=split_img)
    else:  # cut-reframe
        n, what = run_cut_reframe(video, workdir, subs_choice, overlay_on, split_img=split_img)

    log(f"DONE in {time.time() - t0:.0f}s. {n} {what} ready.")
    log("Review:  python dashboard.py   then open http://localhost:5000")


if __name__ == "__main__":
    main()
