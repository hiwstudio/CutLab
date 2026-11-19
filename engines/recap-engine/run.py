"""Recap Engine - turn a long video into a narrated story recap.

SEPARATE, ISOLATED system (its own copy of the shared helpers). Does not touch
the clip engine.

Pipeline:
  download -> transcribe -> detect scenes -> summarize (story outline) ->
  index footage (scene cards) -> write recap script -> match beats to scenes ->
  voiceover (TTS) -> reconcile length -> assemble recap.mp4

Every stage caches to the project workdir, so a rerun resumes instead of
recomputing.
"""
import argparse
import time
from pathlib import Path

import config
from engine import index, publish, recap, story, treatments, tts
from engine.scenes import detect_scenes
from engine.source import resolve_input
from engine.transcribe import transcribe
from engine.utils import check_ffmpeg, die, fmt_ts, log, safe_slug


def main() -> None:
    parser = argparse.ArgumentParser(description="Recap Engine")
    parser.add_argument("video", nargs="?", default=None,
                        help="video file path or URL")
    parser.add_argument("--minutes", type=int, default=None,
                        help="target recap length in minutes (overrides the "
                             "automatic length for long sources / the prompt for "
                             "short ones)")
    parser.add_argument("--redo", action="store_true",
                        help="ignore caches and rebuild from scratch")
    parser.add_argument("--treat-plan", metavar="PROJECT", default=None,
                        help="movierecap profile: propose visual treatments for "
                             "an already-assembled project, writing "
                             "treatments.json for review")
    parser.add_argument("--treat-apply", metavar="PROJECT", default=None,
                        help="movierecap profile: render treatments.json onto "
                             "the finished recap (audio is stream-copied)")
    args = parser.parse_args()

    # A profile is a set of defaults folded in before any stage reads config.
    config.apply_profile()
    if config.RECAP_PROFILE:
        log(f"Profile: {config.RECAP_PROFILE} "
            f"(shot cap {config.SHOT_MAX_SECONDS}s, "
            f"{config.MATCH_MAX_SCENES_PER_BEAT} scenes/beat)")

    check_ffmpeg()

    # The treatment stages act on a finished project, so they short-circuit the
    # pipeline rather than running after it: planning needs a human between it
    # and rendering.
    if args.treat_plan or args.treat_apply:
        name = args.treat_plan or args.treat_apply
        project = Path(name) if Path(name).is_dir() else config.OUTPUT_DIR / name
        if not project.is_dir():
            die(f"no such project: {project}")
        if args.treat_plan:
            treatments.plan(project)
        else:
            if not args.video:
                die("--treat-apply also needs the source video: treatments cut "
                    "new footage from it.  Usage: "
                    "py run.py <source video> --treat-apply <project>")
            treatments.apply(project, resolve_input(args.video))
        return
    video = resolve_input(args.video)
    workdir = config.OUTPUT_DIR / safe_slug(video.stem, 60)
    workdir.mkdir(parents=True, exist_ok=True)
    if args.redo:
        _clear_caches(workdir)
    log(f"Recap project folder: {workdir}")

    t0 = time.time()

    # 1-2. transcript + 3. scenes (both cached)
    transcript = transcribe(video, workdir)
    scenes = detect_scenes(video, workdir=workdir)
    log(f"Transcript: {len(transcript['segments'])} segments; "
        f"{len(scenes)} scenes over {fmt_ts(transcript.get('duration', 0))}.")

    # 4. how long is this recap? Decided BEFORE the outline, because the outline's
    #    beat granularity is what sets the pace of the finished cut (see below).
    src_minutes = float(transcript.get("duration") or 0.0) / 60.0
    target_min, win_lo, win_hi = _resolve_length(args.minutes, src_minutes)

    # 5. story outline (map-reduce), cut into beats sized for that runtime
    outline = story.summarize_transcript(transcript, workdir, target_min)

    # 6. footage understanding (scene cards + CLIP/dialogue embeddings)
    scene_cards = index.build_scene_cards(scenes, transcript, video, workdir)

    # 7. optional: direct the edit before writing (OFF by default - see CLAUDE.md)
    plan = (story.plan_shots(outline, transcript, target_min, workdir)
            if config.DIRECT_SHOTS else None)

    # 7. write the narration over that edit, beat by beat
    script = story.write_recap_script(outline, target_min, workdir, plan)

    # 8. carry the planned scenes into the edit (no re-matching on this path)
    edit = story.match_beats_to_scenes(script, scenes, transcript, workdir)

    # 8. voiceover, then 9. reconcile real length into the target window
    beats = tts.synthesize(edit, workdir)
    beats = story.reconcile_length(beats, workdir, target_min, win_lo, win_hi)

    # 9b. validate + repair the visual timeline so every beat's footage fully
    #     covers its (now final) narration before we render anything.
    beats = story.ensure_scene_coverage(beats, scenes, workdir)

    # 10. assemble the final recap
    out = recap.assemble(video, beats, workdir)

    # 11. publishing assets: platform captions + thumbnail concepts. The recap is
    #     already done by here, so these never block the video; both cache+resume.
    captions = publish.generate_captions(outline, script, video.stem, workdir)
    thumbs = publish.generate_thumbnails(outline, scene_cards, video, workdir)
    #     ...and an image-gen enhancement prompt per thumbnail concept, so each
    #     concept can be elevated into a polished, upload-ready thumbnail (with
    #     bold YouTube text baked in) instead of hand-edited. Feed it the real
    #     YouTube title from the captions so the overlay text stays on-message.
    yt_title = ((captions.get("youtube") or {}).get("title") or "").strip()
    publish.generate_thumbnail_enhancements(thumbs, video.stem, workdir,
                                            youtube_title=yt_title)

    log(f"DONE in {time.time() - t0:.0f}s -> {out}")
    log(f"Publish-ready assets in: {workdir}")


