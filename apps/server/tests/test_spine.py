"""Spine edits use the same transactional revisions as every existing operation."""
from pathlib import Path

import pytest
from test_ops import engine, project, apply, clip_of, track_of
from cutlab.edl.engine import Rejected
from cutlab.edl.schema import EDL
from cutlab.render.planner import build_plan


def seed(engine, project):
    return apply(engine, project, [
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1", "in_ms": 0, "out_ms": 2000, "start_ms": 0, "id": "clp_aa"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_v1", "in_ms": 2000, "out_ms": 4000, "start_ms": 2000, "id": "clp_bb"},
        {"op": "add_scene", "id": "scn_aa", "title": "Opening", "start_ms": 0, "end_ms": 2000},
        {"op": "add_scene", "id": "scn_bb", "title": "Ending", "start_ms": 2000, "end_ms": 4000},
    ])


def test_review_invalidates_only_affected_scene_and_undo_restores(engine, project):
    seed(engine, project)
    apply(engine, project, [{"op": "set_scene", "scene": s, "approved": True} for s in ("scn_aa", "scn_bb")])
    result = apply(engine, project, [{"op": "set_gain", "clip": "clp_aa", "gain_db": -6}])
    assert [s["approved"] for s in result["edl"]["scenes"]] == [False, True]
    engine.undo(project)
    assert all(s["approved"] for s in engine.get_edl(project)["scenes"])


def test_scene_reorder_moves_crossing_voice_and_caption_but_keeps_music(engine, project):
    seed(engine, project)
    apply(engine, project, [
        {"op": "set_track", "track": "trk_a1", "role": "music"},
        {"op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0, "out_ms": 4000, "start_ms": 0, "id": "clp_mu"},
        {"op": "add_track", "id": "trk_vo", "kind": "audio"},
        {"op": "add_clip", "track": "trk_vo", "asset": "ast_a1", "in_ms": 1000, "out_ms": 3000, "start_ms": 1000, "id": "clp_vo"},
        {"op": "add_caption", "track": "trk_c1", "text": "Across boundary", "start_ms": 1000, "end_ms": 3000},
    ])
    result = apply(engine, project, [{"op": "move_scene", "scene": "scn_bb", "to_index": 0}])["edl"]
    assert [s["id"] for s in result["scenes"]] == ["scn_bb", "scn_aa"]
    assert clip_of(result, "clp_aa")["start_ms"] == 2000
    assert clip_of(result, "clp_bb")["start_ms"] == 0
    assert clip_of(result, "clp_mu")["out_ms"] == 4000
    voice = track_of(result, "trk_vo")["clips"]
    assert [(c["start_ms"], c["in_ms"], c["out_ms"]) for c in voice] == [(0, 2000, 3000), (3000, 1000, 2000)]
    assert [(c["start_ms"], c["end_ms"]) for c in track_of(result, "trk_c1")["clips"]] == [(0, 1000), (3000, 4000)]


def test_locked_track_rejects_whole_transaction(engine, project):
    seed(engine, project)
    apply(engine, project, [{"op": "set_track", "track": "trk_v1", "locked": True}])
    before = engine.get_edl(project)
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "set_scene", "scene": "scn_aa", "title": "Changed"}, {"op": "remove_clip", "clip": "clp_aa"}])
    assert exc.value.issues[0].code == "E_LOCKED"
    assert engine.get_edl(project) == before
    apply(engine, project, [{"op": "set_track", "track": "trk_v1", "locked": False}, {"op": "remove_clip", "clip": "clp_aa"}])


def test_atomic_timing_validates_source_and_overlap(engine, project):
    seed(engine, project)
    before = engine.get_edl(project)
    for end in (11000, 3000):
        with pytest.raises(Rejected):
            apply(engine, project, [{"op": "set_clip_timing", "clip": "clp_aa", "in_ms": 0, "out_ms": end, "start_ms": 0}])
        assert engine.get_edl(project) == before
    result = apply(engine, project, [{"op": "set_clip_timing", "clip": "clp_aa", "in_ms": 500, "out_ms": 1500, "start_ms": 500}])
    assert clip_of(result["edl"], "clp_aa")["start_ms"] == 500


