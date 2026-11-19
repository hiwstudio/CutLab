"""Silence/dead-air removal for the 'cut-reframe' mode.

Detects silent stretches, keeps the active (spoken) parts, and compacts them
into one continuous video in a single ffmpeg pass. Also remaps subtitle word
timings onto the compacted timeline so captions stay in sync.
"""
import json
import re
import subprocess
from pathlib import Path

import config
from engine.utils import FFMPEG, has_video, log, probe_duration, run_ffmpeg


def detect_silences(video: Path, noise_db: int = None,
                    min_silence: float = None) -> list:
    """Return [(start, end), ...] silent intervals using ffmpeg silencedetect."""
    noise_db = config.SILENCE_NOISE_DB if noise_db is None else noise_db
    min_silence = config.SILENCE_MIN_LEN if min_silence is None else min_silence
    cmd = [
        FFMPEG, "-hide_banner", "-nostats", "-i", str(video),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    log_text = res.stderr
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", log_text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", log_text)]
    silences = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        silences.append((max(0.0, s), e))
    return silences


def active_ranges(duration: float, silences: list, pad: float = None,
                  min_keep: float = None, merge_gap: float = 0.25) -> list:
    """Complement of the silent intervals = the parts to keep, padded/merged."""
    pad = config.SILENCE_PAD if pad is None else pad
    min_keep = config.SILENCE_MIN_KEEP if min_keep is None else min_keep

    keep, cursor = [], 0.0
    for s, e in silences:
        if e is None:
            e = duration
        if s > cursor:
            keep.append([cursor, s])
        cursor = max(cursor, e)
    if cursor < duration:
        keep.append([cursor, duration])

    # pad each kept range slightly so we don't clip the first/last syllable
    padded = []
    for s, e in keep:
        padded.append([max(0.0, s - pad), min(duration, e + pad)])

    # merge ranges that are now adjacent/overlapping
    merged = []
    for r in padded:
        if merged and r[0] - merged[-1][1] <= merge_gap:
            merged[-1][1] = max(merged[-1][1], r[1])
        else:
            merged.append(r)

    # drop tiny fragments
    ranges = [(round(s, 3), round(e, 3)) for s, e in merged if e - s >= min_keep]
    return ranges or [(0.0, round(duration, 3))]


def reel_ranges(moments: list, min_total: float = None,
                max_total: float = None) -> list:
    """Pick the strongest moments and assemble a highlight reel of min_total..
    max_total seconds. Greedy by score: keep adding the next best moment until
    we're inside the band, then stop (shortest edit that clears the minimum).
    Returns (start, end) ranges in chronological order for compact_video."""
    min_total = config.REEL_MIN_SECONDS if min_total is None else min_total
    max_total = config.REEL_MAX_SECONDS if max_total is None else max_total
    ranked = sorted(moments, key=lambda m: -(m.get("score") or 0))
    picked, total = [], 0.0
    for m in ranked:
        if total >= min_total:
            break                      # shortest edit that clears the floor
        s, e = float(m["start"]), float(m["end"])
        if e <= s:
            continue
        if any(s < pe and e > ps for ps, pe in picked):
            continue                   # overlaps a moment we already kept - skip
        if picked and total + (e - s) > max_total:
            continue                   # would overshoot the cap; try a shorter one
        picked.append((s, e))
        total += e - s
    picked.sort(key=lambda r: r[0])
    return [(round(s, 3), round(e, 3)) for s, e in picked]


def compact_video(video: Path, ranges: list, workdir: Path,
                  out_name: str = "compacted.mp4") -> Path:
    """Keep only `ranges` and concatenate them into one (single pass).
    Works for audio-only inputs too (no video stream)."""
    out_file = workdir / out_name
    if out_file.exists():
        log(f"{out_name} already exists, skipping compaction")
        return out_file
    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in ranges)
    af = f"aselect='{sel}',asetpts=N/SR/TB"
    log(f"Compacting to {len(ranges)} active part(s)...")
    if has_video(video):
        vf = f"select='{sel}',setpts=N/FRAME_RATE/TB"
        args = [
            "-i", str(video), "-vf", vf, "-af", af,
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", out_file.name,
        ]
    else:
        args = [
            "-i", str(video), "-af", af, "-vn",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", out_file.name,
        ]
    run_ffmpeg(args, desc="compact", cwd=workdir)
    return out_file


def remap_segments(segments: list, ranges: list) -> list:
    """Shift word timings from the original timeline onto the compacted one.
    Words inside removed (silent) regions are dropped."""
    comp_start, acc = [], 0.0
    for s, e in ranges:
        comp_start.append(acc)
        acc += (e - s)

    new_words = []
    for seg in segments:
        for w in seg["words"]:
            for idx, (s, e) in enumerate(ranges):
                if w["start"] >= s - 0.05 and w["end"] <= e + 0.05:
                    base = comp_start[idx] - s
                    new_words.append({
                        "start": round(max(0.0, w["start"] + base), 3),
                        "end": round(max(0.0, w["end"] + base), 3),
                        "word": w["word"],
                    })
                    break
    if not new_words:
        return []
    text = " ".join(w["word"] for w in new_words)
    return [{"start": new_words[0]["start"], "end": new_words[-1]["end"],
             "text": text, "words": new_words}]


def cut_silence(video: Path, transcript: dict, workdir: Path):
    """Full cut step: detect silence, compact, remap captions.
    Returns (compacted_path, new_transcript, new_duration).
    Detected ranges are cached in silence.json; compacted.mp4 is reused if
    both exist (a --redo wipes the whole workdir)."""
    duration = probe_duration(video)
    cache = workdir / "silence.json"
    ranges = None
    if cache.exists() and (workdir / "compacted.mp4").exists():
        log("compacted.mp4 already exists, skipping silence detection")
        ranges = [tuple(r) for r in json.loads(cache.read_text(encoding="utf-8"))]
    if ranges is None:
        silences = detect_silences(video)
        ranges = active_ranges(duration, silences)
        cache.write_text(json.dumps(ranges), encoding="utf-8")
    kept = sum(e - s for s, e in ranges)
    log(f"Active content: {kept:.0f}s of {duration:.0f}s "
        f"({100 * kept / duration:.0f}%) across {len(ranges)} part(s).")
    compacted = compact_video(video, ranges, workdir)
    new_segments = remap_segments(transcript.get("segments", []), ranges)
    new_duration = probe_duration(compacted)
    return compacted, {"segments": new_segments, "duration": new_duration}, new_duration
