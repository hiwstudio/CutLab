"""B3.3 tests: ops engine — golden per-op tests, transactional apply,
undo/redo round-trips, optimistic conflict, proposals."""
from __future__ import annotations

from pathlib import Path

import pytest

from cutlab.db import Database
from cutlab.edl.engine import Conflict, Engine, NotFound, Rejected

CANVAS = {"width": 1280, "height": 720, "fps": 30}


@pytest.fixture()
def engine(db: Database) -> Engine:
    return Engine(db, projects_dir=None)


@pytest.fixture()
def project(engine: Engine) -> str:
    p = engine.create_project("Golden", CANVAS)
    pid = p["id"]
    apply(engine, pid, [
        {"op": "add_asset", "asset_id": "ast_v1", "kind": "video", "src": "media/v1.mp4",
         "duration_ms": 10_000, "width": 640, "height": 360},
        {"op": "add_asset", "asset_id": "ast_a1", "kind": "audio", "src": "media/a1.wav",
         "duration_ms": 8_000},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_track", "kind": "audio", "id": "trk_a1"},
        {"op": "add_track", "kind": "caption", "id": "trk_c1"},
    ])
    return pid


def apply(engine: Engine, pid: str, ops: list[dict], mode: str = "commit") -> dict:
    head = engine.get_project(pid)["head_rev"]
    return engine.apply(pid, head, ops, mode)


def clip_of(edl: dict, clip_id: str) -> dict:
    for t in edl["tracks"]:
        for c in t["clips"]:
            if c["id"] == clip_id:
                return c
    raise KeyError(clip_id)


def track_of(edl: dict, track_id: str) -> dict:
    return next(t for t in edl["tracks"] if t["id"] == track_id)


# -- structural --------------------------------------------------------------


def test_create_project_rev0(engine: Engine):
    p = engine.create_project("P", CANVAS)
    assert p["head_rev"] == 0
    edl = engine.get_edl(p["id"])
    assert edl["edl_version"] == "1.0"
    assert edl["tracks"] == [] and edl["assets"] == {}


def test_add_track_index(engine: Engine, project: str):
    r = apply(engine, project, [{"op": "add_track", "kind": "video", "index": 0, "id": "trk_v0"}])
    assert [t["id"] for t in r["edl"]["tracks"]][0] == "trk_v0"


def test_remove_track(engine: Engine, project: str):
    r = apply(engine, project, [{"op": "remove_track", "track": "trk_a1"}])
    assert "trk_a1" not in [t["id"] for t in r["edl"]["tracks"]]
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "remove_track", "track": "trk_a1"}])
    assert exc.value.issues[0].code == "E_REF"


def test_add_clip_and_overlap_rejection(engine: Engine, project: str):
    r = apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 3000, "start_ms": 0, "id": "clp_x1"},
    ])
    assert clip_of(r["edl"], "clp_x1")["start_ms"] == 0
    assert r["edl"]["project"]["duration_ms"] == 3000
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
             "in_ms": 0, "out_ms": 1000, "start_ms": 2500},
        ])
    assert exc.value.issues[0].code == "E_OVERLAP"


def test_add_clip_kind_checks(engine: Engine, project: str):
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "add_clip", "track": "trk_v1", "asset": "ast_a1",
             "in_ms": 0, "out_ms": 1000, "start_ms": 0},
        ])
    assert exc.value.issues[0].code == "E_KIND"
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "add_clip", "track": "trk_c1", "asset": "ast_v1",
             "in_ms": 0, "out_ms": 1000, "start_ms": 0},
        ])
    assert exc.value.issues[0].code == "E_KIND"


def three_clips(engine: Engine, project: str) -> None:
    """clp_c1 [0,1000), clp_c2 [1000,3000), clp_c3 [4000,5000) on trk_v1."""
    apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 1000, "start_ms": 0, "id": "clp_c1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 2000, "out_ms": 4000, "start_ms": 1000, "id": "clp_c2"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 5000, "out_ms": 6000, "start_ms": 4000, "id": "clp_c3"},
    ])


def test_remove_clip_ripple(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [{"op": "remove_clip", "clip": "clp_c2", "ripple": True}])
    # c2 was 2000ms long: c3 shifts 4000 -> 2000.
    assert clip_of(r["edl"], "clp_c3")["start_ms"] == 2000
    assert r["edl"]["project"]["duration_ms"] == 3000


