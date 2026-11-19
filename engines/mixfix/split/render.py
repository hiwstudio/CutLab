"""SPLIT renderer — speaker on top, reference footage below, word on the seam.

Moved out of mixfix/assemble.py so the core renderer owns MIX and FIX only.
Everything here is specific to the split-screen format.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mixfix import timing
from mixfix.assemble import (_clip_len_ms, _even, _fill, _filter_path, _run,
                             _segment, _segment_key, _write_concat)


def write_word_ass(tmap: dict, out: Path, w: int, seam_y: int,
                   style: dict | None = None) -> Path:
    """One-word-at-a-time captions pinned to the split seam (the KOReels look).

    ASS rather than N drawtext filters: hundreds of word events cost one filter
    and libass does the layout. Each word holds until the next one starts, so
    the seam is never empty mid-sentence.
    """
    s = style or {}
    # 5% of frame height: a fixed pixel size is either lost at 1920 or fills the
    # frame at 360, and this renders at both
    size = int(s.get("size") or max(12, round(seam_y * 2 * 0.05)))
    colour = s.get("colour", "&H0000FFFF")   # ASS is &HAABBGGRR — this is yellow
    outline = int(s.get("outline") or max(2, round(size * 0.07)))
    words = [x for x in tmap.get("words", []) if x.get("text", "").strip()]

    def ts(ms: int) -> str:
        ms = max(0, ms)
        s_, ms_ = divmod(ms, 1000)
        m_, s_ = divmod(s_, 60)
        h_, m_ = divmod(m_, 60)
        return f"{h_:d}:{m_:02d}:{s_:02d}.{ms_ // 10:02d}"

    end_of = tmap["source"]["duration_ms"]
    lines = []
    for i, word in enumerate(words):
        start = word["start_ms"]
        # hold until the next word so the seam never blinks empty between words
        stop = words[i + 1]["start_ms"] if i + 1 < len(words) else min(
            word["end_ms"] + 400, end_of)
        if stop <= start:
            continue
        text = word["text"].strip().upper().replace("\n", " ")
        lines.append(f"Dialogue: 0,{ts(start)},{ts(stop)},W,,0,0,0,,"
                     f"{{\\an5\\pos({w // 2},{seam_y})}}{text}")
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {seam_y * 2}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: W,Arial,{size},{colour},&H00000000,&H00000000,-1,0,1,"
        f"{outline},0,5,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def render_split(project_dir: Path, tl: dict, tmap: dict, cfg: dict,
                 source: Path) -> Path:
    """SPLIT render: the source video fills the top pane for the whole runtime,
    sourced reference footage fills the bottom pane per scene, stacked into one
    frame. The original audio is copied, never re-encoded — same contract as FIX.
    """
    r = cfg["render"]
    sp = cfg.get("split", {})
    w, h, fps = r["width"], r["height"], r["fps"]
    top_h = _even(round(h * float(sp.get("top_fraction", 0.5))))
    bot_h = _even(h - top_h)
    total_ms = tmap["source"]["duration_ms"]
    scenes = sorted(tl["scenes"], key=lambda s: s["start_ms"])
    if not scenes:
        raise RuntimeError("split render needs at least one scene")
    # ponytail: hard cuts in the bottom lane, no crossfade — the reference format
    # cuts hard and a transition here would need the two lanes time-locked.
    bounds = [0] + [s["start_ms"] for s in scenes[1:]] + [total_ms]

    seg_dir = project_dir / "assembly" / "split_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    pieces = []
    for i, scene in enumerate(scenes):
        seg_ms = bounds[i + 1] - bounds[i]
        if seg_ms <= 0:
            continue
        p = seg_dir / f"{i:03d}_{_segment_key(scene, seg_ms, w, bot_h, fps)}.mp4"
        _segment(scene, seg_ms, p, w, bot_h, fps, fill=True)
        pieces.append(p)
    keep = {q.name for q in pieces}
    for stale in seg_dir.glob("*.mp4"):
        if stale.name not in keep:
            stale.unlink()

    concat = project_dir / "assembly" / "split_concat.txt"
    _write_concat(concat, pieces)
    bottom = project_dir / "assembly" / "bottom.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(concat), "-an",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
          "-crf", "20", "-t", f"{total_ms / 1000:.3f}", str(bottom)])

    graph = [f"[0:v]{_fill(w, top_h, fps)}[top]",
             f"[1:v]{_fill(w, bot_h, fps)}[bot]",
             "[top][bot]vstack=inputs=2[stacked]"]
    last = "stacked"
    if sp.get("word_captions", True):
        ass = write_word_ass(tmap, project_dir / "assembly" / "words.ass",
                             w, top_h, sp.get("caption_style"))
        graph.append(f"[{last}]ass='{_filter_path(ass)}'[v]")
        last = "v"

    out = project_dir / "assembly" / "render.mp4"
    # +faststart puts moov ahead of mdat. Without it the review board can load
    # the file but cannot SEEK it, so clicking a scene does nothing until the
    # whole video has downloaded (mixfix/assemble.py carries the same note).
    _run(["-i", str(source), "-i", str(bottom),
          "-filter_complex", ";".join(graph), "-map", f"[{last}]",
          "-map", "0:a:0", "-t", f"{total_ms / 1000:.3f}",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
          "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return out