def test_mixer_export_gain_solo_mute(engine, project):
    seed(engine, project)
    apply(engine, project, [
        {"op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0, "out_ms": 4000, "start_ms": 0},
        {"op": "set_track", "track": "trk_a1", "gain_db": -9, "solo": True},
    ])
    plan = build_plan(EDL.model_validate(engine.get_edl(project)), {"ast_a1": True, "ast_v1": True})
    assert len(plan.video_tracks[0]) == 2
    assert len(plan.audio) == 1 and plan.audio[0].gain_db == -9
    result = apply(engine, project, [{"op": "set_track", "track": "trk_a1", "muted": True}])
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_a1": True, "ast_v1": True})
    assert not plan.audio and plan.duration_ms == 4000


def test_auto_duck_splits_music_at_padded_voice_and_sets_exact_gain(engine, project):
    result = apply(engine, project, [
        {"op": "set_track", "track": "trk_a1", "role": "music", "name": "Score"},
        {"op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0,
         "out_ms": 8000, "start_ms": 0, "id": "clp_music", "gain_db": -2,
         "fade_in_ms": 500, "fade_out_ms": 600},
        {"op": "add_track", "id": "trk_voice", "kind": "audio", "role": "voiceover"},
        {"op": "add_clip", "track": "trk_voice", "asset": "ast_a1", "in_ms": 0,
         "out_ms": 2000, "start_ms": 2000, "id": "clp_voice"},
        {"op": "duck", "music_track": "trk_a1", "voice_track": "trk_voice",
         "gain_db": -14, "padding_ms": 100},
    ])
    pieces = track_of(result["edl"], "trk_a1")["clips"]
    assert [(c["start_ms"], c["out_ms"] - c["in_ms"], c["gain_db"])
            for c in pieces] == [(0, 1900, -2), (1900, 2200, -14), (4100, 3900, -2)]
    assert [(c["fade_in_ms"], c["fade_out_ms"]) for c in pieces] == [
        (500, 0), (0, 0), (0, 600),
    ]
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_a1": True, "ast_v1": True})
    assert [piece.gain_db for piece in plan.audio[:3]] == [-2, -14, -2]


def test_auto_duck_rejects_without_voice_overlap(engine, project):
    apply(engine, project, [
        {"op": "set_track", "track": "trk_a1", "role": "music"},
        {"op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0,
         "out_ms": 1000, "start_ms": 0, "id": "clp_music"},
        {"op": "add_track", "id": "trk_voice", "kind": "audio", "role": "voiceover"},
        {"op": "add_clip", "track": "trk_voice", "asset": "ast_a1", "in_ms": 0,
         "out_ms": 1000, "start_ms": 3000, "id": "clp_voice"},
    ])
    with pytest.raises(Rejected) as exc:
        apply(engine, project, [{"op": "duck", "music_track": "trk_a1",
                                 "voice_track": "trk_voice", "padding_ms": 0}])
    assert exc.value.issues[0].path == "music_track"


def test_replace_clip_and_opacity_are_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    apply(engine, project, [{
        "op": "add_asset", "asset_id": "ast_v2", "kind": "video",
        "src": "media/replacement.mp4", "duration_ms": 6000, "width": 1920, "height": 1080,
    }])
    result = apply(engine, project, [
        {"op": "set_opacity", "clip": "clp_aa", "opacity": 0.42},
        {"op": "replace_clip", "clip": "clp_aa", "asset": "ast_v2"},
    ])
    clip = clip_of(result["edl"], "clp_aa")
    assert clip["asset"] == "ast_v2"
    assert clip["opacity"] == pytest.approx(0.42)
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_v2": True, "ast_a1": True})
    assert plan.video_tracks[0][0].opacity == pytest.approx(0.42)
    from cutlab.render.ffgraph import compile_chunk
    args = compile_chunk(plan, 0, Path("."), Path("work"))
    assert any("colorchannelmixer=aa=0.42" in arg for arg in args)
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "replace_clip", "clip": "clp_aa", "asset": "ast_a1"}])


def test_video_adjustments_are_upserted_removed_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [{
        "op": "set_effect", "clip": "clp_aa", "cap": "color-adjust",
        "params": {"brightness": 0.12, "contrast": 1.2, "saturation": 0.8},
    }, {"op": "set_effect", "clip": "clp_aa", "cap": "sharpen", "params": {"amount": 0.5}}])
    result = apply(engine, project, [{
        "op": "set_effect", "clip": "clp_aa", "cap": "color-adjust",
        "params": {"brightness": -0.2, "contrast": 0.9, "saturation": 1.1},
    }])
    clip = clip_of(result["edl"], "clp_aa")
    assert [(effect["cap"], effect["params"]) for effect in clip["effects"]] == [
        ("color-adjust", {"brightness": -0.2, "contrast": 0.9, "saturation": 1.1}),
        ("sharpen", {"amount": 0.5}),
    ]
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    args = " ".join(__import__("cutlab.render.ffgraph", fromlist=["compile_chunk"]).compile_chunk(plan, 0, Path("."), Path("work")))
    assert "eq=brightness=-0.2:contrast=0.9:saturation=1.1" in args
    assert "unsharp=5:5:0.5:5:5:0" in args
    result = apply(engine, project, [{"op": "remove_effect", "clip": "clp_aa", "cap": "sharpen"}])
    assert [effect["cap"] for effect in clip_of(result["edl"], "clp_aa")["effects"]] == ["color-adjust"]
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_effect", "clip": "clp_aa", "cap": "color-adjust", "params": {"brightness": "bad"}}])