def test_remove_clip_no_ripple(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [{"op": "remove_clip", "clip": "clp_c2", "ripple": False}])
    assert clip_of(r["edl"], "clp_c3")["start_ms"] == 4000


def test_trim_hold_start(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [
        {"op": "trim", "clip": "clp_c2", "new_in_ms": 2500, "new_out_ms": 3500},
    ])
    c2 = clip_of(r["edl"], "clp_c2")
    assert (c2["in_ms"], c2["out_ms"], c2["start_ms"]) == (2500, 3500, 1000)


def test_trim_hold_end(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [
        {"op": "trim", "clip": "clp_c2", "new_in_ms": 3000, "edge_mode": "hold_end"},
    ])
    c2 = clip_of(r["edl"], "clp_c2")
    # Old end was 3000; new source len 1000 -> start moves to 2000.
    assert (c2["in_ms"], c2["out_ms"], c2["start_ms"]) == (3000, 4000, 2000)


def test_trim_overlap_rejected(engine: Engine, project: str):
    three_clips(engine, project)
    # Extending c2's tail into c3 (c2 would span 1000..4500, c3 at 4000).
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "trim", "clip": "clp_c2", "new_in_ms": 500, "new_out_ms": 4000},
        ])
    assert exc.value.issues[0].code == "E_OVERLAP"


def test_trim_range_errors(engine: Engine, project: str):
    three_clips(engine, project)
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "trim", "clip": "clp_c2", "new_in_ms": 4500}])
    assert exc.value.issues[0].code == "E_RANGE"
    # clp_c3 is last on its track: extending past the asset hits the validator.
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "trim", "clip": "clp_c3", "new_out_ms": 99_999}])
    assert exc.value.issues[0].code == "E_RANGE"  # beyond asset duration


def test_split_plain(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [
        {"op": "split", "clip": "clp_c2", "at_ms": 1600, "new_id": "clp_c2b"},
    ])
    left = clip_of(r["edl"], "clp_c2")
    right = clip_of(r["edl"], "clp_c2b")
    assert (left["in_ms"], left["out_ms"], left["start_ms"]) == (2000, 2600, 1000)
    assert (right["in_ms"], right["out_ms"], right["start_ms"]) == (2600, 4000, 1600)


def test_split_inside_speed_clip(engine: Engine, project: str):
    """The B3 edge case: split respecting a 2x speed clip's source mapping."""
    apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 3000, "start_ms": 1000, "speed": 2.0, "id": "clp_sp"},
    ])
    # Timeline span [1000, 2500). Split at 1750 -> source offset 1500.
    r = apply(engine, project, [
        {"op": "split", "clip": "clp_sp", "at_ms": 1750, "new_id": "clp_spb"},
    ])
    left = clip_of(r["edl"], "clp_sp")
    right = clip_of(r["edl"], "clp_spb")
    assert (left["in_ms"], left["out_ms"], left["start_ms"]) == (0, 1500, 1000)
    assert (right["in_ms"], right["out_ms"], right["start_ms"]) == (1500, 3000, 1750)
    assert right["speed"] == 2.0


def test_split_bounds(engine: Engine, project: str):
    three_clips(engine, project)
    for at in (1000, 3000, 9999):
        with pytest.raises(Rejected) as exc:
            apply(engine, project, [{"op": "split", "clip": "clp_c2", "at_ms": at}])
        assert exc.value.issues[0].code == "E_RANGE"


def test_split_caption(engine: Engine, project: str):
    apply(engine, project, [
        {"op": "add_caption", "track": "trk_c1", "text": "hello world",
         "start_ms": 0, "end_ms": 2000, "id": "clp_cap"},
    ])
    r = apply(engine, project, [
        {"op": "split", "clip": "clp_cap", "at_ms": 500, "new_id": "clp_capb"},
    ])
    assert clip_of(r["edl"], "clp_cap")["end_ms"] == 500
    assert clip_of(r["edl"], "clp_capb")["start_ms"] == 500
    assert clip_of(r["edl"], "clp_capb")["text"] == "hello world"


