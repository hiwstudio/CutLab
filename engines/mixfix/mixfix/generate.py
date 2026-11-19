"""Custom-visual generation: turn 'generate' visual-plan scenes into FlowDeck
jobs, and (once the images come back) into timed Ken-Burns montage clips.

The visual_plan AI task decides per scene between stock 'video' and custom
'generate'. For every generate scene this module:
  1. writes a FlowDeck-compatible JSON job (imagery/prompts/<scene>.flowdeck.json)
     whose every prompt = style_lock + " SHOT: " + segment.delta, so the whole
     project shares one byte-identical consistency block (see
     lessons/flowdeck-image-workflow.md);
  2. after the user generates the images and drops them into
     imagery/incoming/<scene>/<scene>_<n>.png, builds a montage clip whose image
     timing follows the plan's segment start_ms exactly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FD_DEFAULTS = {"interPromptDelayMs": 6000, "retries": 1, "timeoutMs": 120000}
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _job(name: str, folder: str, prompts: list[tuple[str, str]]) -> dict:
    return {
        "schemaVersion": 2,
        "project": {"name": name, "outputFolder": folder,
                    "aspectRatio": "16:9", "defaults": FD_DEFAULTS},
        "prompts": [{"id": pid, "filename": pid, "prompt": text}
                    for pid, text in prompts],
    }


def emit_flowdeck_jobs(project_dir: Path, plan: dict, style_lock: str) -> list[str]:
    """Write a master-ref job + one job per generate scene. Returns scene ids."""
    out_dir = project_dir / "imagery" / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    proj = project_dir.name
    lock = (style_lock or "").strip()
    written = []

    master = (lock + " SHOT: definitive establishing hero frame that sets the "
              "exact look, colour, lighting and lens for the entire sequence.")
    (out_dir / "_master-ref.flowdeck.json").write_text(
        json.dumps(_job(f"{proj}-master-ref", f"{proj}/master-ref",
                        [("_master_ref", master)]), indent=2), encoding="utf-8")
    written.append("_master_ref")

    for p in plan["plans"]:
        if p.get("visual_type") != "generate":
            continue
        sid = p["scene_id"]
        prompts = [(f"{sid}_{i + 1}", f"{lock} SHOT: {s['delta'].strip()}")
                   for i, s in enumerate(p["segments"])]
        (out_dir / f"{sid}.flowdeck.json").write_text(
            json.dumps(_job(f"{proj}-{sid}", f"{proj}/{sid}", prompts), indent=2),
            encoding="utf-8")
        written.append(sid)
    return written


def montage_durations(segments: list[dict], scene_end_ms: int) -> list[int]:
    """Per-image durations from segment start_ms; last image runs to scene end."""
    starts = [s["start_ms"] for s in segments]
    return ([starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
            + [scene_end_ms - starts[-1]])


def scene_images(project_dir: Path, scene_id: str, n: int) -> list[Path] | None:
    """The n ordered images for a scene, or None if any are still missing.

    Looks in imagery/incoming/<scene_id>/ and imagery/<scene_id>/ — the latter
    mirrors FlowDeck's own outputFolder layout, which is where images naturally
    land when you copy a finished job across.
    """
    img = project_dir / "imagery"
    folder = next((d for d in (img / "incoming" / scene_id, img / scene_id)
                   if d.is_dir()), None)
    if folder is None:
        return None
    imgs = []
    for k in range(1, n + 1):
        matches = [m for m in sorted(folder.glob(f"{scene_id}_{k}.*"))
                   if m.suffix.lower() in IMG_EXTS]
        if not matches:
            return None
        imgs.append(matches[0])
    return imgs


def ensure_images(project_dir: Path, entry: dict, style_lock: str,
                  tool: str, model: str = "") -> tuple[int, str]:
    """Create any images a 'generate' scene is still missing, with the shared
    generator (`gemini_image.py`), and file them where `scene_images` looks.

    Shelled out rather than imported: the generator is a machine-global tool, not
    a package, and its path is config so this engine is not pinned to one box.

    Never raises. A generator that is absent, keyless or refusing must fall back
    to the FlowDeck hand-off — losing automation is acceptable, losing the run is
    not. Returns (images_written, error_message).
    """
    import subprocess
    import tempfile

    sid = entry["scene_id"]
    if not tool or not Path(tool).exists():
        return 0, f"image tool not found at {tool!r}"
    folder = project_dir / "imagery" / sid
    folder.mkdir(parents=True, exist_ok=True)

    made = 0
    for k, seg in enumerate(entry.get("segments") or [], 1):
        if any(folder.glob(f"{sid}_{k}.*")):
            continue                                   # idempotent resume
        # The style lock leads so every shot in the scene shares a look; the
        # per-segment delta is what actually differs between them.
        prompt = "\n\n".join(x for x in (style_lock.strip(),
                                         str(seg.get("delta", "")).strip()) if x)
        if not prompt:
            return made, f"{sid} segment {k} has no prompt"
        with tempfile.TemporaryDirectory() as td:
            cmd = [sys.executable, str(tool), "--prompt", prompt,
                   "--out", td, "-n", "1"]
            if model:
                cmd += ["--model", model]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=420)
            except subprocess.TimeoutExpired:
                return made, f"{sid} image {k}: generator timed out"
            produced = sorted(Path(td).glob("image-*"))
            if r.returncode != 0 or not produced:
                detail = (r.stderr or r.stdout or "").strip().splitlines()
                return made, f"{sid} image {k}: {detail[-1] if detail else 'no image'}"
            produced[0].replace(folder / f"{sid}_{k}{produced[0].suffix}")
            made += 1
    return made, ""
