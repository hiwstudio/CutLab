"""Clipinn CLI.

    python -m clipinn run <youtube-url> [--project name] [--style blur]
        [--captions top|middle|bottom|off] [--subtitles top|middle|bottom|off]
        [--font Name] [--clips N]
    python -m clipinn status

Anything not given via flags is asked interactively. Caption and subtitle
placements can never collide: once one zone is taken, only the remaining
zones are offered.
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config, pipeline, styles
from .fonts import apply_font
from .utils import check_ffmpeg, die, log, safe_slug
from .youtube import YouTubeError

ZONES = ["top", "middle", "bottom"]


def _video_id(url: str) -> str:
    """Extract the YouTube video id, ignoring tracking params like ?si=."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    parts = [p for p in parsed.path.split("/") if p]
    return parts[-1] if parts else "video"


def _ask(prompt: str, default: str = "") -> str:
    try:
        ans = input(prompt).strip()
    except EOFError:
        ans = ""
    return ans or default


def _ask_zone(kind: str, taken: str | None) -> str | None:
    """Ask y/n for a text layer, then its zone from the free zones only."""
    ans = _ask(f"\n  Add {kind}? [Y/n]: ", "y").lower()
    if ans not in ("", "y", "yes"):
        return None
    free = [z for z in ZONES if z != taken]
    print(f"  Where should the {kind} appear?")
    for i, z in enumerate(free, 1):
        print(f"    {i}. {z.capitalize()}")
    while True:
        c = _ask(f"  Pick 1-{len(free)} (Enter for 1): ", "1")
        if c.isdigit() and 1 <= int(c) <= len(free):
            return free[int(c) - 1]
        print(f"  Please type a number 1-{len(free)}.")


def _zone_flag(value: str | None, kind: str, taken: str | None) -> str | None:
    """Resolve a placement from a CLI flag, or ask. Rejects collisions."""
    if value:
        v = value.strip().lower()
        if v in ("off", "no", "none"):
            return None
        if v not in ZONES:
            die(f"--{kind} must be top, middle, bottom or off (got '{value}')")
        if v == taken:
            die(f"--{kind} {v} collides with the caption placement — "
                f"pick one of: {', '.join(z for z in ZONES if z != taken)}")
        return v
    return _ask_zone(kind, taken)


def _choose_style(cli_style: str | None) -> str:
    options = styles.describe()
    if cli_style:
        s = cli_style.strip().lower()
        if s in styles.STYLES:
            return s
        print(f'  Style "{cli_style}" not found; pick one below.')
    print("\n  Which output style?")
    for i, (name, desc) in enumerate(options, 1):
        print(f"    {i}. {name:<7}- {desc}")
    while True:
        c = _ask(f"  Pick 1-{len(options)} (Enter for 1): ", "1")
        if c.isdigit() and 1 <= int(c) <= len(options):
            return options[int(c) - 1][0]
        print(f"  Please type a number 1-{len(options)}.")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="clipinn", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run", help="turn a YouTube video into short clips")
    p_run.add_argument("url", help="YouTube video URL")
    p_run.add_argument("--project", default=None, help="project name (default: video id)")
    p_run.add_argument("--style", default=None, help="blur | center | split | face")
    p_run.add_argument("--captions", default=None,
                       help="hook caption placement: top | middle | bottom | off")
    p_run.add_argument("--subtitles", default=None,
                       help="spoken-word subtitle placement: top | middle | bottom | off")
    p_run.add_argument("--font", default=None, help="caption/subtitle font name")
    p_run.add_argument("--clips", type=int, default=None, help="max clips to produce")
    p_run.add_argument("--split-image", default=None,
                       help="split style: custom bottom-panel image path")
    sub.add_parser("status", help="show pipeline state for recent runs")
    args = parser.parse_args(argv)

    if args.cmd == "status":
        from .db import DB
        print(DB().report())
        return
    if args.cmd != "run":
        parser.print_help()
        return

    check_ffmpeg()
    if args.clips:
        config.MAX_CLIPS = args.clips
    try:
        config.validate()
    except ValueError as e:
        die(str(e))
    log(f"Intelligence layer: {config.intelligence_layer()}")
    log(f"Clip length: {config.MIN_CLIP_SECONDS}-{config.MAX_CLIP_SECONDS}s  "
        f"|  quality bar: {config.MIN_SCORE}  |  max clips: {config.MAX_CLIPS}")
    config.STYLE = _choose_style(args.style)
    apply_font(args.font)
    config.CAPTION_POSITION = _zone_flag(args.captions, "captions", None)
    config.SUBTITLE_POSITION = _zone_flag(args.subtitles, "subtitles",
                                          config.CAPTION_POSITION)
    log(f"Style: {config.STYLE}  |  Font: {config.SUB_FONT}  |  "
        f"Caption: {config.CAPTION_POSITION or 'off'}  |  "
        f"Subtitles: {config.SUBTITLE_POSITION or 'off'}")

    split_image = Path(args.split_image) if args.split_image else None
    if split_image and not split_image.exists():
        die(f"split image not found: {split_image}")

    url = args.url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    project = args.project or safe_slug(_video_id(url), 40)

    # Expected failures get a readable message, not a traceback. Every stage
    # is file-cached, so "rerun the same command" is always the right advice.
    try:
        done = pipeline.run(project, url, split_image=split_image)
    except KeyboardInterrupt:
        log("Interrupted. Finished work is cached — rerun the same command "
            "to pick up where this left off.")
        sys.exit(130)
    except (YouTubeError, RuntimeError, ValueError) as e:
        die(f"{e}\n\n  Nothing already finished was lost — rerun the same "
            f"command to resume (see: python -m clipinn status).")
    if done:
        log(f"DONE. Clips in projects/{project}/clips/, plan in posting-plan.txt")
    else:
        sys.exit(2)  # paused for the operator — rerun after fulfilling the task


if __name__ == "__main__":
    main()