def test_move_same_track_and_overlap(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [{"op": "move", "clip": "clp_c3", "to_start_ms": 8000}])
    assert clip_of(r["edl"], "clp_c3")["start_ms"] == 8000
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "move", "clip": "clp_c3", "to_start_ms": 500}])
    assert exc.value.issues[0].code == "E_OVERLAP"


def test_move_cross_track(engine: Engine, project: str):
    three_clips(engine, project)
    apply(engine, project, [{"op": "add_track", "kind": "video", "id": "trk_v2"}])
    r = apply(engine, project, [
        {"op": "move", "clip": "clp_c2", "to_start_ms": 0, "to_track": "trk_v2"},
    ])
    assert clip_of(r["edl"], "clp_c2")["start_ms"] == 0
    assert any(c["id"] == "clp_c2" for c in track_of(r["edl"], "trk_v2")["clips"])
    # Video clip cannot move to a caption track.
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "move", "clip": "clp_c1", "to_start_ms": 0, "to_track": "trk_c1"},
        ])
    assert exc.value.issues[0].code == "E_KIND"


def test_delete_range_ripple(engine: Engine, project: str):
    three_clips(engine, project)
    # Range [500, 4500): cuts c1's tail, removes c2, trims c3's head.
    r = apply(engine, project, [
        {"op": "delete_range", "tracks": ["trk_v1"], "from_ms": 500, "to_ms": 4500},
    ])
    edl = r["edl"]
    c1 = clip_of(edl, "clp_c1")
    assert (c1["in_ms"], c1["out_ms"], c1["start_ms"]) == (0, 500, 0)
    with pytest.raises(KeyError):
        clip_of(edl, "clp_c2")
    c3 = clip_of(edl, "clp_c3")
    # c3 [4000,5000) loses its first 500ms and closes the gap to 500.
    assert (c3["in_ms"], c3["out_ms"], c3["start_ms"]) == (5500, 6000, 500)
    assert edl["project"]["duration_ms"] == 1000


def test_delete_range_spanning_clip_splits(engine: Engine, project: str):
    apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 6000, "start_ms": 0, "id": "clp_big"},
    ])
    r = apply(engine, project, [
        {"op": "delete_range", "tracks": ["trk_v1"], "from_ms": 2000, "to_ms": 3000},
    ])
    t = track_of(r["edl"], "trk_v1")
    assert len(t["clips"]) == 2
    left = clip_of(r["edl"], "clp_big")
    right = [c for c in t["clips"] if c["id"] != "clp_big"][0]
    assert (left["in_ms"], left["out_ms"], left["start_ms"]) == (0, 2000, 0)
    assert (right["in_ms"], right["out_ms"], right["start_ms"]) == (3000, 6000, 2000)


def test_delete_range_no_ripple_leaves_gap(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [
        {"op": "delete_range", "tracks": ["trk_v1"], "from_ms": 1000, "to_ms": 3000,
         "ripple": False},
    ])
    assert clip_of(r["edl"], "clp_c3")["start_ms"] == 4000


def test_delete_range_all_tracks(engine: Engine, project: str):
    three_clips(engine, project)
    apply(engine, project, [
        {"op": "add_caption", "track": "trk_c1", "text": "over the cut",
         "start_ms": 0, "end_ms": 5000, "id": "clp_cc"},
    ])
    r = apply(engine, project, [
        {"op": "delete_range", "tracks": "all", "from_ms": 1000, "to_ms": 3000},
    ])
    cap_track = track_of(r["edl"], "trk_c1")
    # Caption spanned the range: split into [0,1000) + [1000, 3000) after ripple.
    assert [(c["start_ms"], c["end_ms"]) for c in cap_track["clips"]] == [(0, 1000), (1000, 3000)]


def test_delete_range_degenerate_remnants_dropped(engine: Engine, project: str):
    """Regression (found by hypothesis): a 1ms delete_range across a 0.5x
    clip floors the left remnant to zero source length; it must be dropped,
    never committed as an invalid out_ms <= in_ms clip."""
    apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
         "in_ms": 0, "out_ms": 100, "start_ms": 0, "speed": 0.5, "id": "clp_dg"},
    ])
    r = apply(engine, project, [
        {"op": "delete_range", "tracks": ["trk_v1"], "from_ms": 1, "to_ms": 2,
         "ripple": False},
    ])
    t = track_of(r["edl"], "trk_v1")
    for c in t["clips"]:
        assert c["out_ms"] > c["in_ms"]


