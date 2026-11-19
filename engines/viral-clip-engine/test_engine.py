"""Smallest-possible regression checks for the pure logic.
Run:  python test_engine.py
"""
from engine.analyze import (
    _boundary_context,
    _dedupe,
    _parse_json_array,
    _snap_end_to_utterance,
    _snap_start_to_utterance,
    _snap_to_words,
)
from engine.styles import _select_face
from engine.silence import active_ranges, reel_ranges, remap_segments
from engine.source import _is_url
from engine.utils import archive_output, ass_ts, fmt_ts, next_version_n, prepare_rerender, safe_slug


def test_parse_json_array():
    assert _parse_json_array('[{"a": 1}]') == [{"a": 1}]
    assert _parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert _parse_json_array('Here you go:\n[{"a": 1},]') == [{"a": 1}]  # trailing comma
    # salvage: malformed items are dropped, valid objects survive
    assert _parse_json_array('[{"a": 1}, {"b": 2}, {broken]') == [{"a": 1}, {"b": 2}]
    try:
        _parse_json_array("no json here")
        assert False, "should have raised"
    except ValueError:
        pass


def test_dedupe():
    a = {"start": 0, "end": 60, "score": 90}
    b = {"start": 10, "end": 55, "score": 80}   # mostly inside a -> dropped
    c = {"start": 100, "end": 160, "score": 70}  # separate -> kept
    kept = _dedupe([a, b, c])
    assert a in kept and c in kept and b not in kept


def _fake_segments():
    """Three 30s lines of speech with word timestamps (90s total)."""
    segs = []
    for i, text in enumerate(["Hook line one.", "Build of the story continues.",
                              "Payoff lands here."]):
        s, e = float(i * 30), float(i * 30 + 30)
        words = [
            {"start": s, "end": s + 1.0, "word": text.split()[0]},
            {"start": e - 1.0, "end": e, "word": text.split()[-1]},
        ]
        segs.append({"start": s, "end": e, "text": text, "words": words})
    return segs


def test_snap_start_mid_sentence_pulls_back():
    segs = _fake_segments()
    # Proposed start 10s into first line -> open at 0
    assert _snap_start_to_utterance(10.0, segs) == 0.0
    # Near end of first line -> open at next thought
    assert _snap_start_to_utterance(28.0, segs) == 30.0


def test_snap_end_mid_sentence_pushes_forward():
    segs = _fake_segments()
    # Mid second line -> finish that line at 60
    assert _snap_end_to_utterance(45.0, segs) == 60.0
    # Barely into third line -> previous clean end
    assert _snap_end_to_utterance(30.5, segs) == 30.0


def test_snap_to_words_never_hard_cuts_mid_utterance():
    """Old bug: end = start + MAX amputated sentences. New path lands on
    segment ends and may use duration grace for a complete thought."""
    import config
    segs = _fake_segments()
    old_max = config.MAX_CLIP_SECONDS
    old_min = config.MIN_CLIP_SECONDS
    old_grace = config.CLIP_DURATION_GRACE
    try:
        config.MIN_CLIP_SECONDS = 50
        config.MAX_CLIP_SECONDS = 70
        config.CLIP_DURATION_GRACE = 10
        # Mid-line open + mid-line close → full utterances, not 5..50
        m = _snap_to_words({"start": 5.0, "end": 50.0}, segs)
        assert m is not None
        assert m["start"] == 0.0          # full first utterance
        assert m["end"] == 60.0           # finished second utterance (not 50)

        config.MIN_CLIP_SECONDS = 20
        config.MAX_CLIP_SECONDS = 40
        config.CLIP_DURATION_GRACE = 10
        # 0..90 proposed -> trim by whole segments under soft_max 50
        m2 = _snap_to_words({"start": 0.0, "end": 90.0}, segs)
        assert m2 is not None
        # ends only on 30 or 60 (segment ends), never e.g. 40.0 mid-line
        assert m2["end"] in (30.0, 60.0)
        assert m2["end"] - m2["start"] <= 50.0 + 0.01
    finally:
        config.MIN_CLIP_SECONDS = old_min
        config.MAX_CLIP_SECONDS = old_max
        config.CLIP_DURATION_GRACE = old_grace


