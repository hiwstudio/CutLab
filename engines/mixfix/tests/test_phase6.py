"""Phase 6 — intelligent visual planning: 'generate' visual type, Style Lock,
FlowDeck job emission, montage timing."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import generate
from mixfix.ai import schemas

LOCK = ("Cinematic photoreal documentary still, dark studio void, consistent "
        "colour language, no logos or text, 16:9.")


def _ctx():
    return {"scene_ids": ["scene_001", "scene_002"],
            "scene_bounds": {"scene_001": [0, 10000], "scene_002": [10000, 20000]}}


def _generate_plan():
    return {"style_lock": LOCK, "plans": [
        {"scene_id": "scene_001", "visual_type": "video",
         "queries": ["real event footage"]},
        {"scene_id": "scene_002", "visual_type": "generate",
         "reason": "a specific named object is described; stock won't match",
         "segments": [
             {"start_ms": 10000, "delta": "the exact device, front three-quarter"},
             {"start_ms": 14000, "delta": "close on its key mechanism"},
         ]}]}


# ---- schema ----
def test_generate_plan_valid():
    schemas.validate("visual_plan", _generate_plan(), _ctx())


def test_generate_requires_style_lock():
    p = _generate_plan()
    del p["style_lock"]
    with pytest.raises(schemas.SchemaError, match="style_lock"):
        schemas.validate("visual_plan", p, _ctx())


def test_generate_first_segment_at_scene_start():
    p = _generate_plan()
    p["plans"][1]["segments"][0]["start_ms"] = 11000  # not scene start (10000)
    with pytest.raises(schemas.SchemaError, match="first segment"):
        schemas.validate("visual_plan", p, _ctx())


def test_generate_segments_must_ascend():
    p = _generate_plan()
    p["plans"][1]["segments"][1]["start_ms"] = 10000  # not > first
    with pytest.raises(schemas.SchemaError, match="ascend"):
        schemas.validate("visual_plan", p, _ctx())


def test_generate_segment_within_scene():
    p = _generate_plan()
    p["plans"][1]["segments"][1]["start_ms"] = 21000  # past scene_002 end
    with pytest.raises(schemas.SchemaError, match="outside scene"):
        schemas.validate("visual_plan", p, _ctx())


def test_legacy_video_plan_still_valid():
    plan = {"plans": [
        {"scene_id": "scene_001", "visual_type": "video", "queries": ["x"]},
        {"scene_id": "scene_002", "visual_type": "video", "queries": ["y"]}]}
    schemas.validate("visual_plan", plan, _ctx())  # no style_lock needed


# ---- generate module ----
def test_montage_durations():
    segs = [{"start_ms": 10000}, {"start_ms": 13000}, {"start_ms": 15000}]
    assert generate.montage_durations(segs, 20000) == [3000, 2000, 5000]


def test_scene_images_missing_and_present(tmp_path):
    proj = tmp_path
    assert generate.scene_images(proj, "scene_002", 2) is None
    folder = proj / "imagery" / "incoming" / "scene_002"
    folder.mkdir(parents=True)
    (folder / "scene_002_1.png").write_bytes(b"x")
    assert generate.scene_images(proj, "scene_002", 2) is None  # only 1 of 2
    (folder / "scene_002_2.jpg").write_bytes(b"y")
    imgs = generate.scene_images(proj, "scene_002", 2)
    assert [p.name for p in imgs] == ["scene_002_1.png", "scene_002_2.jpg"]


def test_emit_flowdeck_jobs_are_valid_and_locked(tmp_path):
    proj = tmp_path / "myproj"
    generate.emit_flowdeck_jobs(proj, _generate_plan(), LOCK)
    pd = proj / "imagery" / "prompts"
    master = json.loads((pd / "_master-ref.flowdeck.json").read_text())
    scene = json.loads((pd / "scene_002.flowdeck.json").read_text())
    # shape FlowDeck requires
    for j in (master, scene):
        assert j["schemaVersion"] == 2
        assert j["project"]["name"] and j["project"]["outputFolder"]
        for pr in j["prompts"]:
            assert pr["id"] and pr["filename"] and pr["prompt"]
    # every prompt carries the identical lock block, then its own SHOT
    assert scene["prompts"][0]["prompt"].startswith(LOCK + " SHOT:")
    assert scene["prompts"][1]["filename"] == "scene_002_2"
    assert len(scene["prompts"]) == 2  # one per segment


# ---- generate_visuals stage (integration) ----
def _mini_img(path, label):
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"color=c=0x2040{label}0:size=640x360:d=1",
                    "-frames:v", "1", str(path)], check=True, capture_output=True)


def test_generate_visuals_stage_pauses_then_builds(tmp_path):
    from mixfix.pipeline import Pipeline
    from mixfix.state import State
    proj = tmp_path / "proj"
    (proj / "timing").mkdir(parents=True)
    (proj / "research").mkdir()
    tmap = {"version": "1.0",
            "source": {"audio_path": "x", "duration_ms": 12000,
                       "transcriber": "json", "model": "n/a"},
            "words": [], "segments": [
                {"id": "seg_001", "text": "a.", "start_ms": 0, "end_ms": 6000,
                 "word_indices": [0, 0]},
                {"id": "seg_002", "text": "b.", "start_ms": 6000, "end_ms": 12000,
                 "word_indices": [0, 0]}],
            "scenes": [{"id": "scene_001", "segment_ids": ["seg_001", "seg_002"],
                        "start_ms": 0, "end_ms": 12000,
                        "visual_intent": "x", "assets": []}],
            "meta": {"project": "proj"}}
    (proj / "timing" / "timing_map.json").write_text(json.dumps(tmap))
    (proj / "research" / "visual_plan.json").write_text(json.dumps({
        "style_lock": LOCK, "plans": [{
            "scene_id": "scene_001", "visual_type": "generate",
            "segments": [{"start_ms": 0, "delta": "shot one of the subject"},
                         {"start_ms": 6000, "delta": "shot two of the subject"}]}]}))
    state = State(tmp_path / "t.db")
    state.conn.execute(
        "INSERT INTO runs (run_id, project, mode, brain, status, created_at,"
        " updated_at) VALUES ('r1','proj','mix','operator','running',0,0)")
    cfg = {"root": str(tmp_path), "render": {"width": 320, "height": 180,
           "fps": 10, "transition_s": 0.3}}
    pipe = Pipeline(state, None, cfg, "r1", proj, "mix")

    # images not dropped yet → paused, FlowDeck jobs emitted
    assert pipe.stage_generate_visuals() == "paused"
    assert (proj / "imagery" / "prompts" / "scene_001.flowdeck.json").exists()

    # drop the two images → builds a montage and sets the scene asset
    inc = proj / "imagery" / "incoming" / "scene_001"
    inc.mkdir(parents=True)
    _mini_img(inc / "scene_001_1.png", "8")
    _mini_img(inc / "scene_001_2.png", "a")
    assert pipe.stage_generate_visuals() == "done"
    tmap2 = json.loads((proj / "timing" / "timing_map.json").read_text())
    asset = tmap2["scenes"][0]["assets"][0]
    assert asset["kind"] == "clip" and Path(asset["path"]).exists()


# ---- research robustness (regression: stalled yt-dlp hung the whole run) ----
def test_politeness_converts_timeout_to_research_error():
    import subprocess as sp
    from mixfix.research import Politeness, ResearchError

    def always_times_out():
        raise sp.TimeoutExpired(cmd="yt-dlp", timeout=90)

    p = Politeness(min_interval_s=0.0, retries=2)
    with pytest.raises(ResearchError, match="timed out"):
        p.call(always_times_out)


def test_ytdlp_has_bounded_timeouts_configured():
    """Both call classes must carry a finite limit."""
    import tempfile, pathlib
    from mixfix.research import Cache, Politeness, YtDlpSource
    from mixfix.state import State
    src = YtDlpSource(Cache(State(pathlib.Path(tempfile.mkdtemp()) / "t.db")),
                      Politeness(min_interval_s=0.0))
    assert 0 < src.meta_timeout_s < 600
    assert 0 < src.download_timeout_s <= 3600


def test_ytdlp_timeout_fires_even_with_a_lingering_grandchild(tmp_path, monkeypatch):
    """Regression: yt-dlp spawns ffmpeg, which inherits stdout/stderr. With
    subprocess.run(capture_output=True) the timeout silently never fired —
    communicate() joined the reader threads forever. Must now fire in seconds."""
    import subprocess as sp
    import time as t
    from mixfix.research import Cache, Politeness, YtDlpSource
    from mixfix.state import State

    real_popen = sp.Popen

    def fake_popen(cmd, **kw):
        if cmd and str(cmd[0]) == "taskkill":     # let the real kill through
            return real_popen(cmd, **kw)
        # a child that outlives its parent holding the handles, like ffmpeg
        return real_popen([sys.executable, "-c", "import time; time.sleep(90)"], **kw)

    monkeypatch.setattr(sp, "Popen", fake_popen)
    src = YtDlpSource(Cache(State(tmp_path / "t.db")), Politeness(min_interval_s=0.0),
                      meta_timeout_s=2.0)
    start = t.time()
    with pytest.raises(sp.TimeoutExpired):
        src._ytdlp(["--version"])
    elapsed = t.time() - start
    assert elapsed < 30, f"timeout did not actually fire (took {elapsed:.0f}s)"


def test_truncated_download_is_rejected_not_fatal(tmp_path):
    """Regression: yt-dlp exited 0 leaving a 262-byte stub; ffmpeg then failed
    and the uncaught error killed the ENTIRE research stage."""
    from mixfix.pipeline import _playable
    stub = tmp_path / "stub.mp4"
    stub.write_bytes(b"\x00" * 262)          # what yt-dlp actually produced
    assert not _playable(stub)
    assert not _playable(tmp_path / "missing.mp4")
    real = tmp_path / "real.mp4"
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc2=size=320x180:rate=10:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", str(real)],
                   check=True, capture_output=True)
    assert _playable(real)


def test_scene_images_found_in_flowdeck_style_folder(tmp_path):
    """Images copied to imagery/<scene>/ (FlowDeck's own layout) must be found."""
    folder = tmp_path / "imagery" / "scene_007"
    folder.mkdir(parents=True)
    (folder / "scene_007_1.jpg").write_bytes(b"x")
    (folder / "scene_007_2.jpg").write_bytes(b"y")
    imgs = generate.scene_images(tmp_path, "scene_007", 2)
    assert imgs and [p.name for p in imgs] == ["scene_007_1.jpg", "scene_007_2.jpg"]


def test_ranking_prefers_shallow_offsets_when_scores_are_close():
    """Deep offsets time out / hit expired CDN URLs; a nearly-as-good shallow
    window must win. A clearly better deep match should still rank first."""
    from mixfix import match
    scene = {"start_ms": 0, "end_ms": 10000, "visual_intent": "gears",
             "text": "bronze gears", "segment_ids": []}
    cands = [{"video_id": "deep", "url": "u1", "title": "d", "channel": "c",
              "duration_s": 4000},
             {"video_id": "shallow", "url": "u2", "title": "s", "channel": "c",
              "duration_s": 300}]
    # same words -> near-identical raw scores; deep sits 50 min in
    tx = {"deep": [{"text": "bronze gears turning", "start_ms": 3000000,
                    "end_ms": 3012000}],
          "shallow": [{"text": "bronze gears turning", "start_ms": 0,
                       "end_ms": 12000}]}
    out = match.rank_candidates(scene, cands, tx)
    assert out[0]["video_id"] == "shallow", "shallow window should win a close call"


def test_playable_rejects_valid_container_with_corrupt_video(tmp_path):
    """Regression: an interrupted download can leave a good moov atom over
    corrupt H.264. Size + duration both look fine, so it used to reach
    sample_frames and raise 'Invalid NAL unit size' mid-stage."""
    import subprocess
    from mixfix.pipeline import _playable
    good = tmp_path / "good.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=320x240:rate=15:duration=3", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(good)], check=True)
    assert _playable(good)

    bad = tmp_path / "bad.mp4"
    raw = bytearray(good.read_bytes())
    # scribble over the middle of the mdat payload, leaving the container intact
    for i in range(len(raw) // 3, len(raw) // 3 + 3000):
        raw[i] = 0xFF
    bad.write_bytes(bytes(raw))
    assert bad.stat().st_size == good.stat().st_size
    assert not _playable(bad), "corrupt video data must not pass as playable"


# ---- AI task leak (regression: pending verify tasks stranded forever) ----
def _fixture_research_dir(fx, height=360):
    """Two searchable videos so a scene gets more than one candidate."""
    import subprocess
    (fx / "videos").mkdir(parents=True)
    (fx / "transcripts").mkdir()
    search = {}
    for vid, words in (("vid1", "bronze gears turning"),
                       ("vid2", "bronze gears close up")):
        # must clear MIN_SOURCE_HEIGHT or the candidate is dropped before verify
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"testsrc=size=640x{height}:rate=5:duration=6", "-c:v", "libx264",
                        "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        str(fx / "videos" / f"{vid}.mp4")],
                       check=True, capture_output=True)
        (fx / "transcripts" / f"{vid}.json").write_text(json.dumps(
            {"segments": [{"text": words, "start_ms": 0, "end_ms": 6000}]}))
        search.setdefault("bronze gears", []).append(
            {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
             "title": words, "channel": "c", "duration_s": 6})
    (fx / "search.json").write_text(json.dumps(search))


