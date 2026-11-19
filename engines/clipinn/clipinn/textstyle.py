"""Per-layer text looks for the caption (the hook) and the subtitles.

A spec is {"preset": name, "caption": {...}, "subtitles": {...}}. Any layer field left
out comes from its preset. "classic" is the builder's original hard-coded look, and
tests/test_textstyle.py holds it to the byte against output captured before this
module existed - so a clip nobody styles renders exactly as it always has.
"""
import re

from . import fonts

SIZES = {"s": 0.8, "m": 1.0, "l": 1.25}
TIMINGS = ("word", "phrase", "karaoke")
CAPTION_FIT_MAX = 68    # the caption fitter's original starting size
LAYERS = ("caption", "subtitles")

# font None / size None = the engine default (config.SUB_FONT, config.SUB_FONT_SIZE,
# CAPTION_FIT_MAX). That is what keeps "classic" identical to the old output,
# including a job-wide font chosen the old way.
_BASE = {"font": None, "bold": True, "size": None, "scale": "m", "color": "#FFFFFF",
         "bg": None, "bg_opacity": 1.0, "outline": 8, "shadow": 2, "upper": False}
_SUB_BASE = {**_BASE, "timing": None, "highlight": "#3DDC84"}

# Fixed by the look itself, never sent by a form: a bold Impact smears, and size is
# expressed to people as Small / Medium / Large on top of the preset's own size.
NOT_EDITABLE = ("size", "bold")


def _preset(label, caption, subtitles):
    return {"label": label, "caption": {**_BASE, **caption},
            "subtitles": {**_SUB_BASE, **subtitles}}


PRESETS = {
    "classic": _preset("Classic", {"color": "#FFFF00"}, {}),
    "clean": _preset(
        "Clean White",
        {"font": "Verdana", "size": 60, "outline": 4, "shadow": 1},
        {"font": "Verdana", "size": 64, "outline": 4, "shadow": 1, "timing": "phrase"}),
    "boxed": _preset(
        "Boxed",
        {"font": "Arial", "color": "#111111", "size": 62, "bg": "#FFFFFF",
         "outline": 0, "shadow": 0},
        {"font": "Arial", "size": 64, "bg": "#000000", "bg_opacity": 0.72,
         "outline": 0, "shadow": 0, "timing": "phrase"}),
    "karaoke": _preset(
        "Karaoke",
        {"font": "Arial", "size": 64, "outline": 6, "upper": True},
        {"font": "Arial", "size": 70, "outline": 6, "upper": True, "timing": "karaoke"}),
    "bold_yellow": _preset(
        "Bold Yellow",
        {"font": "Impact", "bold": False, "size": 72, "upper": True},
        {"font": "Impact", "bold": False, "color": "#FFD400", "size": 110, "outline": 10,
         "upper": True, "timing": "word"}),
    "minimal": _preset(
        "Minimal",
        {"font": "Georgia", "bold": False, "size": 52, "outline": 0, "shadow": 3},
        {"font": "Georgia", "bold": False, "size": 52, "outline": 0, "shadow": 3,
         "timing": "phrase"}),
}


def resolve(spec):
    """Fill every field of both layers. Idempotent, and None means classic."""
    spec = spec or {}
    name = spec.get("preset") if spec.get("preset") in PRESETS else "classic"
    out = {"preset": name}
    for layer in LAYERS:
        base = PRESETS[name][layer]
        given = spec.get(layer) or {}
        out[layer] = {**base, **{k: v for k, v in given.items() if k in base}}
    return out


