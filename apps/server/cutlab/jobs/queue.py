"""Durable SQLite-backed job queue.

Jobs are rows in the `jobs` table. Progress through a job is checkpointed as
named stages whose artifacts (file paths) are recorded in `artifacts_json`.
On worker startup every `running` job is reset to `queued` (attempts += 1,
or `failed` once attempts exhaust); execution then resumes at the first stage
whose artifacts are missing or fail the integrity check (exists + size > 0).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ..config import JOB_MAX_ATTEMPTS
from ..db import Database, dumps, utcnow
from ..util.ids import new_job_id

# Called with the full job row after every mutation (for WS broadcast).
EventCallback = Callable[[dict[str, Any]], None]


class JobCancelled(Exception):
    pass


class JobQueue:
    def __init__(self, db: Database, on_event: EventCallback | None = None):
        self.db = db
        self.on_event = on_event

    # -- lifecycle -----------------------------------------------------------

    def enqueue(self, kind: str, input: dict[str, Any], project_id: str | None = None) -> str:
        job_id = new_job_id()
        now = utcnow()
        self.db.execute(
            "INSERT INTO jobs (id, kind, project_id, input_json, state, progress,"
            " artifacts_json, attempts, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'queued', 0, '{}', 0, ?, ?)",
            (job_id, kind, project_id, dumps(input), now, now),
        )
        self._emit(job_id)
        return job_id

    def claim(self) -> dict[str, Any] | None:
        """Atomically claim the oldest queued job. Returns the row or None."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE state='queued' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE jobs SET state='running', error=NULL, updated_at=? WHERE id=?",
                (utcnow(), row["id"]),
            )
        job = self.get(row["id"])
        self._emit(row["id"])
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if row:
            row["input"] = json.loads(row["input_json"])
            row["artifacts"] = json.loads(row["artifacts_json"])
        return row

    def cancel(self, job_id: str) -> bool:
        cur = self.db.execute(
            "UPDATE jobs SET state='cancelled', updated_at=? "
            "WHERE id=? AND state IN ('queued','running')",
            (utcnow(), job_id),
        )
        if cur.rowcount:
            self._emit(job_id)
        return bool(cur.rowcount)

    def recover_on_start(self) -> list[str]:
        """Reset crashed (`running`) jobs to `queued`; exhaust attempts -> failed."""
        recovered: list[str] = []
        for row in self.db.query("SELECT id, attempts FROM jobs WHERE state='running'"):
            attempts = row["attempts"] + 1
            if attempts >= JOB_MAX_ATTEMPTS:
                self.db.execute(
                    "UPDATE jobs SET state='failed', attempts=?, error=?, updated_at=? WHERE id=?",
                    (attempts, "max attempts exceeded after crash", utcnow(), row["id"]),
                )
            else:
                self.db.execute(
                    "UPDATE jobs SET state='queued', attempts=?, updated_at=? WHERE id=?",
                    (attempts, utcnow(), row["id"]),
                )
            recovered.append(row["id"])
            self._emit(row["id"])
        return recovered

    # -- progress / checkpointing --------------------------------------------

    def set_stage(self, job_id: str, stage: str) -> None:
        self.db.execute(
            "UPDATE jobs SET stage=?, updated_at=? WHERE id=?", (stage, utcnow(), job_id)
        )
        self._emit(job_id)

    def set_progress(self, job_id: str, progress: float) -> None:
        self.db.execute(
            "UPDATE jobs SET progress=?, updated_at=? WHERE id=?",
            (min(max(progress, 0.0), 1.0), utcnow(), job_id),
        )
        self._emit(job_id)

    def checkpoint(self, job_id: str, stage: str, artifacts: Any) -> None:
        """Record a completed stage's artifacts (path, list of paths, or dict)."""
        job = self.get(job_id)
        assert job is not None
        all_artifacts = job["artifacts"]
        all_artifacts[stage] = artifacts
        self.db.execute(
            "UPDATE jobs SET artifacts_json=?, stage=?, updated_at=? WHERE id=?",
            (dumps(all_artifacts), stage, utcnow(), job_id),
        )
        self._emit(job_id)

    def finish(self, job_id: str, state: str, error: str | None = None) -> None:
        assert state in ("done", "failed", "cancelled")
        progress_sql = ", progress=1.0" if state == "done" else ""
        self.db.execute(
            f"UPDATE jobs SET state=?, error=?, updated_at=?{progress_sql} WHERE id=?",
            (state, error, utcnow(), job_id),
        )
        self._emit(job_id)

    def fail_or_requeue(self, job_id: str, error: str) -> str:
        """After an exception: bump attempts; requeue unless attempts exhausted."""
        job = self.get(job_id)
        assert job is not None
        attempts = job["attempts"] + 1
        state = "failed" if attempts >= JOB_MAX_ATTEMPTS else "queued"
        self.db.execute(
            "UPDATE jobs SET state=?, attempts=?, error=?, updated_at=? WHERE id=?",
            (state, attempts, error, utcnow(), job_id),
        )
        self._emit(job_id)
        return state

    def is_cancelled(self, job_id: str) -> bool:
        row = self.db.query_one("SELECT state FROM jobs WHERE id=?", (job_id,))
        return row is not None and row["state"] == "cancelled"

    def _emit(self, job_id: str) -> None:
        if self.on_event:
            job = self.get(job_id)
            if job:
                self.on_event(job)


def artifacts_valid(artifacts: Any) -> bool:
    """Integrity check: every referenced file exists and has size > 0."""
    paths: list[str] = []
    if isinstance(artifacts, str):
        paths = [artifacts]
    elif isinstance(artifacts, list):
        paths = [p for p in artifacts if isinstance(p, str)]
    elif isinstance(artifacts, dict):
        for v in artifacts.values():
            if isinstance(v, str):
                paths.append(v)
            elif isinstance(v, list):
                paths.extend(p for p in v if isinstance(p, str))
    if not paths:
        return False
    for p in paths:
        f = Path(p)
        # Non-path metadata entries (e.g. logged ffmpeg commands) are skipped.
        if not f.is_absolute():
            continue
        if not f.exists() or f.stat().st_size == 0:
            return False
    return True


class JobContext:
    """Passed to job handlers; provides checkpointed stage execution."""

    def __init__(self, queue: JobQueue, job: dict[str, Any]):
        self.queue = queue
        self.job = job
        self.job_id = job["id"]
        self.input = job["input"]
        self.project_id = job.get("project_id")
        self.executed_stages: list[str] = []  # stages actually run (not skipped)

    def run_stage(self, name: str, fn: Callable[[], Any]) -> Any:
        """Run `fn` unless this stage already has valid artifacts (resume)."""
        self.check_cancelled()
        existing = self.job["artifacts"].get(name)
        if existing is not None and artifacts_valid(existing):
            return existing
        self.queue.set_stage(self.job_id, name)
        artifacts = fn()
        if artifacts is None:
            artifacts = []
        self.queue.checkpoint(self.job_id, name, artifacts)
        self.job["artifacts"][name] = artifacts
        self.executed_stages.append(name)
        return artifacts

    def set_progress(self, progress: float) -> None:
        self.queue.set_progress(self.job_id, progress)

    def check_cancelled(self) -> None:
        if self.queue.is_cancelled(self.job_id):
            raise JobCancelled(self.job_id)
