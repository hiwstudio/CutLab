"""P6: capability registry — manifests, handlers, render wiring, and an
end-to-end render with a registry effect + transition + export preset."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from cutlab import capabilities
from cutlab.render.captions import caption_styles


def test_builtins_registered():
    ids = capabilities.known_cap_ids()
    assert {"grayscale", "blur", "vignette", "fade", "bold-pop",
            "h264-archive", "h264-social"} <= ids


def test_effect_filter_instantiation():
    assert capabilities.effect_filter("grayscale", {}) == "hue=s=0"
    assert capabilities.effect_filter("blur", {}) == "boxblur=8:2"
    assert capabilities.effect_filter("blur", {"radius": 4}) == "boxblur=4:2"
    assert capabilities.effect_filter("nope", {}) is None


def test_effect_params_must_be_numeric():
    # String params can't reach the filtergraph (injection-safe).
    assert capabilities.effect_filter("blur", {"radius": "8,evil=1"}) is None


def test_transition_filter():
    f = capabilities.transition_filter("fade", 2.5, 0.5)
    assert f == "fade=t=out:st=2.500:d=0.500"
    assert capabilities.transition_filter("nope", 0, 1) is None


def test_export_args():
    video, audio = capabilities.export_args("h264-social")
    assert "-maxrate" in video and "-c:a" in audio
    assert capabilities.export_args("nope") is None


def test_manifest_files_extend_registry(tmp_path, monkeypatch):
    caps_dir = tmp_path / "capabilities"
    caps_dir.mkdir()
    (caps_dir / "sepia.json").write_text(
        '{"id": "sepia", "kind": "effect", "name": "Sepia", '
        '"filter": "colorchannelmixer=.393:.769:.189", "defaults": {}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(capabilities, "CAPS_DIR", caps_dir)
    capabilities.registry.cache_clear()
    try:
        assert "sepia" in capabilities.known_cap_ids()
        assert capabilities.effect_filter("sepia", {}).startswith("colorchannelmixer")
    finally:
        capabilities.registry.cache_clear()


def test_caption_style_manifest_override(tmp_path, monkeypatch):
    caps_dir = tmp_path / "capabilities"
    caps_dir.mkdir()
    (caps_dir / "brand.json").write_text(
        '{"id": "brand-caps", "kind": "caption_style", "name": "Brand", '
        '"size_frac": 0.09, "primary": "&H00FF00FF"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(capabilities, "CAPS_DIR", caps_dir)
    capabilities.registry.cache_clear()
    try:
        styles = caption_styles()
        assert "brand-caps" in styles
        assert styles["brand-caps"].size_frac == 0.09
        assert styles["default"].size_frac != 0.09  # built-ins untouched
    finally:
        capabilities.registry.cache_clear()


def test_plan_carries_effects_and_transitions():
    from cutlab.edl.schema import EDL
    from cutlab.render.ffgraph import compile_chunk
    from cutlab.render.planner import build_plan

    edl = EDL.model_validate({
        "edl_version": "1.0",
        "project": {"id": "proj_capx1", "name": "C",
                    "canvas": {"width": 320, "height": 180, "fps": 30}},
        "assets": {"ast_v1": {"kind": "video", "src": "m/v.mp4",
                              "duration_ms": 5000, "width": 320, "height": 180}},
        "tracks": [{"id": "trk_v1", "kind": "video", "clips": [{
            "id": "clp_fx", "asset": "ast_v1", "in_ms": 0, "out_ms": 5000,
            "start_ms": 0,
            "effects": [{"cap": "grayscale", "params": {}},
                        {"cap": "unknown-fx", "params": {}}],
            "transition_out": {"cap": "fade", "duration_ms": 500},
        }]}],
    })
    plan = build_plan(edl, {"ast_v1": False})
    [piece] = plan.video_tracks[0]
    assert piece.effects == [("grayscale", {})]
    assert piece.transition_out == ("fade", 500)
    assert any("unknown-fx" in w for w in plan.warnings)
    args = compile_chunk(plan, 0, Path("."), Path("w"))
    graph = ";".join(a for a in args if "hue" in a or "fade" in a)
    assert "hue=s=0" in graph
    assert "fade=t=out:st=4.500:d=0.500" in graph  # clip tail: 5.0s - 0.5s


# -- end-to-end: registry effect visibly changes the render ---------------------


@pytest.mark.slow
def test_grayscale_effect_renders(db, tmp_path: Path):
    """testsrc2 is colourful; with the grayscale effect the rendered frame's
    chroma collapses to neutral (U/V ≈ 128)."""
    from cutlab import config
    from cutlab.db import Database
    from cutlab.edl.engine import Engine
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.worker import Worker
    from cutlab.render.runner import render_handler
    from tests.media_fixtures import make_video

    engine = Engine(db, projects_dir=tmp_path / "projects")
    pid = engine.create_project("Fx", {"width": 320, "height": 180, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    make_video(pdir / "media" / "v.mp4", seconds=2, size="320x180")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_fx", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 2000, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_fx",
         "in_ms": 0, "out_ms": 2000, "start_ms": 0, "id": "clp_fx",
         "effects": [{"cap": "grayscale", "params": {}}]},
    ])
    queue = JobQueue(db)
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": engine.get_project(pid)["head_rev"],
        "project_dir": str(pdir), "output": "fx",
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]

    out = job["artifacts"]["mux"]["file"]
    proc = subprocess.run(
        [config.FFMPEG, "-hide_banner", "-ss", "1", "-i", out, "-frames:v", "1",
         "-vf", "signalstats,metadata=print", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    uavg = float(re.search(r"signalstats\.UAVG=([0-9.]+)", proc.stderr).group(1))
    vavg = float(re.search(r"signalstats\.VAVG=([0-9.]+)", proc.stderr).group(1))
    assert abs(uavg - 128) < 3 and abs(vavg - 128) < 3, (uavg, vavg)
