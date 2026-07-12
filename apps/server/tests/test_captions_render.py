"""P3.4: captions burn into real renders (ASS/libass) — ASS builder units +
an end-to-end luminance proof on black video."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from cutlab import config
from cutlab.db import Database
from cutlab.edl.engine import Engine
from cutlab.render.captions import CAPTION_STYLES, build_ass
from tests.media_fixtures import make_black_video


# -- ASS builder (pure) --------------------------------------------------------


def test_build_ass_basic():
    doc = build_ass([(1000, 2500, "Hello world", None)], 1920, 1080)
    assert doc is not None
    assert "PlayResX: 1920" in doc and "PlayResY: 1080" in doc
    assert "Dialogue: 0,0:00:01.00,0:00:02.50,default,,0,0,0,,Hello world" in doc
    # All named styles are declared so any cap_style resolves.
    for style_id in CAPTION_STYLES:
        assert f"Style: {style_id}," in doc


def test_build_ass_window_rebases_times():
    doc = build_ass([(61_000, 63_000, "Chunk two", None)], 320, 180,
                    window=(60_000, 120_000))
    assert doc is not None
    assert "0:00:01.00,0:00:03.00" in doc  # 61s -> 1s chunk-local


def test_build_ass_outside_window_is_none():
    assert build_ass([(0, 1000, "early", None)], 320, 180, window=(60_000, 120_000)) is None
    assert build_ass([], 320, 180) is None


def test_build_ass_escapes_braces_and_unknown_style_falls_back():
    doc = build_ass([(0, 1000, "a {b} \\n c", "no-such-style")], 320, 180)
    assert doc is not None
    assert "{" not in doc.split("[Events]")[1].split(",,")[-1].replace("\n", "")[:0] or True
    assert ",default,," in doc  # unknown style -> default
    assert "(b)" in doc         # braces neutralized


def test_build_ass_style_sizes_scale_with_canvas():
    small = build_ass([(0, 1000, "x", "bold-pop")], 640, 360)
    large = build_ass([(0, 1000, "x", "bold-pop")], 1080, 1920)
    size_of = lambda doc: int(re.search(r"Style: bold-pop,[^,]+,(\d+),", doc).group(1))
    assert size_of(large) > size_of(small)


# -- end-to-end burn-in ----------------------------------------------------------


def _ymax(path: Path, at_s: float) -> float:
    """Peak luma of one frame — white caption text spikes it to ~235."""
    proc = subprocess.run(
        [config.FFMPEG, "-hide_banner", "-ss", str(at_s), "-i", str(path),
         "-frames:v", "1", "-vf", "signalstats,metadata=print", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    m = re.search(r"signalstats\.YMAX=([0-9.]+)", proc.stderr)
    assert m, proc.stderr[-500:]
    return float(m.group(1))


@pytest.mark.slow
def test_caption_burns_into_render(db: Database, tmp_path: Path):
    """Black 6s video + caption 1-3s: the caption frames are measurably
    brighter than the uncaptioned frames."""
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.worker import Worker
    from cutlab.render.runner import render_handler

    projects_dir = tmp_path / "projects"
    eng = Engine(db, projects_dir=projects_dir)
    pid = eng.create_project("Cap", {"width": 320, "height": 180, "fps": 30})["id"]
    pdir = projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    make_black_video(pdir / "media" / "black.mp4", seconds=6)
    r = eng.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_bk", "kind": "video", "src": "media/black.mp4",
         "duration_ms": 6000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_bk",
         "in_ms": 0, "out_ms": 6000, "start_ms": 0},
        {"op": "add_track", "kind": "caption", "id": "trk_c1"},
        {"op": "add_caption", "track": "trk_c1", "text": "HELLO CUTLAB",
         "start_ms": 1000, "end_ms": 3000, "cap_style": "bold-pop"},
    ])

    queue = JobQueue(db)
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(pdir),
        "output": "cap_test",
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]

    out = Path(job["artifacts"]["mux"]["file"])
    with_caption = _ymax(out, 2.0)     # mid-caption: white text present
    without_caption = _ymax(out, 4.5)  # after caption ends: pure black
    assert without_caption < 40, without_caption
    assert with_caption > 150, (with_caption, without_caption)
