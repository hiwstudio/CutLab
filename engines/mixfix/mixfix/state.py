"""SQLite state layer — durable, resumable, idempotent (pipeline-state conventions).

Tables: runs, stages, assets, gates, ai_tasks.
Every stage is a row; rerunning the CLI resumes from the first non-done stage.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

# shared by the schema and the rebuild migration below, so the two can't drift
RUNS_BODY = """(
    run_id     TEXT PRIMARY KEY,
    project    TEXT NOT NULL,
    -- No CHECK on mode: modes.py is the authority on which modes exist, and
    -- `modes.stages_for` rejects an unknown one before a run is ever created.
    -- A hard-coded list here duplicated that, could not see modes registering
    -- from outside the package, and -- because SQLite cannot ALTER a CHECK --
    -- cost a full table rebuild every time a mode was added.
    mode       TEXT NOT NULL,
    brain      TEXT NOT NULL CHECK (brain IN ('operator','api')),
    input_ref  TEXT,
    status     TEXT NOT NULL DEFAULT 'running'
               CHECK (status IN ('pending','running','paused','failed','done')),
    template   TEXT,                      -- set when the stage list came from a template
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)"""
RUNS_COLUMNS = ("run_id, project, mode, brain, input_ref, status, template, "
                "created_at, updated_at")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS runs {RUNS_BODY};
""" + """
CREATE TABLE IF NOT EXISTS stages (
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    stage_name  TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','paused','done','failed','skipped')),
    attempt     INTEGER NOT NULL DEFAULT 0,
    started_at  REAL,
    finished_at REAL,
    error       TEXT,
    output_json TEXT,
    params_json TEXT,                     -- per-stage config override (node parameters)
    PRIMARY KEY (run_id, stage_name)
);
CREATE TABLE IF NOT EXISTS assets (
    asset_id   TEXT PRIMARY KEY,          -- content hash
    run_id     TEXT REFERENCES runs(run_id),
    stage_name TEXT,
    kind       TEXT NOT NULL,             -- timing_map | clip | image | voiceover | ...
    path       TEXT NOT NULL,
    meta_json  TEXT,
    parent_ids TEXT,                      -- JSON list of asset_ids this was derived from
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS gates (
    gate_id      TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','approved','rejected')),
    payload_json TEXT,
    created_at   REAL NOT NULL,
    decided_at   REAL
);
CREATE TABLE IF NOT EXISTS ai_tasks (
    task_id      TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    stage_name   TEXT NOT NULL,
    task_type    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','done','failed')),
    brain        TEXT,                    -- which brain fulfilled it (single-fulfillment)
    request_dir  TEXT NOT NULL,
    result_json  TEXT,
    error        TEXT,
    created_at   REAL NOT NULL,
    completed_at REAL
);
"""


