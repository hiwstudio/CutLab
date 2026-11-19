"""SPLIT pipeline — MixFix's core with the split-plan stage added.

A subclass, not a fork: intake, timing, research, timeline, QA and export are
identical to FIX and every fix to them lands here for free. Only the plan and
the renderer differ.
"""
from __future__ import annotations

import json

from mixfix import timing
from mixfix.ai.schemas import SchemaError
from mixfix.pipeline import Pipeline

# SPLIT reuses FIX's intake and every downstream stage; only the plan differs.
# No fix_shots: the speaker holds the top pane for the whole runtime, so shot
# boundaries and face presence — which exist to decide when covering the
# speaker is safe — have nothing to decide.
SPLIT_STAGES = ["fix_intake", "timing_map", "split_plan", "research_extract",
                "timeline", "assemble", "render_qa", "export"]

SPLIT_KNOBS = {"split_plan": ["split"], "assemble": ["render", "split"]}


class SplitPipeline(Pipeline):
    def _handlers(self) -> dict:
        return {**super()._handlers(), "split_plan": self.stage_split_plan}

    def stage_split_plan(self) -> str:
        """Plan the bottom pane, scene by scene. Same result shape as
        replace_plan (scenes + queries) so research_extract, the timeline and
        the review board consume it unchanged — only the rules differ."""
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        payload = {
            "segments": [{"id": s["id"], "text": s["text"],
                          "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                         for s in tmap["segments"]],
            # what has actually yielded usable footage before, so query style
            # improves run over run instead of starting cold every time
            "proven_sources": self.proven_sources(),
        }
        context = {"segment_bounds": {s["id"]: [s["start_ms"], s["end_ms"]]
                                      for s in tmap["segments"]}}
        try:
            result = self.router.fulfill(
                self.run_id, "split_plan", "split_plan",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "split_plan", "split_plan")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"
        tmap = timing.attach_scenes(tmap, result)
        timing.save(tmap, self.project_dir / "timing" / "timing_map.json")
        plan_path = self.project_dir / "research" / "visual_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps({
            "archive_queries": result.get("archive_queries") or [],
            "plans": [{"scene_id": sc["id"], "visual_type": "video",
                       "queries": sc["queries"],
                       # carried into research so the WINDOW can be chosen by
                       # position, not just by what words were spoken over it
                       "moment": sc.get("moment", "any")}
                      for sc in result["scenes"]]},
            indent=2), encoding="utf-8")
        n_arch = len(result.get("archive_queries") or [])
        self.state.stage_finish(self.run_id, "split_plan", "done",
                                {"scenes": len(result["scenes"]),
                                 "archive_queries": n_arch})
        self.say(f"Split plan: {len(result['scenes'])} bottom-pane scene(s)"
                 + (f", {n_arch} archive quer{'y' if n_arch == 1 else 'ies'}"
                    if n_arch else " (no archive — per-scene search only)"))
        return "done"
