"""P2.5: plan -> propose -> accept/reject loop (engine + API)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutlab.api import create_app
from cutlab.db import Database
from cutlab.edl.engine import Conflict, Engine, NotFound, Rejected

CANVAS = {"width": 1280, "height": 720, "fps": 30}


@pytest.fixture()
def engine(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    eng = Engine(db, projects_dir=None)
    yield eng
    db.close()


def _project(engine: Engine) -> str:
    return engine.create_project("P", CANVAS)["id"]


def test_propose_does_not_move_head(engine: Engine):
    pid = _project(engine)
    r = engine.apply(pid, 0, [{"op": "add_track", "kind": "video"}], mode="propose")
    assert engine.get_project(pid)["head_rev"] == 0
    props = engine.proposals(pid)
    assert [p["rev"] for p in props] == [r["rev"]]


def test_accept_proposal_commits_and_moves_head(engine: Engine):
    pid = _project(engine)
    r = engine.apply(pid, 0, [{"op": "add_track", "kind": "video", "id": "trk_p1"}],
                     mode="propose")
    accepted = engine.accept_proposal(pid, r["rev"])
    assert accepted == r["rev"]
    assert engine.get_project(pid)["head_rev"] == r["rev"]
    # It's now a committed revision and no longer a pending proposal.
    assert engine.proposals(pid) == []
    edl = engine.get_edl(pid)
    assert any(t["id"] == "trk_p1" for t in edl["tracks"])


def test_reject_proposal(engine: Engine):
    pid = _project(engine)
    r = engine.apply(pid, 0, [{"op": "add_track", "kind": "audio"}], mode="propose")
    engine.reject_proposal(pid, r["rev"])
    assert engine.get_project(pid)["head_rev"] == 0
    assert engine.proposals(pid) == []
    # A rejected proposal cannot then be accepted.
    with pytest.raises(Rejected) as exc:
        engine.accept_proposal(pid, r["rev"])
    assert exc.value.issues[0].code == "E_STATE"


def test_accept_stale_proposal_conflicts(engine: Engine):
    pid = _project(engine)
    # Propose against head 0, then commit something else -> head moves to 1.
    prop = engine.apply(pid, 0, [{"op": "add_track", "kind": "video"}], mode="propose")
    engine.apply(pid, 0, [{"op": "add_track", "kind": "audio"}])  # commit -> head=...
    with pytest.raises(Conflict):
        engine.accept_proposal(pid, prop["rev"])


def test_accept_unknown_rev(engine: Engine):
    pid = _project(engine)
    with pytest.raises(NotFound):
        engine.accept_proposal(pid, 99)


# -- API ----------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data", start_worker=False, verify_ffmpeg=False)
    with TestClient(app) as c:
        yield c


def test_api_propose_accept_flow(client: TestClient):
    pid = client.post("/api/v1/projects", json={"name": "Prop", "canvas": CANVAS}).json()["id"]
    # Propose.
    r = client.post(f"/api/v1/projects/{pid}/apply", json={
        "base_rev": 0, "mode": "propose",
        "ops": [{"op": "add_track", "kind": "video", "id": "trk_api1"}],
    })
    assert r.status_code == 200
    prev = r.json()["rev"]
    assert client.get(f"/api/v1/projects/{pid}").json()["head_rev"] == 0

    # It shows up in proposals.
    props = client.get(f"/api/v1/projects/{pid}/proposals").json()
    assert [p["rev"] for p in props] == [prev]

    # Accept.
    a = client.post(f"/api/v1/projects/{pid}/proposals/{prev}/accept")
    assert a.status_code == 200 and a.json()["rev"] == prev
    assert client.get(f"/api/v1/projects/{pid}").json()["head_rev"] == prev
    assert client.get(f"/api/v1/projects/{pid}/proposals").json() == []


def test_api_reject_flow(client: TestClient):
    pid = client.post("/api/v1/projects", json={"name": "Prop", "canvas": CANVAS}).json()["id"]
    r = client.post(f"/api/v1/projects/{pid}/apply", json={
        "base_rev": 0, "mode": "propose",
        "ops": [{"op": "add_track", "kind": "audio"}],
    })
    rev = r.json()["rev"]
    assert client.post(f"/api/v1/projects/{pid}/proposals/{rev}/reject").status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/proposals").json() == []
    # Accepting a rejected proposal -> 422 (E_STATE).
    assert client.post(f"/api/v1/projects/{pid}/proposals/{rev}/accept").status_code == 422