def now() -> float:
    return time.time()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class State:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the preview HTTP server touches gates from
        # handler threads; writes are tiny and guarded by sqlite's own locking
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # migrations: CREATE TABLE IF NOT EXISTS won't add a column to a table
        # that already exists, so older databases need them applied by hand
        for table, col in (("assets", "parent_ids"), ("stages", "params_json"),
                           ("runs", "template")):
            if col not in {r[1] for r in
                           self.conn.execute(f"PRAGMA table_info({table})")}:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        self.conn.commit()
        self._migrate_run_modes()

    def _migrate_run_modes(self) -> None:
        """Drop the old CHECK constraint on runs.mode by rebuilding the table.

        SQLite cannot ALTER a CHECK, so every new mode used to need its own
        migration and its own literal in the constraint. Removing the
        constraint outright ends that: the mode registry already rejects
        unknown modes, and a mode registering from outside the package (SPLIT,
        ASSEMBLY) was never visible to a list hard-coded here anyway.

        Detected by the constraint's presence rather than by any mode name, so
        this runs exactly once per database and needs no edit for a future mode.
        Existing rows are copied by name. Safe with the child tables in place:
        python's sqlite3 leaves foreign key enforcement off, so dropping the
        old `runs` does not cascade.
        """
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'"
        ).fetchone()
        if not row or "CHECK (mode IN" not in row[0]:
            return
        self.conn.executescript(f"""
            BEGIN;
            CREATE TABLE runs_new {RUNS_BODY};
            INSERT INTO runs_new ({RUNS_COLUMNS})
                SELECT {RUNS_COLUMNS} FROM runs;
            DROP TABLE runs;
            ALTER TABLE runs_new RENAME TO runs;
            COMMIT;
        """)

    # ---- runs ----
    def create_run(self, project: str, mode: str, brain: str, input_ref: str | None,
                   stage_names: list[str]) -> str:
        run_id = new_id("run")
        t = now()
        with self.conn:
            self.conn.execute(
                "INSERT INTO runs (run_id, project, mode, brain, input_ref, status,"
                " created_at, updated_at) VALUES (?,?,?,?,?,'running',?,?)",
                (run_id, project, mode, brain, input_ref, t, t))
            for i, name in enumerate(stage_names):
                self.conn.execute(
                    "INSERT INTO stages (run_id, stage_name, seq) VALUES (?,?,?)",
                    (run_id, name, i))
        return run_id

    def set_template(self, run_id: str, name: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE runs SET template=? WHERE run_id=?",
                              (name, run_id))

    def ensure_stages(self, run_id: str, stage_names: list[str]) -> None:
        """Add stages introduced after a run was created (resume migration).

        A template-built run is skipped: its stage list is the author's choice,
        and back-filling the mode's default stages would silently reinstate
        every stage the template deliberately left out.
        """
        run = self.get_run(run_id)
        if run is not None and run["template"]:
            return
        existing = {r["stage_name"] for r in self.stages(run_id)}
        with self.conn:
            for i, name in enumerate(stage_names):
                if name not in existing:
                    self.conn.execute(
                        "INSERT INTO stages (run_id, stage_name, seq)"
                        " VALUES (?,?,?)", (run_id, name, i))

    def latest_run(self, project: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM runs WHERE project=? ORDER BY created_at DESC LIMIT 1",
            (project,)).fetchone()

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()

    def set_run_status(self, run_id: str, status: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE runs SET status=?, updated_at=? WHERE run_id=?",
                (status, now(), run_id))

    # ---- stages ----
    def stages(self, run_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM stages WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()

    def stage(self, run_id: str, name: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM stages WHERE run_id=? AND stage_name=?",
            (run_id, name)).fetchone()

    def stage_start(self, run_id: str, name: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE stages SET status='running', attempt=attempt+1, started_at=?,"
                " error=NULL WHERE run_id=? AND stage_name=?", (now(), run_id, name))

    def stage_finish(self, run_id: str, name: str, status: str,
                     output: dict | None = None, error: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE stages SET status=?, finished_at=?, output_json=?, error=?"
                " WHERE run_id=? AND stage_name=?",
                (status, now(), json.dumps(output) if output else None, error,
                 run_id, name))

    def get_params(self, run_id: str, name: str) -> dict:
        row = self.stage(run_id, name)
        if row is None or not row["params_json"]:
            return {}
        return json.loads(row["params_json"])

    def set_params(self, run_id: str, name: str, params: dict) -> None:
        """Node parameters: a partial config.yaml overlaid on this stage only."""
        if self.stage(run_id, name) is None:
            raise KeyError(f"no stage {name} in run {run_id}")
        with self.conn:
            self.conn.execute(
                "UPDATE stages SET params_json=? WHERE run_id=? AND stage_name=?",
                (json.dumps(params) if params else None, run_id, name))

    def invalidate_from(self, run_id: str, name: str) -> list[str]:
        """Reset this stage and everything after it to pending; returns the names.

        The point of the graph: change one node and only its downstream reruns.
        `attempt` is deliberately kept — it is the stage's history, not its state.

        Gates are reset too. A gate approves *specific* content; leaving
        `timeline_approval` approved while its stage reruns would let new,
        unreviewed output walk straight through a human checkpoint.
        """
        target = self.stage(run_id, name)
        if target is None:
            raise KeyError(f"no stage {name} in run {run_id}")
        affected = [r["stage_name"] for r in self.stages(run_id)
                    if r["seq"] >= target["seq"]]
        with self.conn:
            self.conn.execute(
                "UPDATE stages SET status='pending', started_at=NULL,"
                " finished_at=NULL, error=NULL, output_json=NULL"
                " WHERE run_id=? AND seq>=?", (run_id, target["seq"]))
            self.conn.executemany(
                "UPDATE gates SET status='pending', decided_at=NULL"
                " WHERE run_id=? AND name=?",
                [(run_id, f"{s}_approval") for s in affected])
            # a done run must reopen, or the CLI starts a fresh one instead
            self.conn.execute(
                "UPDATE runs SET status='paused', updated_at=? WHERE run_id=?",
                (now(), run_id))
        return affected

    # ---- assets ----
    def add_asset(self, asset_id: str, run_id: str, stage_name: str, kind: str,
                  path: str, meta: dict | None = None,
                  parents: list[str] | None = None) -> None:
        """`parents` = asset_ids this was derived from (lineage edges).

        Optional: without it the graph falls back to stage attribution, which
        says which stage made an asset but not which inputs it came from.
        """
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO assets (asset_id, run_id, stage_name, kind,"
                " path, meta_json, parent_ids, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (asset_id, run_id, stage_name, kind, path,
                 json.dumps(meta) if meta else None,
                 json.dumps(parents) if parents else None, now()))

    def get_asset(self, asset_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()

    # ---- ai_tasks ----
    def create_ai_task(self, run_id: str, stage_name: str, task_type: str,
                       request_dir: str) -> str:
        task_id = new_id("task")
        with self.conn:
            self.conn.execute(
                "INSERT INTO ai_tasks (task_id, run_id, stage_name, task_type,"
                " request_dir, created_at) VALUES (?,?,?,?,?,?)",
                (task_id, run_id, stage_name, task_type, request_dir, now()))
        return task_id

    def pending_ai_task(self, run_id: str, stage_name: str,
                        task_type: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM ai_tasks WHERE run_id=? AND stage_name=? AND task_type=?"
            " AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (run_id, stage_name, task_type)).fetchone()

    def done_ai_task(self, run_id: str, stage_name: str,
                     task_type: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM ai_tasks WHERE run_id=? AND stage_name=? AND task_type=?"
            " AND status='done' ORDER BY completed_at DESC LIMIT 1",
            (run_id, stage_name, task_type)).fetchone()

    def complete_ai_task(self, task_id: str, brain: str, result: dict) -> None:
        """Single-fulfillment: only a pending task can be completed, exactly once."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE ai_tasks SET status='done', brain=?, result_json=?,"
                " completed_at=? WHERE task_id=? AND status='pending'",
                (brain, json.dumps(result), now(), task_id))
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"ai_task {task_id} already fulfilled — refusing double-processing")

    def fail_ai_task(self, task_id: str, error: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE ai_tasks SET status='failed', error=?, completed_at=?"
                " WHERE task_id=?", (error, now(), task_id))

    def supersede_ai_tasks(self, run_id: str, stage_prefix: str,
                           reason: str) -> list[sqlite3.Row]:
        """Abandon pending tasks whose answer can no longer change anything.

        A verify_clip task is raised per (scene, candidate window). If the scene
        is later accepted via a different candidate — or its candidate list is
        thrown away and re-searched — nothing will ever consume the earlier
        task, and it counts as 'awaiting verification' forever.

        Matching is done in Python, not SQL LIKE: stage labels are
        'research_extract:scene_006_<video>_<ms>' and '_' is a LIKE wildcard.
        Status stays within the table's CHECK constraint ('failed'); the reason
        goes in `error`, so a superseded task is never mistaken for a real one.
        """
        rows = [r for r in self.conn.execute(
            "SELECT * FROM ai_tasks WHERE run_id=? AND status='pending'",
            (run_id,)).fetchall() if r["stage_name"].startswith(stage_prefix)]
        if rows:
            with self.conn:
                self.conn.executemany(
                    "UPDATE ai_tasks SET status='failed', error=?, completed_at=?"
                    " WHERE task_id=? AND status='pending'",
                    [(f"superseded: {reason}", now(), r["task_id"]) for r in rows])
        return rows

    def all_pending_ai_tasks(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM ai_tasks WHERE status='pending' ORDER BY created_at").fetchall()

    def close(self) -> None:
        self.conn.close()
