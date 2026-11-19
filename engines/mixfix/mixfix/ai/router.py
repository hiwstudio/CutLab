"""Intelligence Router — decides which brain fulfills each AI task.

Mode 1 (brain=api):      dispatch to the LLM adapter immediately, collect result.
Mode 2 (brain=operator): leave the task pending for the driving agent; the
                         pipeline pauses until a schema-valid result.json exists.
Single-fulfillment is enforced at the state layer (complete_ai_task).
"""
from __future__ import annotations

import json
from pathlib import Path

from .llm_adapter import LLMAdapter
from .tasks import TaskQueue


class Router:
    def __init__(self, brain: str, queue: TaskQueue, adapter: LLMAdapter | None):
        if brain not in ("operator", "api"):
            raise ValueError(f"unknown brain: {brain}")
        if brain == "api" and adapter is None:
            raise ValueError("brain=api requires a configured LLM adapter")
        self.brain = brain
        self.queue = queue
        self.adapter = adapter

    def fulfill(self, run_id: str, stage_name: str, task_type: str,
                payload: dict, files: dict | None = None,
                context: dict | None = None) -> dict | None:
        """Returns the validated result dict, or None if waiting on the operator."""
        # A completed task for this stage short-circuits (idempotent resume).
        done = self.queue.state.done_ai_task(run_id, stage_name, task_type)
        if done:
            return json.loads(done["result_json"])

        task_id = self.queue.raise_task(run_id, stage_name, task_type, payload, files)

        if self.brain == "api":
            # Autonomous System Mode: the LLM API is the intelligence.
            row = self.queue.state.conn.execute(
                "SELECT * FROM ai_tasks WHERE task_id=?", (task_id,)).fetchone()
            request = json.loads(
                (Path(row["request_dir"]) / "request.json").read_text(encoding="utf-8"))
            result = self.adapter.run_task(request)
            self.queue.write_result(task_id, result)
            return self.queue.try_collect(task_id, brain="api", context=context)

        # Claude Code Operator Mode: the driving agent is the intelligence.
        # Zero LLM API calls here — collect a result if the operator wrote one.
        return self.queue.try_collect(task_id, brain="operator", context=context)
