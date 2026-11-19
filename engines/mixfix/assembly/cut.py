"""Join the fetched windows behind the hook into one file.

The output is written to `input/source.mp4` on purpose: from that point the run
is an ordinary FIX run over a video, and every downstream stage — timing_map,
fix_shots, timeline, render_fix, render_qa, export — needs no knowledge that the
file was assembled rather than downloaded.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from mixfix.research import cut_section
from mixfix.tools import FFMPEG


def _run(args: list[str]) -> None:
    proc = subprocess.run([FFMPEG, "-v", "error", "-y", *args],
                          capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(proc.stderr or '')[-400:]}")


def _duration_ms(path: Path) -> int:
    from mixfix.tools import FFPROBE
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return int(round(float(out) * 1000))


def hook_source(plan: dict) -> dict:
    """The window the hook is lifted from.

    The hook is a sub-range of one selected window, never material outside the
    section — a teaser promising something the video does not contain is a bait
    the retention curve punishes at the exact moment it resolves.
    """
    h = plan["hook"]
    for w in plan["windows"]:
        if (w["source_start_ms"] <= h["source_start_ms"]
                and h["source_end_ms"] <= w["source_end_ms"]):
            return w
    raise ValueError(
        f"hook [{h['source_start_ms']},{h['source_end_ms']}] is not inside any "
        "selected window — it must be lifted from the section itself")


def build_cut(project_dir: Path, plan: dict, cfg: dict) -> tuple[Path, int, int]:
    """Returns (cut_path, hook_ms, body_ms)."""
    win_dir = project_dir / "assembly" / "windows"
    out = project_dir / "input" / "source.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    host = hook_source(plan)
    h = plan["hook"]
    hook_clip = project_dir / "assembly" / "hook.mp4"
    if not hook_clip.exists():
        cut_section(win_dir / f"{host['id']}.mp4", hook_clip,
                    h["source_start_ms"] - host["source_start_ms"],
                    h["source_end_ms"] - host["source_start_ms"])

    pieces = [hook_clip] + [win_dir / f"{w['id']}.mp4" for w in plan["windows"]]
    missing = [p.name for p in pieces if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing cut pieces: {missing}")

    concat = project_dir / "assembly" / "cut_concat.txt"
    concat.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in pieces), encoding="utf-8")

    # Re-encoded rather than stream-copied. Every piece already went through
    # cut_section's encoder so the parameters match, but concat's stream-copy
    # path still splices timestamps rather than rebuilding them, and a podcast
    # cut is exactly the case where a drifting audio PTS turns into visible lip
    # desync twenty minutes in. One clean pass is worth the minutes.
    if not out.exists():
        _run(["-f", "concat", "-safe", "0", "-i", str(concat),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
              "-movflags", "+faststart", str(out)])

    hook_ms = _duration_ms(hook_clip)
    body_ms = sum(w["source_end_ms"] - w["source_start_ms"]
                  for w in plan["windows"])
    return out, hook_ms, body_ms
