"""Adaptive visual analysis — vision only when the transcript isn't enough.

The scorer flags candidates it can't judge from words alone (needs_visual).
For ONLY those clips, this stage downloads a cheap low-res sample of the
window, extracts a few frames, and runs a vision review that confirms,
adjusts, or rejects the clip. Unflagged clips never touch this path, so
straightforward videos pay zero extra cost.

Verdicts are merged back into moments.json (visual_reviewed: true), so the
review runs once per clip ever.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from . import config, youtube
from .moments import OperatorTask, weighted_score
from .utils import FFMPEG, log, probe_duration
import subprocess

VISION_PROMPT = """You are finishing the judgment of ONE candidate short-form \
clip. The transcript alone was not enough — the attached frames (sampled \
evenly across the clip window, in order) show what actually happens on \
screen. The transcript-only subscores are included below.

Using the frames, decide what the visuals add or remove: real reactions and \
expressions, physical comedy, demonstrations, visual payoff — or nothing \
(static talking heads, unusable footage, the referenced event not visible).

Respond with ONLY strict JSON:
{"verdict": "keep" or "reject",
 "subscores": {"hook":0,"self_containment":0,"payoff":0,"emotion":0,\
"quotability":0,"density":0,"duration_fit":0},
 "visual_notes": "<1-2 lines: what the frames show and how they changed \
your judgment>"}
Return the FULL corrected subscores (0-10 integers), not deltas."""


def _flagged(clips: list) -> list:
    return [c for c in clips
            if c.get("needs_visual") and not c.get("visual_reviewed")]


def _backfill_text(flagged: list, project_dir: Path) -> None:
    """Recover each clip's transcript from select_task.json.

    Clips reloaded from an operator-written moments.json carry no "text" —
    only the LLM path merges it in — so the review task shipped an empty
    transcript and the reviewer judged the frames blind. select_task.json
    holds the same windows keyed by candidate_id.
    """
    if all(c.get("text") for c in flagged):
        return
    task = project_dir / "select_task.json"
    if not task.exists():
        return
    by_cand = {c.get("candidate_id"): c.get("text", "") for c
               in json.loads(task.read_text(encoding="utf-8-sig"))["candidates"]}
    for c in flagged:
        if not c.get("text"):
            c["text"] = by_cand.get(c.get("candidate_id"), "")


def ensure_frames(clip: dict, project_dir: Path, url: str) -> list:
    """Low-res sample + evenly spaced frames for one flagged clip. Cached."""
    # candidate_id, not clip_id — see the note in pipeline.stage_download
    vdir = project_dir / "visual" / clip.get("candidate_id", clip["clip_id"])
    frames = sorted(vdir.glob("frame_*.jpg"))
    if len(frames) >= config.VISUAL_FRAMES:
        return frames
    vdir.mkdir(parents=True, exist_ok=True)
    sample = vdir / "sample.mp4"
    if not sample.exists():
        log(f"  {clip['clip_id']}: downloading {config.VISUAL_SAMPLE_RES}p "
            "sample for visual analysis...")
        youtube.download_section(url, clip["start_ms"], clip["end_ms"], sample,
                                 max_res=config.VISUAL_SAMPLE_RES)
    dur = probe_duration(sample)
    n = config.VISUAL_FRAMES
    for i in range(n):
        out = vdir / f"frame_{i + 1:02d}.jpg"
        if out.exists():
            continue
        t = dur * (i + 0.5) / n
        subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{t:.2f}", "-i", str(sample),
             "-frames:v", "1", "-q:v", "4", str(out)],
            capture_output=True, text=True, check=True)
    return sorted(vdir.glob("frame_*.jpg"))


def review(clips: list, project_dir: Path, url: str) -> None:
    """Visually review every flagged clip; merge verdicts into moments.json.
    No-op when nothing is flagged."""
    flagged = _flagged(clips)
    if not flagged:
        return
    log(f"Visual analysis needed for {len(flagged)} clip(s) "
        f"(transcript wasn't enough): {', '.join(c['clip_id'] for c in flagged)}")
    _backfill_text(flagged, project_dir)
    for c in flagged:
        c["frames"] = [str(p) for p in ensure_frames(c, project_dir, url)]

    if config.LLM_ENABLED:
        verdicts = {c["clip_id"]: _llm_vision(c) for c in flagged}
    else:
        verdicts = _operator_vision(flagged, project_dir)

    moments_file = project_dir / "moments.json"
    stored = json.loads(moments_file.read_text(encoding="utf-8-sig"))
    by_cand = {m.get("candidate_id"): m for m in stored}
    for c in flagged:
        v = verdicts.get(c["clip_id"], {})
        m = by_cand.get(c.get("candidate_id"))
        targets = [t for t in (c, m) if t is not None]
        for t in targets:
            t["visual_reviewed"] = True
            t["visual_notes"] = v.get("visual_notes", "")
            if str(v.get("verdict", "keep")).lower() == "reject":
                t["disqualified"] = True
                t["disqualify_reason"] = "visual review: " + v.get("visual_notes", "")
            elif v.get("subscores"):
                t["subscores"] = v["subscores"]
                t["score"] = weighted_score(v["subscores"])
        log(f"  {c['clip_id']}: {v.get('verdict', 'keep')} "
            f"(score {c.get('score')}) — {v.get('visual_notes', '')[:80]}")
    moments_file.write_text(json.dumps(stored, ensure_ascii=False, indent=1),
                            encoding="utf-8")


def _llm_vision(clip: dict) -> dict:
    """Send frames + context to the multimodal model."""
    from openai import OpenAI
    from .moments import _parse_json_obj
    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)
    content = [{"type": "text", "text": json.dumps({
        "transcript": clip.get("text", "")[:3000],
        "duration_s": round((clip["end_ms"] - clip["start_ms"]) / 1000, 1),
        "transcript_only_subscores": clip.get("subscores", {}),
        "rationale_so_far": clip.get("rationale", ""),
    }, ensure_ascii=False)}]
    for f in clip["frames"]:
        b64 = base64.b64encode(Path(f).read_bytes()).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL, max_tokens=800, temperature=0.2,
                messages=[{"role": "system", "content": VISION_PROMPT},
                          {"role": "user", "content": content}])
            return _parse_json_obj(resp.choices[0].message.content)
        except Exception as e:
            log(f"  vision attempt {attempt + 1} failed for "
                f"{clip['clip_id']}: {e}")
    return {"verdict": "keep", "visual_notes": "vision call failed; kept as-is"}


def _operator_vision(flagged: list, project_dir: Path) -> dict:
    """Operator mode: write the task (frames + context) and pause; consume
    visual_verdicts.json when the operator has written it."""
    verdict_file = project_dir / "visual_verdicts.json"
    if verdict_file.exists():
        return json.loads(verdict_file.read_text(encoding="utf-8-sig"))
    task = project_dir / "visual_task.json"
    task.write_text(json.dumps({
        "instructions": (
            "OPERATOR TASK — visual review. For each clip below, look at its "
            "frames (paths listed) and finish the judgment the transcript "
            "couldn't: do the visuals deliver (reactions, physical comedy, "
            "demonstrations, visual payoff) or not (static heads, event not "
            "visible)? Write visual_verdicts.json next to this file as "
            '{"clip_01": {"verdict": "keep"|"reject", "subscores": {full '
            "corrected 0-10 subscores}, \"visual_notes\": \"1-2 lines\"}, ...} "
            "then rerun clipinn."),
        "clips": [{
            "clip_id": c["clip_id"],
            "start_ms": c["start_ms"], "end_ms": c["end_ms"],
            "transcript": c.get("text", "")[:2000],
            "transcript_only_subscores": c.get("subscores", {}),
            "frames": c["frames"],
        } for c in flagged],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    raise OperatorTask(
        f"Visual review needed: inspect the frames listed in\n  {task}\n"
        f"and write verdicts to {verdict_file}, then rerun.")