def test_mirror_and_exit_transition_are_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [
        {"op": "set_effect", "clip": "clp_aa", "cap": "mirror", "params": {}},
        {"op": "set_transition_out", "clip": "clp_aa", "transition_out": {"cap": "fade-white", "duration_ms": 400}},
    ])
    clip = clip_of(result["edl"], "clp_aa")
    assert clip["effects"] == [{"cap": "mirror", "params": {}}]
    assert clip["transition_out"] == {"cap": "fade-white", "duration_ms": 400}
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "hflip" in graph and "fade=t=out:st=1.600:d=0.400:c=white" in graph
    result = apply(engine, project, [{"op": "set_transition_out", "clip": "clp_aa", "transition_out": None}])
    assert "transition_out" not in clip_of(result["edl"], "clp_aa")
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_transition_out", "clip": "clp_aa", "transition_out": {"cap": "unknown", "duration_ms": 500}}])


def test_reverse_and_freeze_frame_are_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [
        {"op": "set_reverse", "clip": "clp_aa", "reversed": True},
        {"op": "set_freeze_frame", "clip": "clp_aa", "at_ms": 800},
    ])
    clip = clip_of(result["edl"], "clp_aa")
    assert clip["reversed"] is True and clip["freeze_frame_at_ms"] == 800
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    assert plan.video_tracks[0][0].reversed and plan.video_tracks[0][0].freeze_frame_at_ms == 800
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "-ss 0.800 -t 0.033" in graph and "reverse" in graph and "tpad=stop_mode=clone" in graph
    result = apply(engine, project, [{"op": "set_freeze_frame", "clip": "clp_aa", "at_ms": None}])
    assert "freeze_frame_at_ms" not in clip_of(result["edl"], "clp_aa")
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_freeze_frame", "clip": "clp_aa", "at_ms": 3000}])


def test_overlay_track_is_named_and_preserves_image_layering(engine, project):
    result = apply(engine, project, [
        {"op": "add_track", "kind": "video", "id": "trk_ov", "role": "overlay", "name": "Overlays & stickers"},
        {"op": "add_asset", "asset_id": "ast_img", "kind": "image", "src": "media/sticker.png", "width": 200, "height": 200},
        {"op": "add_clip", "track": "trk_ov", "asset": "ast_img", "in_ms": 0, "out_ms": 2000, "start_ms": 0, "id": "clp_sticker"},
    ])
    overlay = track_of(result["edl"], "trk_ov")
    assert (overlay["role"], overlay["name"], overlay["clips"][0]["asset"]) == (
        "overlay", "Overlays & stickers", "ast_img")
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True, "ast_img": False})
    assert plan.video_tracks[-1][0].is_image
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "format=rgba" in graph
    assert "scale=1080:1080,setsar=1,format=yuv420p" not in graph


def test_visual_animation_is_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [{
        "op": "set_video_animation", "clip": "clp_aa", "fade_in_ms": 250, "fade_out_ms": 500,
    }])
    clip = clip_of(result["edl"], "clp_aa")
    assert (clip["video_fade_in_ms"], clip["video_fade_out_ms"]) == (250, 500)
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "fade=t=in:st=0:d=0.25" in graph and "fade=t=out:st=1.5:d=0.5" in graph
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_video_animation", "clip": "clp_aa", "fade_in_ms": 1500, "fade_out_ms": 1000}])


def test_project_background_is_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [{"op": "set_background", "color": "#1A2B3C"}])
    assert result["edl"]["project"]["canvas"]["background_color"] == "#1A2B3C"
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    assert plan.background_color == "#1A2B3C"
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "color=c=0x1A2B3C" in graph
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_background", "color": "blue"}])


def test_project_canvas_supports_vertical_and_4k_presets(engine, project):
    seed(engine, project)
    vertical = apply(engine, project, [{
        "op": "set_canvas", "width": 1080, "height": 1920, "fps": 30,
    }])
    canvas = vertical["edl"]["project"]["canvas"]
    assert (canvas["width"], canvas["height"], canvas["fps"]) == (1080, 1920, 30)
    four_k = apply(engine, project, [{
        "op": "set_canvas", "width": 3840, "height": 2160, "fps": 60,
    }])
    plan = build_plan(EDL.model_validate(four_k["edl"]), {"ast_v1": True, "ast_a1": True})
    assert (plan.width, plan.height, plan.fps) == (3840, 2160, 60)


def test_circle_mask_is_revisioned_and_render_planned(engine, project):
    seed(engine, project)
    result = apply(engine, project, [{"op": "set_effect", "clip": "clp_aa", "cap": "circle-mask", "params": {}}])
    assert clip_of(result["edl"], "clp_aa")["effects"] == [{"cap": "circle-mask", "params": {}}]
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    from cutlab.render.ffgraph import compile_chunk
    graph = " ".join(compile_chunk(plan, 0, Path("."), Path("work")))
    assert "format=rgba,geq=" in graph and "min(W,H)" in graph


