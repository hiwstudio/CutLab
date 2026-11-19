"""Pipeline state — durable SQLite backbone (pipeline-state schema).

runs / stages / assets / events. Idempotent stages, resume = re-run,
a stage is done only after its outputs are registered in assets.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .utils import sha256_file

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  project    TEXT NOT NULL,
  input_ref  TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stages (
  run_id     INTEGER NOT NULL,
  stage_name TEXT NOT NULL,
  seq        INTEGER NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending',
  attempt    INTEGER NOT NULL DEFAULT 0,
  started_at TEXT, finished_at TEXT, error TEXT,
  PRIMARY KEY (run_id, stage_name)
);
CREATE TABLE IF NOT EXISTS assets (
  asset_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       INTEGER NOT NULL,
  stage_name   TEXT NOT NULL,
  kind         TEXT NOT NULL,
  path         TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  run_id INTEGER NOT NULL, ts TEXT NOT NULL,
  stage_name TEXT, level TEXT NOT NULL, message TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path | None = None):
        self.conn = sqlite3.connect(path or config.DB_PATH, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript(SCHEMA)

    # --- runs ---
    def get_or_create_run(self, project: str, input_ref: str) -> int:
        row = self.conn.execute(
            "SELECT run_id FROM runs WHERE project=? AND status!='done' "
            "ORDER BY run_id DESC LIMIT 1", (project,)).fetchone()
        if row:
            return row["run_id"]
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO runs (project, input_ref, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?)", (project, input_ref, "running", now(), now()))
        return cur.lastrowid

    def set_run_status(self, run_id: int, status: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE runs SET status=?, updated_at=? WHERE run_id=?",
                              (status, now(), run_id))

    # --- stages ---
    def stage_status(self, run_id: int, name: str) -> str:
        row = self.conn.execute(
            "SELECT status FROM stages WHERE run_id=? AND stage_name=?",
            (run_id, name)).fetchone()
        return row["status"] if row else "pending"

    def stage_start(self, run_id: int, name: str, seq: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO stages (run_id, stage_name, seq, status, attempt, started_at) "
                "VALUES (?,?,?,?,1,?) ON CONFLICT(run_id, stage_name) DO UPDATE SET "
                "status='running', attempt=attempt+1, started_at=?, error=NULL",
                (run_id, name, seq, "running", now(), now()))

    def stage_finish(self, run_id: int, name: str, status: str, error: str = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE stages SET status=?, finished_at=?, error=? "
                "WHERE run_id=? AND stage_name=?", (status, now(), error, run_id, name))

    # --- assets (append-only) ---
    def register_asset(self, run_id: int, stage: str, kind: str, path: Path) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO assets (run_id, stage_name, kind, path, content_hash, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, stage, kind, str(path), sha256_file(Path(path)), now()))

    # --- events ---
    def event(self, run_id: int, level: str, message: str, stage: str = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO events (run_id, ts, stage_name, level, message) "
                "VALUES (?,?,?,?,?)", (run_id, now(), stage, level, message))

    # --- status report ---
    def report(self) -> str:
        lines = []
        for r in self.conn.execute(
                "SELECT * FROM runs ORDER BY run_id DESC LIMIT 10"):
            lines.append(f"run {r['run_id']}  {r['project']}  [{r['status']}]  {r['input_ref']}")
            for s in self.conn.execute(
                    "SELECT * FROM stages WHERE run_id=? ORDER BY seq", (r["run_id"],)):
                err = f"  ERROR: {s['error'][:120]}" if s["error"] else ""
                lines.append(f"    {s['seq']}. {s['stage_name']:<12} {s['status']}{err}")
        return "\n".join(lines) or "no runs yet"
