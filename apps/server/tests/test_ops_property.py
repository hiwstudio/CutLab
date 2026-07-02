"""B3.3 property test (acceptance test 2): any random plan sequence — whether
each plan is accepted or rejected — never leaves the head EDL invalid, and
undo/redo never breaks validity either."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from cutlab.db import Database
from cutlab.edl.engine import Engine, Rejected
from cutlab.edl.validate import validate

CANVAS = {"width": 640, "height": 360, "fps": 30}
ASSET_MS = 10_000


def media_clips(edl: dict) -> list[tuple[str, dict]]:
    out = []
    for t in edl["tracks"]:
        if t["kind"] in ("video", "audio"):
            for c in t["clips"]:
                out.append((t["id"], c))
    return out


def track_end(edl: dict, track_id: str) -> int:
    ends = [0]
    for t in edl["tracks"]:
        if t["id"] == track_id:
            for c in t["clips"]:
                if "out_ms" in c:
                    length = round((c["out_ms"] - c["in_ms"]) / c.get("speed", 1.0))
                    ends.append(c["start_ms"] + length)
                else:
                    ends.append(c["end_ms"])
    return max(ends)


def draw_op(data, edl: dict) -> dict:
    clips = media_clips(edl)
    choices = ["add_clip", "add_caption"]
    if clips:
        choices += ["remove_clip", "trim", "split", "move", "set_speed",
                    "set_gain", "delete_range"]
    kind = data.draw(st.sampled_from(choices))

    if kind == "add_clip":
        track = data.draw(st.sampled_from(["trk_v1", "trk_a1"]))
        in_ms = data.draw(st.integers(0, ASSET_MS - 200))
        out_ms = data.draw(st.integers(in_ms + 100, ASSET_MS))
        return {"op": "add_clip", "track": track, "asset": "ast_v1",
                "in_ms": in_ms, "out_ms": out_ms,
                "start_ms": track_end(edl, track),
                "speed": data.draw(st.sampled_from([0.5, 1.0, 1.0, 2.0]))}
    if kind == "add_caption":
        s = data.draw(st.integers(0, 5000))
        return {"op": "add_caption", "track": "trk_c1", "text": "prop",
                "start_ms": s, "end_ms": s + data.draw(st.integers(1, 2000))}

    track_id, clip = data.draw(st.sampled_from(clips))
    if kind == "remove_clip":
        return {"op": "remove_clip", "clip": clip["id"],
                "ripple": data.draw(st.booleans())}
    if kind == "trim":
        return {"op": "trim", "clip": clip["id"],
                "new_in_ms": data.draw(st.integers(0, ASSET_MS - 1)),
                "new_out_ms": data.draw(st.integers(1, ASSET_MS)),
                "edge_mode": data.draw(st.sampled_from(["hold_start", "hold_end"]))}
    if kind == "split":
        return {"op": "split", "clip": clip["id"],
                "at_ms": clip["start_ms"] + data.draw(st.integers(0, 4000))}
    if kind == "move":
        return {"op": "move", "clip": clip["id"],
                "to_start_ms": data.draw(st.integers(0, 20_000))}
    if kind == "set_speed":
        return {"op": "set_speed", "clip": clip["id"],
                "speed": data.draw(st.sampled_from([0.5, 1.0, 2.0, 4.0])),
                "ripple": data.draw(st.booleans())}
    if kind == "set_gain":
        return {"op": "set_gain", "clip": clip["id"],
                "gain_db": data.draw(st.integers(-60, 12))}
    f = data.draw(st.integers(0, 8000))
    return {"op": "delete_range", "tracks": [track_id], "from_ms": f,
            "to_ms": f + data.draw(st.integers(1, 4000)),
            "ripple": data.draw(st.booleans())}


@settings(max_examples=30, deadline=None)
@given(data=st.data())
def test_random_plans_never_invalidate_head(data):
    db = Database(":memory:")
    engine = Engine(db)
    pid = engine.create_project("Prop", CANVAS)["id"]
    setup_rev = engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_v1", "kind": "video", "src": "media/v.mp4",
         "duration_ms": ASSET_MS, "width": 320, "height": 180},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_track", "kind": "audio", "id": "trk_a1"},
        {"op": "add_track", "kind": "caption", "id": "trk_c1"},
    ])["rev"]
    applied = 0
    for _ in range(12):
        edl = engine.get_edl(pid)
        # Plans of 1-2 ops, drawn against the current state.
        plan = [draw_op(data, edl)]
        if data.draw(st.booleans()):
            plan.append(draw_op(data, edl))
        head = engine.get_project(pid)["head_rev"]
        try:
            engine.apply(pid, head, plan)
            applied += 1
        except Rejected:
            pass
        r = validate(engine.get_edl(pid))
        assert r.valid, [i.to_dict() for i in r.errors]
        # Occasionally undo/redo; head must stay valid.
        action = data.draw(st.sampled_from(["none", "none", "undo", "undo_redo"]))
        # Never undo past the fixture revision (assets/tracks would vanish).
        if action in ("undo", "undo_redo") and engine.get_project(pid)["head_rev"] > setup_rev:
            try:
                engine.undo(pid)
                if action == "undo_redo":
                    engine.redo(pid)
            except Rejected:
                pass
            assert validate(engine.get_edl(pid)).valid
    assert applied >= 1
    db.close()