def test_select_face_prefer_right_ignores_left():
    # small_w=480; left face center ~100, right face center ~360
    left = (60, 40, 80, 80)
    right = (320, 50, 90, 90)
    assert _select_face([left, right], 480, "right") == right
    assert _select_face([left, right], 480, "left") == left
    assert _select_face([left], 480, "right") is None  # hold track
    assert _select_face([left, right], 480, "largest") == right  # bigger box


def test_boundary_context_surfaces_neighbors():
    segs = _fake_segments()
    ctx = _boundary_context(segs, 30.0, 60.0)
    assert "Build" in ctx["opening_line"]
    assert "Build" in ctx["closing_line"] or "story" in ctx["closing_line"]
    assert "Hook" in ctx["context_before"]
    assert "Payoff" in ctx["context_after"]


def test_active_ranges():
    # 10s video, silence 3-7 -> keep [0,3] and [7,10] (padded 0.1)
    r = active_ranges(10.0, [(3.0, 7.0)], pad=0.1, min_keep=0.4)
    assert r == [(0.0, 3.1), (6.9, 10.0)]
    # unterminated silence runs to the end
    r = active_ranges(10.0, [(3.0, None)], pad=0.0, min_keep=0.4)
    assert r == [(0.0, 3.0)]
    # all-silent input falls back to the whole video
    assert active_ranges(10.0, [(0.0, None)], pad=0.0, min_keep=0.4) == [(0.0, 10.0)]


def test_reel_ranges():
    m = [{"start": 0, "end": 120, "score": 70},    # best, alone clears 90 min
         {"start": 200, "end": 320, "score": 90},  # highest score
         {"start": 400, "end": 460, "score": 60}]
    # top score (200-320=120s) already clears the 90s minimum -> just that one
    assert reel_ranges(m, min_total=90, max_total=180) == [(200.0, 320.0)]
    # tighter band forces combining shorter picks, returned chronologically
    short = [{"start": 0, "end": 40, "score": 80},
             {"start": 100, "end": 140, "score": 90},
             {"start": 300, "end": 340, "score": 70}]
    assert reel_ranges(short, min_total=90, max_total=180) == [
        (0.0, 40.0), (100.0, 140.0), (300.0, 340.0)]
    assert reel_ranges([], min_total=90, max_total=180) == []
    # overlapping high scorers: the lower one is skipped for a distinct moment
    ov = [{"start": 250, "end": 330, "score": 92},
          {"start": 307, "end": 387, "score": 88},   # overlaps the 92 -> skip
          {"start": 120, "end": 200, "score": 85}]    # distinct -> used instead
    assert reel_ranges(ov, min_total=90, max_total=180) == [(120.0, 200.0), (250.0, 330.0)]


def test_remap_segments():
    segs = [{"words": [
        {"start": 1.0, "end": 1.5, "word": "hello"},
        {"start": 5.0, "end": 5.5, "word": "dropped"},   # inside removed region
        {"start": 8.0, "end": 8.5, "word": "world"},
    ]}]
    out = remap_segments(segs, [(0.0, 3.0), (7.0, 10.0)])
    words = out[0]["words"]
    assert [w["word"] for w in words] == ["hello", "world"]
    assert words[0]["start"] == 1.0
    assert words[1]["start"] == 4.0  # 8.0 shifted onto compacted timeline


def test_url_and_slug_and_ts():
    assert _is_url("https://youtu.be/abc")
    assert _is_url("www.tiktok.com/@x/video/1")
    assert not _is_url(r"C:\videos\my-video.mp4")
    # an existing local file wins even if its name contains a video host
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "clip.x.com.mp4"
        f.write_bytes(b"")
        assert _is_url(str(f) + "-missing")  # gone -> host substring wins
        assert not _is_url(str(f))
    assert safe_slug("Hello, World! (2024)") == "hello-world-2024"
    assert safe_slug("") == "clip"
    assert fmt_ts(3661) == "01:01:01"
    assert ass_ts(61.5) == "0:01:01.50"


