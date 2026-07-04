"""P1.7: durable understanding job — full pipeline, EDL registration, and
crash-resume (completed stages are not re-run)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutlab.db import Database, dumps
from cutlab.edl.engine import Engine
from cutlab.jobs import understanding as u_mod
from cutlab.jobs.queue import JobQueue
from cutlab.jobs.worker import Worker
from cutlab.understanding import transcribe as transcribe_mod
from tests.media_fixtures import make_hardcut_video, make_tone_silence_tone
from tests.test_transcribe import FakeInfo, FakeModel, FakeSegment, FakeWord


@pytest.fixture()
def fake_whisper(monkeypatch):
    """Replace faster-whisper with a deterministic fake so the job is fast."""
    seg = FakeSegment(
        start=0.2, end=1.4, text="hello there",
        words=[FakeWord(0.2, 0.6, " hello"), FakeWord(0.7, 1.4, " there")],
    )
    monkeypatch.setattr(
        transcribe_mod, "_load_faster_whisper",
        lambda: FakeModel([seg], FakeInfo(language="en")),
    )


def _setup(db: Database, tmp_path: Path):
    projects_dir = tmp_path / "projects"
    engine = Engine(db, projects_dir=projects_dir)
    pid = engine.create_project("U", {"width": 640, "height": 360, "fps": 30})["id"]
    project_dir = projects_dir / pid
    (project_dir / "media").mkdir(parents=True, exist_ok=True)
    return engine, pid, project_dir


def _register_asset(db, engine, pid, project_dir, asset_id, src_rel, src_path):
    """Ingest-equivalent: probe, store row + EDL asset so understanding can run."""
    from cutlab.util.ffprobe import probe

    pr = probe(src_path)
    db.execute(
        "INSERT INTO assets (project_id, asset_id, kind, src, duration_ms, width,"
        " height, probe_json, status) VALUES (?,?,?,?,?,?,?,?, 'ready')",
        (pid, asset_id, "video", src_rel, pr.duration_ms, pr.width, pr.height,
         dumps(pr.raw)),
    )
    head = engine.get_project(pid)["head_rev"]
    engine.apply(pid, head, [{
        "op": "add_asset", "asset_id": asset_id, "kind": "video", "src": src_rel,
        "duration_ms": pr.duration_ms, "width": pr.width, "height": pr.height,
    }])
    return pr.duration_ms


@pytest.mark.slow
def test_understanding_full_pipeline(db, tmp_path, fake_whisper):
    queue = JobQueue(db)
    engine, pid, project_dir = _setup(db, tmp_path)
    # A clip with hard cuts AND a middle silence -> exercises scenes + silence.
    src = make_tone_silence_tone(project_dir / "media" / "clip.mp4", seg_seconds=2.0)
    dur = _register_asset(db, engine, pid, project_dir, "ast_u1", "media/clip.mp4", src)

    job_id = queue.enqueue("understanding", {
        "project_id": pid, "asset_id": "ast_u1", "kind": "video",
        "src": "media/clip.mp4", "project_dir": str(project_dir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("understanding", u_mod.understanding_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    assert set(job["artifacts"]) == {
        "scenes", "silence", "transcript", "beats", "saliency", "assemble"
    }

    # Final artifact on disk + valid schema.
    final = project_dir / "understanding" / "ast_u1.understanding.json"
    assert final.exists()
    from cutlab.understanding.schema import Understanding

    u = Understanding.model_validate_json(final.read_text(encoding="utf-8"))
    assert u.asset_id == "ast_u1"
    assert u.duration_ms > 0
    assert len(u.silence) == 1               # the middle silence
    assert u.transcript and u.transcript.word_count() == 2   # fake whisper
    assert u.saliency and len(u.saliency.windows) > 0
    assert u.provenance.silence["tool"] == "ffmpeg silencedetect"

    # Registered in the EDL and the assets row.
    edl = engine.get_edl(pid)
    assert edl["assets"]["ast_u1"]["understanding"] == "understanding/ast_u1.understanding.json"
    row = db.query_one("SELECT understanding FROM assets WHERE asset_id='ast_u1'")
    assert row["understanding"] == "understanding/ast_u1.understanding.json"


@pytest.mark.slow
def test_understanding_crash_resume(db, tmp_path, fake_whisper):
    """Crash after scenes+silence: on resume only transcript/beats/saliency/
    assemble run; the scene/silence artifacts are untouched."""
    queue = JobQueue(db)
    engine, pid, project_dir = _setup(db, tmp_path)
    src = make_hardcut_video(project_dir / "media" / "clip.mp4", seg_seconds=2.0)
    _register_asset(db, engine, pid, project_dir, "ast_u2", "media/clip.mp4", src)

    job_id = queue.enqueue("understanding", {
        "project_id": pid, "asset_id": "ast_u2", "kind": "video",
        "src": "media/clip.mp4", "project_dir": str(project_dir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("understanding", u_mod.understanding_handler)

    # Run once fully, then simulate a crash rewound to after 'silence'.
    assert worker.run_one()
    done = queue.get(job_id)
    assert done["state"] == "done"
    scenes_file = project_dir / "understanding" / "ast_u2.scenes.json"
    silence_file = project_dir / "understanding" / "ast_u2.silence.json"
    scenes_mtime = scenes_file.stat().st_mtime_ns
    silence_mtime = silence_file.stat().st_mtime_ns

    # Rewind: keep scenes+silence artifacts, drop the rest; mark running.
    kept = {k: v for k, v in done["artifacts"].items() if k in ("scenes", "silence")}
    for name in ("transcript", "beats", "saliency", "assemble"):
        f = project_dir / "understanding" / f"ast_u2.{name}.json"
        if name == "assemble":
            f = project_dir / "understanding" / "ast_u2.understanding.json"
        if name == "transcript":
            f = project_dir / "understanding" / "ast_u2.transcript.json"
        if f.exists():
            f.unlink()
    db.execute("UPDATE jobs SET state='running', artifacts_json=? WHERE id=?",
               (dumps(kept), job_id))

    queue.recover_on_start()
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    # Scene + silence stages were NOT re-run (mtimes unchanged).
    assert scenes_file.stat().st_mtime_ns == scenes_mtime
    assert silence_file.stat().st_mtime_ns == silence_mtime
    # And the resumed stages produced a valid final artifact.
    assert (project_dir / "understanding" / "ast_u2.understanding.json").exists()


@pytest.mark.slow
def test_understanding_image_asset_is_empty(db, tmp_path):
    from tests.media_fixtures import make_image

    queue = JobQueue(db)
    engine, pid, project_dir = _setup(db, tmp_path)
    img = make_image(project_dir / "media" / "frame.png")
    db.execute(
        "INSERT INTO assets (project_id, asset_id, kind, src, width, height,"
        " probe_json, status) VALUES (?,?,?,?,?,?,?, 'ready')",
        (pid, "ast_img", "image", "media/frame.png", 320, 180, "{}"),
    )
    engine.apply(pid, engine.get_project(pid)["head_rev"], [{
        "op": "add_asset", "asset_id": "ast_img", "kind": "image",
        "src": "media/frame.png", "width": 320, "height": 180,
    }])
    job_id = queue.enqueue("understanding", {
        "project_id": pid, "asset_id": "ast_img", "kind": "image",
        "src": "media/frame.png", "project_dir": str(project_dir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("understanding", u_mod.understanding_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    # No audio/video signals for a still image; artifact still valid.
    final = project_dir / "understanding" / "ast_img.understanding.json"
    from cutlab.understanding.schema import Understanding

    u = Understanding.model_validate_json(final.read_text(encoding="utf-8"))
    assert u.transcript is None and u.scenes == [] and u.silence == []