def _research_pipeline(tmp_path, height=360):
    from mixfix.ai.router import Router
    from mixfix.ai.tasks import TaskQueue
    from mixfix.pipeline import Pipeline
    from mixfix.state import State
    proj = tmp_path / "proj"
    (proj / "timing").mkdir(parents=True)
    (proj / "research").mkdir()
    _fixture_research_dir(tmp_path / "fx", height=height)
    (proj / "timing" / "timing_map.json").write_text(json.dumps({
        "version": "1.0",
        "source": {"audio_path": "x", "duration_ms": 5000,
                   "transcriber": "json", "model": "n/a"},
        "words": [], "segments": [{"id": "seg_001", "text": "bronze gears",
                                   "start_ms": 0, "end_ms": 5000,
                                   "word_indices": [0, 0]}],
        "scenes": [{"id": "scene_001", "segment_ids": ["seg_001"],
                    "start_ms": 0, "end_ms": 5000,
                    "visual_intent": "bronze gears", "assets": []}],
        "meta": {"project": "proj"}}))
    (proj / "research" / "visual_plan.json").write_text(json.dumps({
        "plans": [{"scene_id": "scene_001", "visual_type": "video",
                   "queries": ["bronze gears"]}]}))
    state = State(tmp_path / "t.db")
    state.conn.execute(
        "INSERT INTO runs (run_id, project, mode, brain, status, created_at,"
        " updated_at) VALUES ('r1','proj','mix','operator','running',0,0)")
    queue = TaskQueue(state, tmp_path / "ai_tasks")
    cfg = {"root": str(tmp_path),
           "research": {"source": "fixture", "fixture_dir": "fx"}}
    return Pipeline(state, Router("operator", queue, None), cfg, "r1", proj, "mix"), state


