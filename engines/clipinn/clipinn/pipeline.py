"""The Clipinn pipeline: analyze first, download only what's needed.

  probe    — metadata + transcript (auto-captions; audio+whisper fallback)
             -> timing_map.json  (never downloads the video)
  select   — rubric-scored moment selection -> moments.json
  download — yt-dlp --download-sections, one small file per chosen clip
  render   — per-clip whisper + style + ASS overlays -> clips/*.mp4
  export   — clips.json + posting-plan.txt

Stages are idempotent (file cache + pipeline-state DB); resume = re-run.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config, moments, timing, visual, youtube
from .db import DB
from .moments import OperatorTask
from .render import render_clip
from .utils import fmt_ts, log

PLATFORMS = ["TikTok", "YouTube Shorts", "Instagram Reels", "Facebook Reels"]


def stage_probe(ctx: dict) -> None:
    pdir = ctx["project_dir"]
    info_file = pdir / "info.json"
    tm_file = pdir / "timing_map.json"
    if not info_file.exists():
        log("Fetching video metadata (no download)...")
        info = youtube.video_info(ctx["url"])
        info_file.write_text(json.dumps(info, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    ctx["info"] = json.loads(info_file.read_text(encoding="utf-8-sig"))
    if tm_file.exists():
        ctx["tm"] = timing.load(tm_file)
        return
    log("Fetching transcript from YouTube captions (no video download)...")
    events = youtube.fetch_auto_subs(ctx["info"]["url"])
    dur_ms = int(ctx["info"]["duration_s"] * 1000)
    if events:
        tm = timing.from_caption_events(events, dur_ms, ctx["project"])
    else:
        log("No captions available — downloading audio only for whisper...")
        audio = youtube.download_audio(ctx["info"]["url"], pdir / "audio.mp3")
        tm = timing.from_whisper(audio, ctx["project"])
    timing.save(tm, tm_file)
    ctx["db"].register_asset(ctx["run_id"], "probe", "timing_map", tm_file)
    ctx["tm"] = tm
    log(f"Timing map: {len(tm['segments'])} segments over "
        f"{fmt_ts(dur_ms / 1000)}")


def stage_select(ctx: dict) -> None:
    clips = moments.select_moments(ctx["tm"], ctx["project_dir"])
    if not clips:
        raise RuntimeError(
            f"No clips cleared the quality bar ({config.MIN_SCORE}). "
            "Lower CLIP_QUALITY_BAR or the video may lack strong moments.")
    ctx["clips"] = clips
    log(f"Selected {len(clips)} clips:")
    for c in clips:
        log(f"  {c['clip_id']}  {fmt_ts(c['start_ms'] / 1000)}-"
            f"{fmt_ts(c['end_ms'] / 1000)}  score={c['score']}  "
            f"{c.get('suggested_title', '')[:55]}")


def stage_visual(ctx: dict) -> None:
    """Adaptive visual analysis — instant no-op unless the scorer flagged
    clips it couldn't judge from the transcript alone."""
    visual.review(ctx["clips"], ctx["project_dir"], ctx["info"]["url"])
    # verdicts may have rescored or rejected clips — re-finalize from the
    # merged moments.json so the standard quality bar applies again
    ctx["clips"] = moments.select_moments(ctx["tm"], ctx["project_dir"])
    if not ctx["clips"]:
        raise RuntimeError(
            "Visual review rejected every remaining clip — nothing to render.")


def stage_download(ctx: dict) -> None:
    seg_dir = ctx["project_dir"] / "segments"
    ok, failed = [], []
    for c in ctx["clips"]:
        # where the clip starts inside its padded segment (deterministic)
        c["download_offset_s"] = min(config.SEGMENT_PAD_S, c["start_ms"] / 1000)
        # keyed by candidate_id, NOT clip_id: clip_id is positional and
        # renumbers whenever the selected set changes (e.g. visual review
        # rejects one), which would silently match a cached segment to a
        # different moment. candidate_id is stable for the life of the map.
        seg = seg_dir / f"{c.get('candidate_id', c['clip_id'])}.mp4"
        c["segment"] = seg
        if seg.exists():
            padded_start = max(0.0, c["start_ms"] / 1000 - config.SEGMENT_PAD_S)
            padded_end = c["end_ms"] / 1000 + config.SEGMENT_PAD_S
            expected_ms = int(round((padded_end - padded_start) * 1000))
            if youtube.media_covers(seg, expected_ms, require_audio=True):
                log(f"  {seg.name} already downloaded, skipping")
                ok.append(c)
                continue
            log(f"  {seg.name} exists but is incomplete — redownloading")
            seg.unlink()
        span = (c["end_ms"] - c["start_ms"]) / 1000
        log(f"  downloading {c['clip_id']} ({span:.0f}s section)...")
        try:
            youtube.download_section(ctx["info"]["url"], c["start_ms"],
                                     c["end_ms"], seg)
        except youtube.YouTubeError as e:
            # Keep the clips that did download; this one retries next run.
            log(f"  {c['clip_id']} FAILED to download: {str(e)[:200]}")
            ctx["db"].event(ctx["run_id"], "error",
                            f"{c['clip_id']} download failed: {e}"[:1000], "download")
            failed.append(c)
            continue
        ctx["db"].register_asset(ctx["run_id"], "download", "video", seg)
        ok.append(c)

    if not ok:
        raise RuntimeError(
            "Every segment download failed. Check the network and that "
            f"YouTube cookies from {config.YT_BROWSER or 'your browser'} are "
            "valid (open YouTube there while logged in), then rerun.")
    if failed:
        log(f"{len(failed)} segment(s) failed to download and were skipped: "
            f"{', '.join(c['clip_id'] for c in failed)}. Rerun to retry them.")
    ctx["clips"] = ok    # render/export only what actually downloaded


