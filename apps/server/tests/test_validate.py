"""B3.2 tests: every A4 rule, one fixture per error code (table-driven)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cutlab.edl.validate import validate


def base_edl() -> dict:
    """A small valid EDL: one video asset, one video track, two clips."""
    return {
        "edl_version": "1.0",
        "project": {
            "id": "proj_test1",
            "name": "Test",
            "canvas": {"width": 1920, "height": 1080, "fps": 30},
            "duration_ms": 0,
        },
        "assets": {
            "ast_v1": {
                "kind": "video", "src": "media/v1.mp4",
                "duration_ms": 10_000, "width": 1280, "height": 720,
            },
            "ast_a1": {"kind": "audio", "src": "media/a1.wav", "duration_ms": 8_000},
            "ast_i1": {"kind": "image", "src": "media/i1.png", "width": 640, "height": 480},
        },
        "tracks": [
            {
                "id": "trk_v1",
                "kind": "video",
                "clips": [
                    {"id": "clp_aa", "asset": "ast_v1", "in_ms": 0, "out_ms": 3000, "start_ms": 0},
                    {"id": "clp_bb", "asset": "ast_v1", "in_ms": 4000, "out_ms": 6000, "start_ms": 3000},
                ],
            },
            {
                "id": "trk_c1",
                "kind": "caption",
                "clips": [
                    {"id": "clp_t1", "start_ms": 100, "end_ms": 900, "text": "hello"},
                ],
            },
        ],
    }


def codes(result) -> set[str]:
    return {i.code for i in result.errors}


def warning_codes(result) -> set[str]:
    return {i.code for i in result.warnings}


def test_valid_edl_passes():
    r = validate(base_edl())
    assert r.valid, [i.to_dict() for i in r.errors]
    assert r.errors == []
    assert r.edl is not None


def test_empty_edl_valid():
    edl = base_edl()
    edl["assets"] = {}
    edl["tracks"] = []
    r = validate(edl)
    assert r.valid


def mutate(path_fn):
    edl = base_edl()
    path_fn(edl)
    return edl


SCHEMA_CASES = [
    # (name, mutator, expected code)
    ("bad_version", lambda e: e.update(edl_version="2.0"), "E_SCHEMA"),
    ("bad_project_id", lambda e: e["project"].update(id="project-1"), "E_SCHEMA"),
    ("name_too_long", lambda e: e["project"].update(name="x" * 121), "E_RANGE"),
    ("empty_name", lambda e: e["project"].update(name=""), "E_RANGE"),
    ("odd_canvas", lambda e: e["project"]["canvas"].update(width=1919), "E_SCHEMA"),
    ("canvas_too_small", lambda e: e["project"]["canvas"].update(height=8), "E_RANGE"),
    ("canvas_too_big", lambda e: e["project"]["canvas"].update(width=8000), "E_RANGE"),
    ("illegal_fps", lambda e: e["project"]["canvas"].update(fps=23.976), "E_SCHEMA"),
    ("bad_asset_key", lambda e: e["assets"].update({"asset1": e["assets"].pop("ast_v1")}), "E_SCHEMA"),
    ("bad_asset_kind", lambda e: e["assets"]["ast_v1"].update(kind="gif"), "E_SCHEMA"),
    ("video_no_duration", lambda e: e["assets"]["ast_v1"].pop("duration_ms"), "E_SCHEMA"),
    ("video_no_dims", lambda e: e["assets"]["ast_v1"].pop("width"), "E_SCHEMA"),
    ("bad_track_id", lambda e: e["tracks"][0].update(id="track_one!"), "E_SCHEMA"),
    ("bad_track_kind", lambda e: e["tracks"][0].update(kind="subtitle"), "E_SCHEMA"),
    ("bad_clip_id", lambda e: e["tracks"][0]["clips"][0].update(id="clip_x~"), "E_SCHEMA"),
    ("unknown_field", lambda e: e["tracks"][0]["clips"][0].update(zoom=2), "E_SCHEMA"),
    ("in_after_out", lambda e: e["tracks"][0]["clips"][0].update(in_ms=3000, out_ms=1000), "E_SCHEMA"),
    ("speed_too_low", lambda e: e["tracks"][0]["clips"][0].update(speed=0.05), "E_RANGE"),
    ("speed_too_high", lambda e: e["tracks"][0]["clips"][0].update(speed=20), "E_RANGE"),
    ("gain_out_of_range", lambda e: e["tracks"][0]["clips"][0].update(gain_db=13), "E_RANGE"),
    ("transform_scale", lambda e: e["tracks"][0]["clips"][0].update(transform={"scale": 99}), "E_RANGE"),
    ("crop_manual_no_rect", lambda e: e["tracks"][0]["clips"][0].update(crop={"mode": "manual"}), "E_SCHEMA"),
    ("crop_reframe_auto_rejected", lambda e: e["tracks"][0]["clips"][0].update(crop={"mode": "reframe_auto"}), "E_SCHEMA"),
    ("transition_duration", lambda e: e["tracks"][0]["clips"][0].update(transition_out={"cap": "xfade", "duration_ms": 3000}), "E_RANGE"),
    ("caption_text_empty", lambda e: e["tracks"][1]["clips"][0].update(text=""), "E_RANGE"),
    ("caption_text_long", lambda e: e["tracks"][1]["clips"][0].update(text="x" * 501), "E_RANGE"),
    ("caption_end_before_start", lambda e: e["tracks"][1]["clips"][0].update(start_ms=900, end_ms=100), "E_SCHEMA"),
    ("caption_clip_on_video_track", lambda e: e["tracks"][0]["clips"].__setitem__(
        0, {"id": "clp_zz", "start_ms": 0, "end_ms": 100, "text": "no"}), "E_SCHEMA"),
    ("float_times_rejected", lambda e: e["tracks"][0]["clips"][0].update(in_ms=0.5), "E_SCHEMA"),
]


@pytest.mark.parametrize("name,mutator,code", SCHEMA_CASES, ids=[c[0] for c in SCHEMA_CASES])
def test_error_cases(name, mutator, code):
    edl = mutate(mutator)
    r = validate(edl)
    assert not r.valid, name
    assert code in codes(r), f"{name}: expected {code}, got {[i.to_dict() for i in r.errors]}"


CROSS_CASES = [
    ("dangling_asset_ref", lambda e: e["tracks"][0]["clips"][0].update(asset="ast_nope"), "E_REF"),
    ("audio_asset_on_video_track", lambda e: e["tracks"][0]["clips"][0].update(asset="ast_a1"), "E_KIND"),
    ("out_beyond_asset", lambda e: e["tracks"][0]["clips"][1].update(out_ms=99_999), "E_RANGE"),
    ("overlap", lambda e: e["tracks"][0]["clips"][1].update(start_ms=1000), "E_OVERLAP"),
    ("unsorted", lambda e: (
        e["tracks"][0]["clips"][0].update(start_ms=5000),
        e["tracks"][0]["clips"][1].update(start_ms=0),
    ), "E_ORDER"),
    ("duplicate_track_id", lambda e: e["tracks"][1].update(id="trk_v1"), "E_DUP"),
    ("duplicate_clip_id", lambda e: e["tracks"][0]["clips"][1].update(id="clp_aa"), "E_DUP"),
    ("wrong_duration", lambda e: e["project"].update(duration_ms=123), "E_DURATION"),
]


@pytest.mark.parametrize("name,mutator,code", CROSS_CASES, ids=[c[0] for c in CROSS_CASES])
def test_cross_checks(name, mutator, code):
    edl = mutate(mutator)
    r = validate(edl)
    assert not r.valid, name
    assert code in codes(r), f"{name}: expected {code}, got {[i.to_dict() for i in r.errors]}"


def test_image_clip_rules():
    edl = base_edl()
    # Image on a video track is allowed; in_ms must be 0, out_ms = display duration.
    edl["tracks"][0]["clips"] = [
        {"id": "clp_img", "asset": "ast_i1", "in_ms": 0, "out_ms": 2500, "start_ms": 0},
    ]
    assert validate(edl).valid
    edl["tracks"][0]["clips"][0]["in_ms"] = 100
    edl["tracks"][0]["clips"][0]["out_ms"] = 2600
    r = validate(edl)
    assert not r.valid and "E_RANGE" in codes(r)


def test_video_asset_allowed_on_audio_track():
    edl = base_edl()
    edl["tracks"].append({
        "id": "trk_a1", "kind": "audio",
        "clips": [{"id": "clp_au", "asset": "ast_v1", "in_ms": 0, "out_ms": 5000, "start_ms": 0}],
    })
    assert validate(edl).valid


def test_unknown_caps_warn_not_error():
    edl = base_edl()
    edl["tracks"][0]["clips"][0]["effects"] = [{"cap": "vignette", "params": {"amount": 0.5}}]
    edl["tracks"][0]["clips"][0]["transition_out"] = {"cap": "crossfade", "duration_ms": 500}
    edl["tracks"][1]["clips"][0]["cap_style"] = "bold-pop"
    r = validate(edl)
    assert r.valid
    assert len([w for w in r.warnings if w.code == "W_UNKNOWN_CAP"]) == 3


def test_speed_affects_overlap():
    edl = base_edl()
    # clip_a: 0-3000 source at 0.5x speed -> 6000ms timeline, overlaps clip_b at 3000.
    edl["tracks"][0]["clips"][0]["speed"] = 0.5
    r = validate(edl)
    assert not r.valid and "E_OVERLAP" in codes(r)
    # At 2x speed -> 1500ms timeline, no overlap.
    edl["tracks"][0]["clips"][0]["speed"] = 2.0
    assert validate(edl).valid


def test_src_existence_checked_with_base_dir(tmp_path: Path):
    edl = base_edl()
    r = validate(edl, base_dir=tmp_path)
    assert not r.valid and "E_SRC" in codes(r)
    for rel in ("media/v1.mp4", "media/a1.wav", "media/i1.png"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"stub")
    assert validate(edl, base_dir=tmp_path).valid


def test_issue_shape():
    edl = mutate(lambda e: e["tracks"][0]["clips"][1].update(start_ms=1000))
    r = validate(edl)
    d = r.to_dict()
    assert d["valid"] is False
    issue = d["errors"][0]
    assert set(issue) == {"code", "path", "message"}
    assert issue["path"].startswith("tracks[0].clips[1]")