def test_set_speed(engine: Engine, project: str):
    three_clips(engine, project)
    # c2 source 2000ms at 2x -> 1000ms timeline; gap opens, still valid.
    r = apply(engine, project, [{"op": "set_speed", "clip": "clp_c2", "speed": 2.0}])
    assert clip_of(r["edl"], "clp_c2")["speed"] == 2.0
    # 0.5x -> 4000ms timeline, would overlap c3 at 4000... exactly touches: 1000+4000=5000 > 4000 -> overlap
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "set_speed", "clip": "clp_c2", "speed": 0.5}])
    assert exc.value.issues[0].code == "E_OVERLAP"
    # With ripple, later clips shift right instead.
    r = apply(engine, project, [{"op": "set_speed", "clip": "clp_c2", "speed": 0.5, "ripple": True}])
    c3 = clip_of(r["edl"], "clp_c3")
    assert c3["start_ms"] == 7000  # was 4000; c2 grew from 1000 (2x) to 4000 (0.5x)


def test_set_gain_transform_crop(engine: Engine, project: str):
    three_clips(engine, project)
    r = apply(engine, project, [
        {"op": "set_gain", "clip": "clp_c1", "gain_db": -6},
        {"op": "set_transform", "clip": "clp_c1", "transform": {"scale": 0.5, "x": 10}},
        {"op": "set_crop", "clip": "clp_c1",
         "crop": {"mode": "manual", "rect": {"x": 0, "y": 0, "w": 320, "h": 180}}},
    ])
    c1 = clip_of(r["edl"], "clp_c1")
    assert c1["gain_db"] == -6
    assert c1["transform"]["scale"] == 0.5 and c1["transform"]["x"] == 10
    # Merge semantics: second set_transform keeps scale, changes y.
    r = apply(engine, project, [
        {"op": "set_transform", "clip": "clp_c1", "transform": {"y": -20}},
    ])
    c1 = clip_of(r["edl"], "clp_c1")
    assert c1["transform"]["scale"] == 0.5 and c1["transform"]["y"] == -20
    assert c1["crop"]["mode"] == "manual"


def test_set_canvas_and_project(engine: Engine, project: str):
    r = apply(engine, project, [
        {"op": "set_canvas", "width": 1080, "height": 1920, "fps": 60},
        {"op": "set_project", "name": "Renamed", "profile": "tiktok"},
    ])
    assert r["edl"]["project"]["canvas"] == {"width": 1080, "height": 1920, "fps": 60.0}
    assert r["edl"]["project"]["name"] == "Renamed"
    assert engine.get_project(project)["name"] == "Renamed"
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_canvas", "width": 1081, "height": 1920, "fps": 60}])


def test_add_caption_only_on_caption_tracks(engine: Engine, project: str):
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "add_caption", "track": "trk_v1", "text": "no", "start_ms": 0, "end_ms": 100},
        ])
    assert exc.value.issues[0].code == "E_KIND"


def test_set_understanding(engine: Engine, project: str):
    r = apply(engine, project, [
        {"op": "set_understanding", "asset": "ast_v1",
         "understanding": "understanding/ast_v1.understanding.json"},
    ])
    assert r["edl"]["assets"]["ast_v1"]["understanding"] == \
        "understanding/ast_v1.understanding.json"
    # Idempotent re-set is rejected as a no-op (register loop treats this as done).
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "set_understanding", "asset": "ast_v1",
             "understanding": "understanding/ast_v1.understanding.json"},
        ])
    assert exc.value.issues[0].code == "E_NOOP"
    # Unknown asset -> E_REF.
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [
            {"op": "set_understanding", "asset": "ast_none",
             "understanding": "u.json"},
        ])
    assert exc.value.issues[0].code == "E_REF"


def test_later_phase_ops_not_implemented(engine: Engine, project: str):
    for op in ("remove_silence", "compact", "caption_from_transcript", "reorder"):
        with pytest.raises(Rejected) as exc:
            apply(engine, project, [{"op": op}])
        assert exc.value.issues[0].code == "E_NOT_IMPLEMENTED"


