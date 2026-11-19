"""Step 6: write clips.json + a human-readable posting plan."""
import json
from datetime import datetime
from pathlib import Path

from engine.utils import fmt_ts, log

PLATFORMS = ["TikTok", "YouTube Shorts", "Instagram Reels", "Facebook Reels"]


def write_metadata(video: Path, moments: list, workdir: Path) -> Path:
    data = {
        "source_video": video.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "clip_count": len(moments),
        "clips": [
            {
                "n": i,
                "file": m.get("file"),
                "start": m["start"],
                "end": m["end"],
                "duration_seconds": round(m["end"] - m["start"], 1),
                "timestamp": f"{fmt_ts(m['start'])} - {fmt_ts(m['end'])}",
                "score": m.get("score"),
                "hook": m.get("hook", ""),
                "title": m.get("title", ""),
                "caption": m.get("caption", ""),
                "hashtags": m.get("hashtags", []),
                "reason": m.get("reason", ""),
                "platforms": PLATFORMS,
            }
            for i, m in enumerate(moments, 1)
        ],
    }
    out = workdir / "clips.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable posting plan
    lines = [f"POSTING PLAN - {video.name}", "=" * 60, ""]
    for c in data["clips"]:
        lines += [
            f"CLIP {c['n']}  |  {c['timestamp']}  |  {c['duration_seconds']}s  |  score {c['score']}",
            f"File:     {c['file']}",
            f"Hook:     {c['hook']}",
            f"Title:    {c['title']}",
            f"Caption:  {c['caption']}",
            f"Hashtags: {' '.join(c['hashtags'])}",
            f"Why:      {c['reason']}",
            "-" * 60, "",
        ]
    lines += [
        "POSTING SUGGESTIONS",
        "- Post 1-2 clips/day per platform; spread the best (highest score) across the week.",
        "- TikTok & Reels: post at your audience's evening hours; reply to early comments.",
        "- Shorts: titles matter most; keep them under 70 chars.",
        "- Reuse top performers after 2-3 weeks with a different hook.",
    ]
    (workdir / "posting-plan.txt").write_text("\n".join(lines), encoding="utf-8")

    log(f"Metadata written -> {out}")
    return out


def write_caption_file(path: Path, top_caption: str, social_caption: str,
                       on_video: bool) -> Path:
    """Write a .txt holding the on-video top caption and a universal social
    caption. Always written, even when the overlay is turned off."""
    status = ("shown ON the video" if on_video
              else "NOT shown on the video (you turned the overlay off)")
    body = (
        f"TOP CAPTION ({status}):\n"
        f"{top_caption or '(none)'}\n\n"
        f"{'-' * 50}\n\n"
        f"SOCIAL MEDIA CAPTION (works for TikTok, YouTube, Instagram, Facebook):\n"
        f"{social_caption or top_caption or '(none)'}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
