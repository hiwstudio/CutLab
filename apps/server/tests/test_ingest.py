"""B3.4 tests: ffprobe wrapper + 4-stage checkpointed ingest."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutlab.db import Database, utcnow
from cutlab.edl.engine import Engine
from cutlab.jobs.ingest import ingest_handler
from cutlab.jobs.queue import JobQueue
from cutlab.jobs.worker import Worker
from cutlab.util.ffprobe import probe
from tests.media_fixtures import make_audio, make_image, make_video


@pytest.fixture(scope="session")
def fixture_video(tmp_path_factory) -> Path:
    return make_video(tmp_path_factory.mktemp("media") / "clip5s.mp4", seconds=5, tone_hz=440)


def test_probe_video(fixture_video: Path):
    r = probe(fixture_video)
    assert r.has_video and r.has_audio
    assert r.width == 320 and r.height == 180
    assert r.fps == pytest.approx(30, abs=0.5)
    assert r.duration_ms == pytest.approx(5000, abs=200)


def setup_project(db: Database, tmp_path: Path) -> tuple[Engine, str, Path]:
    projects_dir = tmp_path / "projects"
    engine = Engine(db, projects_dir=projects_dir)
    pid = engine.create_project("Ingest", {"width": 640, "height": 360, "fps": 30})["id"]
    project_dir = projects_dir / pid
    (project_dir / "media").mkdir(parents=True, exist_ok=True)
    return engine, pid, project_dir


def enqueue_ingest(db: Database, queue: JobQueue, pid: str, project_dir: Path,
                   asset_id: str, kind: str, src_rel: str) -> str:
    db.execute(
        "INSERT INTO assets (project_id, asset_id, kind, src, status)"
        " VALUES (?, ?, ?, ?, 'ingesting')",
        (pid, asset_id, kind, src_rel),
    )
    return queue.enqueue("ingest", {
        "project_id": pid, "asset_id": asset_id, "kind": kind,
        "src": src_rel, "project_dir": str(project_dir),
    }, project_id=pid)


def test_ingest_video_full_pipeline(db: Database, queue: JobQueue,
                                    tmp_path: Path, fixture_video: Path):
    engine, pid, project_dir = setup_project(db, tmp_path)
    src = project_dir / "media" / "clip.mp4"
    src.write_bytes(fixture_video.read_bytes())

    job_id = enqueue_ingest(db, queue, pid, project_dir, "ast_vid1", "video", "media/clip.mp4")
    worker = Worker(db, queue)
    worker.register("ingest", ingest_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    assert set(job["artifacts"]) == {"probe", "proxy", "waveform", "thumbs"}

    # Assets row updated.
    row = db.query_one("SELECT * FROM assets WHERE asset_id='ast_vid1'")
    assert row["status"] == "ready"
    assert row["duration_ms"] == pytest.approx(5000, abs=200)
    assert row["width"] == 320 and row["height"] == 180
    assert row["proxy"] == "proxies/ast_vid1.mp4"

    # Artifacts on disk.
    proxy = project_dir / "proxies" / "ast_vid1.mp4"
    assert proxy.exists() and proxy.stat().st_size > 0
    pr = probe(proxy)
    assert pr.height == 180 or pr.height == 540  # AR preserved; source smaller than 540p target
    peaks = json.loads((project_dir / "understanding" / "ast_vid1.peaks.json").read_text())
    assert 0 < len(peaks["buckets"]) <= 1000
    assert max(peaks["buckets"]) > 0.1  # the sine tone is audible
    thumbs = list((project_dir / "thumbs" / "ast_vid1").glob("t_*.jpg"))
    assert len(thumbs) >= 1  # 5s @ 1 frame / 5s

    # Registered in the EDL via add_asset op.
    edl = engine.get_edl(pid)
    assert "ast_vid1" in edl["assets"]
    assert edl["assets"]["ast_vid1"]["duration_ms"] == row["duration_ms"]
    assert edl["assets"]["ast_vid1"]["proxy"] == "proxies/ast_vid1.mp4"


def test_ingest_audio_and_image(db: Database, queue: JobQueue, tmp_path: Path):
    engine, pid, project_dir = setup_project(db, tmp_path)
    make_audio(project_dir / "media" / "tone.m4a", seconds=2, tone_hz=880)
    make_image(project_dir / "media" / "frame.png")

    enqueue_ingest(db, queue, pid, project_dir, "ast_aud1", "audio", "media/tone.m4a")
    enqueue_ingest(db, queue, pid, project_dir, "ast_img1", "image", "media/frame.png")
    worker = Worker(db, queue)
    worker.register("ingest", ingest_handler)
    assert worker.run_one() and worker.run_one()

    edl = engine.get_edl(pid)
    audio = edl["assets"]["ast_aud1"]
    assert audio["duration_ms"] == pytest.approx(2000, abs=200)
    assert "width" not in audio  # exclude_none snapshot
    image = edl["assets"]["ast_img1"]
    assert image["width"] == 320 and image["height"] == 180
    # Audio has waveform but no proxy/thumbs; image has neither.
    assert (project_dir / "understanding" / "ast_aud1.peaks.json").exists()
    assert not (project_dir / "proxies" / "ast_aud1.mp4").exists()
    assert not (project_dir / "thumbs" / "ast_img1").exists()


def test_ingest_missing_source_fails(db: Database, queue: JobQueue, tmp_path: Path):
    engine, pid, project_dir = setup_project(db, tmp_path)
    job_id = enqueue_ingest(db, queue, pid, project_dir, "ast_gone", "video", "media/gone.mp4")
    worker = Worker(db, queue)
    worker.register("ingest", ingest_handler)
    for _ in range(3):
        worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "failed"
    assert db.query_one("SELECT status FROM assets WHERE asset_id='ast_gone'")["status"] == "failed"


def test_ingest_resume_skips_probe_and_proxy(db: Database, queue: JobQueue,
                                             tmp_path: Path, fixture_video: Path):
    """Crash after proxy stage: restart runs only waveform + thumbs."""
    engine, pid, project_dir = setup_project(db, tmp_path)
    src = project_dir / "media" / "clip.mp4"
    src.write_bytes(fixture_video.read_bytes())
    job_id = enqueue_ingest(db, queue, pid, project_dir, "ast_res1", "video", "media/clip.mp4")

    worker = Worker(db, queue)
    worker.register("ingest", ingest_handler)
    assert worker.run_one()
    done = queue.get(job_id)
    assert done["state"] == "done"
    proxy = project_dir / "proxies" / "ast_res1.mp4"
    proxy_mtime = proxy.stat().st_mtime_ns

    # Simulate crash-after-proxy: reset to running with waveform+thumbs artifacts gone.
    artifacts = {k: v for k, v in done["artifacts"].items() if k in ("probe", "proxy")}
    (project_dir / "understanding" / "ast_res1.peaks.json").unlink()
    for t in (project_dir / "thumbs" / "ast_res1").glob("*"):
        t.unlink()
    from cutlab.db import dumps
    db.execute("UPDATE jobs SET state='running', artifacts_json=? WHERE id=?",
               (dumps(artifacts), job_id))
    # EDL already has the asset; drop it so re-registration isn't a dup...
    # actually the E_DUP guard makes re-registration a no-op. Leave it.

    queue.recover_on_start()
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    # Proxy untouched (mtime unchanged) — stage was skipped.
    assert proxy.stat().st_mtime_ns == proxy_mtime
    assert (project_dir / "understanding" / "ast_res1.peaks.json").exists()
    assert len(list((project_dir / "thumbs" / "ast_res1").glob("t_*.jpg"))) >= 1
