"""Text styling: presets must never change what an unstyled clip looks like.

The golden files in tests/golden_ass/ were written by the builder as it existed
BEFORE text styling was added. Any drift in the default path is a visible change
to every clip already in production, so it is a test failure, not a judgement call.

    python tests/test_textstyle.py --write-golden   # only ever run on the old code
    python -m pytest tests/test_textstyle.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clipinn import config, fonts, textstyle  # noqa: E402
from clipinn.subtitles import build_ass  # noqa: E402

GOLDEN = Path(__file__).parent / "golden_ass"

WORDS = [("Now,", 0, 400), ("I", 450, 600), ("love", 620, 900), ("cheesecake,", 950, 1500),
         ("but", 1600, 1800), ("I've", 1820, 2100), ("never", 2150, 2500),
         ("had", 2550, 2800), ("Lebanese", 2850, 3400), ("{cheesecake}", 3450, 4100),
         ("before.", 4200, 4900)]
TM = {"words": [{"text": t, "start_ms": a, "end_ms": b} for t, a, b in WORDS]}
CAPTION = "He had never tasted Lebanese cheesecake"

# name -> (config overrides, caption, caption_box)
SCENARIOS = {
    "blur_top_word": ({"CAPTION_POSITION": "top", "SUBTITLE_POSITION": "bottom",
                       "SUB_STYLE": "word", "SUB_FONT": "Arial"}, CAPTION, 480),
    "blur_top_phrase": ({"CAPTION_POSITION": "top", "SUBTITLE_POSITION": "bottom",
                         "SUB_STYLE": "phrase", "SUB_FONT": "Arial"}, CAPTION, 480),
    "middle_impact": ({"CAPTION_POSITION": "middle", "SUBTITLE_POSITION": "bottom",
                       "SUB_STYLE": "phrase", "SUB_FONT": "Impact"}, CAPTION, None),
    "subs_only": ({"CAPTION_POSITION": None, "SUBTITLE_POSITION": "bottom",
                   "SUB_STYLE": "word", "SUB_FONT": "Arial"}, "", None),
    "caption_only": ({"CAPTION_POSITION": "top", "SUBTITLE_POSITION": None,
                      "SUB_STYLE": "word", "SUB_FONT": "Arial"}, CAPTION, None),
}


def render(name, **extra):
    overrides, caption, box = SCENARIOS[name]
    keys = list(overrides) + list(extra) + ["OUT_WIDTH", "OUT_HEIGHT", "SUB_FONT_SIZE",
                                             "TEXT_STYLE"]
    saved = {k: getattr(config, k, None) for k in keys}
    try:
        config.OUT_WIDTH, config.OUT_HEIGHT, config.SUB_FONT_SIZE = 1080, 1920, 80
        config.TEXT_STYLE = None
        for k, v in {**overrides, **extra}.items():
            setattr(config, k, v)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.ass"
            build_ass(TM, caption, 5.0, out, caption_box=box)
            return out.read_text(encoding="utf-8")
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


def _events(ass):
    return [line for line in ass.splitlines() if line.startswith("Dialogue: 0,")]


def test_default_output_is_unchanged():
    for name in SCENARIOS:
        expected = (GOLDEN / f"{name}.ass").read_text(encoding="utf-8")
        assert render(name) == expected, f"default render drifted: {name}"


def test_choosing_classic_matches_the_original_byte_for_byte():
    classic = textstyle.resolve({"preset": "classic"})
    for name in SCENARIOS:
        expected = (GOLDEN / f"{name}.ass").read_text(encoding="utf-8")
        assert render(name, TEXT_STYLE=classic) == expected, f"classic drifted: {name}"


def test_resolve_is_idempotent_and_none_is_classic():
    assert textstyle.resolve(None)["preset"] == "classic"
    r = textstyle.resolve({"preset": "karaoke", "subtitles": {"color": "#FF0000"}})
    assert textstyle.resolve(r) == r
    assert r["subtitles"]["color"] == "#FF0000" and r["subtitles"]["timing"] == "karaoke"


def test_ass_colours_are_reversed_and_alpha_is_transparency():
    assert textstyle.ass_color("#FFFF00") == "&H0000FFFF"
    assert textstyle.ass_color("#3DDC84") == "&H0084DC3D"
    assert textstyle.ass_color("#000000", 0.72) == "&H47000000"
    assert textstyle.ass_inline_color("#3DDC84") == "&H84DC3D&"


def test_karaoke_keeps_the_phrase_and_lights_one_word():
    ev = _events(render("subs_only", TEXT_STYLE=textstyle.resolve({"preset": "karaoke"})))
    assert ev, "karaoke produced no subtitle events"
    for line in ev:
        assert line.count("{\\c&H84DC3D&}") == 1, line
    group = [line for line in ev if "LEBANESE" in line]
    assert len(group) == 3, "one event per word of 'had Lebanese cheesecake'"
    assert all("HAD" in line and "(CHEESECAKE)" in line for line in group)
    times = [line.split(",")[1:3] for line in group]
    assert times[0][1] == times[1][0] and times[1][1] == times[2][0], \
        "events must run back to back or the phrase blinks"


def test_uppercase_and_escaping_survive_together():
    ass = render("blur_top_word", TEXT_STYLE=textstyle.resolve({"preset": "bold_yellow"}))
    assert "HE HAD NEVER" in ass.replace("\\N", " ")
    assert "(CHEESECAKE)" in ass, "transcript braces must still be neutralised"


def test_boxed_look_draws_a_box_instead_of_an_outline():
    ass = render("blur_top_phrase", TEXT_STYLE=textstyle.resolve({"preset": "boxed"}))
    f = next(line for line in ass.splitlines() if line.startswith("Style: Sub,")).split(",")
    assert f[15] == "3", "BorderStyle 3 draws the box"
    assert f[17] == "0", "a box carries no drop shadow"
    assert f[5] == "&H47000000", "libass paints the box with OutlineColour"


def test_a_second_layer_font_is_installed_into_the_render_dir():
    custom = [f["name"] for f in fonts.list_fonts() if f["file"]]
    assert custom, "needs at least one font file in fonts/"
    saved = (config.TEXT_STYLE, config.ACTIVE_FONT_FILE)
    try:
        config.ACTIVE_FONT_FILE = None
        config.TEXT_STYLE = textstyle.resolve(
            {"preset": "classic", "caption": {"font": custom[0]}})
        with tempfile.TemporaryDirectory() as td:
            fonts.install_into(Path(td))
            assert list(Path(td).iterdir()), "the caption's font file was not copied"
            assert fonts.fontsdir_suffix() == ":fontsdir=."
            fonts.remove_from(Path(td))
            assert not list(Path(td).iterdir())
    finally:
        config.TEXT_STYLE, config.ACTIVE_FONT_FILE = saved


if __name__ == "__main__" and "--write-golden" in sys.argv:
    GOLDEN.mkdir(exist_ok=True)
    for name in SCENARIOS:
        (GOLDEN / f"{name}.ass").write_text(render(name), encoding="utf-8")
    print(f"wrote {len(SCENARIOS)} golden files to {GOLDEN}")
