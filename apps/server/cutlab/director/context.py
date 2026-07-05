"""Context compiler (P2): turn a project's EDL + understanding into a compact
brief the LLM reasons over, plus the system prompt that constrains it to CutLab's
op vocabulary.

The director never lets the model touch pixels or raw JSON edits — it may only
emit a plan of ops (A2.2), which the engine validates and applies as a *proposal*
the human accepts or rejects (A2.3). The system prompt spells that out.
"""
from __future__ import annotations

import json

from ..edl.schema import EDL, CaptionClip, MediaClip
from ..understanding.schema import Understanding

# The ops the director is allowed to emit. Deliberately a safe subset: the smart
# ops plus the primitive structural edits. No set_canvas-to-illegal, no asset
# registration ops (those are server-internal).
DIRECTOR_OP_VOCAB = {
    "remove_silence": "{asset, tracks?, min_ms?, ripple?} — cut silent spans of an asset's clips",
    "caption_from_transcript": "{asset, track, max_words?, max_gap_ms?} — add captions from speech",
    "reframe": "{width, height, fps?} — change canvas + center-crop video clips (e.g. 1080x1920)",
    "trim": "{clip, new_in_ms?, new_out_ms?, edge_mode?} — trim a clip",
    "split": "{clip, at_ms} — split a clip at a timeline point",
    "remove_clip": "{clip, ripple?} — remove a clip",
    "move": "{clip, to_start_ms, to_track?} — move a clip",
    "set_speed": "{clip, speed, ripple?} — change a clip's speed (0.1–10)",
    "set_gain": "{clip, gain_db} — change a clip's gain (−60..+12 dB)",
    "delete_range": "{tracks, from_ms, to_ms, ripple?} — delete a timeline range",
    "add_caption": "{track, text, start_ms, end_ms} — add one caption",
    "set_project": "{name?} — rename the project",
}

SYSTEM_PROMPT = f"""You are the edit director inside CutLab, a timeline video editor.
You translate the user's natural-language request into a PLAN of edit operations.

Hard rules:
- Respond with ONLY a JSON object: {{"ops": [ ... ], "note": "one short sentence"}}.
- Each op is one of the allowed operations below, with its exact parameter names.
- All times are integer milliseconds on the TIMELINE (not source time).
- Refer to clips and assets by the ids given in the project brief. Never invent ids.
- You never edit pixels or raw JSON; you only emit ops. The plan is PROPOSED to the
  user, who accepts or rejects it — so prefer a focused, correct plan.
- If the request cannot be done with the allowed ops, return {{"ops": [], "note": "why"}}.

Allowed operations:
{chr(10).join(f"- {name}: {desc}" for name, desc in DIRECTOR_OP_VOCAB.items())}
"""


def _clip_brief(clip) -> dict:
    if isinstance(clip, MediaClip):
        return {
            "id": clip.id, "asset": clip.asset,
            "timeline_ms": [clip.start_ms, clip.end_ms()],
            "source_ms": [clip.in_ms, clip.out_ms],
            "speed": clip.speed, "gain_db": clip.gain_db,
        }
    if isinstance(clip, CaptionClip):
        return {"id": clip.id, "timeline_ms": [clip.start_ms, clip.end_ms],
                "text": clip.text[:60]}
    return {"id": getattr(clip, "id", "?")}


def _understanding_brief(u: Understanding) -> dict:
    return {
        "duration_ms": u.duration_ms,
        "has_transcript": bool(u.transcript and u.transcript.segments),
        "word_count": u.transcript.word_count() if u.transcript else 0,
        "scenes": len(u.scenes),
        "silence_spans": len(u.silence),
        "tempo_bpm": u.tempo_bpm,
    }


def compile_context(edl: EDL, understanding: dict[str, Understanding]) -> dict:
    """A compact, model-friendly JSON brief of the project state."""
    return {
        "canvas": {
            "width": edl.project.canvas.width,
            "height": edl.project.canvas.height,
            "fps": edl.project.canvas.fps,
        },
        "duration_ms": edl.project.duration_ms,
        "assets": {
            aid: {
                "kind": a.kind,
                "duration_ms": a.duration_ms,
                "analyzed": aid in understanding,
                **({"understanding": _understanding_brief(understanding[aid])}
                   if aid in understanding else {}),
            }
            for aid, a in edl.assets.items()
        },
        "tracks": [
            {"id": t.id, "kind": t.kind, "clips": [_clip_brief(c) for c in t.clips]}
            for t in edl.tracks
        ],
    }


def build_prompt(edl: EDL, understanding: dict[str, Understanding], command: str) -> str:
    """The full user-turn prompt: the brief + the request."""
    brief = compile_context(edl, understanding)
    return (
        "PROJECT BRIEF:\n"
        + json.dumps(brief, indent=1)
        + "\n\nUSER REQUEST:\n"
        + command.strip()
        + '\n\nReturn only the JSON plan: {"ops": [...], "note": "..."}.'
    )
