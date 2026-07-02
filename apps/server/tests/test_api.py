"""B3.6 tests: HTTP + WS API surface, incl. acceptance test 5 (optimistic
locking: two concurrent applies from the same base_rev -> one 200, one 409)."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from cutlab.api import create_app
from tests.media_fixtures import make_video

CANVAS = {"width": 320, "height": 180, "fps": 30}


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data", start_worker=False, verify_ffmpeg=False)
    with TestClient(app) as c:
        c.data_dir = tmp_path / "data"
        yield c


@pytest.fixture()
def worker_client(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data", start_worker=True, verify_ffmpeg=False)
    with TestClient(app) as c:
        yield c


def make_project(client: TestClient, name: str = "API") -> str:
    r = client.post("/api/v1/projects", json={"name": name, "canvas": CANVAS})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def setup_timeline(client: TestClient, pid: str) -> int:
    # The asset src must exist on disk (E_SRC is enforced once the project
    # dir exists); a stub file is enough for apply-only tests.
    stub = client.data_dir / "projects" / pid / "media" / "x.mp4"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_bytes(b"stub")
    r = client.post(f"/api/v1/projects/{pid}/apply", json={"base_rev": 0, "ops": [
        {"op": "add_asset", "asset_id": "ast_x1", "kind": "video", "src": "media/x.mp4",
         "duration_ms": 5000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_x1",
         "in_ms": 0, "out_ms": 3000, "start_ms": 0, "id": "clp_x1"},
    ]})
    assert r.status_code == 200, r.text
    return r.json()["rev"]


def test_project_crud(client: TestClient):
    pid = make_project(client)
    assert client.get(f"/api/v1/projects/{pid}").json()["head_rev"] == 0
    assert any(p["id"] == pid for p in client.get("/api/v1/projects").json())
    edl = client.get(f"/api/v1/projects/{pid}/edl").json()
    assert edl["project"]["canvas"]["width"] == 320
    assert client.get("/api/v1/projects/proj_none1").status_code == 404
    r = client.post("/api/v1/projects", json={"name": "Bad", "canvas": {**CANVAS, "fps": 23.9}})
    assert r.status_code == 422


def test_apply_conflict_and_validation(client: TestClient):
    pid = make_project(client)
    rev = setup_timeline(client, pid)
    assert rev == 1
    # Stale base_rev -> 409 with E_CONFLICT.
    r = client.post(f"/api/v1/projects/{pid}/apply", json={"base_rev": 0, "ops": []})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "E_CONFLICT"
    # Invalid plan -> 422 with issues.
    r = client.post(f"/api/v1/projects/{pid}/apply", json={"base_rev": rev, "ops": [
        {"op": "trim", "clip": "clp_missing", "new_in_ms": 0},
    ]})
    assert r.status_code == 422
    issues = r.json()["error"]["issues"]
    assert issues[0]["code"] == "E_REF"
    # EDL at old rev still fetchable.
    assert client.get(f"/api/v1/projects/{pid}/edl", params={"rev": 0}).json()["tracks"] == []


def test_optimistic_locking_concurrent(tmp_path: Path):
    """Acceptance test 5: two concurrent applies from the same base_rev."""
    app = create_app(data_dir=tmp_path / "data", start_worker=False, verify_ffmpeg=False)

    async def run() -> list[int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/v1/projects", json={"name": "Race", "canvas": CANVAS})
            pid = r.json()["id"]
            plan = {"base_rev": 0, "ops": [{"op": "add_track", "kind": "video"}]}
            r1, r2 = await asyncio.gather(
                ac.post(f"/api/v1/projects/{pid}/apply", json=plan),
                ac.post(f"/api/v1/projects/{pid}/apply", json=plan),
            )
            return sorted([r1.status_code, r2.status_code])

    assert asyncio.run(run()) == [200, 409]


def test_undo_redo_endpoints(client: TestClient):
    pid = make_project(client)
    rev = setup_timeline(client, pid)
    assert client.post(f"/api/v1/projects/{pid}/undo").json()["rev"] == 0
    assert client.post(f"/api/v1/projects/{pid}/redo").json()["rev"] == rev
    client.post(f"/api/v1/projects/{pid}/undo")
    r = client.post(f"/api/v1/projects/{pid}/undo")
    assert r.status_code == 422  # nothing to undo


def test_revisions_list(client: TestClient):
    pid = make_project(client)
    setup_timeline(client, pid)
    revs = client.get(f"/api/v1/projects/{pid}/revisions").json()
    assert [r["rev"] for r in revs] == [0, 1]
    assert revs[0]["summary"] == "create project"


def test_ws_revision_events(client: TestClient):
    pid = make_project(client)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"project_id": pid})
        time.sleep(0.1)  # let the subscribe land
        setup_timeline(client, pid)
        msg = ws.receive_json()
        assert msg["type"] == "revision"
        assert msg["project_id"] == pid and msg["rev"] == 1


def test_media_traversal_forbidden(client: TestClient):
    pid = make_project(client)
    r = client.get(f"/media/{pid}/..%2f..%2fcutlab.db")
    assert r.status_code in (403, 404)


def test_job_endpoints_404(client: TestClient):
    assert client.get("/api/v1/jobs/job_nope").status_code == 404
    assert client.post("/api/v1/jobs/job_nope/cancel").status_code == 404


def test_render_requires_known_rev(client: TestClient):
    pid = make_project(client)
    r = client.post(f"/api/v1/projects/{pid}/render", json={"rev": 99})
    assert r.status_code == 404


def wait_job(client: TestClient, job_id: str, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.15)
    raise TimeoutError(job)


@pytest.mark.slow
def test_upload_ingest_render_e2e(worker_client: TestClient, tmp_path: Path):
    """Upload -> ingest job -> EDL asset -> timeline -> render -> media serving."""
    client = worker_client
    pid = make_project(client, "E2E")
    fixture = make_video(tmp_path / "src.mp4", seconds=3, tone_hz=440)

    with fixture.open("rb") as f:
        r = client.post(f"/api/v1/projects/{pid}/assets",
                        files={"file": ("clip.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["status"] == "ingesting"

    job = wait_job(client, up["job_id"])
    assert job["state"] == "done", job["error"]

    assets = client.get(f"/api/v1/projects/{pid}/assets").json()
    assert assets[0]["status"] == "ready"
    assert assets[0]["proxy"] == f"proxies/{up['asset_id']}.mp4"
    edl = client.get(f"/api/v1/projects/{pid}/edl").json()
    assert up["asset_id"] in edl["assets"]

    # Proxy is served over /media.
    r = client.get(f"/media/{pid}/{assets[0]['proxy']}")
    assert r.status_code == 200 and len(r.content) > 0

    # Build a 2s cut and render it.
    head = client.get(f"/api/v1/projects/{pid}").json()["head_rev"]
    r = client.post(f"/api/v1/projects/{pid}/apply", json={"base_rev": head, "ops": [
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": up["asset_id"],
         "in_ms": 500, "out_ms": 2500, "start_ms": 0},
    ]})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/projects/{pid}/render", json={})
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["job_id"])
    assert job["state"] == "done", job["error"]

    # Final render served over /media.
    rel = Path(job["artifacts"]["mux"]["file"]).name
    r = client.get(f"/media/{pid}/renders/{rel}")
    assert r.status_code == 200 and len(r.content) > 1000


@pytest.mark.slow
def test_upload_by_path_and_cancel(worker_client: TestClient, tmp_path: Path):
    client = worker_client
    pid = make_project(client, "ByPath")
    fixture = make_video(tmp_path / "byp.mp4", seconds=2, tone_hz=440)
    r = client.post(f"/api/v1/projects/{pid}/assets", json={"path": str(fixture)})
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["job_id"])
    assert job["state"] == "done", job["error"]
    r = client.post(f"/api/v1/projects/{pid}/assets", json={"path": str(tmp_path / "no.mp4")})
    assert r.status_code == 422
