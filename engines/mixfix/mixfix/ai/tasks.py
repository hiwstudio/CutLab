"""AI task queue — the file handshake shared by both brains.

A task lives at ai_tasks/pending/<task_id>/:
    request.json  — task_type, instructions, payload, output schema description
    (optional files: frames, transcripts, ...)
The task completes when a schema-valid result.json appears in that directory.
Completed task dirs move to ai_tasks/done/<task_id>/.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import schemas
from ..state import State

from . import sourcing

TASK_INSTRUCTIONS = {
    "write_script": (
        "Write documentary narration for the given topic/research package. "
        "Return JSON with keys: narration (the plain narration text), "
        "elevenlabs_script (narration formatted for ElevenLabs), "
        "aistudio_script (narration formatted for Google AI Studio TTS)."
    ),
    "scene_breakdown": (
        "Group the given transcript segments into scenes for a documentary. "
        "Return JSON: {\"scenes\": [{\"id\": \"scene_001\", \"segment_ids\": [...], "
        "\"visual_intent\": \"what the audience should see\"}]}. Every segment id "
        "must appear in exactly one scene; keep scenes 1-4 segments long."
    ),
    "visual_plan": (
        "You are the visual director. For EACH scene decide, with full context, "
        "the strongest way to tell that part of the story, then produce what the "
        "engine needs to source or generate it. Works for ANY topic (cars, tech, "
        "history, science, finance, sports, nature, business, product reviews, "
        "education, etc.) — nothing here is automotive-specific.\n\n"
        "PER-SCENE DECISION — before defaulting to stock footage, ask:\n"
        " • Is this explaining a concept, describing an object, or introducing a "
        "place/person/technology?\n"
        " • Is a comparison being made?\n"
        " • Is a SPECIFIC, recognizable subject named (a product, vehicle, "
        "building, animal, historical object, piece of equipment)?\n"
        " • Would a purpose-built custom visual communicate this more clearly than "
        "whatever generic clip a stock search would return?\n"
        "If yes → visual_type 'generate'. If real, literal footage of the subject "
        "genuinely exists and reads better (real events, real places in motion, "
        "real demos) → visual_type 'video' with youtube queries. Do NOT generate "
        "every scene — choose per scene whichever tells the story strongest. A "
        "typical mix is fine.\n\n"
        "BE EXTREMELY SPECIFIC when generating. Describe the EXACT subject the "
        "narration names, not a generic stand-in: a named Ferrari model rendered "
        "with its correct design, a Lamborghini Revuelto that clearly reads as a "
        "Revuelto, the actual building/animal/device/person-type discussed — never "
        "'a generic red sports car' when a specific one is meant. (When depicting "
        "real third-party brands, capture the authentic design by silhouette and "
        "detail but do not render real logos/badges/wordmarks — image models "
        "garble them.)\n\n"
        "CONTEXT-AWARE + CONTINUITY. Write every generated shot considering the "
        "narration, the surrounding scenes, the emotional tone, the pacing and the "
        "project's style, so visuals feel like one film, not isolated inserts. To "
        "guarantee visual consistency you MUST also return a project-wide "
        "'style_lock': ONE block of text (render style, lens, environment, colour "
        "language, quality, and hard negatives like 'no logos/text') that will be "
        "prepended VERBATIM to every generated prompt. The per-shot text carries "
        "ONLY that shot's unique subject/composition — the style_lock carries "
        "everything shared. (This is how the FlowDeck/Google-Flow pipeline holds "
        "consistency; it is text-only, so identical anchoring text is the lever.)\n\n"
        "SEGMENTING A 'generate' SCENE. A longer scene should become several timed "
        "image beats, not one static image — one per distinct visual moment in the "
        "narration. Each segment has an absolute start_ms (the first MUST equal the "
        "scene's start_ms; the rest ascend within the scene) and a 'delta' — the "
        "specific shot description for that beat. Let pacing decide the count.\n\n"
        "Return JSON: {\"style_lock\": \"...\" (required if any generate), "
        "\"plans\": [ {\"scene_id\": \"scene_001\", \"visual_type\": "
        "\"video\"|\"generate\", \"queries\": [\"youtube query\", ...] (video), "
        "\"reason\": \"why generate beats stock here\" (generate), \"segments\": "
        "[{\"start_ms\": 0, \"delta\": \"the exact shot for this beat\"}, ...] "
        "(generate) } ]}. Cover every scene exactly once.\n\n"
        "(Legacy: visual_type \"image\" with a single \"image_prompt\" is still "
        "accepted for a one-still scene.) Original video-scene contract:\n"
        "{\"scene_id\": \"scene_001\", \"visual_type\": \"video\", "
        "\"queries\": [\"youtube search query\", ...] (required for video), "
        "\"image_prompt\": \"generation prompt\" (required for image)}]}. "
        "Cover every scene exactly once. Prefer 2-3 specific, footage-oriented "
        "search queries per video scene.\n\n"
        "SOURCING THE 'video' SCENES — those clips are pulled off YouTube by "
        "the same research stage, ranked by the same scorer and reviewed on the "
        "same board as every other mode, so the same rules apply:\n\n"
        + sourcing.block(sourcing.ARCHIVE_FIRST, sourcing.WRITING_QUERIES,
                         sourcing.AIM_FOR_SUPPORT, sourcing.MOMENT,
                         sourcing.PROVEN_SOURCES)
        + "\n\nSo a 'video' plan may also carry \"moment\": "
          "\"action\"|\"talking\"|\"any\", and the result may carry a "
          "top-level \"archive_queries\": [...] when the piece is about one "
          "event."
    ),
    "replace_plan": (
        "You are planning visual overlays for an existing talking video (FIX "
        "mode). The original audio plays untouched; overlays temporarily cover "
        "the picture with contextual footage. Given transcript segments, shot "
        "boundaries, and face-presence samples, pick the segment stretches that "
        "benefit most from an overlay. Return JSON: {\"scenes\": [{\"id\": "
        "\"scene_001\", \"segment_ids\": [...], \"visual_intent\": \"what to "
        "show\", \"queries\": [\"youtube search query\", ...]}]}. Rules (payload "
        "gives limits): an overlay must not exceed max_cover_ms, and the "
        "original footage must return between overlays for at least min_gap_ms. "
        "Prefer overlaying stretches where no face is on screen. Do NOT cover "
        "every segment — only where footage genuinely helps."
    ),
    "select_clip": (
        "You are the archival researcher choosing reference footage for one "
        "scene. The payload lists a SHORTLIST of candidate clips; the attached "
        "images are named c<i>_*.jpg, where <i> is the candidate index — a few "
        "frames spanning that candidate's window.\n\n"
        "THESE ARE USUALLY STORYBOARD PREVIEWS: low-resolution thumbnails pulled "
        "without downloading the video, so a human can then open your pick at its "
        "timestamp (payload 'watch_at') and confirm it. Judge SUBJECT and gross "
        "COMPOSITION from them — is this the thing named, is it real footage or a "
        "title card / talking head / on-screen text — and do not fail a candidate "
        "merely for looking soft, since the preview is soft by nature. Your job is "
        "to hand the human strong candidates, not to make the final cut.\n\n"
        "Look at every candidate's frames, then pick the single strongest — or "
        "none, if they all fail.\n\n"
        "THE RULE THAT OVERRIDES EVERYTHING: reference footage exists to "
        "visually SUPPORT what is being said. It does not have to recreate it. "
        "The viewer glances at it and thinks 'yes, that is what he is talking "
        "about'. That is satisfied by the right SUBJECT, not the right INSTANT.\n\n"
        "Classify your chosen candidate on the relevance ladder:\n"
        " • 'exact'   — the specific moment described\n"
        " • 'subject' — the named person/place/thing, a different moment "
        "(other footage of that person speaking, competing, arriving)\n"
        " • 'topic'   — the event or concept honestly represented\n"
        " • 'generic' — could illustrate any story; stock wallpaper\n"
        " • 'wrong'   — different subject, or contradicts the narration\n"
        "'subject' and 'topic' are ACCEPTABLE and are what editors cut with most "
        "of the time. Do NOT reject a good 'subject' clip while holding out for "
        "an 'exact' clip that may not exist. Only 'generic' and 'wrong' fail.\n\n"
        "PRESENTATION GATE — independent of relevance. Reject what the preview "
        "still shows clearly even at low resolution: a phone filming a TV (bezel, "
        "off-axis); nested picture-in-picture or reaction/watchalong layouts; "
        "large watermarks or burned-in lower thirds; a full-screen title or text "
        "card. Do NOT reject for mere softness or low detail — that is the preview, "
        "not the footage, and the human confirms sharpness on the real clip.\n\n"
        "Prefer, in order: acceptable tier + clean presentation > higher tier with "
        "worse presentation. Between two similar candidates take the one whose "
        "framing reads at a glance.\n\n"
        "WHEN THE PREVIEW IS TOO COARSE TO BE SURE: if the subject is right but you "
        "cannot rule out a thin lower-third, a small corner watermark, or motion the "
        "tile may have frozen past, still pick the candidate AND set 'caution' to a "
        "short phrase naming the doubt (e.g. 'possible lower-third, confirm on the "
        "clip'). Do not silently accept it and do not reject a good subject for a "
        "doubt you cannot confirm — the caution routes it to a human, who confirms "
        "on the deep-link. Leave 'caution' null when the frames are clearly clean.\n\n"
        "Return JSON: {\"choice\": <index into the shortlist, or null if none are "
        "usable>, \"tier\": \"exact|subject|topic\" (required when choice is not "
        "null), \"confidence\": 0-100 int, \"reason\": \"one sentence naming what "
        "is on screen and why it supports (or fails) the narration\", \"caution\": "
        "\"short phrase the human must confirm, or null\", "
        "\"best_start_ms\": int or null, \"best_end_ms\": int or null (optional "
        "tighter sub-range measured from that candidate's clip start)}."
    ),
    "verify_clip": (
        "You are verifying that an extracted video clip visually supports a "
        "narration scene. Look at the attached frame images (frame_*.jpg, sampled "
        "1/sec in order) and the scene text + visual intent in the payload. "
        "Return JSON: {\"confidence\": 0-100 int (does the footage SHOW what the "
        "narration needs?), \"reason\": \"one sentence\", \"best_start_ms\": int or "
        "null, \"best_end_ms\": int or null (optional tighter sub-range measured "
        "from clip start)}. Be strict: topic-adjacent but visually wrong = low."
    ),
}


class TaskQueue:
    def __init__(self, state: State, root: Path):
        self.state = state
        self.root = Path(root)
        self.pending_dir = self.root / "pending"
        self.done_dir = self.root / "done"
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)

    def raise_task(self, run_id: str, stage_name: str, task_type: str,
                   payload: dict, files: dict[str, Path] | None = None) -> str:
        """Create a pending task (idempotent per stage: reuse an open one)."""
        existing = self.state.pending_ai_task(run_id, stage_name, task_type)
        if existing:
            return existing["task_id"]
        task_id = self.state.create_ai_task(run_id, stage_name, task_type, "")
        task_dir = self.pending_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        request = {
            "task_id": task_id,
            "task_type": task_type,
            "instructions": TASK_INSTRUCTIONS[task_type],
            "payload": payload,
            "result_file": "result.json (write it in this directory)",
        }
        (task_dir / "request.json").write_text(
            json.dumps(request, indent=2), encoding="utf-8")
        if files:
            for name, src in files.items():
                shutil.copy2(src, task_dir / name)
        with self.state.conn:
            self.state.conn.execute(
                "UPDATE ai_tasks SET request_dir=? WHERE task_id=?",
                (str(task_dir), task_id))
        return task_id

    def try_collect(self, task_id: str, brain: str,
                    context: dict | None = None) -> dict | None:
        """Validate + consume a result.json if present. None = still pending.

        Raises schemas.SchemaError on a malformed result (task stays pending;
        the bad result.json is renamed so it can be corrected).
        """
        row = self.state.conn.execute(
            "SELECT * FROM ai_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown task {task_id}")
        if row["status"] == "done":
            return json.loads(row["result_json"])
        task_dir = Path(row["request_dir"])
        result_path = task_dir / "result.json"
        if not result_path.exists():
            return None
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            schemas.validate(row["task_type"], result, context)
        except (json.JSONDecodeError, schemas.SchemaError) as e:
            result_path.rename(task_dir / "result.rejected.json")
            raise schemas.SchemaError(
                f"result.json for {task_id} rejected: {e}. "
                f"Fix it and write result.json again in {task_dir}") from e
        self.state.complete_ai_task(task_id, brain, result)
        dest = self.done_dir / task_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(task_dir), str(dest))
        return result

    def supersede(self, run_id: str, stage_prefix: str, reason: str) -> int:
        """Abandon pending tasks under `stage_prefix` and clear their dirs out of
        pending/, so neither the DB count nor the operator's task list shows work
        that nothing will ever consume. Returns how many were superseded."""
        rows = self.state.supersede_ai_tasks(run_id, stage_prefix, reason)
        for row in rows:
            task_dir = Path(row["request_dir"])
            if not task_dir.is_dir():
                continue
            dest = self.done_dir / task_dir.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(task_dir), str(dest))
        return len(rows)

    def write_result(self, task_id: str, result: dict) -> None:
        """Used by the API brain to drop its result into the task dir."""
        row = self.state.conn.execute(
            "SELECT * FROM ai_tasks WHERE task_id=?", (task_id,)).fetchone()
        (Path(row["request_dir"]) / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8")
