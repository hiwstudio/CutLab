"""Render QA suite (render-qa conventions) — export is blocked without a pass.

Checks: stream sanity, duration vs Timing Map, black frames, frozen frames,
silence gaps, integrated loudness. Every check reports evidence; passed =
all checks passed.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .tools import FFMPEG, FFPROBE

DEFAULTS = {
    "duration_tolerance_ms": 200,
    "max_black_s": 0.5,
    # static visuals (images, mostly-still clips) are a product feature;
    # only stretches longer than any reasonable scene count as frozen
    "max_freeze_s": 12.0,
    "max_silence_s": 2.0,
    "target_lufs": -16,
    "lufs_tolerance": 3.0,
    # Luminance below which a pixel counts as black. 0.10 is generous — a
    # legitimately dark subject (deep space, night exterior) sits above true
    # black but under 10%, so a whole genre of correct footage reads as a black
    # frame. Lower it per-run on the render_qa node when the piece is dark BY
    # DESIGN and the frames still carry a clear subject. Do not lower it to
    # silence sparse inserts that really are dead air — fix those in the art
    # (see lessons/dark-motion-graphics-trip-black-frame-qa.md).
    "black_pix_th": 0.10,
}


def _ffmpeg_stderr(args: list[str]) -> str:
    proc = subprocess.run([FFMPEG, "-v", "info", "-nostats", *args,
                           "-f", "null", "-"],
                          capture_output=True, text=True)
    return proc.stderr


def _black_stretches(video: Path, max_black_s: float,
                     pix_th: float = DEFAULTS["black_pix_th"]) -> list[tuple[float, float]]:
    err = _ffmpeg_stderr(["-i", str(video), "-an",
                          "-vf", f"blackdetect=d={max_black_s}:pix_th={pix_th}"])
    return [(float(s), float(d)) for s, d in
            re.findall(r"black_start:([\d.]+).*?black_duration:([\d.]+)", err)]


def run_qa(video: Path, tmap: dict, cfg: dict,
           check_loudness: bool = True,
           baseline_video: Path | None = None,
           check_silence: bool = True) -> dict:
    t = {**DEFAULTS, **cfg.get("qa", {}), "target_lufs":
         cfg.get("render", {}).get("target_lufs", DEFAULTS["target_lufs"])}
    checks = {}

    # --- stream sanity ---
    probe = json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(video)], capture_output=True, text=True,
        check=True).stdout)
    vstreams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    astreams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    r = cfg["render"]
    # accept the compatible 8-bit 4:2:0 family (limited yuv420p and full-range
    # yuvj420p from JPEG sources both play everywhere); reject 4:4:4 / 10-bit,
    # which is what actually breaks Windows/TV/hardware decoders
    compatible_pix = {"yuv420p", "yuvj420p"}
    stream_ok = (len(vstreams) == 1 and len(astreams) == 1
                 and vstreams[0]["width"] == r["width"]
                 and vstreams[0]["height"] == r["height"]
                 and vstreams[0].get("pix_fmt") in compatible_pix)
    checks["streams"] = {
        "passed": stream_ok,
        "video_streams": len(vstreams), "audio_streams": len(astreams),
        "pix_fmt": vstreams[0].get("pix_fmt") if vstreams else None,
        "resolution": f"{vstreams[0]['width']}x{vstreams[0]['height']}"
                      if vstreams else None}

    # --- duration vs Timing Map ---
    dur_ms = int(round(float(probe["format"]["duration"]) * 1000))
    want = tmap["source"]["duration_ms"]
    delta = abs(dur_ms - want)
    checks["duration"] = {"passed": delta <= t["duration_tolerance_ms"],
                          "rendered_ms": dur_ms, "timing_map_ms": want,
                          "delta_ms": delta}

    # --- black frames ---
    # FIX mode: black stretches inherited from the original video (its own
    # fades/cuts) are not render defects — only NEW black stretches fail.
    blacks = _black_stretches(video, t["max_black_s"], t["black_pix_th"])
    inherited = []
    if baseline_video is not None and blacks:
        base = _black_stretches(baseline_video, t["max_black_s"],
                                t["black_pix_th"])
        def is_inherited(s):
            return any(abs(s[0] - b[0]) <= 1.5 for b in base)
        inherited = [b for b in blacks if is_inherited(b)]
        blacks = [b for b in blacks if not is_inherited(b)]
    checks["black_frames"] = {
        "passed": not blacks,
        "stretches_s": [d for _, d in blacks],
        "inherited_from_source_s": [d for _, d in inherited]}

    # --- frozen frames ---
    err = _ffmpeg_stderr(["-i", str(video), "-an",
                          "-vf", f"freezedetect=n=-60dB:d={t['max_freeze_s']}"])
    freezes = re.findall(r"freeze_duration: ([\d.]+)", err)
    checks["frozen_frames"] = {"passed": not freezes,
                               "stretches_s": [float(f) for f in freezes]}

    # --- silence ---
    # Only meaningful when WE produced the audio. A passthrough mode stream-copies
    # the source, so a pause in the source is the source's, not a render defect —
    # the same reasoning that already exempts loudness and baseline-compares black
    # frames. Measured: an assembly failed on five 1.6-2.5s gaps, every one of them
    # a conversational pause deep inside a window, none at a cut we made.
    err = _ffmpeg_stderr(["-i", str(video), "-vn",
                          "-af", f"silencedetect=noise=-45dB:d={t['max_silence_s']}"])
    silences = re.findall(r"silence_duration: ([\d.]+)", err)
    checks["silence"] = {"passed": (not silences) or not check_silence,
                         "gaps_s": [float(s) for s in silences],
                         "judged": check_silence}

    # --- loudness ---
    err = _ffmpeg_stderr(["-i", str(video), "-vn", "-af", "ebur128"])
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    lufs = float(m[-1]) if m else None
    checks["loudness"] = {
        "passed": not check_loudness or (
            lufs is not None
            and abs(lufs - t["target_lufs"]) <= t["lufs_tolerance"]),
        "integrated_lufs": lufs, "target_lufs": t["target_lufs"],
        "enforced": check_loudness}

    return {"video": str(video),
            "passed": all(c["passed"] for c in checks.values()),
            "checks": checks, "thresholds": t}