# Sources at/above this are "long" and recap automatically to the standard
# config window; anything shorter prompts the owner for the recap length.
LONG_SOURCE_MINUTES = 60


def _resolve_length(cli_minutes, src_minutes: float):
    """Decide (target, window_lo, window_hi) in minutes.

    - Long source (>= LONG_SOURCE_MINUTES) with no --minutes: recap automatically
      to the configured standard window (RECAP_MIN_MINUTES..RECAP_MAX_MINUTES).
    - Otherwise (an explicit --minutes, or a short source): the owner picks the
      length. That choice IS the target and defines its own +/-15% acceptance
      band, so a short video is never forced up into the standard window.
    """
    if cli_minutes is not None:
        return _explicit_window(cli_minutes)
    if src_minutes >= LONG_SOURCE_MINUTES:
        lo, hi = config.RECAP_MIN_MINUTES, config.RECAP_MAX_MINUTES
        return (lo + hi) // 2, lo, hi
    return _explicit_window(_ask_recap_minutes(src_minutes))


def _explicit_window(target):
    """A chosen target minute count plus a +/-15% acceptance band around it."""
    target = max(1, int(target))
    lo = max(1, round(target * 0.85))
    hi = max(lo + 1, round(target * 1.15))
    return target, lo, hi


def _ask_recap_minutes(src_minutes: float) -> int:
    """Short source: ask the owner how long the recap should be - no fixed
    default is imposed. On a non-interactive run with no answer, fall back to a
    ~3x compression so the pipeline still produces something sensible."""
    log(f"Source video is ~{src_minutes:.0f} min "
        f"(under {LONG_SOURCE_MINUTES} min) - choose the recap length.")
    try:
        ans = input("   Desired recap length in minutes: ").strip()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    try:
        return max(1, int(float(ans)))
    except ValueError:
        fallback = max(1, round(src_minutes / 3))
        log(f"   No length given; defaulting to ~{fallback} min (~3x compression).")
        return fallback


def _clear_caches(workdir) -> None:
    """Delete stage outputs so the run rebuilds (keeps audio/transcript heavy
    artifacts unless they're stage JSONs)."""
    for name in ("outline.json", "scene_cards.json", "scene_embeddings.npz",
                 "script.json", "edit.json", "recap.json"):
        p = workdir / name
        if p.exists():
            p.unlink()
    log("Cleared stage caches (--redo).")


if __name__ == "__main__":
    main()
