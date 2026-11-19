"""Phase 3 tests: timeline build/score/edits, preview HTTP round-trip, gate."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import timeline as tl
from mixfix.preview import PreviewHandler, approve_gate, ensure_gate
from mixfix.state import State


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / "timing").mkdir(parents=True)
    tmap = {
        "version": "1.0",
        "source": {"audio_path": "x", "duration_ms": 20000,
                   "transcriber": "json", "model": "n/a"},
        "words": [],
        "segments": [
            {"id": "seg_001", "text": "first sentence.", "start_ms": 0,
             "end_ms": 10000, "word_indices": [0, 0]},
            {"id": "seg_002", "text": "second sentence.", "start_ms": 10000,
             "end_ms": 20000, "word_indices": [0, 0]},
        ],
        "scenes": [
            {"id": "scene_001", "segment_ids": ["seg_001"], "start_ms": 0,
             "end_ms": 10000, "visual_intent": "a thing",
             "assets": [{"asset_id": "abc", "kind": "clip",
                         "path": str(tmp_path / "missing.mp4"),
                         "confidence": 90}]},
            {"id": "scene_002", "segment_ids": ["seg_002"], "start_ms": 10000,
             "end_ms": 20000, "visual_intent": "another thing", "assets": []},
        ],
        "meta": {"project": "proj"},
    }
    (proj / "timing" / "timing_map.json").write_text(json.dumps(tmap))
    (proj / "research").mkdir()
    (proj / "research" / "progress.json").write_text(json.dumps({
        "scene_001": {"status": "accepted", "candidate_idx": 0,
                      "accepted": {"candidate_idx": 0},
                      "candidates": [
                          {"title": "t0", "channel": "c", "url": "u?v=x",
                           "clip_start_ms": 0, "clip_end_ms": 5000, "score": 0.9},
                          {"title": "t1", "channel": "c", "url": "u?v=y",
                           "clip_start_ms": 0, "clip_end_ms": 5000, "score": 0.5}]},
    }))
    return proj


def test_build_and_score(tmp_path):
    proj = _project(tmp_path)
    t = tl.build(proj)
    assert len(t["scenes"]) == 2
    s = t["score"]
    assert s["coverage_pct"] == 50.0            # scene_002 uncovered
    assert s["max_uncovered_stretch_ms"] == 10000
    assert s["confidence_floor"] == 90
    assert s["weak_scenes"] == ["scene_002"]
    # non-accepted candidate listed as alternative
    assert t["scenes"][0]["alternatives"][0]["candidate_idx"] == 1


def test_edits_round_trip(tmp_path):
    proj = _project(tmp_path)
    t = tl.build(proj)
    t = tl.apply_edit(proj, t, {"action": "approve_clip", "scene_id": "scene_001"})
    assert t["scenes"][0]["review"] == "approved"
    t = tl.apply_edit(proj, t, {"action": "trim", "scene_id": "scene_001",
                                "trim_in_ms": 100, "trim_out_ms": 4000})
    assert t["scenes"][0]["visual"]["trim_in_ms"] == 100
    with pytest.raises(tl.EditError):
        tl.apply_edit(proj, t, {"action": "trim", "scene_id": "scene_001",
                                "trim_in_ms": 5000, "trim_out_ms": 100})
    t = tl.apply_edit(proj, t, {"action": "swap_alternative",
                                "scene_id": "scene_001", "candidate_idx": 1})
    prog = json.loads((proj / "research" / "progress.json").read_text())
    assert prog["scene_001"]["status"] == "verifying"
    assert prog["scene_001"]["candidate_idx"] == 1
    assert t["scenes"][0]["visual"] is None
    # edits persist: reload matches
    assert tl.load(proj)["scenes"][0]["review"] == "pending"


def test_gate_block_and_approve(tmp_path):
    state = State(tmp_path / "t.db")
    state.conn.execute(
        "INSERT INTO runs (run_id, project, mode, brain, status, created_at,"
        " updated_at) VALUES ('r1','p','mix','operator','running',0,0)")
    gate = ensure_gate(state, "r1", "timeline_approval")
    assert gate["status"] == "pending"
    assert ensure_gate(state, "r1", "timeline_approval")["gate_id"] == gate["gate_id"]
    approve_gate(state, "r1", "timeline_approval")
    assert ensure_gate(state, "r1", "timeline_approval")["status"] == "approved"


def test_preview_http_round_trip(tmp_path):
    """Regression: gate approval from a handler thread (check_same_thread bug)."""
    proj = _project(tmp_path)
    tl.build(proj)
    state = State(tmp_path / "t.db")
    state.conn.execute(
        "INSERT INTO runs (run_id, project, mode, brain, status, created_at,"
        " updated_at) VALUES ('r1','p','mix','operator','running',0,0)")
    ensure_gate(state, "r1", "timeline_approval")
    handler = type("H", (PreviewHandler,),
                   {"project_dir": proj, "state": state, "run_id": "r1"})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        body = json.dumps({"action": "approve_clip",
                           "scene_id": "scene_001"}).encode()
        r = urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{port}/edit", data=body))
        assert json.loads(r.read())["ok"] is True
        r = urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{port}/approve", data=b"{}"))
        assert json.loads(r.read())["ok"] is True
        assert ensure_gate(state, "r1", "timeline_approval")["status"] == "approved"
    finally:
        httpd.shutdown()


def test_review_endpoints_round_trip(tmp_path):
    """New review app: comments, flags, submit package, approval blockers."""
    proj = _project(tmp_path)
    tl.build(proj)
    state = State(tmp_path / "t.db")
    state.conn.execute(
        "INSERT INTO runs (run_id, project, mode, brain, status, created_at,"
        " updated_at) VALUES ('r1','p','mix','operator','running',0,0)")
    ensure_gate(state, "r1", "timeline_approval")
    handler = type("H", (PreviewHandler,),
                   {"project_dir": proj, "state": state, "run_id": "r1",
                    "video_path": None})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def post(path, obj, expect_error=False):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(obj).encode()))
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            assert expect_error, e.read()
            return json.loads(e.read())

    try:
        # state endpoint serves the app's data contract
        st = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/state").read())
        assert st["timeline"]["scenes"] and st["video_ready"] is False
        # scene + project comments persist
        assert post("/comment", {"scene_id": "scene_001", "text": "tight"})["ok"]
        assert post("/comment", {"scene_id": None, "text": "overall good"})["ok"]
        # flag blocks approval; changes-request always allowed
        assert post("/flag", {"scene_id": "scene_001", "flag": "revision"})["ok"]
        err = post("/submit", {"decision": "approve"}, expect_error=True)
        assert "scene_001" in err["error"]
        assert post("/submit", {"decision": "changes"})["ok"]
        pkg = json.loads((proj / "review_package.json").read_text())
        assert pkg["decision"] == "changes"
        assert pkg["scenes"][0]["comments"][0]["text"] == "tight"
        assert pkg["project_comments"][0]["text"] == "overall good"
        # clearing the flag unlocks approval, which approves the gate
        assert post("/flag", {"scene_id": "scene_001", "flag": None})["ok"]
        assert post("/submit", {"decision": "approve"})["ok"]
        assert ensure_gate(state, "r1", "timeline_approval")["status"] == "approved"
    finally:
        httpd.shutdown()


def test_review_board_rows_cannot_grow_past_the_viewport():
    """Regression: with `1fr` the auto-sized row grew to the inspector's full
    scroll length, pushing the stage below the fold — the bottom of the video
    and the transport bar were cut off, and the body is overflow:hidden so
    nothing could scroll back to them. Panes scroll; the frame never does."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "mixfix" / "review_ui.html"
           ).read_text(encoding="utf-8")
    assert "grid-template-rows:48px minmax(0,1fr) auto" in css
    assert "grid-template-rows:minmax(0,1fr)" in css, "#main row must be capped"


def test_preview_is_invalidated_by_a_re_cut_clip(tmp_path):
    """Regression: freshness was judged on timeline.json alone. Re-cutting a
    clip (now a one-second local operation, so it happens often) changes the
    pixels without touching the timeline, and the stale render kept being
    served as current — frames grabbed from it produced a wrong conclusion
    about a crop that had actually worked."""
    import json
    import os
    import time

    from mixfix.preview import _inputs_mtime

    proj = tmp_path / "p"
    (proj / "timeline").mkdir(parents=True)
    clip = proj / "clip.mp4"
    clip.write_bytes(b"x")
    tl = proj / "timeline" / "timeline.json"
    tl.write_text(json.dumps({"scenes": [
        {"id": "s1", "visual": {"kind": "clip", "path": str(clip)}}]}))

    before = _inputs_mtime(proj, tl)
    # the clip is re-cut; the timeline is untouched
    later = time.time() + 50
    os.utime(clip, (later, later))
    assert _inputs_mtime(proj, tl) > before, \
        "a re-cut clip must invalidate the cached preview"