def test_unknown_op_rejected(engine: Engine, project: str):
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "explode"}])
    assert exc.value.issues[0].code == "E_SCHEMA"


# -- plan semantics ----------------------------------------------------------


def test_plan_is_transactional(engine: Engine, project: str):
    head_before = engine.get_project(project)["head_rev"]
    revs_before = len(engine.revisions(project))
    with pytest.raises(Rejected):
        apply(engine, project, [
            {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1",
             "in_ms": 0, "out_ms": 1000, "start_ms": 0, "id": "clp_ok"},
            {"op": "trim", "clip": "clp_nope", "new_in_ms": 1},  # E_REF -> whole plan dies
        ])
    assert engine.get_project(project)["head_rev"] == head_before
    assert len(engine.revisions(project)) == revs_before
    with pytest.raises(KeyError):
        clip_of(engine.get_edl(project), "clp_ok")


def test_optimistic_conflict(engine: Engine, project: str):
    head = engine.get_project(project)["head_rev"]
    engine.apply(project, head, [{"op": "add_track", "kind": "video"}])
    with pytest.raises(Conflict) as exc:
        engine.apply(project, head, [{"op": "add_track", "kind": "audio"}])
    assert exc.value.head_rev == head + 1


def test_propose_mode_does_not_move_head(engine: Engine, project: str):
    head = engine.get_project(project)["head_rev"]
    r = apply(engine, project, [{"op": "add_track", "kind": "video"}], mode="propose")
    assert engine.get_project(project)["head_rev"] == head
    revs = engine.revisions(project)
    assert revs[-1]["state"] == "proposed" and revs[-1]["rev"] == r["rev"]


def test_undo_redo_round_trip(engine: Engine, project: str):
    """Undo/redo restore exact snapshots (acceptance test 2)."""
    snapshots = {engine.get_project(project)["head_rev"]: engine.get_edl(project)}
    three_clips(engine, project)
    snapshots[engine.get_project(project)["head_rev"]] = engine.get_edl(project)
    apply(engine, project, [{"op": "set_gain", "clip": "clp_c1", "gain_db": -12}])
    snapshots[engine.get_project(project)["head_rev"]] = engine.get_edl(project)

    revs = sorted(snapshots)
    r2 = engine.undo(project)
    assert r2 == revs[1]
    assert engine.get_edl(project) == snapshots[revs[1]]
    r1 = engine.undo(project)
    assert r1 == revs[0]
    assert engine.get_edl(project) == snapshots[revs[0]]
    assert engine.redo(project) == revs[1]
    assert engine.get_edl(project) == snapshots[revs[1]]
    assert engine.redo(project) == revs[2]
    assert engine.get_edl(project) == snapshots[revs[2]]
    with pytest.raises(Rejected):
        engine.redo(project)


def test_undo_at_rev0_rejected(engine: Engine):
    p = engine.create_project("U", CANVAS)
    with pytest.raises(Rejected):
        engine.undo(p["id"])


def test_branching_after_undo(engine: Engine, project: str):
    base_head = engine.get_project(project)["head_rev"]
    apply(engine, project, [{"op": "add_track", "kind": "video", "id": "trk_bra"}])
    engine.undo(project)
    r = apply(engine, project, [{"op": "add_track", "kind": "audio", "id": "trk_brb"}])
    # Redo from base now follows the newest branch.
    engine.undo(project)
    assert engine.get_project(project)["head_rev"] == base_head
    assert engine.redo(project) == r["rev"]
    tracks = [t["id"] for t in engine.get_edl(project)["tracks"]]
    assert "trk_brb" in tracks and "trk_bra" not in tracks


def test_not_found(engine: Engine):
    with pytest.raises(NotFound):
        engine.get_project("proj_missing1")
    with pytest.raises(NotFound):
        engine.apply("proj_missing1", 0, [])


def test_revision_rows_complete(engine: Engine, project: str):
    three_clips(engine, project)
    rows = engine.revisions(project)
    last = rows[-1]
    assert last["parent_rev"] == rows[-2]["rev"]
    assert last["state"] == "committed"
    assert "add clip" in last["summary"]
    assert last["created_at"]
