"""SPLIT mode: plan schema, word-caption timing, and an end-to-end split render
(stacked geometry, duration, untouched audio, stream counts)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mixfix import assemble, templates
from mixfix.tools import FFMPEG, FFPROBE
from mixfix.ai.schemas import SchemaError
from split.schema import validate_split_plan
from split import SPLIT_STAGES
from split.render import render_split, write_word_ass

CONTEXT = {"segment_bounds": {"seg_001": [0, 3000], "seg_002": [3000, 6000]}}


def _scene(id_, seg_ids):
    return {"id": id_, "segment_ids": seg_ids,
            "visual_intent": "the fight being described", "queries": ["a query"]}


def test_full_coverage_passes():
    validate_split_plan(
        {"scenes": [_scene("s1", ["seg_001"]), _scene("s2", ["seg_002"])]},
        CONTEXT)


def test_uncovered_segment_raises():
    # the bottom pane would sit on a grey card for seg_002
    with pytest.raises(SchemaError, match="every segment"):
        validate_split_plan({"scenes": [_scene("s1", ["seg_001"])]}, CONTEXT)


def test_segment_in_two_scenes_raises():
    with pytest.raises(SchemaError, match="multiple scenes"):
        validate_split_plan(
            {"scenes": [_scene("s1", ["seg_001", "seg_002"]),
                        _scene("s2", ["seg_002"])]}, CONTEXT)


def test_missing_queries_raises():
    sc = _scene("s1", ["seg_001"])
    del sc["queries"]
    with pytest.raises(SchemaError):
        validate_split_plan({"scenes": [sc]}, CONTEXT)


def test_split_has_no_cover_limits():
    """A single scene over everything is legal here — unlike replace_plan,
    where it would breach max_cover. The speaker is never hidden."""
    validate_split_plan(
        {"scenes": [_scene("s1", ["seg_001", "seg_002"])]}, CONTEXT)


TMAP = {
    "source": {"duration_ms": 6000},
    "words": [{"text": "first", "start_ms": 0, "end_ms": 400},
              {"text": "second", "start_ms": 1000, "end_ms": 1400},
              {"text": "third", "start_ms": 5000, "end_ms": 5400}],
    "segments": [{"id": "seg_001", "text": "first second.", "start_ms": 0,
                  "end_ms": 3000},
                 {"id": "seg_002", "text": "third.", "start_ms": 3000,
                  "end_ms": 6000}],
}


def test_word_ass_holds_each_word_until_the_next(tmp_path):
    out = write_word_ass(TMAP, tmp_path / "w.ass", 1080, 960)
    body = out.read_text(encoding="utf-8")
    events = [ln for ln in body.splitlines() if ln.startswith("Dialogue:")]
    assert len(events) == 3
    # first word must hold until the second starts (1.0s), not end at 0.4s
    assert "0:00:00.00,0:00:01.00" in events[0]
    assert "FIRST" in events[0] and "\\pos(540,960)" in events[0]
    # last word gets a tail but never runs past the audio
    assert "0:00:05.80" in events[2]


def _make_video(path: Path, dur: float, pattern: str = "testsrc2",
                size: str = "320x180") -> None:
    subprocess.run(
        [FFMPEG, "-v", "error", "-y",
         "-f", "lavfi", "-i", f"{pattern}=size={size}:rate=10:duration={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(path)],
        check=True, capture_output=True)


def _probe(path: Path, entries: str) -> str:
    return subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", entries,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()


def _md5_audio(path: Path) -> str:
    return subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-map", "0:a", "-c", "copy",
         "-f", "md5", "-"], check=True, capture_output=True, text=True).stdout.strip()


def test_render_split_end_to_end(tmp_path):
    proj = tmp_path / "proj"
    (proj / "input").mkdir(parents=True)
    source = proj / "input" / "source.mp4"
    _make_video(source, 6.0)
    ref = tmp_path / "ref.mp4"
    _make_video(ref, 6.0, pattern="smptebars")

    tl = {"project": "p", "total_ms": 6000, "scenes": [
        {"id": "s1", "start_ms": 0, "end_ms": 3000,
         "visual": {"kind": "clip", "path": str(ref), "asset_id": "a",
                    "trim_in_ms": 0, "trim_out_ms": 3000}},
        {"id": "s2", "start_ms": 3000, "end_ms": 6000,
         "visual": {"kind": "clip", "path": str(ref), "asset_id": "a",
                    "trim_in_ms": 1000, "trim_out_ms": 4000}},
    ]}
    cfg = {"render": {"width": 180, "height": 320, "fps": 10},
           "split": {"top_fraction": 0.5, "word_captions": False}}

    out = render_split(proj, tl, tmap_copy(), cfg, source)
    assert out.exists()
    assert _probe(out, "stream=width,height").split() == ["180", "320"]
    assert abs(float(_probe(out, "format=duration")) * 1000 - 6000) <= 300
    # audio is stream-copied: SPLIT never modifies the original track
    assert _md5_audio(source) == _md5_audio(out)
    kinds = _probe(out, "stream=codec_type").split()
    assert kinds.count("video") == 1 and kinds.count("audio") == 1


def test_render_split_odd_top_fraction_keeps_even_panes(tmp_path):
    """An odd pane height makes libx264 reject the frame outright."""
    proj = tmp_path / "proj2"
    (proj / "input").mkdir(parents=True)
    source = proj / "input" / "source.mp4"
    _make_video(source, 4.0)
    ref = tmp_path / "ref2.mp4"
    _make_video(ref, 4.0, pattern="smptebars")

    tl = {"project": "p", "total_ms": 4000, "scenes": [
        {"id": "s1", "start_ms": 0, "end_ms": 4000,
         "visual": {"kind": "clip", "path": str(ref), "asset_id": "a",
                    "trim_in_ms": 0, "trim_out_ms": 4000}}]}
    cfg = {"render": {"width": 180, "height": 322, "fps": 10},
           "split": {"top_fraction": 0.61, "word_captions": False}}
    tmap = {"source": {"duration_ms": 4000}, "words": [],
            "segments": [{"id": "seg_001", "text": "x.", "start_ms": 0,
                          "end_ms": 4000}]}
    out = render_split(proj, tl, tmap, cfg, source)
    assert _probe(out, "stream=height").strip() in ("320", "322")


def tmap_copy():
    import copy
    return copy.deepcopy(TMAP)


def test_source_video_is_excluded_from_its_own_research(tmp_path):
    """A search for what the speaker is saying ranks the source video first —
    its transcript IS the narration. Using it puts the same footage in both
    panes (SPLIT) or covers the speaker with themselves (FIX)."""
    from mixfix.pipeline import Pipeline

    proj = tmp_path / "p"
    (proj / "input").mkdir(parents=True)
    pipe = Pipeline.__new__(Pipeline)          # only _source_video_ids is under test
    pipe.project_dir = proj
    assert pipe._source_video_ids() == set()   # local source.mp4 only

    (proj / "input" / "source.txt").write_text(
        "https://www.youtube.com/watch?v=J6Zert5VaWk\n", encoding="utf-8")
    assert pipe._source_video_ids() == {"J6Zert5VaWk"}

    for url in ("https://youtu.be/J6Zert5VaWk",
                "https://www.youtube.com/shorts/J6Zert5VaWk"):
        (proj / "input" / "source.txt").write_text(url, encoding="utf-8")
        assert pipe._source_video_ids() == {"J6Zert5VaWk"}, url


OLD_RUNS_DDL = """
CREATE TABLE runs (
    run_id     TEXT PRIMARY KEY,
    project    TEXT NOT NULL,
    mode       TEXT NOT NULL CHECK (mode IN ('mix','fix')),
    brain      TEXT NOT NULL CHECK (brain IN ('operator','api')),
    input_ref  TEXT,
    status     TEXT NOT NULL DEFAULT 'running'
               CHECK (status IN ('pending','running','paused','failed','done')),
    template   TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);"""


def test_existing_db_migrates_to_allow_split(tmp_path):
    """A database created before SPLIT must keep its rows and accept the mode."""
    import sqlite3
    from mixfix.state import State

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript(OLD_RUNS_DDL)
    con.execute("INSERT INTO runs (run_id, project, mode, brain, status,"
                " created_at, updated_at) VALUES"
                " ('run_old','proj','mix','operator','done',1.0,2.0)")
    con.commit()
    con.close()

    state = State(db)
    assert state.get_run("run_old")["project"] == "proj"   # nothing lost
    run_id = state.create_run("p2", "split", "operator", None, SPLIT_STAGES)
    assert state.get_run(run_id)["mode"] == "split"
    assert [r["stage_name"] for r in state.stages(run_id)] == SPLIT_STAGES


def test_split_template_is_portrait_and_matches_stages():
    tpl = next(t for t in templates.builtins() if t["name"] == "split")
    assert tpl["mode"] == "split"
    assert [s["name"] for s in tpl["stages"]] == SPLIT_STAGES
    asm = next(s for s in tpl["stages"] if s["name"] == "assemble")
    assert asm["params"]["render"] == {"width": 1080, "height": 1920}
    # fix_shots exists to protect the speaker; SPLIT never covers them
    assert "fix_shots" not in SPLIT_STAGES