def test_output_versioning():
    """Revisions archive prior deliverables; latest keeps the unversioned name."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        assert next_version_n(d, "Cut reframe") == 1
        cur = d / "Cut reframe.mp4"
        cur.write_bytes(b"v-current")
        (d / "Cut reframe.caption.txt").write_text("cap", encoding="utf-8")
        archived = archive_output(cur, label="Cut reframe")
        assert archived is not None
        assert archived.name == "Cut reframe v1.mp4"
        assert archived.read_bytes() == b"v-current"
        assert not cur.exists()
        assert (d / "Cut reframe v1.caption.txt").read_text(encoding="utf-8") == "cap"
        assert next_version_n(d, "Cut reframe") == 2

        # Legacy filename becomes the next sequential version under the same label
        legacy = d / "cut-reframed.mp4"
        legacy.write_bytes(b"legacy")
        prepare_rerender(d, "Cut reframe.mp4", "Cut reframe",
                         legacy=["cut-reframed.mp4"])
        assert (d / "Cut reframe v2.mp4").read_bytes() == b"legacy"
        assert not legacy.exists()
        assert not (d / "Cut reframe.mp4").exists()  # free for the new render


def test_intelligence_layer_exclusive():
    """Operator mode and the LLM API are never both active."""
    import importlib
    import os
    import config
    saved = os.environ.get("CLAUDECODE"), os.environ.get("AGENT_OPERATOR")
    try:
        os.environ["AGENT_OPERATOR"] = "1"          # force operator
        importlib.reload(config)
        assert config.OPERATOR_MODE and not config.LLM_ENABLED
        os.environ["AGENT_OPERATOR"] = "0"          # force standalone
        os.environ.pop("CLAUDECODE", None)
        importlib.reload(config)
        assert not config.OPERATOR_MODE
    finally:
        for k, v in zip(("CLAUDECODE", "AGENT_OPERATOR"), saved):
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        importlib.reload(config)


def test_blur_geometry():
    from pathlib import Path
    from engine import styles
    orig = styles.probe_size
    try:
        # landscape -> 25/50/25, cover-cropped to fill the band
        styles.probe_size = lambda p: (1920, 1080)
        assert styles._blur_geometry(Path("x"), True) == (1080, 960, 480, True)
        assert styles._blur_geometry(Path("x"), False) == (1080, 960, 480, True)
        # portrait -> fitted, never cropped to half height; caption band kept
        styles.probe_size = lambda p: (1080, 1920)
        w, box_h, top, cover = styles._blur_geometry(Path("x"), True)
        assert cover is False and top >= 300
        # unprobeable file falls back to the landscape band
        styles.probe_size = lambda p: (_ for _ in ()).throw(RuntimeError())
        assert styles._blur_geometry(Path("x"), True) == (1080, 960, 480, True)
    finally:
        styles.probe_size = orig


def test_styles():
    from engine.styles import STYLES, piecewise, smooth_track
    assert list(STYLES) == ["blur", "center", "split", "face"]
    assert piecewise([(0, 100.0)]) == "100.0"
    e = piecewise([(0, 0.0), (2, 100.0)])
    assert "gte(t,0)*lt(t,2)" in e and e.endswith("gte(t,2)*100.0")
    # small wiggle inside the dead zone -> camera never moves
    assert all(x == 500 for _, x in smooth_track([(0, 500), (1, 510), (2, 495)], 1000))
    # big jump -> camera eases toward the face, never overshoots
    xs = [x for _, x in smooth_track([(0, 500), (1, 900), (2, 900), (3, 900)], 1000)]
    assert xs[0] == 500 and xs[1] < xs[2] <= 900


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
