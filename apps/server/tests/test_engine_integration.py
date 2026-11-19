"""Real ingest, revision/proposal isolation and operator handoff for MixFix."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutlab import config
from cutlab.api import create_app
from cutlab.integrations import mixfix
from cutlab.jobs.engine_import import engine_import_handler
from cutlab.jobs.queue import JobContext
from cutlab.util.ffrun import run_ffmpeg
from tests.media_fixtures import make_video, make_image

CANVAS = {"width": 320, "height": 180, "fps": 30}
INSTALLED_MIXFIX_ROOT = config.MIXFIX_ROOT


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    root = tmp_path_factory.mktemp("engine-media")
    make_video(root / "source.mp4", 4)
    make_video(root / "replacement.mp4", 4, tone_hz=880)
    make_image(root / "still.png")
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=220:duration=4", "-c:a", "libmp3lame", str(root / "voice.mp3")])
    return root


@pytest.fixture
def connected(tmp_path, monkeypatch, media):
    engine_root = tmp_path / "mixfix"
    source = engine_root / "projects" / "sample"
    for directory in ["timeline", "timing", "voiceover", "input"]:
        (source / directory).mkdir(parents=True)
    shutil.copy(media / "voice.mp3", source / "voiceover/voice.mp3")
    shutil.copy(media / "source.mp4", source / "input/source.mp4")
    timeline = {"total_ms": 4000, "scenes": [
        {"id": "scene_001", "start_ms": 0, "end_ms": 1500, "narration": "First scene",
         "visual": {"kind": "clip", "path": str(media / "source.mp4"), "trim_in_ms": 500,
                    "source": {"title": "Original footage", "url": "https://example.com/source"}},
         "alternatives": [{"title": "Alternative footage"}]},
        {"id": "scene_002", "start_ms": 2000, "end_ms": 4000, "narration": "Second scene",
         "visual": {"kind": "image", "path": str(media / "still.png")}}]}
    (source / "timeline/timeline.json").write_text(json.dumps(timeline))
    timing = {"words": [{"text": f"word{i}", "start_ms": i * 300, "end_ms": (i + 1) * 300} for i in range(12)]}
    (source / "timing/timing_map.json").write_text(json.dumps(timing))
    monkeypatch.setattr(config, "MIXFIX_ROOT", engine_root)
    app = create_app(tmp_path / "data", start_worker=False, verify_ffmpeg=False)
    with TestClient(app) as client:
        yield client, app.state.cutlab, source, media


def imported(connected, mode="mix"):
    client, state, source, media = connected
    response = client.post("/api/v1/engines/mixfix/import", json={"source_project": "sample", "mode": mode, "canvas": CANVAS})
    assert response.status_code == 200, response.text
    info = response.json()
    assert state.worker.run_one()
    job = state.queue.get(info["job_id"])
    assert job["state"] == "done", job["error"]
    return info["project_id"], job


def test_complete_import_resume_and_source_trace(connected):
    client, state, source, _ = connected
    before = (source / "timeline/timeline.json").read_bytes()
    pid, job = imported(connected)
    edl = state.engine.get_edl(pid)
    assert edl["project"]["duration_ms"] == 4000
    assert [(s["start_ms"], s["end_ms"]) for s in edl["scenes"]] == [(0, 2000), (2000, 4000)]
    assert [t["kind"] for t in edl["tracks"]] == ["video", "audio", "caption"]
    assert [len(t["clips"]) for t in edl["tracks"]] == [2, 1, 2]
    clip = edl["tracks"][0]["clips"][0]
    assert (clip["in_ms"], clip["out_ms"]) == (500, 2500)
    for asset in edl["assets"].values():
        assert (state.projects_dir / pid / asset["src"]).is_file()
    link = client.get(f"/api/v1/projects/{pid}/engine-link").json()
    assert link["manifest"]["scenes"][0]["visual"]["source"]["title"] == "Original footage"
    assert link["manifest"]["warnings"]
    rev = state.engine.get_project(pid)["head_rev"]
    engine_import_handler(JobContext(state.queue, job))
    assert state.engine.get_project(pid)["head_rev"] == rev
    assert (source / "timeline/timeline.json").read_bytes() == before


def test_scene_update_preserves_manual_edit_and_requires_accept(connected):
    client, state, source, media = connected
    pid, _ = imported(connected)
    edl = state.engine.get_edl(pid)
    clip = edl["tracks"][0]["clips"][0]
    scene_id = edl["scenes"][0]["id"]
    base = state.engine.get_project(pid)["head_rev"]
    edited = state.engine.apply(pid, base, [
        {"op": "set_opacity", "clip": clip["id"], "opacity": 0.6},
        {"op": "set_transform", "clip": clip["id"], "transform": {"x": 12, "scale": 1.1}}])
    baseline = state.engine.get_edl(pid)
    tl = mixfix.read_json(source / "timeline/timeline.json")
    tl["scenes"][0]["visual"]["path"] = str(media / "replacement.mp4")
    tl["scenes"][0]["visual"]["trim_in_ms"] = 0
    tl["scenes"][0]["visual"]["source"]["title"] = "Updated footage"
    (source / "timeline/timeline.json").write_text(json.dumps(tl))
    r = client.post(f"/api/v1/projects/{pid}/engine-scenes/{scene_id}/refresh", json={"base_rev": edited["rev"]})
    assert r.status_code == 200, r.text
    state.worker.run_one()
    job = state.queue.get(r.json()["job_id"])
    assert job["state"] == "done", job["error"]
    current = state.engine.get_edl(pid)
    assert current["tracks"] == baseline["tracks"]  # only asset registration commits
    proposal = state.engine.proposals(pid)[0]
    proposed = state.engine.get_edl(pid, proposal["rev"])
    new = proposed["tracks"][0]["clips"][0]
    old = baseline["tracks"][0]["clips"][0]
    assert new["asset"] != old["asset"]
    assert (new["in_ms"], new["out_ms"]) == (0, 2000)
    for key in ("start_ms", "speed", "opacity", "transform", "effects"):
        assert new[key] == old[key]
    assert proposed["tracks"][0]["clips"][1] == baseline["tracks"][0]["clips"][1]
    assert proposed["tracks"][1:] == baseline["tracks"][1:]
    assert client.post(f"/api/v1/projects/{pid}/proposals/{proposal['rev']}/accept").status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/engine-link").json()["manifest"]["scenes"][0]["visual"]["source"]["title"] == "Updated footage"
    state.engine.undo(pid)
    assert client.get(f"/api/v1/projects/{pid}/engine-link").json()["manifest"]["scenes"][0]["visual"]["source"]["title"] == "Original footage"


def test_request_is_durable_handoff_without_source_mutation(connected):
    client, state, source, _ = connected
    pid, _ = imported(connected)
    sid = state.engine.get_edl(pid)["scenes"][0]["id"]
    rev = state.engine.get_project(pid)["head_rev"]
    before = (source / "timeline/timeline.json").read_bytes()
    r = client.post(f"/api/v1/projects/{pid}/engine-scenes/{sid}/request", json={"base_rev": rev, "note": "A closer view of the dish"})
    assert r.status_code == 200
    state.worker.run_one()
    request_id = r.json()["job_id"]
    handoff = client.get(f"/api/v1/projects/{pid}/engine-requests/{request_id}")
    assert handoff.status_code == 200
    assert handoff.json()["state"] == "awaiting_operator"
    assert handoff.json()["review_action"] == {"scene_id": "scene_001", "flag": "regen"}
    assert state.engine.get_project(pid)["head_rev"] == rev
    assert (source / "timeline/timeline.json").read_bytes() == before
    assert not (source / "timeline/review.json").exists()
    assert client.post(f"/api/v1/projects/{pid}/engine-scenes/{sid}/refresh", json={"base_rev": rev - 1}).status_code == 409


def test_fix_preserves_gaps_and_original_audio(connected):
    _, state, _, _ = connected
    pid, _ = imported(connected, "fix")
    edl = state.engine.get_edl(pid)
    assert [t["id"] for t in edl["tracks"]] == ["trk_mfbase", "trk_mfvisual", "trk_mfvoice", "trk_mfcaptions"]
    assert edl["tracks"][0]["clips"][0]["out_ms"] == 4000
    assert edl["tracks"][0]["clips"][0]["gain_db"] == -60
    assert edl["tracks"][1]["clips"][0]["out_ms"] == 2000  # tin500 + window1500
    assert edl["tracks"][2]["clips"][0]["gain_db"] == 0
    assert [(s["start_ms"], s["end_ms"]) for s in edl["scenes"]] == [(0, 1500), (2000, 4000)]


@pytest.mark.parametrize("name,mode", [("../sample", "mix"), ("sample", "split"), ("missing", "mix")])
def test_rejects_invalid_sources_before_creating_project(connected, name, mode):
    client, state, _, _ = connected
    before = state.engine.list_projects()
    r = client.post("/api/v1/engines/mixfix/import", json={"source_project": name, "mode": mode, "canvas": CANVAS})
    assert r.status_code == 422
    assert state.engine.list_projects() == before


def test_missing_visual_is_explicit_not_empty_timeline(connected):
    client, state, source, _ = connected
    tl = mixfix.read_json(source / "timeline/timeline.json")
    tl["scenes"][0]["visual"] = None
    (source / "timeline/timeline.json").write_text(json.dumps(tl))
    r = client.post("/api/v1/engines/mixfix/import", json={"source_project": "sample", "canvas": CANVAS})
    assert r.status_code == 422 and "scene_001" in r.text
    assert state.engine.list_projects() == []


def test_worker_and_editor_cannot_overwrite_same_head(connected, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from cutlab.edl import engine as engine_module
    from cutlab.edl.engine import Conflict
    _, state, _, _ = connected
    pid = state.engine.create_project("Race", CANVAS)["id"]
    barrier = Barrier(2)
    original = engine_module.validate
    def synchronize(*args, **kwargs):
        result = original(*args, **kwargs)
        barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(engine_module, "validate", synchronize)
    def apply(name):
        try:
            state.engine.apply(pid, 0, [{"op": "set_project", "name": name}])
            return "committed"
        except Conflict:
            return "conflict"
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(apply, ["Worker", "Editor"])) == ["committed", "conflict"]
    assert state.engine.get_project(pid)["head_rev"] == 1


@pytest.mark.skipif(not (INSTALLED_MIXFIX_ROOT / "mixfix/assemble.py").is_file(), reason="owner MixFix installation required")
def test_real_engine_hold_covers_millisecond_boundary(connected, monkeypatch):
    client, state, source, _ = connected
    # Load the real installed renderer, while source discovery uses the fixture.
    with monkeypatch.context() as patch:
        patch.setattr(config, "MIXFIX_ROOT", INSTALLED_MIXFIX_ROOT)
        renderer = mixfix.module("assemble")
    monkeypatch.setattr(mixfix, "module", lambda name: renderer)
    timeline = mixfix.read_json(source / "timeline/timeline.json")
    timeline["scenes"][0]["visual"]["trim_in_ms"] = 3500
    timeline["scenes"][1]["start_ms"] = 1980
    (source / "timeline/timeline.json").write_text(json.dumps(timeline))
    pid, _ = imported(connected)
    edl = state.engine.get_edl(pid)
    clip = edl["tracks"][0]["clips"][0]
    assert clip["in_ms"] == 0 and clip["out_ms"] == 1980
    assert edl["assets"][clip["asset"]]["duration_ms"] >= 1980
