"""Timeline builder + edits + Visual Enhancement Score.

The timeline is a review/edit view derived from the Timing Map scenes layer,
research progress (alternatives), and the visual plan. Edits update timeline
data (never rendered video); the pipeline rebuilds and the preview refreshes.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .tools import FFMPEG

from . import timing


def _thumb(clip: Path, out: Path, at_s: float = 0.5) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-ss", str(at_s), "-i", str(clip),
         "-frames:v", "1", "-vf", "scale=320:-2", str(out)],
        check=True, capture_output=True)


def build(project_dir: Path) -> dict:
    """Assemble timeline.json from timing map + visual plan + research progress."""
    tmap = timing.load(project_dir / "timing" / "timing_map.json")
    plan_path = project_dir / "research" / "visual_plan.json"
    plans = {}
    if plan_path.exists():
        plans = {p["scene_id"]: p for p in
                 json.loads(plan_path.read_text(encoding="utf-8"))["plans"]}
    prog_path = project_dir / "research" / "progress.json"
    progress = (json.loads(prog_path.read_text(encoding="utf-8"))
                if prog_path.exists() else {})

    prev = load(project_dir) or {"scenes": []}
    prev_by_id = {s["id"]: s for s in prev.get("scenes", [])}

    scenes = []
    for sc in tmap["scenes"]:
        sid = sc["id"]
        seg_text = " ".join(s["text"] for s in tmap["segments"]
                            if s["id"] in sc["segment_ids"])
        plan = plans.get(sid, {})
        entry = {
            "id": sid,
            "start_ms": sc["start_ms"],
            "end_ms": sc["end_ms"],
            "duration_ms": sc["end_ms"] - sc["start_ms"],
            "narration": seg_text,
            "visual_intent": sc["visual_intent"],
            "visual_type": plan.get("visual_type", "video"),
            "visual": None,
            "alternatives": [],
            "review": prev_by_id.get(sid, {}).get("review", "pending"),
        }
        if sc.get("assets"):
            a = sc["assets"][0]
            old = prev_by_id.get(sid, {}).get("visual") or {}
            entry["visual"] = {
                "asset_id": a["asset_id"], "path": a["path"], "kind": a["kind"],
                "confidence": a.get("confidence"),
                "trim_in_ms": old.get("trim_in_ms", 0),
                "trim_out_ms": old.get("trim_out_ms", entry["duration_ms"]),
            }
            thumb = project_dir / "timeline" / "thumbs" / f"{sid}.jpg"
            try:
                _thumb(Path(a["path"]), thumb)
                entry["visual"]["thumb"] = str(thumb)
            except subprocess.CalledProcessError:
                pass
        if entry["visual_type"] == "image":
            entry["image_prompt"] = plan.get("image_prompt", "")
            incoming = list((project_dir / "imagery" / "incoming").glob(f"{sid}.*"))
            entry["image_ready"] = bool(incoming)
            if incoming:
                entry["visual"] = {"kind": "image", "path": str(incoming[0]),
                                   "asset_id": None,
                                   "trim_in_ms": 0,
                                   "trim_out_ms": entry["duration_ms"]}
        st = progress.get(sid, {})
        accepted_idx = st.get("accepted", {}).get("candidate_idx")
        # what is playing RIGHT NOW, with its link and window — the reviewer needs
        # to see the current source next to the alternatives, not just its filename
        if entry["visual"] and accepted_idx is not None:
            cands = st.get("candidates", [])
            if 0 <= accepted_idx < len(cands):
                c = cands[accepted_idx]
                entry["visual"]["source"] = {
                    "title": c.get("title"), "channel": c.get("channel"),
                    "url": c.get("url"), "clip_start_ms": c.get("clip_start_ms"),
                    "clip_end_ms": c.get("clip_end_ms"),
                    "manual": bool(c.get("manual")),
                }
        for i, c in enumerate(st.get("candidates", [])):
            if i != accepted_idx:
                # .get throughout: a hand-picked candidate has no lexical score
                # and never went through the ranker, so it carries fewer fields
                entry["alternatives"].append(
                    {"candidate_idx": i, "title": c.get("title", "(untitled)"),
                     "channel": c.get("channel", ""), "url": c.get("url"),
                     "clip_start_ms": c.get("clip_start_ms", 0),
                     "clip_end_ms": c.get("clip_end_ms", 0),
                     "score": c.get("score"), "manual": bool(c.get("manual"))})
        scenes.append(entry)

    tl = {"project": tmap["meta"].get("project", project_dir.name),
          "total_ms": tmap["source"]["duration_ms"],
          "scenes": scenes}
    tl["score"] = score(tl)
    save(project_dir, tl)
    return tl


def score(tl: dict) -> dict:
    """Visual Enhancement Score — computed metrics, no vibes."""
    scenes = tl["scenes"]
    total = sum(s["duration_ms"] for s in scenes) or 1
    covered = sum(s["duration_ms"] for s in scenes if s["visual"])
    # longest consecutive uncovered stretch
    stretch = cur = 0
    for s in scenes:
        cur = 0 if s["visual"] else cur + s["duration_ms"]
        stretch = max(stretch, cur)
    assets = [s["visual"]["asset_id"] for s in scenes
              if s["visual"] and s["visual"].get("asset_id")]
    confs = [s["visual"]["confidence"] for s in scenes
             if s["visual"] and s["visual"].get("confidence") is not None]
    weak = [s["id"] for s in scenes
            if not s["visual"]
            or (s["visual"].get("confidence") or 100) < 70]
    return {
        "coverage_pct": round(100 * covered / total, 1),
        "max_uncovered_stretch_ms": stretch,
        "variety_index": round(len(set(assets)) / len(assets), 2) if assets else 0.0,
        "confidence_floor": min(confs) if confs else None,
        "weak_scenes": weak,
    }


# ---- edits ----
class EditError(ValueError):
    pass


def apply_edit(project_dir: Path, tl: dict, edit: dict) -> dict:
    """Apply one edit to timeline data. Returns the updated timeline.
    Actions: trim | remove_visual | approve_clip | reject_clip | swap_alternative
             | set_window
    """
    action = edit.get("action")
    scene = next((s for s in tl["scenes"] if s["id"] == edit.get("scene_id")), None)
    if scene is None:
        raise EditError(f"unknown scene_id: {edit.get('scene_id')}")

    if action == "trim":
        if not scene["visual"]:
            raise EditError(f"{scene['id']} has no visual to trim")
        tin, tout = int(edit["trim_in_ms"]), int(edit["trim_out_ms"])
        if not 0 <= tin < tout:
            raise EditError("need 0 <= trim_in_ms < trim_out_ms")
        scene["visual"]["trim_in_ms"] = tin
        scene["visual"]["trim_out_ms"] = tout
    elif action == "remove_visual":
        scene["visual"] = None
        scene["review"] = "rejected"
        _clear_scene_asset(project_dir, scene["id"])
    elif action == "approve_clip":
        scene["review"] = "approved"
    elif action in ("reject_clip", "swap_alternative"):
        # Send the scene back to research: clear asset, point progress at the
        # requested (or next) candidate; the next `mixfix run` re-verifies.
        scene["visual"] = None
        scene["review"] = "pending"
        _clear_scene_asset(project_dir, scene["id"])
        prog_path = project_dir / "research" / "progress.json"
        progress = json.loads(prog_path.read_text(encoding="utf-8"))
        st = progress[scene["id"]]
        if action == "swap_alternative":
            st["candidate_idx"] = int(edit["candidate_idx"])
            # a swap is a human decision, not a hint: mark it so the shortlist
            # offers this clip alone instead of re-auditioning it against two
            # others the reviewer already passed over
            cands = st.get("candidates", [])
            if 0 <= st["candidate_idx"] < len(cands):
                cands[st["candidate_idx"]]["chosen"] = True
        else:
            st["candidate_idx"] = st.get("accepted", {}).get(
                "candidate_idx", st.get("candidate_idx", 0)) + 1
        st["status"] = "verifying"
        st.pop("accepted", None)
        prog_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    elif action == "set_window":
        _set_window(project_dir, scene, edit)
    else:
        raise EditError(f"unknown action: {action}")

    tl["score"] = score(tl)
    save(project_dir, tl)
    return tl


_VIDEO_ID = re.compile(r"(?:v=|be/|shorts/|embed/)([\w-]{11})")


def _set_window(project_dir: Path, scene: dict, edit: dict) -> None:
    """Hand-pick the exact source window for a scene.

    `trim` moves the in/out points INSIDE a clip already on disk. This is the
    other operation: "use 1:10–1:15 of that video", a window nothing has fetched
    yet. It appends a candidate flagged `manual`, which the ranker never scores
    or reorders — a human choice must not be demoted by the machine — and sends
    the scene back to research so the next run fetches exactly that.
    """
    url = str(edit.get("url") or "").strip()
    m = _VIDEO_ID.search(url)
    if not m:
        raise EditError("need a YouTube URL containing a video id")
    try:
        start, end = int(edit["start_ms"]), int(edit["end_ms"])
    except (KeyError, TypeError, ValueError):
        raise EditError("start_ms and end_ms must be integers (ms)") from None
    if start < 0 or end <= start:
        raise EditError("need 0 <= start_ms < end_ms")

    prog_path = project_dir / "research" / "progress.json"
    progress = (json.loads(prog_path.read_text(encoding="utf-8"))
                if prog_path.exists() else {})
    st = progress.setdefault(scene["id"],
                             {"status": "new", "candidate_idx": 0, "candidates": []})
    cand = {"video_id": m.group(1), "url": url,
            "title": str(edit.get("title") or "").strip() or "hand-picked window",
            "channel": "you", "clip_start_ms": start, "clip_end_ms": end,
            "manual": True}
    st.setdefault("candidates", []).append(cand)
    # point the cursor at it so the shortlist offers this and nothing before it
    st["candidate_idx"] = len(st["candidates"]) - 1
    st["status"] = "verifying"
    st.pop("accepted", None)
    prog_path.parent.mkdir(parents=True, exist_ok=True)
    prog_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")

    scene["visual"] = None            # nothing to show until it is fetched
    scene["review"] = "pending"
    _clear_scene_asset(project_dir, scene["id"])


def _clear_scene_asset(project_dir: Path, scene_id: str) -> None:
    tmap = timing.load(project_dir / "timing" / "timing_map.json")
    for sc in tmap["scenes"]:
        if sc["id"] == scene_id:
            sc["assets"] = []
    timing.save(tmap, project_dir / "timing" / "timing_map.json")


def save(project_dir: Path, tl: dict) -> None:
    p = project_dir / "timeline" / "timeline.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tl, indent=2), encoding="utf-8")


def load(project_dir: Path) -> dict | None:
    p = project_dir / "timeline" / "timeline.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