def _answer(state, confidence, choice=0, tier="subject"):
    """Write an operator verdict into the single open shortlist task.
    choice=None rejects the whole shortlist."""
    row = state.all_pending_ai_tasks()[0]
    (Path(row["request_dir"]) / "result.json").write_text(json.dumps(
        {"choice": choice, "tier": tier, "confidence": confidence, "reason": "r",
         "best_start_ms": None, "best_end_ms": None}))
    return row["task_id"]


def test_research_does_not_strand_verify_tasks(tmp_path):
    """Regression: a verify task raised for candidate 0 stayed 'pending' forever
    once the scene was settled another way, so every later run reported a scene
    still awaiting verification and `mixfix status` overcounted."""
    pipe, state = _research_pipeline(tmp_path)
    prog = tmp_path / "proj" / "research" / "progress.json"

    assert pipe.stage_research_extract() == "paused"
    stranded = state.all_pending_ai_tasks()
    assert len(stranded) == 1
    first_id = stranded[0]["task_id"]

    # Operator re-queries the scene while that task is still unanswered — the
    # candidate list is rebuilt, so nothing will ever consume it.
    p = json.loads(prog.read_text())
    p["scene_001"] = {"status": "new", "candidate_idx": 0, "candidates": []}
    prog.write_text(json.dumps(p))

    assert pipe.stage_research_extract() == "paused"
    open_now = state.all_pending_ai_tasks()
    assert first_id not in [r["task_id"] for r in open_now], "stale task not cleared"
    assert len(open_now) == 1, "exactly one live task after a re-query"
    assert not (tmp_path / "ai_tasks" / "pending" / first_id).exists()

    # Accept the scene; no verify task may remain open anywhere.
    _answer(state, 95)
    assert pipe.stage_research_extract() == "done"
    assert json.loads(prog.read_text())["scene_001"]["status"] == "accepted"
    assert state.all_pending_ai_tasks() == []


