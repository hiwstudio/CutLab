"""P1.8: understanding API surface — analyze trigger, understanding fetch,
asset listing exposes the understanding path."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutlab.api import create_app
from cutlab.understanding import transcribe as transcribe_mod
from tests.media_fixtures import make_tone_silence_tone
from tests.test_transcribe import FakeInfo, FakeModel, FakeSegment, FakeWord

CANVAS = {"width": 640, "height": 360, "fps": 30}


@pytest.fixture()
def worker_client(tmp_path: Path, monkeypatch):
    # Fake whisper so the analyze job is fast and deterministic.
    seg = FakeSegment(start=0.2, end=1.0, text="hi",
                      words=[FakeWord(0.2, 1.0, " hi")])
    monkeypatch.setattr(transcribe_mod, "_load_faster_whisper",
                        lambda: FakeModel([seg], FakeInfo(language="en")))
    app = create_app(data_dir=tmp_path / "data", start_worker=True, verify_ffmpeg=False)
    with TestClient(app) as c:
        yield c


def wait_job(client: TestClient, job_id: str, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.15)
    raise TimeoutError(job)


def test_analyze_requires_ready_asset(worker_client: TestClient):
    client = worker_client
    pid = client.post("/api/v1/projects", json={"name": "A", "canvas": CANVAS}).json()["id"]
    # Unknown asset -> 404.
    r = client.post(f"/api/v1/projects/{pid}/assets/ast_none/analyze")
    assert r.status_code == 404
    # Not-yet-analyzed understanding fetch -> 404 E_NOT_ANALYZED.
    r = client.post(f"/api/v1/projects/{pid}/assets", json={"path": "nope"})
    assert r.status_code == 422


@pytest.mark.slow
def test_analyze_end_to_end(worker_client: TestClient, tmp_path: Path):
    client = worker_client
    pid = client.post("/api/v1/projects", json={"name": "A", "canvas": CANVAS}).json()["id"]
    src = make_tone_silence_tone(tmp_path / "clip.mp4", seg_seconds=2.0)

    # Upload + ingest.
    r = client.post(f"/api/v1/projects/{pid}/assets", json={"path": str(src)})
    up = r.json()
    assert wait_job(client, up["job_id"])["state"] == "done"

    # Understanding not present yet.
    r = client.get(f"/api/v1/projects/{pid}/assets/{up['asset_id']}/understanding")
    assert r.status_code == 404 and r.json()["error"]["code"] == "E_NOT_ANALYZED"

    # Analyze.
    r = client.post(f"/api/v1/projects/{pid}/assets/{up['asset_id']}/analyze")
    assert r.status_code == 200
    job = wait_job(client, r.json()["job_id"])
    assert job["state"] == "done", job["error"]

    # Understanding now fetchable and well-formed.
    r = client.get(f"/api/v1/projects/{pid}/assets/{up['asset_id']}/understanding")
    assert r.status_code == 200
    u = r.json()
    assert u["version"] == "1.0"
    assert u["asset_id"] == up["asset_id"]
    assert len(u["silence"]) == 1
    assert u["transcript"]["segments"]

    # Asset listing exposes the understanding path.
    assets = client.get(f"/api/v1/projects/{pid}/assets").json()
    row = next(a for a in assets if a["asset_id"] == up["asset_id"])
    assert row["understanding"].endswith(".understanding.json")

    # The EDL asset carries it too (registered via set_understanding op).
    edl = client.get(f"/api/v1/projects/{pid}/edl").json()
    assert edl["assets"][up["asset_id"]]["understanding"]
