"""Revision engine: transactional plan apply, undo/redo, snapshots.

Every mutation goes through `apply(project_id, base_rev, ops, mode)`:
the whole plan validates against a working copy in sequence or the whole
plan rejects. A successful apply writes a new revision row (full EDL
snapshot) and, in commit mode, moves the project head.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..db import Database, dumps, utcnow
from ..util.ids import new_project_id
from . import diff
from .ops import OpError, parse_ops
from .schema import EDL, empty_edl
from .validate import Issue, validate


class EngineError(Exception):
    """Base for apply failures that map to HTTP error responses."""


class NotFound(EngineError):
    pass


class Conflict(EngineError):
    def __init__(self, head_rev: int, base_rev: int):
        super().__init__(f"base_rev {base_rev} is stale; head is {head_rev}")
        self.head_rev = head_rev
        self.base_rev = base_rev


class Rejected(EngineError):
    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues[:5]))
        self.issues = issues


# on_revision(project_id, rev, summary, state)
RevisionCallback = Callable[[str, int, str, str], None]


class Engine:
    def __init__(
        self,
        db: Database,
        projects_dir: Path | None = None,
        on_revision: RevisionCallback | None = None,
    ):
        self.db = db
        self.projects_dir = projects_dir
        self.on_revision = on_revision

    # -- projects -------------------------------------------------------------

    def create_project(self, name: str, canvas: dict[str, Any]) -> dict[str, Any]:
        project_id = new_project_id()
        try:
            edl = empty_edl(project_id, name, canvas)
        except Exception as e:
            raise Rejected([Issue("E_SCHEMA", "canvas", str(e))]) from e
        now = utcnow()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, head_rev, created_at, updated_at)"
                " VALUES (?, ?, 0, ?, ?)",
                (project_id, name, now, now),
            )
            conn.execute(
                "INSERT INTO revisions (project_id, rev, parent_rev, state, ops_json,"
                " edl_json, summary, created_at) VALUES (?, 0, NULL, 'committed', '[]', ?, ?, ?)",
                (project_id, edl.model_dump_json(exclude_none=True), "create project", now),
            )
        self._write_edl_file(project_id, edl)
        if self.on_revision:
            self.on_revision(project_id, 0, "create project", "committed")
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM projects WHERE id=?", (project_id,))
        if row is None:
            raise NotFound(f"project {project_id} not found")
        return row

    def list_projects(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM projects ORDER BY created_at DESC")

    # -- revisions ------------------------------------------------------------

    def get_edl(self, project_id: str, rev: int | None = None) -> dict[str, Any]:
        project = self.get_project(project_id)
        rev = project["head_rev"] if rev is None else rev
        row = self.db.query_one(
            "SELECT edl_json FROM revisions WHERE project_id=? AND rev=?",
            (project_id, rev),
        )
        if row is None:
            raise NotFound(f"revision {rev} not found for {project_id}")
        return json.loads(row["edl_json"])

    def revisions(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.db.query(
            "SELECT rev, parent_rev, state, summary, created_at FROM revisions"
            " WHERE project_id=? ORDER BY rev",
            (project_id,),
        )

    # -- apply ----------------------------------------------------------------

    def apply(
        self,
        project_id: str,
        base_rev: int,
        raw_ops: list[dict[str, Any]],
        mode: str = "commit",
    ) -> dict[str, Any]:
        if mode not in ("commit", "propose"):
            raise Rejected([Issue("E_SCHEMA", "mode", f"unknown mode '{mode}'")])
        project = self.get_project(project_id)
        head = project["head_rev"]
        if base_rev != head:
            raise Conflict(head_rev=head, base_rev=base_rev)

        try:
            ops = parse_ops(raw_ops)
        except OpError as e:
            raise Rejected([Issue(e.code, e.path, e.message)]) from e

        before = EDL.model_validate(self.get_edl(project_id, head))
        working = before.model_copy(deep=True)
        ctx = self._build_op_context(project_id, working)
        summaries: list[str] = []
        try:
            for op in ops:
                previous = working.model_copy(deep=True)
                summaries.append(op.apply(working, ctx))
                from .scenes import guard_and_review
                guard_and_review(previous, working, op.op)
        except OpError as e:
            raise Rejected([Issue(e.code, e.path, e.message)]) from e

        working.project.duration_ms = working.computed_duration_ms()
        # Validate the serialized snapshot, not the model: in-place mutations
        # skip pydantic's shape validators, so a full re-parse is the safety
        # net that guarantees no committed revision can hold an invalid EDL.
        snapshot = json.loads(working.model_dump_json(exclude_none=True))
        result = validate(snapshot, base_dir=self._base_dir(project_id))
        if not result.valid:
            raise Rejected(result.errors)

        summary = diff.summarize(summaries, before, working)
        now = utcnow()
        with self.db.transaction() as conn:
            live_head = conn.execute("SELECT head_rev FROM projects WHERE id=?", (project_id,)).fetchone()["head_rev"]
            if live_head != base_rev:
                raise Conflict(head_rev=live_head, base_rev=base_rev)
            row = conn.execute(
                "SELECT COALESCE(MAX(rev), 0) AS m FROM revisions WHERE project_id=?",
                (project_id,),
            ).fetchone()
            new_rev = row["m"] + 1
            state = "committed" if mode == "commit" else "proposed"
            conn.execute(
                "INSERT INTO revisions (project_id, rev, parent_rev, state, ops_json,"
                " edl_json, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, new_rev, base_rev, state, dumps(raw_ops),
                 working.model_dump_json(exclude_none=True), summary, now),
            )
            if mode == "commit":
                conn.execute(
                    "UPDATE projects SET head_rev=?, name=?, updated_at=? WHERE id=?",
                    (new_rev, working.project.name, now, project_id),
                )
        if mode == "commit":
            self._write_edl_file(project_id, working)
        if self.on_revision:
            self.on_revision(project_id, new_rev, summary, state)
        return {
            "rev": new_rev,
            "summary": summary,
            "edl": json.loads(working.model_dump_json(exclude_none=True)),
            "warnings": [w.to_dict() for w in result.warnings],
        }

    # -- proposals (P2: plan -> propose -> accept/reject) ---------------------

    def proposals(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.db.query(
            "SELECT rev, parent_rev, summary, created_at FROM revisions"
            " WHERE project_id=? AND state='proposed' ORDER BY rev",
            (project_id,),
        )

    def accept_proposal(self, project_id: str, rev: int) -> int:
        """Commit a proposed revision as the new head. Clean only if the
        proposal was made against the current head; otherwise it is stale and
        the caller must re-propose against the new head."""
        project = self.get_project(project_id)
        head = project["head_rev"]
        row = self.db.query_one(
            "SELECT parent_rev, state FROM revisions WHERE project_id=? AND rev=?",
            (project_id, rev),
        )
        if row is None:
            raise NotFound(f"revision {rev} not found for {project_id}")
        if row["state"] != "proposed":
            raise Rejected([Issue("E_STATE", "rev", f"revision {rev} is not a proposal")])
        if row["parent_rev"] != head:
            raise Conflict(head_rev=head, base_rev=row["parent_rev"] or -1)
        now = utcnow()
        with self.db.transaction() as conn:
            live_head = conn.execute("SELECT head_rev FROM projects WHERE id=?", (project_id,)).fetchone()["head_rev"]
            if live_head != row["parent_rev"]:
                raise Conflict(head_rev=live_head, base_rev=row["parent_rev"] or -1)
            conn.execute(
                "UPDATE revisions SET state='committed' WHERE project_id=? AND rev=?",
                (project_id, rev),
            )
            edl = EDL.model_validate(json.loads(
                conn.execute("SELECT edl_json FROM revisions WHERE project_id=? AND rev=?",
                             (project_id, rev)).fetchone()["edl_json"]
            ))
            conn.execute(
                "UPDATE projects SET head_rev=?, name=?, updated_at=? WHERE id=?",
                (rev, edl.project.name, now, project_id),
            )
        self._write_edl_file(project_id, edl)
        if self.on_revision:
            self.on_revision(project_id, rev, f"accept proposal r{rev}", "committed")
        return rev

    def reject_proposal(self, project_id: str, rev: int) -> int:
        self.get_project(project_id)
        row = self.db.query_one(
            "SELECT state FROM revisions WHERE project_id=? AND rev=?",
            (project_id, rev),
        )
        if row is None:
            raise NotFound(f"revision {rev} not found for {project_id}")
        if row["state"] != "proposed":
            raise Rejected([Issue("E_STATE", "rev", f"revision {rev} is not a proposal")])
        self.db.execute(
            "UPDATE revisions SET state='rejected' WHERE project_id=? AND rev=?",
            (project_id, rev),
        )
        if self.on_revision:
            self.on_revision(project_id, rev, f"reject proposal r{rev}", "rejected")
        return rev

    # -- undo / redo ----------------------------------------------------------

    def undo(self, project_id: str) -> int:
        project = self.get_project(project_id)
        head = project["head_rev"]
        row = self.db.query_one(
            "SELECT parent_rev FROM revisions WHERE project_id=? AND rev=? AND state='committed'",
            (project_id, head),
        )
        if row is None or row["parent_rev"] is None:
            raise Rejected([Issue("E_RANGE", "head", "nothing to undo")])
        return self._repoint(project_id, row["parent_rev"])

    def redo(self, project_id: str) -> int:
        project = self.get_project(project_id)
        head = project["head_rev"]
        row = self.db.query_one(
            "SELECT MAX(rev) AS r FROM revisions"
            " WHERE project_id=? AND parent_rev=? AND state='committed'",
            (project_id, head),
        )
        if row is None or row["r"] is None:
            raise Rejected([Issue("E_RANGE", "head", "nothing to redo")])
        return self._repoint(project_id, row["r"])

    def _repoint(self, project_id: str, rev: int) -> int:
        self.db.execute(
            "UPDATE projects SET head_rev=?, updated_at=? WHERE id=?",
            (rev, utcnow(), project_id),
        )
        edl = EDL.model_validate(self.get_edl(project_id, rev))
        self.db.execute(
            "UPDATE projects SET name=? WHERE id=?", (edl.project.name, project_id)
        )
        self._write_edl_file(project_id, edl)
        if self.on_revision:
            self.on_revision(project_id, rev, f"head -> r{rev}", "committed")
        return rev

    # -- helpers --------------------------------------------------------------

    def _build_op_context(self, project_id: str, edl: EDL) -> "OpContext":
        """Load understanding artifacts for assets that have one, so smart ops
        (remove_silence, caption_from_transcript) can read them. Missing/broken
        artifacts are simply absent from the map — the op reports E_NO_UNDERSTANDING."""
        from ..understanding.schema import Understanding
        from .ops import OpContext

        understanding: dict[str, Understanding] = {}
        base = self._base_dir(project_id)
        if base is not None:
            for asset_id, asset in edl.assets.items():
                if not asset.understanding:
                    continue
                try:
                    path = base / asset.understanding
                    if path.is_file():
                        understanding[asset_id] = Understanding.model_validate_json(
                            path.read_text(encoding="utf-8")
                        )
                except Exception:
                    continue
        return OpContext(understanding=understanding)

    def _base_dir(self, project_id: str) -> Path | None:
        if self.projects_dir is None:
            return None
        d = self.projects_dir / project_id
        return d if d.exists() else None

    def _write_edl_file(self, project_id: str, edl: EDL) -> None:
        """Mirror the head EDL to data/projects/{id}/edl.json (A4)."""
        if self.projects_dir is None:
            return
        d = self.projects_dir / project_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "edl.json").write_text(
            edl.model_dump_json(exclude_none=True, indent=2), encoding="utf-8"
        )