def test_low_resolution_candidate_is_dropped_before_verification(tmp_path):
    """Regression: a 144x216 upload reached clip verification, where the frames
    look correct — the content was never the problem. Scaled into a 1080p frame
    it is mush, so it must be dropped before spending a verification on it."""
    pipe, state = _research_pipeline(tmp_path, height=216)
    prog_path = tmp_path / "proj" / "research" / "progress.json"
    for _ in range(4):  # the stage advances one candidate per pass
        # 'paused' while candidates remain, 'done' once the scene is exhausted
        assert pipe.stage_research_extract() in ("paused", "done")
        assert state.all_pending_ai_tasks() == [], "low-res clip must not be verified"
        if json.loads(prog_path.read_text())["scene_001"]["status"] == "exhausted":
            break
    assert json.loads(prog_path.read_text())["scene_001"]["status"] == "exhausted"
    assert any("too low-res" in m for m in pipe.messages), pipe.messages


def test_resourced_scene_is_rerendered_not_reused_from_cache(tmp_path):
    """Regression: segments were named by timeline position ('007_t400.mp4') and
    _segment() skips an existing file, so a scene that gained real footage after
    re-sourcing still rendered the previous grey card."""
    import subprocess
    from mixfix import assemble
    proj = tmp_path / "proj"
    (proj / "voiceover").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", "4",
                    str(proj / "voiceover" / "voice.mp3")],
                   check=True, capture_output=True)
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=320x180:rate=10:duration=4", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(clip)], check=True, capture_output=True)
    tmap = {"source": {"duration_ms": 4000}}
    cfg = {"render": {"width": 320, "height": 180, "fps": 10, "transition_s": 0}}
    seg_dir = proj / "assembly" / "segments"

    uncovered = {"scenes": [{"id": "scene_001", "start_ms": 0, "end_ms": 4000}]}
    assemble.render(proj, uncovered, tmap, cfg)
    card = sorted(seg_dir.glob("*.mp4"))
    assert len(card) == 1
    card_bytes = card[0].read_bytes()

    # the scene is re-sourced and now has real footage
    covered = {"scenes": [{"id": "scene_001", "start_ms": 0, "end_ms": 4000,
                           "visual": {"kind": "clip", "path": str(clip),
                                      "asset_id": "abc123", "trim_in_ms": 0}}]}
    assemble.render(proj, covered, tmap, cfg)
    segs = sorted(seg_dir.glob("*.mp4"))
    assert len(segs) == 1, "the superseded segment should be pruned"
    assert segs[0].read_bytes() != card_bytes, "stale grey card was reused"


