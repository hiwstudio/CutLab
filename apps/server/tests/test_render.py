"""B3.5 tests: render pipeline.

Includes acceptance test 3 (render correctness: duration ±1 frame + spectral
tone-order check + gain check) and acceptance test 4 (crash resume: SIGKILL
the worker mid-chunks; completed chunks are not re-rendered).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from cutlab import config
from cutlab.db import Database
from cutlab.edl.engine import Engine
from cutlab.edl.schema import EDL
from cutlab.jobs.queue import JobQueue
from cutlab.jobs.worker import Worker
from cutlab.render.audio import atempo_chain
from cutlab.render.ffgraph import compile_all
from cutlab.render.planner import build_plan
from cutlab.render.runner import render_handler
from cutlab.util.ffprobe import probe
from tests.media_fixtures import make_video

SERVER_DIR = Path(__file__).resolve().parents[1]


# -- pure-function units -----------------------------------------------------


def test_atempo_chain():
    assert atempo_chain(1.0) == []
    assert atempo_chain(2.0) == ["atempo=2"]
    assert atempo_chain(4.0) == ["atempo=2.0", "atempo=2"]
    assert atempo_chain(0.25) == ["atempo=0.5", "atempo=0.5"]
    assert atempo_chain(10.0) == ["atempo=2.0", "atempo=2.0", "atempo=2.0", "atempo=1.25"]
    assert atempo_chain(0.1) == ["atempo=0.5", "atempo=0.5", "atempo=0.5", "atempo=0.8"]


def _plan_edl(duration_ms: int) -> EDL:
    return EDL.model_validate({
        "edl_version": "1.0",
        "project": {"id": "proj_plan1", "name": "P",
                    "canvas": {"width": 320, "height": 180, "fps": 30}},
        "assets": {"ast_v1": {"kind": "video", "src": "media/v.mp4",
                              "duration_ms": duration_ms, "width": 320, "height": 180}},
        "tracks": [{"id": "trk_v1", "kind": "video", "clips": [
            {"id": "clp_v1", "asset": "ast_v1", "in_ms": 0,
             "out_ms": duration_ms, "start_ms": 0},
        ]}],
    })


def test_plan_chunks():
    plan = build_plan(_plan_edl(150_000), {"ast_v1": True})
    assert plan.chunks == [(0, 60_000), (60_000, 120_000), (120_000, 150_000)]
    assert len(plan.audio) == 1
    plan = build_plan(_plan_edl(8_000), {"ast_v1": False})
    assert plan.chunks == [(0, 8_000)]
    assert plan.audio == []


def test_compiler_deterministic(tmp_path: Path):
    plan = build_plan(_plan_edl(150_000), {"ast_v1": True})
    a = compile_all(plan, tmp_path, tmp_path / "w", tmp_path / "out.mp4")
    b = compile_all(plan, tmp_path, tmp_path / "w", tmp_path / "out.mp4")
    assert a == b
    assert len(a["chunks"]) == 3
    assert "concat" in " ".join(a["mux"])


def test_caption_tracks_planned():
    """P3.4: caption clips become CaptionPieces in the plan (burned via ASS)."""
    edl = _plan_edl(5_000)
    edl.tracks.append(EDL.model_validate({
        "edl_version": "1.0",
        "project": {"id": "proj_plan1", "name": "P",
                    "canvas": {"width": 320, "height": 180, "fps": 30}},
        "assets": {},
        "tracks": [{"id": "trk_cx", "kind": "caption", "clips": [
            {"id": "clp_cx", "start_ms": 0, "end_ms": 1000, "text": "burn me",
             "cap_style": "bold-pop"},
        ]}],
    }).tracks[0])
    plan = build_plan(edl, {"ast_v1": True})
    assert len(plan.video_tracks) == 1
    assert len(plan.captions) == 1
    cap = plan.captions[0]
    assert (cap.start_ms, cap.end_ms, cap.text, cap.style) == (0, 1000, "burn me", "bold-pop")
    # And the chunk compiler emits an ass filter for it.
    from cutlab.render.ffgraph import compile_chunk

    args = compile_chunk(plan, 0, Path("."), Path("w"))
    assert any("ass=chunk_0000.ass" in a for a in args)


# -- end-to-end render helpers ------------------------------------------------


def _decode_window(path: Path, at_s: float, dur_s: float = 0.5) -> np.ndarray:
    cmd = [config.FFMPEG, "-hide_banner", "-v", "error",
           "-ss", str(at_s), "-t", str(dur_s), "-i", str(path),
           "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float64)


def _dominant_hz(samples: np.ndarray, rate: int = 8000) -> float:
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(samples.size)))
    spectrum[0] = 0  # ignore DC
    return float(np.fft.rfftfreq(samples.size, 1 / rate)[int(spectrum.argmax())])


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples ** 2)))


def _video_duration_s(path: Path) -> float:
    r = probe(path)
    video = next(s for s in r.raw["streams"] if s["codec_type"] == "video")
    return float(video.get("duration") or r.raw["format"]["duration"])


def _setup_render_project(db: Database, tmp_path: Path, name: str) -> tuple[Engine, str, Path]:
    projects_dir = tmp_path / "projects"
    engine = Engine(db, projects_dir=projects_dir)
    pid = engine.create_project(name, {"width": 320, "height": 180, "fps": 30})["id"]
    project_dir = projects_dir / pid
    (project_dir / "media").mkdir(parents=True, exist_ok=True)
    return engine, pid, project_dir


# -- acceptance test 3: render correctness ------------------------------------


@pytest.mark.slow
def test_render_correctness_three_clips(db: Database, queue: JobQueue, tmp_path: Path):
    engine, pid, project_dir = _setup_render_project(db, tmp_path, "Correctness")
    make_video(project_dir / "media" / "a.mp4", seconds=4, tone_hz=440)
    make_video(project_dir / "media" / "b.mp4", seconds=3, tone_hz=660)
    make_video(project_dir / "media" / "c.mp4", seconds=5, tone_hz=880)

    # 3s + (2s source @ 2x = 1s) + 4s = 8.0s timeline; clip c at -12dB.
    r = engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_ta", "kind": "video", "src": "media/a.mp4",
         "duration_ms": 4000, "width": 320, "height": 180},
        {"op": "add_asset", "asset_id": "ast_tb", "kind": "video", "src": "media/b.mp4",
         "duration_ms": 3000, "width": 320, "height": 180},
        {"op": "add_asset", "asset_id": "ast_tc", "kind": "video", "src": "media/c.mp4",
         "duration_ms": 5000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_ta",
         "in_ms": 0, "out_ms": 3000, "start_ms": 0, "id": "clp_ta"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_tb",
         "in_ms": 0, "out_ms": 2000, "start_ms": 3000, "speed": 2.0, "id": "clp_tb"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_tc",
         "in_ms": 0, "out_ms": 4000, "start_ms": 4000, "gain_db": -12, "id": "clp_tc"},
    ])
    assert r["edl"]["project"]["duration_ms"] == 8000

    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(project_dir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]

    out = Path(job["artifacts"]["mux"]["file"])
    assert out.exists()
    # Duration 8.0s ± 1 frame (1/30s).
    assert _video_duration_s(out) == pytest.approx(8.0, abs=1 / 30 + 0.001)

    # Spectral check on 3 windows: tone order 440 -> 660 -> 880.
    # (atempo preserves pitch, so the 2x clip still reads 660 Hz.)
    w1 = _decode_window(out, 1.4)
    w2 = _decode_window(out, 3.3)
    w3 = _decode_window(out, 6.0)
    assert _dominant_hz(w1) == pytest.approx(440, abs=25)
    assert _dominant_hz(w2) == pytest.approx(660, abs=25)
    assert _dominant_hz(w3) == pytest.approx(880, abs=25)

    # Gain: clip c is -12dB relative to clip a (amplitude ratio ~0.25).
    ratio = _rms(w3) / _rms(w1)
    assert 0.15 < ratio < 0.4, f"gain ratio {ratio}"

    # Determinism: full command list logged in artifacts.
    cmds = json.loads(Path(job["artifacts"]["plan"]["commands"]).read_text())
    assert len(cmds["chunks"]) == 1 and cmds["mux"]


# -- gaps and layers -----------------------------------------------------------


@pytest.mark.slow
def test_render_gap_becomes_black_silence(db: Database, queue: JobQueue, tmp_path: Path):
    engine, pid, project_dir = _setup_render_project(db, tmp_path, "Gaps")
    make_video(project_dir / "media" / "a.mp4", seconds=2, tone_hz=440)
    r = engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_ga", "kind": "video", "src": "media/a.mp4",
         "duration_ms": 2000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_ga",
         "in_ms": 0, "out_ms": 1000, "start_ms": 0, "id": "clp_g1"},
        # 2s gap, then the clip again.
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_ga",
         "in_ms": 0, "out_ms": 1000, "start_ms": 3000, "id": "clp_g2"},
    ])
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(project_dir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    out = Path(job["artifacts"]["mux"]["file"])
    assert _video_duration_s(out) == pytest.approx(4.0, abs=1 / 30 + 0.001)
    # The gap window is silent; the clip windows are not.
    assert _rms(_decode_window(out, 1.7)) < 0.02 * _rms(_decode_window(out, 0.3))


# -- acceptance test 4: crash resume -------------------------------------------


@pytest.mark.slow
def test_crash_resume_kills_worker_mid_chunks(tmp_path: Path):
    """SIGKILL the standalone worker after chunk 0; on restart, completed
    chunks are not re-rendered (mtimes unchanged) and the output is valid."""
    db_path = tmp_path / "crash.db"
    db = Database(db_path)
    queue = JobQueue(db)
    engine, pid, project_dir = _setup_render_project(db, tmp_path, "Crash")
    # 3-minute synthetic timeline -> 3 chunks of 60s.
    make_video(project_dir / "media" / "long.mp4", seconds=180, tone_hz=440)
    r = engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_lg", "kind": "video", "src": "media/long.mp4",
         "duration_ms": 180_000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_lg",
         "in_ms": 0, "out_ms": 180_000, "start_ms": 0, "id": "clp_lg"},
    ])
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(project_dir),
    }, project_id=pid)

    python = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    worker_cmd = [str(python), "-m", "cutlab.jobs.worker", "--db", str(db_path), "--once"]

    # Run 1: kill as soon as chunk_0 is checkpointed.
    proc = subprocess.Popen(worker_cmd, cwd=SERVER_DIR,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 300
    killed = False
    while time.monotonic() < deadline:
        job = queue.get(job_id)
        if "chunk_0" in job["artifacts"]:
            proc.kill()  # SIGKILL equivalent on Windows
            proc.wait(timeout=30)
            killed = True
            break
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert killed, f"worker finished too fast or hung: {queue.get(job_id)['state']}"

    job = queue.get(job_id)
    assert job["state"] == "running"  # crashed mid-flight
    done_chunks = {k: Path(v["file"]) for k, v in job["artifacts"].items()
                   if k.startswith("chunk_")}
    assert done_chunks
    assert "mux" not in job["artifacts"]
    mtimes = {k: p.stat().st_mtime_ns for k, p in done_chunks.items()}

    # Run 2: fresh worker recovers and completes.
    proc = subprocess.run(worker_cmd, cwd=SERVER_DIR, capture_output=True,
                          text=True, timeout=600)
    job = queue.get(job_id)
    assert job["state"] == "done", f"{job['error']}\n{proc.stderr[-1000:]}"
    assert job["attempts"] == 1  # one crash recovery

    # Completed chunks were not re-rendered.
    for k, p in done_chunks.items():
        assert p.stat().st_mtime_ns == mtimes[k], f"{k} was re-rendered"

    out = Path(job["artifacts"]["mux"]["file"])
    assert out.exists()
    assert _video_duration_s(out) == pytest.approx(180.0, abs=0.1)
    db.close()
