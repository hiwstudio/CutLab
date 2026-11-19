"""Phase 1 tests: state transitions, AI task handshake, router integrity,
timing map validation, scene breakdown, crash-resume."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import timing
from mixfix.ai import schemas
from mixfix.ai.router import Router
from mixfix.ai.tasks import TaskQueue
from mixfix.state import State


@pytest.fixture()
def state(tmp_path):
    return State(tmp_path / "test.db")


@pytest.fixture()
def queue(state, tmp_path):
    return TaskQueue(state, tmp_path / "ai_tasks")


def make_run(state, stages=("s1", "s2")):
    return state.create_run("proj", "mix", "operator", None, list(stages))


# ---- state ----
def test_run_and_stage_lifecycle(state):
    run_id = make_run(state)
    assert state.get_run(run_id)["status"] == "running"
    state.stage_start(run_id, "s1")
    state.stage_finish(run_id, "s1", "done", {"ok": 1})
    rows = state.stages(run_id)
    assert rows[0]["status"] == "done" and rows[1]["status"] == "pending"
    assert rows[0]["attempt"] == 1


def test_invalid_status_rejected(state):
    run_id = make_run(state)
    with pytest.raises(sqlite3.IntegrityError):
        state.conn.execute("UPDATE runs SET status='bogus' WHERE run_id=?", (run_id,))


# ---- ai task handshake ----
def test_task_raise_is_idempotent(state, queue):
    run_id = make_run(state)
    t1 = queue.raise_task(run_id, "s1", "write_script", {"topic": "x"})
    t2 = queue.raise_task(run_id, "s1", "write_script", {"topic": "x"})
    assert t1 == t2  # no duplicate pending tasks per stage


def test_malformed_result_rejected_and_stays_pending(state, queue):
    run_id = make_run(state)
    tid = queue.raise_task(run_id, "s1", "write_script", {"topic": "x"})
    task_dir = Path(state.conn.execute(
        "SELECT request_dir FROM ai_tasks WHERE task_id=?", (tid,)).fetchone()[0])
    (task_dir / "result.json").write_text(json.dumps({"narration": "too short"}))
    with pytest.raises(schemas.SchemaError):
        queue.try_collect(tid, brain="operator")
    row = state.conn.execute(
        "SELECT status FROM ai_tasks WHERE task_id=?", (tid,)).fetchone()
    assert row["status"] == "pending"
    assert (task_dir / "result.rejected.json").exists()


def _valid_script_result():
    long = "This is a sufficiently long narration text for validation. " * 3
    return {"narration": long, "elevenlabs_script": long, "aistudio_script": long}


def test_valid_result_completes_and_moves_dir(state, queue):
    run_id = make_run(state)
    tid = queue.raise_task(run_id, "s1", "write_script", {"topic": "x"})
    task_dir = Path(state.conn.execute(
        "SELECT request_dir FROM ai_tasks WHERE task_id=?", (tid,)).fetchone()[0])
    (task_dir / "result.json").write_text(json.dumps(_valid_script_result()))
    result = queue.try_collect(tid, brain="operator")
    assert result["narration"]
    row = state.conn.execute(
        "SELECT status, brain FROM ai_tasks WHERE task_id=?", (tid,)).fetchone()
    assert row["status"] == "done" and row["brain"] == "operator"
    assert not task_dir.exists()  # moved to done/


def test_single_fulfillment_enforced(state, queue):
    run_id = make_run(state)
    tid = queue.raise_task(run_id, "s1", "write_script", {"topic": "x"})
    state.complete_ai_task(tid, "operator", _valid_script_result())
    with pytest.raises(RuntimeError, match="double-processing"):
        state.complete_ai_task(tid, "api", _valid_script_result())


def test_router_operator_mode_makes_no_api_calls(state, queue):
    run_id = make_run(state)
    router = Router("operator", queue, adapter=None)  # no adapter needed/allowed
    assert router.fulfill(run_id, "s1", "write_script", {"topic": "x"}) is None


def test_router_api_mode_requires_adapter():
    with pytest.raises(ValueError, match="requires a configured LLM adapter"):
        Router("api", queue=None, adapter=None)


# ---- timing map ----
def _words():
    return [
        {"text": "Hello", "start_ms": 0, "end_ms": 400},
        {"text": "world.", "start_ms": 420, "end_ms": 900},
        {"text": "Second", "start_ms": 1000, "end_ms": 1400},
        {"text": "sentence.", "start_ms": 1450, "end_ms": 2000},
    ]


def _tmap():
    words = _words()
    return {
        "version": "1.0",
        "source": {"audio_path": "x.mp3", "duration_ms": 2100,
                   "transcriber": "json", "model": "n/a"},
        "words": words,
        "segments": timing._group_sentences(words),
        "meta": {"project": "t"},
    }


def test_timing_map_valid():
    tmap = _tmap()
    timing.validate(tmap)
    assert [s["id"] for s in tmap["segments"]] == ["seg_001", "seg_002"]


def test_timing_map_rejects_overlap():
    tmap = _tmap()
    tmap["words"][1]["start_ms"] = 100  # overlaps word 0 (ends 400) beyond jitter
    with pytest.raises(timing.TimingMapError, match="overlaps"):
        timing.validate(tmap)


def test_timing_map_rejects_beyond_duration():
    tmap = _tmap()
    tmap["words"][-1]["end_ms"] = 99999
    with pytest.raises(timing.TimingMapError):
        timing.validate(tmap)


# ---- scene breakdown ----
def test_scene_breakdown_schema_and_attach():
    tmap = _tmap()
    ctx = {"segment_ids": [s["id"] for s in tmap["segments"]]}
    good = {"scenes": [
        {"id": "scene_001", "segment_ids": ["seg_001"], "visual_intent": "opening shot"},
        {"id": "scene_002", "segment_ids": ["seg_002"], "visual_intent": "detail shot"},
    ]}
    schemas.validate("scene_breakdown", good, ctx)
    tmap = timing.attach_scenes(tmap, good)
    assert tmap["scenes"][0]["start_ms"] == 0
    assert tmap["scenes"][1]["end_ms"] == 2000
    assert all(sc["assets"] == [] for sc in tmap["scenes"])


def test_scene_breakdown_rejects_missing_coverage():
    ctx = {"segment_ids": ["seg_001", "seg_002"]}
    bad = {"scenes": [
        {"id": "scene_001", "segment_ids": ["seg_001"], "visual_intent": "x"}]}
    with pytest.raises(schemas.SchemaError, match="cover every segment"):
        schemas.validate("scene_breakdown", bad, ctx)


def test_scene_breakdown_rejects_unknown_segment():
    ctx = {"segment_ids": ["seg_001"]}
    bad = {"scenes": [
        {"id": "scene_001", "segment_ids": ["seg_999"], "visual_intent": "x"}]}
    with pytest.raises(schemas.SchemaError, match="unknown segment"):
        schemas.validate("scene_breakdown", bad, ctx)


# ---- resume ----
def test_resume_skips_done_stages(state):
    run_id = make_run(state, stages=("a", "b", "c"))
    state.stage_start(run_id, "a")
    state.stage_finish(run_id, "a", "done")
    # simulate crash during b: status stays 'running'
    state.stage_start(run_id, "b")
    todo = [r["stage_name"] for r in state.stages(run_id) if r["status"] != "done"]
    assert todo == ["b", "c"]
    done_finished_at = state.stage(run_id, "a")["finished_at"]
    state.stage_start(run_id, "b")
    state.stage_finish(run_id, "b", "done")
    assert state.stage(run_id, "a")["finished_at"] == done_finished_at  # untouched
    assert state.stage(run_id, "b")["attempt"] == 2
