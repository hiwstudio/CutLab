"""P3.2: L1 segment previews — pure window_plan math + an end-to-end windowed
render (correct duration, fast encode)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cutlab.db import Database
from cutlab.edl.engine import Engine
from cutlab.render.planner import AudioPiece, Plan, VideoPiece, window_plan


def piece(start, end, in_ms=0, speed=1.0, image=False):
    return VideoPiece(src="m/v.mp4", is_image=image, in_ms=in_ms,
                      out_ms=in_ms + round((end - start) * speed),
                      speed=speed, start_ms=start, end_ms=end,
                      asset_w=640, asset_h=360)


def base_plan():
    return Plan(width=640, height=360, fps=30, duration_ms=10_000,
                video_tracks=[[piece(0, 4000), piece(4000, 10_000, in_ms=5000)]],
                audio=[AudioPiece(src="m/v.mp4", in_ms=0, out_ms=10_000, speed=1.0,
                                  start_ms=0, end_ms=10_000, gain_db=0.0)])


def test_window_plan_inside_one_piece():
    w = window_plan(base_plan(), 1000, 3000)
    assert w.duration_ms == 2000 and w.quality == "preview"
    [track] = w.video_tracks
    assert len(track) == 1
    p = track[0]
    assert (p.start_ms, p.end_ms) == (0, 2000)
    assert (p.in_ms, p.out_ms) == (1000, 3000)  # source follows the window
    [a] = w.audio
    assert (a.start_ms, a.end_ms, a.in_ms, a.out_ms) == (0, 2000, 1000, 3000)


def test_window_plan_straddles_pieces():
    w = window_plan(base_plan(), 3000, 6000)
    [track] = w.video_tracks
    assert len(track) == 2
    first, second = track
    assert (first.start_ms, first.end_ms) == (0, 1000)
    assert (first.in_ms, first.out_ms) == (3000, 4000)
    assert (second.start_ms, second.end_ms) == (1000, 3000)
    assert (second.in_ms, second.out_ms) == (5000, 7000)  # piece's own in offset


def test_window_plan_respects_speed():
    plan = Plan(width=640, height=360, fps=30, duration_ms=5000,
                video_tracks=[[piece(0, 5000, speed=2.0)]])
    w = window_plan(plan, 1000, 2000)
    p = w.video_tracks[0][0]
    # 1s of timeline at 2x speed = 2s of source, starting 2s in.
    assert (p.in_ms, p.out_ms) == (2000, 4000)


def test_window_plan_clamps_and_rejects_empty():
    w = window_plan(base_plan(), 8000, 99_999)
    assert w.duration_ms == 2000
    with pytest.raises(ValueError):
        window_plan(base_plan(), 5000, 5000)


def test_window_plan_image_piece():
    plan = Plan(width=640, height=360, fps=30, duration_ms=4000,
                video_tracks=[[piece(0, 4000, image=True)]])
    w = window_plan(plan, 1000, 3000)
    p = w.video_tracks[0][0]
    assert p.is_image and (p.in_ms, p.out_ms) == (0, 2000)


@pytest.mark.slow
def test_preview_render_end_to_end(db: Database, tmp_path: Path):
    """Windowed render of the middle 2s of a 6s timeline -> 2.0s output."""
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.worker import Worker
    from cutlab.render.runner import render_handler
    from cutlab.util.ffprobe import probe
    from tests.media_fixtures import make_video

    projects_dir = tmp_path / "projects"
    eng = Engine(db, projects_dir=projects_dir)
    pid = eng.create_project("Prev", {"width": 320, "height": 180, "fps": 30})["id"]
    pdir = projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    make_video(pdir / "media" / "v.mp4", seconds=6, size="320x180")
    r = eng.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_pv", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 6000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_pv",
         "in_ms": 0, "out_ms": 6000, "start_ms": 0},
    ])

    queue = JobQueue(db)
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(pdir),
        "output": "preview_test", "range_ms": [2000, 4000],
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    out = Path(job["artifacts"]["mux"]["file"])
    assert out.name == "preview_test.mp4"
    pr = probe(out)
    assert abs(pr.duration_ms - 2000) <= 100, pr.duration_ms