def test_section_timeout_scales_with_the_window_it_asks_for(tmp_path, monkeypatch):
    """A fixed ceiling tuned for b-roll seconds rejects a healthy fetch the
    moment a mode asks for minutes of video: measured 3.85 MiB / 45s for a 77s
    window, so a 10-minute window needs ~6 minutes and blew the 300s cap. The
    budget must be max(floor, window_seconds * per_s)."""
    import pathlib
    import tempfile
    from mixfix.research import Cache, Politeness, YtDlpSource
    from mixfix.state import State

    # chunk_s high so a single 10-min window stays on the single-fetch path and
    # this test measures the timeout scaling in isolation (chunking is covered
    # by its own test below).
    src = YtDlpSource(Cache(State(pathlib.Path(tempfile.mkdtemp()) / "t.db")),
                      Politeness(min_interval_s=0.0),
                      archive_dir=tmp_path / "arch",
                      download_timeout_s=300.0, download_timeout_per_s=3.0,
                      section_pad_s=0.0, chunk_s=100_000.0)
    seen = {}

    def fake_ytdlp(args, timeout=None, progress_glob=None):
        seen["timeout"] = timeout
        seen["progress_glob"] = progress_glob
        raise RuntimeError("stop here — the timeout is what is under test")

    monkeypatch.setattr(src, "_ytdlp", fake_ytdlp)

    # short window: the floor still governs
    try:
        src.fetch_segment("https://youtu.be/x", 0, 20_000)
    except Exception:
        pass
    assert seen["timeout"] == 300.0

    # 10-minute window: the floor would have failed a healthy fetch
    try:
        src.fetch_segment("https://youtu.be/y", 0, 600_000)
    except Exception:
        pass
    assert seen["timeout"] == 1800.0
    # The generous elapsed budget is safe only because a no-progress watchdog
    # watches the destination file; without a target it degrades to a plain wait.
    assert seen["progress_glob"], "the fetch must tell the watchdog what to watch"


