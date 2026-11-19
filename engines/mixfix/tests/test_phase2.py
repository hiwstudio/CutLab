"""Phase 2 tests: matching funnel, visual plan / verify schemas, library dedup,
fixture research source."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import match
from mixfix.ai import schemas
from mixfix.library import Library, sha1_file
from mixfix.research import FixtureSource
from mixfix.state import State


# ---- matching ----
def _transcript():
    return [
        {"text": "welcome to the channel today we look at cars",
         "start_ms": 0, "end_ms": 4000},
        {"text": "here is the engine bay of the revuelto hybrid v12",
         "start_ms": 4000, "end_ms": 9000},
        {"text": "the electric motors sit on the front axle",
         "start_ms": 9000, "end_ms": 14000},
        {"text": "now let us talk about the interior seats",
         "start_ms": 14000, "end_ms": 19000},
    ]


def test_rank_windows_finds_relevant_section():
    ranked = match.rank_windows(
        "Underneath the body is a hybrid V12 with electric motors.",
        "engine bay close-up", _transcript(), target_ms=5000)
    assert ranked, "expected at least one window"
    top = ranked[0]
    assert top["score"] > 0
    # top window must include the engine-bay sentence (4000-9000)
    assert top["start_ms"] <= 4000 + 1500 and top["end_ms"] >= 9000 - 1500


def test_rank_windows_empty_transcript():
    assert match.rank_windows("x", "y", [], 5000) == []


def test_rank_candidates_orders_by_score():
    scene = {"text": "hybrid v12 engine with electric motors",
             "visual_intent": "engine bay", "start_ms": 0, "end_ms": 5000,
             "segment_ids": []}
    cands = [{"video_id": "good", "url": "u1", "title": "t", "channel": "c",
              "duration_s": 60},
             {"video_id": "bad", "url": "u2", "title": "t", "channel": "c",
              "duration_s": 60}]
    transcripts = {"good": _transcript(),
                   "bad": [{"text": "cooking pasta recipe tutorial",
                            "start_ms": 0, "end_ms": 20000}]}
    ranked = match.rank_candidates(scene, cands, transcripts)
    assert ranked[0]["video_id"] == "good"


# ---- schemas ----
def test_visual_plan_schema():
    ctx = {"scene_ids": ["scene_001", "scene_002"]}
    good = {"plans": [
        {"scene_id": "scene_001", "visual_type": "video",
         "queries": ["lamborghini engine bay"]},
        {"scene_id": "scene_002", "visual_type": "image",
         "image_prompt": "ultra realistic photo of a v12 engine bay"},
    ]}
    schemas.validate("visual_plan", good, ctx)
    bad = {"plans": [good["plans"][0]]}  # missing scene_002
    with pytest.raises(schemas.SchemaError, match="cover every scene"):
        schemas.validate("visual_plan", bad, ctx)
    bad2 = {"plans": [{**good["plans"][0], "queries": []},
                      good["plans"][1]]}
    with pytest.raises(schemas.SchemaError, match="queries"):
        schemas.validate("visual_plan", bad2, ctx)


def test_verify_clip_schema():
    schemas.validate("verify_clip",
                     {"confidence": 88, "reason": "shows engine bay"}, {})
    with pytest.raises(schemas.SchemaError, match="confidence"):
        schemas.validate("verify_clip",
                         {"confidence": 150, "reason": "x"}, {})
    with pytest.raises(schemas.SchemaError, match="confidence"):
        schemas.validate("verify_clip",
                         {"confidence": "high", "reason": "x"}, {})


# ---- library ----
def _mini_video(path: Path, seconds: int = 2):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"testsrc=size=64x64:rate=5:duration={seconds}",
         "-c:v", "libx264", "-preset", "ultrafast", str(path)],
        check=True, capture_output=True)


def test_library_dedup(tmp_path):
    state = State(tmp_path / "t.db")
    lib = Library(state, tmp_path / "library")
    v1, v2 = tmp_path / "a.mp4", tmp_path / "b.mp4"
    _mini_video(v1)
    v2.write_bytes(v1.read_bytes())  # identical content
    r1 = lib.ingest_clip(v1, "run_x", {"source_url": "u"})
    r2 = lib.ingest_clip(v2, "run_x", {"source_url": "u"})
    assert r1["asset_id"] == r2["asset_id"]
    assert r1["duplicate"] is False and r2["duplicate"] is True
    assert lib.dedup_hits == 1
    assert len(list((tmp_path / "library" / "clips").glob("*.mp4"))) == 1


# ---- fixture source ----
def test_fixture_source_search_and_extract(tmp_path):
    fx = tmp_path / "fx"
    (fx / "videos").mkdir(parents=True)
    (fx / "transcripts").mkdir()
    _mini_video(fx / "videos" / "vid1.mp4", seconds=4)
    (fx / "search.json").write_text(json.dumps({
        "engine bay": [{"video_id": "vid1",
                        "url": "https://www.youtube.com/watch?v=vid1",
                        "title": "Engine tour", "channel": "cars",
                        "duration_s": 4}]}))
    (fx / "transcripts" / "vid1.json").write_text(json.dumps({
        "segments": [{"text": "the engine bay", "start_ms": 0, "end_ms": 4000}]}))
    src = FixtureSource(fx)
    res = src.search("engine bay close up", n=3)  # token-overlap fallback
    assert res and res[0]["video_id"] == "vid1"
    assert src.transcript("vid1", res[0]["url"])[0]["text"] == "the engine bay"
    out = src.extract_section(res[0]["url"], 500, 2500, tmp_path / "clip.mp4")
    assert out.exists() and sha1_file(out)