def stage_render(ctx: dict) -> None:
    clips_dir = ctx["project_dir"] / "clips"
    log(f"Rendering {len(ctx['clips'])} clips (style: {config.STYLE}, "
        f"caption: {config.CAPTION_POSITION or 'off'}, "
        f"subtitles: {config.SUBTITLE_POSITION or 'off'})")
    rendered, failed = [], []
    for c in ctx["clips"]:
        try:
            out = render_clip(c, c["segment"], clips_dir,
                              split_image=ctx.get("split_image"))
        except Exception as e:
            # One bad clip must not throw away the other nine.
            log(f"  {c['clip_id']} FAILED to render: {type(e).__name__}: "
                f"{str(e)[:200]}")
            ctx["db"].event(ctx["run_id"], "error",
                            f"{c['clip_id']} render failed: {e}"[:1000], "render")
            failed.append(c)
            continue
        ctx["db"].register_asset(ctx["run_id"], "render", "video", out)
        rendered.append(c)
    if not rendered:
        raise RuntimeError(
            "Every clip failed to render. The downloaded segments may be "
            "corrupt — delete projects/<name>/segments/ and rerun.")
    if failed:
        log(f"{len(failed)} clip(s) failed to render and were dropped: "
            f"{', '.join(c['clip_id'] for c in failed)}. Rerun to retry them.")
    ctx["clips"] = rendered   # export only what actually exists


def stage_export(ctx: dict) -> None:
    pdir = ctx["project_dir"]
    data = {
        "source": ctx["info"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "clip_count": len(ctx["clips"]),
        "clips": [{
            "clip_id": c["clip_id"], "file": c.get("file"),
            "start_ms": c["start_ms"], "end_ms": c["end_ms"],
            "timestamp": f"{fmt_ts(c['start_ms'] / 1000)} - {fmt_ts(c['end_ms'] / 1000)}",
            "duration_s": round((c["end_ms"] - c["start_ms"]) / 1000, 1),
            "score": c["score"], "subscores": c.get("subscores", {}),
            "hook_text": c.get("hook_text", ""),
            "suggested_title": c.get("suggested_title", ""),
            "caption": c.get("caption", ""), "hashtags": c.get("hashtags", []),
            "rationale": c.get("rationale", ""), "platforms": PLATFORMS,
            "title_supported": c.get("title_supported"),
            "title_problem": c.get("title_problem", ""),
        } for c in ctx["clips"]],
    }
    out = pdir / "clips.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"POSTING PLAN — {ctx['info']['title']}", "=" * 60, ""]
    for c in data["clips"]:
        lines += [
            f"{c['clip_id']}  |  {c['timestamp']}  |  {c['duration_s']}s  |  score {c['score']}",
            f"File:     {c['file']}",
            f"Hook:     {c['hook_text']}",
            f"Title:    {c['suggested_title']}",
            f"Caption:  {c['caption']}",
            f"Hashtags: {' '.join(c['hashtags'])}",
            f"Why:      {c['rationale']}",
            "-" * 60, "",
        ]
    lines += ["POSTING SUGGESTIONS",
              "- Post 1-2 clips/day per platform; spread the best across the week.",
              "- Shorts: titles matter most; keep them under 70 chars.",
              "- Reuse top performers after 2-3 weeks with a different hook."]
    (pdir / "posting-plan.txt").write_text("\n".join(lines), encoding="utf-8")
    ctx["db"].register_asset(ctx["run_id"], "export", "meta", out)
    log(f"Exported -> {out}")


STAGES = [("probe", stage_probe), ("select", stage_select),
          ("visual", stage_visual), ("download", stage_download),
          ("render", stage_render), ("export", stage_export)]

# Stages whose in-memory outputs later stages need even when skipped as 'done'.
_ALWAYS_RUN = {"probe", "select", "download"}  # cheap: all file-cached


def run(project: str, url: str, split_image: Path = None) -> bool:
    """Walk the stages. Returns True when the pipeline completed."""
    db = DB()
    project_dir = config.PROJECTS_DIR / project
    project_dir.mkdir(parents=True, exist_ok=True)
    run_id = db.get_or_create_run(project, url)
    ctx = {"db": db, "run_id": run_id, "project": project, "url": url,
           "project_dir": project_dir, "split_image": split_image}

    for seq, (name, fn) in enumerate(STAGES, 1):
        # ponytail: stages re-run every time and rely on their own file caches
        # for idempotency; the DB records history/assets, it is not the skip gate.
        db.stage_start(run_id, name, seq)
        try:
            fn(ctx)
        except OperatorTask as e:
            db.stage_finish(run_id, name, "pending")
            db.set_run_status(run_id, "paused")
            db.event(run_id, "info", "paused for operator selection", name)
            log(str(e))
            return False
        except Exception as e:
            db.stage_finish(run_id, name, "failed", str(e)[:1000])
            db.set_run_status(run_id, "failed")
            db.event(run_id, "error", str(e)[:1000], name)
            raise
        db.stage_finish(run_id, name, "done")
    db.set_run_status(run_id, "done")
    return True