def test_a_long_window_is_fetched_in_chunks_not_one_giant_request(tmp_path, monkeypatch):
    """YouTube throttles by request SIZE: a 3-min section pulls clean while an
    8-min window of the same video stalls to zero. A window past chunk_s is
    split into <=chunk_s pieces, each fetched through the ordinary path, so the
    per-fetch timeout scales with the CHUNK — never the whole window."""
    import pathlib
    import tempfile
    from mixfix.research import Cache, Politeness, YtDlpSource
    from mixfix.state import State

    src = YtDlpSource(Cache(State(pathlib.Path(tempfile.mkdtemp()) / "t.db")),
                      Politeness(min_interval_s=0.0),
                      archive_dir=tmp_path / "arch",
                      download_timeout_s=300.0, download_timeout_per_s=3.0,
                      section_pad_s=0.0, chunk_s=200.0)
    calls = []

    def fake_ytdlp(args, timeout=None, progress_glob=None):
        calls.append(timeout)
        raise RuntimeError("stop at the first chunk fetch")

    monkeypatch.setattr(src, "_ytdlp", fake_ytdlp)
    # 8-minute window -> ~3 chunks of ~160s; the first chunk fetch fires here
    try:
        src.fetch_segment("https://youtu.be/z", 0, 480_000)
    except Exception:
        pass
    assert calls, "a chunked window must still reach the single-fetch path"
    # the timeout reflects a ~160s chunk, NOT the whole 480s window (=1440)
    assert calls[0] < 1440.0, f"per-chunk timeout should scale to the chunk, got {calls[0]}"
