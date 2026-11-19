"""P2.2-2.4: smart ops — remove_silence, caption_from_transcript, reframe.

Pure planner tests + op-level tests through the engine with a real understanding
artifact on disk (so OpContext loading is exercised end to end)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutlab.db import Database
from cutlab.edl.engine import Engine, Rejected
from cutlab.edl.schema import EDL, MediaClip
from cutlab.edl.smartops import (
    group_words_into_phrases,
    overlap_source_span,
    plan_caption_from_transcript,
    plan_remove_silence,
    source_ms_to_timeline,
)
from cutlab.understanding.schema import (
    SilenceSpan,
    Transcript,
    TranscriptSegment,
    Understanding,
    Word,
)

CANVAS = {"width": 1280, "height": 720, "fps": 30}


def make_edl_with_clip(**clip_over) -> EDL:
    clip = {"id": "clp_a1", "asset": "ast_v1", "in_ms": 0, "out_ms": 10000,
            "start_ms": 0, **clip_over}
    return EDL.model_validate({
        "edl_version": "1.0",
        "project": {"id": "proj_smrt1", "name": "S", "canvas": CANVAS},
        "assets": {"ast_v1": {"kind": "video", "src": "m/v.mp4",
                              "duration_ms": 10000, "width": 1280, "height": 720}},
        "tracks": [{"id": "trk_v1", "kind": "video", "clips": [clip]}],
    })


def understanding_with(silence=None, segments=None) -> Understanding:
    return Understanding(
        version="1.0", asset_id="ast_v1", kind="video", duration_ms=10000,
        silence=[SilenceSpan(start_ms=s, end_ms=e) for s, e in (silence or [])],
        transcript=Transcript(language="en", segments=segments or []) if segments is not None else None,
    )


# -- mapping helpers ----------------------------------------------------------


def test_source_to_timeline_identity():
    clip = make_edl_with_clip().tracks[0].clips[0]
    assert source_ms_to_timeline(clip, 3000) == 3000
    assert source_ms_to_timeline(clip, 10000) is None   # out of window
    assert source_ms_to_timeline(clip, -1) is None


def test_source_to_timeline_with_speed_and_offset():
    # in=2000, speed=2x, start=1000: source 4000 -> (4000-2000)/2 + 1000 = 2000
    clip = make_edl_with_clip(in_ms=2000, out_ms=6000, speed=2.0, start_ms=1000).tracks[0].clips[0]
    assert source_ms_to_timeline(clip, 4000) == 2000
    span = overlap_source_span(clip, 3000, 5000)  # -> tl (1500, 2500)
    assert span == (1500, 2500)


# -- remove_silence planner ---------------------------------------------------


def test_plan_remove_silence_basic():
    edl = make_edl_with_clip()
    u = understanding_with(silence=[(3000, 5000)])
    plan = plan_remove_silence(edl, u, "ast_v1", None, min_ms=300, ripple=True)
    assert len(plan) == 1
    assert plan[0]["op"] == "delete_range"
    assert (plan[0]["from_ms"], plan[0]["to_ms"]) == (3000, 5000)
    assert plan[0]["ripple"] is True


def test_plan_remove_silence_respects_min_ms():
    edl = make_edl_with_clip()
    u = understanding_with(silence=[(1000, 1100), (3000, 5000)])  # 100ms + 2000ms
    plan = plan_remove_silence(edl, u, "ast_v1", None, min_ms=500, ripple=True)
    assert len(plan) == 1
    assert (plan[0]["from_ms"], plan[0]["to_ms"]) == (3000, 5000)


def test_plan_remove_silence_multiple_deleted_right_to_left():
    edl = make_edl_with_clip()
    u = understanding_with(silence=[(1000, 2000), (6000, 7000)])
    plan = plan_remove_silence(edl, u, "ast_v1", None, min_ms=300, ripple=True)
    # Two ranges, emitted latest-first so ripples don't shift earlier coords.
    assert [(o["from_ms"], o["to_ms"]) for o in plan] == [(6000, 7000), (1000, 2000)]


def test_plan_remove_silence_no_silence():
    edl = make_edl_with_clip()
    assert plan_remove_silence(edl, understanding_with(silence=[]), "ast_v1", None, 300, True) == []


# -- remove_silence through the engine ----------------------------------------


@pytest.fixture()
def engine(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    projects_dir = tmp_path / "projects"
    eng = Engine(db, projects_dir=projects_dir)
    yield eng
    db.close()


def _project_with_analyzed_asset(engine: Engine, understanding: Understanding,
                                 clip=True) -> str:
    p = engine.create_project("Smart", CANVAS)
    pid = p["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "v.mp4").write_bytes(b"stub")
    # Write the understanding artifact and register it.
    udir = pdir / "understanding"
    udir.mkdir(parents=True, exist_ok=True)
    (udir / "ast_v1.understanding.json").write_text(
        understanding.model_dump_json(exclude_none=True), encoding="utf-8"
    )
    ops = [
        {"op": "add_asset", "asset_id": "ast_v1", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 10000, "width": 1280, "height": 720},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_track", "kind": "caption", "id": "trk_c1"},
        {"op": "set_understanding", "asset": "ast_v1",
         "understanding": "understanding/ast_v1.understanding.json"},
    ]
    if clip:
        ops.append({"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
                    "in_ms": 0, "out_ms": 10000, "start_ms": 0, "id": "clp_a1"})
    engine.apply(pid, engine.get_project(pid)["head_rev"], ops)
    return pid


def clips_on(edl: dict, track_id: str) -> list[dict]:
    return next(t for t in edl["tracks"] if t["id"] == track_id)["clips"]


def test_remove_silence_op_end_to_end(engine: Engine):
    u = understanding_with(silence=[(3000, 5000)])
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [
        {"op": "remove_silence", "asset": "ast_v1", "tracks": ["trk_v1"]},
    ])
    # The 2s silence was cut and the tail rippled left: 10s clip -> 8s of content.
    assert r["edl"]["project"]["duration_ms"] == 8000
    assert "remove silence" in r["summary"]


def test_remove_silence_without_understanding_errors(engine: Engine):
    # Asset with no understanding registered.
    p = engine.create_project("NoU", CANVAS)
    pid = p["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "v.mp4").write_bytes(b"stub")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_v1", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 10000, "width": 1280, "height": 720},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 10000, "start_ms": 0},
    ])
    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"],
                     [{"op": "remove_silence", "asset": "ast_v1"}])
    assert exc.value.issues[0].code == "E_NO_UNDERSTANDING"


# -- caption_from_transcript --------------------------------------------------


def words(*specs) -> list[Word]:
    return [Word(start_ms=s, end_ms=e, word=w) for s, e, w in specs]


def test_group_words_into_phrases_by_count_and_punct():
    ws = words((0, 100, "one"), (100, 200, "two"), (200, 300, "three."),
               (300, 400, "four"), (400, 500, "five"))
    groups = group_words_into_phrases(ws, max_words=6, max_gap_ms=700)
    # Sentence break after "three." then the rest.
    assert [g[2] for g in groups] == ["one two three.", "four five"]


def test_group_words_breaks_on_gap():
    ws = words((0, 100, "a"), (100, 200, "b"), (2000, 2100, "c"))  # big gap before c
    groups = group_words_into_phrases(ws, max_words=6, max_gap_ms=700)
    assert [g[2] for g in groups] == ["a b", "c"]


def test_plan_caption_from_transcript_positions():
    edl = make_edl_with_clip()
    seg = TranscriptSegment(start_ms=0, end_ms=600, text="hello there friend",
                            words=words((0, 200, "hello"), (200, 400, "there"),
                                        (400, 600, "friend.")))
    u = understanding_with(segments=[seg])
    plan = plan_caption_from_transcript(edl, u, "ast_v1", "trk_c1",
                                        max_words=6, max_gap_ms=700, cap_style=None)
    assert len(plan) == 1
    assert plan[0]["op"] == "add_caption" and plan[0]["track"] == "trk_c1"
    assert plan[0]["text"] == "hello there friend."
    assert (plan[0]["start_ms"], plan[0]["end_ms"]) == (0, 600)


def test_caption_from_transcript_op_end_to_end(engine: Engine):
    seg = TranscriptSegment(start_ms=100, end_ms=900, text="a b c d",
                            words=words((100, 300, "a"), (300, 500, "b"),
                                        (2000, 2200, "c"), (2200, 2400, "d.")))
    u = understanding_with(segments=[seg])
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [
        {"op": "caption_from_transcript", "asset": "ast_v1", "track": "trk_c1", "max_words": 6},
    ])
    caps = clips_on(r["edl"], "trk_c1")
    # Two phrases (gap between b and c): "a b" and "c d."
    assert len(caps) == 2
    assert caps[0]["text"] == "a b" and caps[1]["text"] == "c d."
    # No overlaps on the caption track (validator would have rejected otherwise).


def test_caption_from_transcript_wrong_track_kind(engine: Engine):
    u = understanding_with(segments=[TranscriptSegment(
        start_ms=0, end_ms=200, text="x", words=words((0, 200, "x.")))])
    pid = _project_with_analyzed_asset(engine, u)
    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"], [
            {"op": "caption_from_transcript", "asset": "ast_v1", "track": "trk_v1"},
        ])
    assert exc.value.issues[0].code == "E_KIND"


def test_auto_lyrics_creates_dedicated_short_phrase_track(engine: Engine):
    seg = TranscriptSegment(
        start_ms=0, end_ms=1800, text="we move through the night again",
        words=words((0, 250, "we"), (250, 500, "move"), (500, 750, "through"),
                    (750, 1000, "the"), (1000, 1350, "night"),
                    (1350, 1800, "again")),
    )
    pid = _project_with_analyzed_asset(engine, understanding_with(segments=[seg]))
    result = engine.apply(pid, engine.get_project(pid)["head_rev"], [{
        "op": "auto_lyrics", "asset": "ast_v1", "max_words": 3,
    }])
    lyrics = next(track for track in result["edl"]["tracks"] if track["name"] == "Auto lyrics")
    assert lyrics["kind"] == "caption" and lyrics["role"] == "captions"
    assert [clip["text"] for clip in lyrics["clips"]] == [
        "we move through", "the night again",
    ]
    assert all(clip["cap_style"] == "karaoke" for clip in lyrics["clips"])


def test_auto_lyrics_requires_timed_asset_on_timeline(engine: Engine):
    seg = TranscriptSegment(start_ms=0, end_ms=200, text="sing",
                            words=words((0, 200, "sing")))
    pid = _project_with_analyzed_asset(engine, understanding_with(segments=[seg]), clip=False)
    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"], [
            {"op": "auto_lyrics", "asset": "ast_v1"},
        ])
    assert exc.value.issues[0].path == "asset"


# -- reframe ------------------------------------------------------------------


def test_reframe_op(engine: Engine):
    u = understanding_with(silence=[])
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [
        {"op": "reframe", "width": 1080, "height": 1920},
    ])
    assert r["edl"]["project"]["canvas"] == {
        "width": 1080, "height": 1920, "fps": 30.0,
        "background_color": "#000000",
    }
    clip = clips_on(r["edl"], "trk_v1")[0]
    assert clip["crop"]["mode"] == "center"
    assert "reframe to 1080x1920" in r["summary"]


def test_reframe_rejects_illegal_canvas(engine: Engine):
    u = understanding_with(silence=[])
    pid = _project_with_analyzed_asset(engine, u)
    with pytest.raises(Rejected):
        engine.apply(pid, engine.get_project(pid)["head_rev"],
                     [{"op": "reframe", "width": 1081, "height": 1920}])  # odd width


def test_snap_to_beat_uses_analyzed_reference_clip(engine: Engine):
    u = understanding_with(silence=[])
    u.beats_ms = [1000, 2000, 3000, 4000, 5000]
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    engine.apply(pid, head, [
        {"op": "add_track", "kind": "audio", "id": "trk_music"},
        {"op": "add_clip", "track": "trk_music", "asset": "ast_v1", "in_ms": 0,
         "out_ms": 10000, "start_ms": 0, "id": "clp_music"},
        {"op": "move", "clip": "clp_a1", "to_start_ms": 4300},
    ])
    result = engine.apply(pid, engine.get_project(pid)["head_rev"], [
        {"op": "snap_to_beat", "clip": "clp_a1", "beat_clip": "clp_music"},
    ])
    assert clips_on(result["edl"], "trk_v1")[0]["start_ms"] == 4000


def test_snap_to_beat_requires_analyzed_beats(engine: Engine):
    u = understanding_with(silence=[])
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    engine.apply(pid, head, [
        {"op": "add_track", "kind": "audio", "id": "trk_music"},
        {"op": "add_clip", "track": "trk_music", "asset": "ast_v1", "in_ms": 0,
         "out_ms": 10000, "start_ms": 0, "id": "clp_music"},
    ])
    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"], [
            {"op": "snap_to_beat", "clip": "clp_a1", "beat_clip": "clp_music"},
        ])
    assert exc.value.issues[0].code == "E_NO_BEATS"


@pytest.mark.slow
def test_reframe_renders_at_target_aspect(tmp_path: Path):
    """reframe -> render: the Phase-0 compiler center-crops to the new canvas,
    so the output is genuinely 9:16."""
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.worker import Worker
    from cutlab.render.runner import render_handler
    from cutlab.util.ffprobe import probe
    from tests.media_fixtures import make_video

    db = Database(tmp_path / "r.db")
    projects_dir = tmp_path / "projects"
    eng = Engine(db, projects_dir=projects_dir)
    pid = eng.create_project("RF", {"width": 640, "height": 360, "fps": 30})["id"]
    pdir = projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    make_video(pdir / "media" / "v.mp4", seconds=2, tone_hz=440, size="640x360")
    eng.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_rf", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 2000, "width": 640, "height": 360},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_rf",
         "in_ms": 0, "out_ms": 2000, "start_ms": 0, "id": "clp_rf"},
    ])
    r = eng.apply(pid, eng.get_project(pid)["head_rev"],
                  [{"op": "reframe", "width": 1080, "height": 1920}])

    queue = JobQueue(db)
    job_id = queue.enqueue("render", {
        "project_id": pid, "rev": r["rev"], "project_dir": str(pdir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("render", render_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    out = Path(job["artifacts"]["mux"]["file"])
    pr = probe(out)
    assert (pr.width, pr.height) == (1080, 1920)
    db.close()


# -- add_emphasis ---------------------------------------------------------


def test_add_emphasis_explicit_point(engine: Engine):
    pid = _project_with_analyzed_asset(engine, understanding_with(silence=[]))
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [
        {"op": "add_emphasis", "clip": "clp_a1", "at_ms": 3000, "duration_ms": 2000, "scale": 1.5},
    ])
    clips = clips_on(r["edl"], "trk_v1")
    # Split into 3 pieces; middle one scaled, timeline unchanged.
    assert len(clips) == 3
    assert [c["start_ms"] for c in clips] == [0, 3000, 5000]
    assert clips[1]["transform"]["scale"] == 1.5
    assert clips[0].get("transform") is None
    assert r["edl"]["project"]["duration_ms"] == 10000


def test_add_emphasis_at_clip_start_splits_once(engine: Engine):
    pid = _project_with_analyzed_asset(engine, understanding_with(silence=[]))
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [
        {"op": "add_emphasis", "clip": "clp_a1", "at_ms": 0, "duration_ms": 1000},
    ])
    clips = clips_on(r["edl"], "trk_v1")
    assert len(clips) == 2
    assert clips[0]["transform"]["scale"] == 1.15  # default scale on the head piece


def test_add_emphasis_uses_saliency_peak(engine: Engine):
    from cutlab.understanding.schema import Saliency, SaliencyWindow

    u = understanding_with(silence=[])
    u.saliency = Saliency(profile="default", window_ms=2000, windows=[
        SaliencyWindow(start_ms=0, end_ms=2000, score=0.2),
        SaliencyWindow(start_ms=6000, end_ms=8000, score=0.9),  # the peak
    ])
    pid = _project_with_analyzed_asset(engine, u)
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [{"op": "add_emphasis", "clip": "clp_a1"}])
    clips = clips_on(r["edl"], "trk_v1")
    scaled = [c for c in clips if (c.get("transform") or {}).get("scale")]
    assert len(scaled) == 1
    assert scaled[0]["start_ms"] == 6000  # emphasis lands on the peak window


def test_add_emphasis_no_saliency_errors(engine: Engine):
    pid = _project_with_analyzed_asset(engine, understanding_with(silence=[]))
    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"],
                     [{"op": "add_emphasis", "clip": "clp_a1"}])  # no at_ms, no saliency
    assert exc.value.issues[0].code == "E_RANGE"


def test_still_later_phase_ops_rejected(engine: Engine):
    u = understanding_with(silence=[])
    pid = _project_with_analyzed_asset(engine, u)
    for op in ("reorder", "find", "apply_style"):
        with pytest.raises(Rejected) as exc:
            engine.apply(pid, engine.get_project(pid)["head_rev"], [{"op": op}])
        assert exc.value.issues[0].code == "E_NOT_IMPLEMENTED"
