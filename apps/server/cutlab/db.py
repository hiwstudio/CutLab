"""SQLite access layer. One DB (data/cutlab.db), WAL mode.

All writes go through a single Database object guarded by an RLock so the
FastAPI thread and the worker thread can share it safely. Rows come back as
dicts.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  head_rev INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
  project_id TEXT NOT NULL REFERENCES projects(id),
  rev INTEGER NOT NULL, parent_rev INTEGER,
  state TEXT NOT NULL CHECK(state IN ('committed','proposed','rejected')),
  ops_json TEXT NOT NULL,
  edl_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, rev)
);
CREATE TABLE IF NOT EXISTS assets (
  project_id TEXT NOT NULL, asset_id TEXT NOT NULL,
  kind TEXT NOT NULL, src TEXT NOT NULL, proxy TEXT,
  duration_ms INTEGER, width INTEGER, height INTEGER,
  probe_json TEXT,
  status TEXT NOT NULL CHECK(status IN ('ingesting','ready','failed')),
  PRIMARY KEY (project_id, asset_id)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  project_id TEXT, input_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('queued','running','done','failed','cancelled')),
  stage TEXT,
  progress REAL NOT NULL DEFAULT 0,
  artifacts_json TEXT NOT NULL DEFAULT '{}',
  error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- generic helpers ----------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def transaction(self):
        """Context manager: BEGIN IMMEDIATE .. COMMIT/ROLLBACK under the lock."""
        return _Transaction(self)


class _Transaction:
    def __init__(self, db: Database):
        self.db = db

    def __enter__(self) -> sqlite3.Connection:
        self.db._lock.acquire()
        self.db._conn.execute("BEGIN IMMEDIATE")
        return self.db._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.db._conn.commit()
            else:
                self.db._conn.rollback()
        finally:
            self.db._lock.release()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