def test_caption_template_is_revisioned(engine, project):
    result = apply(engine, project, [{
        "op": "add_caption", "track": "trk_c1", "text": "A title", "start_ms": 0,
        "end_ms": 1000, "cap_style": "boxed", "id": "clp_cap",
    }])
    result = apply(engine, project, [{
        "op": "set_caption", "clip": "clp_cap", "text": "A better title",
        "start_ms": 100, "end_ms": 1100, "cap_style": "top-title",
    }])
    clip = clip_of(result["edl"], "clp_cap")
    assert (clip["text"], clip["start_ms"], clip["end_ms"], clip["cap_style"]) == (
        "A better title", 100, 1100, "top-title")


def test_audio_fades_are_revisioned_and_render_planned(engine, project):
    apply(engine, project, [{
        "op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0,
        "out_ms": 4000, "start_ms": 0, "id": "clp_fade",
    }])
    result = apply(engine, project, [{
        "op": "set_audio_fades", "clip": "clp_fade", "fade_in_ms": 500, "fade_out_ms": 750,
    }])
    clip = clip_of(result["edl"], "clp_fade")
    assert (clip["fade_in_ms"], clip["fade_out_ms"]) == (500, 750)
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    piece = next(piece for piece in plan.audio if piece.start_ms == 0)
    assert (piece.fade_in_ms, piece.fade_out_ms) == (500, 750)
    from cutlab.render.audio import piece_filter
    rendered = piece_filter(piece, 0, 0, "a0")
    assert "afade=t=in:st=0:d=0.5" in rendered
    assert "afade=t=out:st=3.25:d=0.75" in rendered
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "set_audio_fades", "clip": "clp_fade", "fade_in_ms": 3000, "fade_out_ms": 2000}])


def test_audio_cleanup_is_revisioned_and_render_planned(engine, project):
    apply(engine, project, [{
        "op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0,
        "out_ms": 4000, "start_ms": 0, "id": "clp_clean",
    }])
    result = apply(engine, project, [{
        "op": "set_audio_cleanup", "clip": "clp_clean", "denoise": True,
        "low_cut_hz": 90, "high_cut_hz": 12000,
    }])
    clip = clip_of(result["edl"], "clp_clean")
    assert (clip["audio_denoise"], clip["audio_low_cut_hz"],
            clip["audio_high_cut_hz"]) == (True, 90, 12000)
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    piece = next(piece for piece in plan.audio if piece.start_ms == 0)
    from cutlab.render.audio import piece_filter
    rendered = piece_filter(piece, 0, 0, "a0")
    assert "highpass=f=90" in rendered
    assert "lowpass=f=12000" in rendered
    assert "afftdn=nr=12:nf=-45" in rendered
    with pytest.raises(Rejected):
        apply(engine, project, [{
            "op": "set_audio_cleanup", "clip": "clp_clean", "denoise": False,
            "low_cut_hz": 500, "high_cut_hz": 400,
        }])


@pytest.mark.parametrize(("effect", "expected"), [
    ("voice-enhance", "equalizer=f=3000:t=q:w=1:g=3"),
    ("telephone", "highpass=f=300,lowpass=f=3400"),
    ("echo", "aecho=0.8:0.7:60:0.3"),
])
def test_audio_effect_presets_are_revisioned_and_rendered(engine, project, effect, expected):
    apply(engine, project, [{
        "op": "add_clip", "track": "trk_a1", "asset": "ast_a1", "in_ms": 0,
        "out_ms": 4000, "start_ms": 0, "id": "clp_fx",
    }])
    result = apply(engine, project, [{
        "op": "set_audio_effect", "clip": "clp_fx", "effect": effect,
    }])
    assert clip_of(result["edl"], "clp_fx")["audio_effect"] == effect
    plan = build_plan(EDL.model_validate(result["edl"]), {"ast_v1": True, "ast_a1": True})
    from cutlab.render.audio import piece_filter
    rendered = piece_filter(next(p for p in plan.audio if p.start_ms == 0), 0, 0, "a0")
    assert expected in rendered


def test_scene_overlap_rejected_and_legacy_edl_loads(engine, project):
    seed(engine, project)
    with pytest.raises(Rejected):
        apply(engine, project, [{"op": "add_scene", "title": "Overlap", "start_ms": 100, "end_ms": 500}])
    legacy = engine.get_edl(project)
    legacy.pop("scenes")
    for t in legacy["tracks"]:
        for key in ("name", "role", "gain_db", "muted", "solo", "locked"):
            t.pop(key)
    assert EDL.model_validate(legacy).scenes == []
