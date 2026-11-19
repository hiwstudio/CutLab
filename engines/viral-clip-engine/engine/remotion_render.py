"""Add animated Remotion text to a clean (no-subtitle) clip.

Called by run.py when --remotion is set. For each clip it:
  1. Exports transcript words as Remotion Caption JSON
  2. Copies the clean clip into the clip-captions/public/ folder
  3. Calls `npx remotion render CaptionedClip` with hook + duration props
  4. Writes the final output next to the clean clip (suffixed _r)
"""
import json
import shutil
import subprocess
from pathlib import Path

import config
from engine.utils import log

REMOTION_DIR = config.ROOT / "clip-captions"
PUBLIC_DIR = REMOTION_DIR / "public"


def export_captions(transcript: dict, clip_start: float, clip_end: float) -> list:
    captions = []
    for seg in transcript["segments"]:
        for w in seg.get("words", []):
            if w["start"] < clip_start - 0.05 or w["end"] > clip_end + 0.05:
                continue
            start_ms = max(0.0, (w["start"] - clip_start) * 1000)
            end_ms = max(start_ms + 50, (w["end"] - clip_start) * 1000)
            captions.append({
                "text": " " + w["word"].strip(),
                "startMs": round(start_ms),
                "endMs": round(end_ms),
                "timestampMs": round(start_ms),
                "confidence": round(1.0 - seg.get("no_speech_prob", 0.0), 3),
            })
    return captions


def render_with_remotion(clean_clip: Path, moment: dict, transcript: dict,
                         out_path: Path) -> Path:
    """Render animated text onto clean_clip via Remotion → out_path."""
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    clip_dest = PUBLIC_DIR / "clip.mp4"
    shutil.copy2(clean_clip, clip_dest)

    captions = export_captions(transcript, moment["start"], moment["end"])
    (PUBLIC_DIR / "captions.json").write_text(
        json.dumps(captions), encoding="utf-8")

    dur_frames = max(1, int(round((moment["end"] - moment["start"]) * 30)))
    props_file = REMOTION_DIR / "props.json"
    props_file.write_text(json.dumps({
        "hookText": moment.get("hook", ""),
        "durationFrames": dur_frames,
    }), encoding="utf-8")

    log(f"  remotion: rendering text overlay ({dur_frames} frames)...")
    result = subprocess.run(
        f'npx remotion render CaptionedClip "{out_path}" --props props.json',
        cwd=str(REMOTION_DIR),
        stdout=subprocess.DEVNULL,  # progress spam fills pipe buffer → EPIPE
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed:\n{result.stderr[-3000:]}")
    return out_path
