"""Stage: shot/scene detection.

Finds the visual cut boundaries in a video so the recap never starts or ends a
scene mid-shot. Uses ffmpeg's scene-score filter (classical, no model needed).

Produces a list of scenes: [{"start": s, "end": e, "index": i}, ...]
"""
import json
import re
import subprocess
from pathlib import Path

import config
from engine.utils import log, probe_duration


def detect_cut_times(video: Path, threshold: float = None) -> list:
    """Return sorted timestamps (seconds) where a hard visual cut occurs."""
    threshold = config.SCENE_THRESHOLD if threshold is None else threshold
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    times = sorted({round(float(t), 3)
                    for t in re.findall(r"pts_time:([0-9.]+)", res.stderr)})
    return times


def _blind_share(cuts: list, duration: float, cap: float) -> float:
    """Fraction of the runtime sitting inside stretches longer than `cap` with no
    detected cut in them - i.e. how much of the film the matcher cannot see as
    distinct shots."""
    edges = [0.0] + list(cuts) + [duration]
    gaps = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    return sum(g for g in gaps if g > cap) / duration if duration else 0.0


def _detect_with_fallback(video: Path, threshold: float, duration: float):
    """Detect cuts, lowering the threshold if the film turns out to be too dark
    or too low-contrast for it.

    ffmpeg's scene score is a contrast difference, so a fixed threshold is really
    a fixed assumption about how bright a film is. Measured on The Invisible Man
    (2020) - a deliberately dark, low-contrast thriller - the default 0.30 found
    TWO cuts in a ten-minute opening containing roughly thirty shots, and left 57
    of the film's 124 minutes inside just 18 "scenes". Beats then collapse onto
    the same enormous block and the recap shows the same footage several times
    over. Dropping to 0.12 found 23 cuts in that same opening.

    So: detect, measure how much of the runtime is still invisible, and if too
    much is, try again lower. Returns (cuts, threshold_actually_used).
    """
    cap = config.SCENE_BLIND_CAP_SECONDS
    for attempt in range(config.SCENE_THRESHOLD_RETRIES + 1):
        cuts = [t for t in detect_cut_times(video, threshold)
                if 0.05 < t < duration]
        blind = _blind_share(cuts, duration, cap)
        if blind <= config.SCENE_BLIND_MAX_SHARE or                 attempt == config.SCENE_THRESHOLD_RETRIES:
            if attempt:
                log(f"  scene threshold settled at {threshold:.2f} "
                    f"({blind * 100:.0f}% of runtime still in >{cap:.0f}s blocks)")
            return cuts, threshold
        log(f"  threshold {threshold:.2f} leaves {blind * 100:.0f}% of the film "
            f"in >{cap:.0f}s blocks with no cuts - too dark for it, lowering")
        threshold *= config.SCENE_THRESHOLD_STEP
    return cuts, threshold


def detect_scenes(video: Path, threshold: float = None,
                  min_len: float = None, workdir: Path = None) -> list:
    """Split the video into scenes at the detected cuts, merging shots shorter
    than min_len so we don't get flickery micro-cuts.

    If workdir is given, the result is cached to workdir/scenes.json and reused
    on rerun (same resume-on-disk pattern as transcription)."""
    threshold = config.SCENE_THRESHOLD if threshold is None else threshold
    min_len = config.SCENE_MIN_LEN if min_len is None else min_len

    out = workdir / "scenes.json" if workdir is not None else None
    if out is not None and out.exists():
        log("scenes.json already exists, skipping scene detection")
        return json.loads(out.read_text(encoding="utf-8"))

    duration = probe_duration(video)
    cuts, threshold = _detect_with_fallback(video, threshold, duration)
    boundaries = [0.0] + cuts + [duration]

    # build raw scenes, then merge any that are too short into the previous one
    scenes = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        if e - s < min_len and scenes:
            scenes[-1]["end"] = e          # merge tiny shot into previous
        else:
            scenes.append({"start": round(s, 3), "end": round(e, 3)})
    for i, sc in enumerate(scenes):
        sc["index"] = i
    log(f"Scene detection: {len(scenes)} scenes "
        f"(threshold {threshold}, min {min_len}s) over {duration:.0f}s.")

    if out is not None:
        out.write_text(json.dumps(scenes, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return scenes
