"""Render each downloaded segment into a finished 9:16 clip.

Per clip: whisper the short segment for word-precise subtitle timing (seconds
of work — this is why Clipinn never transcribes the full video), build the ASS
overlay, apply the active style, encode.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, fonts, styles, timing
from .subtitles import build_ass
from .utils import log, probe_duration, run_ffmpeg, safe_slug


def clip_words(segment_path: Path, offset_s: float, duration_s: float,
               cache_path: Path) -> dict:
    """Clip-local Timing Map (words layer) for one downloaded segment.
    Cached; falls back to an empty words layer if whisper is unavailable."""
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8-sig"))
    try:
        tm = timing.from_whisper(segment_path, cache_path.parent.parent.name)
    except ImportError:
        log("  faster-whisper not installed — rendering without subtitles "
            "for this clip (pip install faster-whisper)")
        tm = {"version": "1.0", "source": {"duration_ms": int(duration_s * 1000)},
              "words": [], "segments": [], "meta": {}}
    except Exception as e:
        # A clip with no subtitles still beats losing the whole run.
        log(f"  transcription failed ({type(e).__name__}: {e}) — rendering "
            "this clip without subtitles")
        tm = {"version": "1.0", "source": {"duration_ms": int(duration_s * 1000)},
              "words": [], "segments": [], "meta": {}}
    # rebase segment-local -> clip-local (drop pad, clamp to clip window)
    words = []
    off_ms, dur_ms = int(offset_s * 1000), int(duration_s * 1000)
    for w in tm.get("words", []):
        s, e = w["start_ms"] - off_ms, w["end_ms"] - off_ms
        if e > 0 and s < dur_ms:
            words.append({**w, "start_ms": max(0, s), "end_ms": min(dur_ms, e)})
    clip_tm = {"version": "1.0",
               "source": {**tm.get("source", {}), "duration_ms": dur_ms},
               "words": words, "segments": [], "meta": tm.get("meta", {})}
    cache_path.write_text(json.dumps(clip_tm, ensure_ascii=False), encoding="utf-8")
    return clip_tm


def render_clip(clip: dict, segment_path: Path, out_dir: Path,
                split_image: Path = None) -> Path:
    """Render one clip. Idempotent: skips if the output exists."""
    name = f"{clip['clip_id']}-{safe_slug(clip.get('suggested_title', ''), 50)}"
    out_file = out_dir / f"{name}.mp4"
    clip["file"] = f"clips/{out_file.name}"
    if out_file.exists() and out_file.stat().st_size > 0:
        log(f"  {out_file.name} exists, skipping")
        return out_file
    out_dir.mkdir(parents=True, exist_ok=True)

    dur_s = (clip["end_ms"] - clip["start_ms"]) / 1000
    offset_s = clip["download_offset_s"]  # where the clip starts inside the segment
    seg_dur = probe_duration(segment_path)
    dur_s = min(dur_s, max(0.5, seg_dur - offset_s))

    # cache keyed by candidate_id (stable); the mp4 keeps clip_id for ordering
    tm = clip_words(segment_path, offset_s, dur_s,
                    out_dir / f"{clip.get('candidate_id', clip['clip_id'])}.words.json")

    fonts.install_into(out_dir)
    ass_file = out_dir / f"{name}.ass"
    r = styles.build(segment_path, ass_file.name, start=offset_s,
                     end=offset_s + dur_s, workdir=out_dir, split_image=split_image)
    caption = clip.get("hook_text", "") if config.CAPTION_POSITION else ""
    build_ass(tm, caption, dur_s, ass_file, caption_box=r.hook_box)

    log(f"  rendering {out_file.name} ({dur_s:.0f}s, style {config.STYLE})...")
    run_ffmpeg(
        ["-ss", f"{offset_s:.3f}", "-to", f"{offset_s + dur_s:.3f}",
         "-i", str(segment_path), *r.inputs,
         "-filter_complex", r.fc,
         "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
         "-crf", str(config.VIDEO_CRF),
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", *r.out_args,
         out_file.name],
        desc=out_file.name, cwd=out_dir)
    ass_file.unlink(missing_ok=True)
    for tmp in r.temp:
        Path(tmp).unlink(missing_ok=True)
    fonts.remove_from(out_dir)
    return out_file
