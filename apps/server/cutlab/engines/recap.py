"""Recap Engine (P5) — pure logic, adapted from the owner's recap-engine.

Story compression: outline the source (map-reduce over the transcript), write
original narration beats, match each beat to source scenes (time prior +
dialogue similarity), and emit an EDL ops plan that the render engine realizes.
The LLM calls and Piper TTS live in jobs/recap.py; everything here is pure.

Adaptations from the bundled Recap Engine (see DECISIONS.md):
  - prompts carried over near-verbatim (they're production-tuned)
  - matching: time prior (w=0.5) + dialogue token-overlap (w=0.15); the CLIP
    visual term (w=0.35) is deferred — its weight slot remains so adding the
    ONNX models later is a config change, not a redesign
  - assembly emits EDL ops (clips + ducked gain + narration audio track)
    instead of running ffmpeg — CutLab's render engine does that
  - length policy: accept natural TTS duration (owner's locked decision)
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from ..understanding.schema import Scene, Understanding

NARRATION_WPM = 200          # measured Piper lessac rate (owner's calibration)
DUCK_ORIGINAL_DB = -25.0     # original audio under narration
MATCH_W_TIME = 0.5
MATCH_W_DIALOGUE = 0.15
# ponytail: CLIP visual matching (w=0.35) deferred until the ONNX models are
# wired in; time prior dominates in the owner's tuning anyway.
MATCH_TIME_WINDOW_S = 180.0
OUTLINE_CHUNK_CHARS = 8000
OUTLINE_CHUNK_OVERLAP = 400

OUTLINE_MAP_SYSTEM = (
    "You extract story structure from film/episode transcripts. Output JSON only."
)
REDUCE_SYSTEM = (
    "You are a film story editor. You receive ordered story beats extracted from "
    "consecutive parts of a single movie. Merge them into ONE coherent, "
    "deduplicated story bible that covers the whole film beginning to end, "
    "including the ending. Keep chronological order. Output JSON only."
)
SCRIPT_SYSTEM = (
    "You are a professional story-recap narrator and screenwriter. You write the "
    "ORIGINAL voiceover that retells a film's plot from beginning to end: "
    "chronological, clear, and engaging in a narrator's voice. Rules: never copy "
    "dialogue verbatim - describe what happens in your own words; cover the WHOLE "
    "story including the ending (this is a full spoiler recap); keep it faithful "
    "to the outline. Output JSON only."
)


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# -- transcript chunking + prompts ---------------------------------------------


def transcript_chunks(u: Understanding,
                      max_chars: int = OUTLINE_CHUNK_CHARS,
                      overlap_chars: int = OUTLINE_CHUNK_OVERLAP) -> list[dict]:
    """Time-ordered [timestamped] text chunks for the map pass."""
    if not u.transcript:
        return []
    lines = [
        f"[{_fmt_ts(s.start_ms / 1000)}] {s.text}"
        for s in u.transcript.segments if s.text.strip()
    ]
    spans = [(s.start_ms / 1000, s.end_ms / 1000) for s in u.transcript.segments
             if s.text.strip()]
    chunks: list[dict] = []
    buf: list[str] = []
    size = 0
    start_idx = 0
    for i, line in enumerate(lines):
        buf.append(line)
        size += len(line) + 1
        if size >= max_chars or i == len(lines) - 1:
            chunks.append({
                "start": spans[start_idx][0], "end": spans[i][1],
                "text": "\n".join(buf),
            })
            # overlap tail so a beat spanning the boundary isn't lost
            tail: list[str] = []
            tsize = 0
            j = i
            while j >= start_idx and tsize < overlap_chars:
                tail.insert(0, lines[j])
                tsize += len(lines[j]) + 1
                j -= 1
            buf = list(tail)
            size = tsize
            start_idx = max(start_idx, j + 1)
    return chunks


def map_prompt(chunk: dict, idx: int, total: int) -> str:
    return (
        f"This is part {idx + 1} of {total} of a film transcript, covering "
        f"roughly {_fmt_ts(chunk['start'])}-{_fmt_ts(chunk['end'])}.\n\n"
        "Extract the ordered story beats in THIS part only. For each beat give:\n"
        '  "title": short label, "summary": 1-2 sentences of what happens,\n'
        '  "approx_start": seconds (float) when it begins (use the [timestamps]),\n'
        '  "approx_end": seconds (float) when it ends.\n\n'
        'Return JSON: {"beats": [ {"title","summary","approx_start","approx_end"} ]}\n\n'
        "TRANSCRIPT PART:\n"
        f"{chunk['text']}"
    )


def reduce_prompt(chunk_beats: list, duration_s: float) -> str:
    return (
        f"Below are story beats from a film about {_fmt_ts(duration_s)} long, in "
        "order. Some may overlap at part boundaries - merge duplicates and smooth "
        "the arc into a single outline.\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "logline": "one-sentence summary of the whole film",\n'
        '  "characters": [ {"name","description"} ],\n'
        '  "setting": "where/when the story takes place",\n'
        '  "beats": [ {"title","summary","approx_start","approx_end"} ],\n'
        '  "ending": "how the film resolves"\n'
        "}\n"
        "The beats array must read start-to-finish as the complete plot.\n\n"
        "EXTRACTED BEATS:\n"
        f"{json.dumps(chunk_beats, ensure_ascii=False)}"
    )


def script_prompt(outline: dict, target_minutes: int) -> str:
    budget_words = int(target_minutes * NARRATION_WPM)
    return (
        "Write the recap narration for this film, based on the story outline "
        "below.\n\n"
        f"TARGET LENGTH: about {target_minutes} minutes spoken, which is roughly "
        f"{budget_words} words TOTAL across all beats. Stay close to this budget.\n\n"
        "Split the narration into ordered beats that follow the plot in order. "
        "For each beat provide:\n"
        '  "narration": the original voiceover prose for this beat,\n'
        '  "approx_start": the source time (seconds) this beat describes,\n'
        '  "approx_end": the source end time (seconds).\n'
        "Carry approx_start/approx_end from the matching outline beats so each "
        "narration beat is anchored to where it happens in the film.\n\n"
        'Return JSON: {"beats": [ {"narration","approx_start","approx_end"} ]}\n\n'
        "STORY OUTLINE:\n"
        f"{json.dumps(outline, ensure_ascii=False)}"
    )


def parse_beats(data: dict | list) -> list[dict]:
    """Normalize an LLM beats reply -> [{order, narration, approx_start,
    approx_end, target_seconds}] (empty narrations dropped)."""
    beats = data.get("beats", data) if isinstance(data, dict) else data
    if not isinstance(beats, list):
        return []
    script: list[dict] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        narration = str(b.get("narration") or "").strip()
        if not narration:
            continue
        words = len(narration.split())
        script.append({
            "order": len(script),
            "narration": narration,
            "approx_start": float(b.get("approx_start") or 0.0),
            "approx_end": float(b.get("approx_end") or 0.0),
            "target_seconds": round(words / NARRATION_WPM * 60.0, 2),
        })
    return script


# -- beat -> scene matching ------------------------------------------------------


_WORD_RE = re.compile(r"[a-z']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _scene_dialogue(scene: Scene, u: Understanding) -> str:
    if not u.transcript:
        return ""
    return " ".join(
        s.text for s in u.transcript.segments
        if s.start_ms < scene.end_ms and s.end_ms > scene.start_ms
    )


def match_beats(beats: list[dict], u: Understanding) -> list[dict]:
    """Assign each beat an anchor scene + enough consecutive scenes to cover its
    narration duration. Score = time prior + dialogue token overlap."""
    scenes = u.scenes or [Scene(index=0, start_ms=0, end_ms=u.duration_ms)]
    dialogues = [_tokens(_scene_dialogue(sc, u)) for sc in scenes]

    for b in beats:
        anchor_s = (b["approx_start"] + b["approx_end"]) / 2 or 0.0
        best_i, best_score = 0, -1.0
        beat_tokens = _tokens(b["narration"])
        for i, sc in enumerate(scenes):
            mid_s = (sc.start_ms + sc.end_ms) / 2000
            dt = abs(mid_s - anchor_s)
            time_score = math.exp(-dt / MATCH_TIME_WINDOW_S)
            dlg = dialogues[i]
            overlap = (len(beat_tokens & dlg) / len(beat_tokens | dlg)
                       if beat_tokens and dlg else 0.0)
            score = MATCH_W_TIME * time_score + MATCH_W_DIALOGUE * overlap
            if score > best_score:
                best_i, best_score = i, score

        # Coverage: extend across consecutive scenes until the footage covers
        # the narration (owner's coverage rule; margin 0.5s).
        need_ms = int((b["target_seconds"] + 0.5) * 1000)
        i0 = i1 = best_i
        covered = scenes[best_i].end_ms - scenes[best_i].start_ms
        while covered < need_ms and (i1 + 1 < len(scenes) or i0 > 0):
            if i1 + 1 < len(scenes):
                i1 += 1
                covered += scenes[i1].end_ms - scenes[i1].start_ms
            elif i0 > 0:
                i0 -= 1
                covered += scenes[i0].end_ms - scenes[i0].start_ms
        b["scenes"] = [scenes[i].model_dump() for i in range(i0, i1 + 1)]
        b["match_score"] = round(best_score, 4)
    return beats


# -- EDL assembly plan -----------------------------------------------------------


@dataclass
class RecapAsset:
    """A narration wav to register: the job synthesized + probed it."""
    asset_id: str
    src: str            # relative to project dir
    duration_ms: int


def plan_recap_edl(
    source_asset_id: str,
    beats: list[dict],
    narration: list[RecapAsset],
    video_track: str = "trk_recapv",
    audio_track: str = "trk_recapn",
) -> list[dict]:
    """Ops plan for the recap timeline (applied in propose mode by the job):
    per beat, the matched footage (speed-fitted to the narration, original
    audio ducked) + the narration clip. Tracks are created fresh so the recap
    proposal composes on an empty-ish timeline or alongside existing tracks."""
    assert len(beats) == len(narration)
    ops: list[dict] = [
        {"op": "add_track", "kind": "video", "id": video_track},
        {"op": "add_track", "kind": "audio", "id": audio_track},
    ]
    for n in narration:
        ops.append({
            "op": "add_asset", "asset_id": n.asset_id, "kind": "audio",
            "src": n.src, "duration_ms": n.duration_ms,
        })

    t = 0
    for b, n in zip(beats, narration):
        span_start = int(b["scenes"][0]["start_ms"])
        span_end = int(b["scenes"][-1]["end_ms"])
        span = span_end - span_start
        target = n.duration_ms
        # Fit footage to narration: trim when there's plenty; slow down
        # (>=0.5x) when the matched span is shorter than the narration.
        speed = max(0.5, min(1.0, span / target))
        src_len = min(span, int(target * speed))
        ops.append({
            "op": "add_clip", "track": video_track, "asset": source_asset_id,
            "in_ms": span_start, "out_ms": span_start + max(50, src_len),
            "start_ms": t, "speed": round(speed, 4),
            "gain_db": DUCK_ORIGINAL_DB,
        })
        ops.append({
            "op": "add_clip", "track": audio_track, "asset": n.asset_id,
            "in_ms": 0, "out_ms": target, "start_ms": t,
        })
        t += target
    return ops