_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def clean(spec, font_names):
    """Validate a look arriving from outside (the web form).

    Returns the spec with canonical values, or raises ValueError naming the bad field.
    Unknown keys are refused rather than dropped: a silently ignored setting is a
    render that quietly looks wrong.
    """
    if not isinstance(spec, dict):
        raise ValueError("the text look must be an object")
    extra = set(spec) - {"preset", *LAYERS}
    if extra:
        raise ValueError(f"unknown text look field(s): {', '.join(sorted(extra))}")
    preset = spec.get("preset") or "classic"
    if preset not in PRESETS:
        raise ValueError(f"unknown look {preset!r}")
    by_lower = {f.lower(): f for f in font_names}
    out = {"preset": preset}
    for layer in LAYERS:
        given = spec.get(layer) or {}
        if not isinstance(given, dict):
            raise ValueError(f"{layer} settings must be an object")
        allowed = set(PRESETS[preset][layer]) - set(NOT_EDITABLE)
        bad = set(given) - allowed
        if bad:
            raise ValueError(f"unknown {layer} setting(s): {', '.join(sorted(bad))}")
        out[layer] = {k: _field(f"{layer} {k}", k, v, by_lower) for k, v in given.items()}
    return out


def _field(where, key, value, fonts_by_lower):
    def hex_color(v):
        if not isinstance(v, str) or not _HEX.fullmatch(v):
            raise ValueError(f"{where} must be a color like #FFD400")
        return v.upper()

    if key == "font":
        if value is None:
            return None
        if not isinstance(value, str) or value.lower() not in fonts_by_lower:
            raise ValueError(f"{where}: {value!r} is not an installed font")
        return fonts_by_lower[value.lower()]
    if key in ("color", "highlight"):
        return hex_color(value)
    if key == "bg":
        return None if value is None else hex_color(value)
    if key == "bg_opacity":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"{where} must be between 0 and 1")
        return round(float(value), 2)
    if key in ("outline", "shadow"):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 20:
            raise ValueError(f"{where} must be a whole number from 0 to 20")
        return value
    if key == "upper":
        if not isinstance(value, bool):
            raise ValueError(f"{where} must be true or false")
        return value
    if key == "scale":
        if value not in SIZES:
            raise ValueError(f"{where} must be one of {', '.join(SIZES)}")
        return value
    if key == "timing":
        if value not in TIMINGS:
            raise ValueError(f"{where} must be one of {', '.join(TIMINGS)}")
        return value
    raise ValueError(f"{where} is not a setting")


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def ass_color(hex_color, opacity=1.0):
    """#RRGGBB -> ASS &HAABBGGRR.

    ASS stores blue first and alpha as TRANSPARENCY, so yellow #FFFF00 is &H0000FFFF.
    The reversed order is the easy mistake: get it wrong and yellow renders cyan.
    """
    r, g, b = _rgb(hex_color)
    return f"&H{round((1 - opacity) * 255):02X}{b:02X}{g:02X}{r:02X}"


def ass_inline_color(hex_color):
    """#RRGGBB -> the \\c override form &HBBGGRR& (no alpha)."""
    r, g, b = _rgb(hex_color)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def family(name, default):
    """The family name ASS needs for a font, or the default when unset or unknown."""
    if not name:
        return default
    entry = fonts.find_font(name)
    return entry["family"] if entry else default


def scaled(layer, default):
    return round((layer["size"] or default) * SIZES.get(layer["scale"], 1.0))


def box_pad(fontsize):
    return max(6, round(fontsize * 0.16))


def style_line(name, layer, family_name, fontsize, margin, pad):
    """One ASS [V4+ Styles] line.

    With a background, BorderStyle 3 draws an opaque box - and libass paints that box
    with OutlineColour, reusing Outline as its padding. So a box and an outline cannot
    coexist on one layer: box on means outline off, by construction.
    """
    boxed = bool(layer["bg"])
    return ",".join(str(x) for x in (
        f"Style: {name}", family_name, fontsize, ass_color(layer["color"]), "&H00FFFFFF",
        ass_color(layer["bg"], layer["bg_opacity"]) if boxed else "&H00000000",
        "&H80000000", -1 if layer["bold"] else 0, 0, 0, 0, 100, 100, 0, 0,
        3 if boxed else 1, pad if boxed else layer["outline"],
        0 if boxed else layer["shadow"], 5, margin, margin, 0, 1))
