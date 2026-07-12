"""P4: Telegram gate round-trip (fake transport) + compaction job end-to-end.

The telegram-gate convention requires a full round-trip test before a gate
guards real runs: gate message sent, each button tapped, idempotent second tap,
unauthorized user ignored, message edited with the decision.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutlab.db import Database
from cutlab.edl.engine import Engine
from cutlab.gates.telegram import TelegramGate
from tests.test_compaction import build_u


class FakeTransport:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, payload: dict) -> dict:
        self.calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 42}}

    def of(self, method: str) -> list[dict]:
        return [p for m, p in self.calls if m == method]


@pytest.fixture()
def gate_env(tmp_path: Path):
    db = Database(tmp_path / "g.db")
    engine = Engine(db, projects_dir=tmp_path / "projects")
    pid = engine.create_project("Gate", {"width": 640, "height": 360, "fps": 30})["id"]
    (engine.projects_dir / pid).mkdir(parents=True, exist_ok=True)
    # A proposal to gate: simple rename in propose mode.
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [{"op": "set_project", "name": "Gated"}], mode="propose")
    transport = FakeTransport()
    gate = TelegramGate(engine, transport=transport, chat_id="123", approvers={777})
    yield engine, gate, transport, pid, r["rev"]
    db.close()


def tap(pid: str, rev: int, decision: str, user_id: int = 777) -> dict:
    return {"callback_query": {
        "id": "cbq1", "data": f"g|{pid}:{rev}|compact|{decision}",
        "from": {"id": user_id, "first_name": "Owner"},
        "message": {"message_id": 42, "chat": {"id": 123}, "text": "🔶 GATE"},
    }}


def test_gate_message_format(gate_env):
    engine, gate, transport, pid, rev = gate_env
    gate.send_proposal_gate(pid, rev, "compact", "Compacted to 30s.", "3 segments")
    [msg] = transport.of("sendMessage")
    assert msg["text"].startswith("🔶 GATE — Gate / compact")
    assert f"{pid} r{rev}" in msg["text"]
    buttons = msg["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["✅ Approve", "❌ Reject"]
    assert all(len(b["callback_data"].encode()) <= 64 for b in buttons)


def test_approve_roundtrip(gate_env):
    engine, gate, transport, pid, rev = gate_env
    assert gate.handle_update(tap(pid, rev, "approve")) == "applied"
    # Decision applied through the same engine path the Studio uses.
    assert engine.get_project(pid)["head_rev"] == rev
    assert engine.get_project(pid)["name"] == "Gated"
    # Ack + message edit happened.
    assert len(transport.of("answerCallbackQuery")) == 1
    [edit] = transport.of("editMessageText")
    assert "✅ Approved" in edit["text"] and "Owner" in edit["text"]
    # Idempotency: second tap -> already decided, no state change.
    assert gate.handle_update(tap(pid, rev, "approve")) == "already-decided"
    assert gate.handle_update(tap(pid, rev, "reject")) == "already-decided"


def test_reject_roundtrip(gate_env):
    engine, gate, transport, pid, rev = gate_env
    assert gate.handle_update(tap(pid, rev, "reject")) == "applied"
    assert engine.get_project(pid)["head_rev"] == 0  # head untouched
    revs = {r["rev"]: r for r in engine.revisions(pid)}
    assert revs[rev]["state"] == "rejected"


def test_unauthorized_silently_ignored(gate_env):
    engine, gate, transport, pid, rev = gate_env
    assert gate.handle_update(tap(pid, rev, "approve", user_id=666)) == "unauthorized"
    # Nothing acked, nothing edited, proposal untouched.
    assert transport.of("answerCallbackQuery") == []
    assert engine.get_project(pid)["head_rev"] == 0


def test_garbage_updates_ignored(gate_env):
    _, gate, _, _, _ = gate_env
    assert gate.handle_update({}) == "ignored"
    assert gate.handle_update({"callback_query": {"data": "nonsense"}}) == "ignored"


# -- compaction job end-to-end ---------------------------------------------------


def test_compaction_job_proposes_and_reports(tmp_path: Path):
    from cutlab.jobs.compaction import compaction_handler
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.worker import Worker

    db = Database(tmp_path / "cj.db")
    engine = Engine(db, projects_dir=tmp_path / "projects")
    pid = engine.create_project("CJob", {"width": 1280, "height": 720, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "long.mp4").write_bytes(b"stub")
    udir = pdir / "understanding"
    udir.mkdir(parents=True, exist_ok=True)
    u = build_u()
    (udir / "ast_cp.understanding.json").write_text(
        u.model_dump_json(exclude_none=True), encoding="utf-8")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_cp", "kind": "video", "src": "media/long.mp4",
         "duration_ms": 120_000, "width": 1280, "height": 720},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_cp",
         "in_ms": 0, "out_ms": 120_000, "start_ms": 0},
        {"op": "set_understanding", "asset": "ast_cp",
         "understanding": "understanding/ast_cp.understanding.json"},
    ])

    queue = JobQueue(db)
    job_id = queue.enqueue("compaction", {
        "project_id": pid, "asset_id": "ast_cp", "target_ms": 35_000,
        "project_dir": str(pdir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("compaction", compaction_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    assert set(job["artifacts"]) == {"candidates", "propose", "gate"}

    # Report follows the clip-scoring output contract.
    report = json.loads((udir / "ast_cp.compaction.json").read_text(encoding="utf-8"))
    assert report["selected"], report
    first = report["selected"][0]
    assert {"clip_id", "start_ms", "end_ms", "score", "subscores",
            "rationale", "hook_text", "suggested_title"} <= set(first)

    # A proposal exists; head untouched until a human decides.
    proposal = json.loads((udir / "ast_cp.compaction.propose.json").read_text(encoding="utf-8"))
    props = engine.proposals(pid)
    assert [p["rev"] for p in props] == [proposal["rev"]]
    head_before = engine.get_project(pid)["head_rev"]
    assert head_before < proposal["rev"]

    # Gate: telegram unconfigured in tests -> recorded as skipped, job still done.
    gate_status = json.loads((udir / "ast_cp.compaction.gate.json").read_text(encoding="utf-8"))
    assert gate_status["sent"] is False and gate_status["rev"] == proposal["rev"]

    # Accepting the proposal (as Studio/Telegram would) realizes the short cut.
    engine.accept_proposal(pid, proposal["rev"])
    edl = engine.get_edl(pid)
    assert edl["project"]["duration_ms"] <= 45_000
    db.close()
