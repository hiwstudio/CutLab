"""P2.6: AI Director — context compiler, plan parsing, command->propose loop
(fake + manual backends), and the API surface."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutlab.api import create_app
from cutlab.db import Database
from cutlab.director import backends
from cutlab.director.backends import FakeBackend, LLMError, ManualBackend, parse_plan
from cutlab.director.context import build_prompt, compile_context
from cutlab.director.director import AwaitingAnswer, Director, PlanRejected, Proposed
from cutlab.edl.engine import Engine
from cutlab.edl.schema import EDL
from cutlab.understanding.schema import Understanding

CANVAS = {"width": 1280, "height": 720, "fps": 30}


# -- plan parsing -------------------------------------------------------------


def test_parse_plan_bare_json():
    ops, note = parse_plan('{"ops": [{"op": "reframe", "width": 1080, "height": 1920}], "note": "vertical"}')
    assert ops == [{"op": "reframe", "width": 1080, "height": 1920}]
    assert note == "vertical"


def test_parse_plan_fenced():
    raw = 'Sure!\n```json\n{"ops": [{"op": "set_project", "name": "x"}], "note": "n"}\n```\nDone.'
    ops, note = parse_plan(raw)
    assert ops[0]["op"] == "set_project"


def test_parse_plan_surrounding_prose():
    raw = 'Here is the plan: {"ops": [], "note": "nothing to do"} hope that helps'
    ops, note = parse_plan(raw)
    assert ops == [] and note == "nothing to do"


def test_parse_plan_rejects_garbage():
    for bad in ("not json at all", '{"note": "no ops key"}', '{"ops": [42]}', '{"ops": "x"}'):
        with pytest.raises(LLMError):
            parse_plan(bad)


# -- context compiler ---------------------------------------------------------


def sample_edl() -> EDL:
    return EDL.model_validate({
        "edl_version": "1.0",
        "project": {"id": "proj_dir1", "name": "D", "canvas": CANVAS, "duration_ms": 5000},
        "assets": {"ast_v1": {"kind": "video", "src": "m/v.mp4", "duration_ms": 5000,
                              "width": 1280, "height": 720,
                              "understanding": "understanding/ast_v1.understanding.json"}},
        "tracks": [{"id": "trk_v1", "kind": "video", "clips": [
            {"id": "clp_a1", "asset": "ast_v1", "in_ms": 0, "out_ms": 5000, "start_ms": 0}]}],
    })


def test_compile_context_includes_state_and_understanding():
    u = Understanding(version="1.0", asset_id="ast_v1", kind="video", duration_ms=5000)
    ctx = compile_context(sample_edl(), {"ast_v1": u})
    assert ctx["canvas"]["width"] == 1280
    assert ctx["assets"]["ast_v1"]["analyzed"] is True
    assert ctx["tracks"][0]["clips"][0]["id"] == "clp_a1"
    prompt = build_prompt(sample_edl(), {"ast_v1": u}, "make it vertical")
    assert "make it vertical" in prompt and "clp_a1" in prompt


# -- director loop (fake + manual) --------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path):
    db = Database(tmp_path / "d.db")
    eng = Engine(db, projects_dir=tmp_path / "projects")
    yield eng
    db.close()


def _project(engine: Engine) -> str:
    p = engine.create_project("Dir", CANVAS)
    pid = p["id"]
    (engine.projects_dir / pid).mkdir(parents=True, exist_ok=True)
    engine.apply(pid, 0, [{"op": "add_track", "kind": "video", "id": "trk_v1"}])
    return pid


def test_director_fake_backend_proposes(engine: Engine):
    fake = FakeBackend('{"ops": [{"op": "reframe", "width": 1080, "height": 1920}], "note": "vertical"}')
    director = Director(engine, engine.projects_dir, backend=fake)
    pid = _project(engine)
    result = director.command(pid, "make it vertical")
    assert isinstance(result, Proposed)
    assert result.note == "vertical"
    # It's a proposal — head did not move.
    assert engine.get_project(pid)["head_rev"] == 1
    props = engine.proposals(pid)
    assert [p["rev"] for p in props] == [result.rev]
    # Accepting realizes it.
    engine.accept_proposal(pid, result.rev)
    assert engine.get_edl(pid)["project"]["canvas"]["width"] == 1080


def test_director_invalid_plan_is_reported_not_applied(engine: Engine):
    # References a clip that doesn't exist -> engine rejects -> PlanRejected.
    fake = FakeBackend('{"ops": [{"op": "trim", "clip": "clp_none", "new_in_ms": 0}], "note": "x"}')
    director = Director(engine, engine.projects_dir, backend=fake)
    pid = _project(engine)
    result = director.command(pid, "trim something")
    assert isinstance(result, PlanRejected)
    assert result.issues[0]["code"] == "E_REF"
    assert engine.proposals(pid) == []


def test_director_manual_flow(engine: Engine):
    director = Director(engine, engine.projects_dir, backend=ManualBackend())
    pid = _project(engine)
    result = director.command(pid, "rename to Hello")
    assert isinstance(result, AwaitingAnswer)
    # The prompt was written to disk (crash-resumable request state).
    assert Path(result.prompt_path).is_file()
    assert "rename to Hello" in Path(result.prompt_path).read_text(encoding="utf-8")
    # Drop the answer back -> proposal.
    answer = '{"ops": [{"op": "set_project", "name": "Hello"}], "note": "renamed"}'
    done = director.answer(pid, result.request_id, answer)
    assert isinstance(done, Proposed)
    engine.accept_proposal(pid, done.rev)
    assert engine.get_project(pid)["name"] == "Hello"


def test_director_empty_command(engine: Engine):
    director = Director(engine, engine.projects_dir, backend=ManualBackend())
    with pytest.raises(LLMError):
        director.command(_project(engine), "   ")


# -- API ----------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data", start_worker=False, verify_ffmpeg=False)
    # Force a deterministic fake backend for the automatic path.
    app.state.cutlab.director.backend = FakeBackend(
        '{"ops": [{"op": "set_project", "name": "Directed"}], "note": "renamed"}'
    )
    with TestClient(app) as c:
        yield c


def test_api_director_command_proposes(client: TestClient):
    pid = client.post("/api/v1/projects", json={"name": "P", "canvas": CANVAS}).json()["id"]
    r = client.post(f"/api/v1/projects/{pid}/director/command", json={"text": "rename it"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "proposed"
    # Shows in proposals; head unchanged.
    assert client.get(f"/api/v1/projects/{pid}").json()["head_rev"] == 0
    props = client.get(f"/api/v1/projects/{pid}/proposals").json()
    assert [p["rev"] for p in props] == [body["rev"]]
    # Accept it.
    client.post(f"/api/v1/projects/{pid}/proposals/{body['rev']}/accept")
    assert client.get(f"/api/v1/projects/{pid}").json()["name"] == "Directed"


def test_api_director_manual_flow(client: TestClient):
    client.app.state.cutlab.director.backend = ManualBackend()
    pid = client.post("/api/v1/projects", json={"name": "P", "canvas": CANVAS}).json()["id"]
    assert client.get(f"/api/v1/projects/{pid}/director/backend").json()["backend"] == "manual"
    r = client.post(f"/api/v1/projects/{pid}/director/command", json={"text": "rename to Z"})
    body = r.json()
    assert body["status"] == "awaiting_answer" and body["request_id"].startswith("dir_")
    a = client.post(f"/api/v1/projects/{pid}/director/answer", json={
        "request_id": body["request_id"],
        "answer": '{"ops": [{"op": "set_project", "name": "Z"}], "note": "ok"}',
    })
    assert a.json()["status"] == "proposed"


def test_api_director_empty_command_422(client: TestClient):
    pid = client.post("/api/v1/projects", json={"name": "P", "canvas": CANVAS}).json()["id"]
    assert client.post(f"/api/v1/projects/{pid}/director/command", json={"text": ""}).status_code == 422
