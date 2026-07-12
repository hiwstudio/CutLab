"""Caption rendering (P3.4): EDL caption clips -> ASS subtitles burned by
ffmpeg/libass in each render chunk.

Adapted from the owner's viral-clip-engine `engine/subtitles.py` (production-
proven ASS generation). Caption *styles* are named presets here; the P6
capability registry exposes them as `caption_style` capabilities, and a future
Remotion handler can join as an alternative backend without touching this path.

Pure module: builds ASS text; file writing happens in the runner.
"""
from __future__ import annotations

from dataclasses import dataclass

# PlayRes is the canvas; libass scales automatically. Font sizes are expressed
# relative to canvas height so styles look right at 1080p and 1920p alike.
_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


@dataclass(frozen=True)
class CaptionStyle:
    id: str
    name: str                 # human label (registry manifest)
    font: str = "Arial"
    size_frac: float = 0.055  # font size as a fraction of canvas height
    primary: str = "&H00FFFFFF"   # ASS BGR
    outline_colour: str = "&H00000000"
    back_colour: str = "&H80000000"
    bold: int = -1
    border_style: int = 1     # 1 outline+shadow, 3 boxed
    outline: float = 3.0
    shadow: float = 1.0
    align: int = 2            # 2 bottom-center, 8 top-center, 5 middle
    margin_v_frac: float = 0.06


_BUILTIN_STYLES: dict[str, CaptionStyle] = {
    s.id: s
    for s in (
        CaptionStyle(id="default", name="Clean"),
        CaptionStyle(id="bold-pop", name="Bold Pop", font="Arial Black",
                     size_frac=0.075, primary="&H0000FFFF",  # yellow
                     outline=4.0, shadow=2.0, margin_v_frac=0.10),
        CaptionStyle(id="boxed", name="Boxed", border_style=3, outline=1.2,
                     shadow=0.0, size_frac=0.05),
        CaptionStyle(id="top-title", name="Top Title", align=8,
                     size_frac=0.065, margin_v_frac=0.08, bold=-1),
    )
}
DEFAULT_STYLE = "default"

_STYLE_FIELDS = {"font", "size_frac", "primary", "outline_colour", "back_colour",
                 "bold", "border_style", "outline", "shadow", "align", "margin_v_frac"}


def caption_styles() -> dict[str, CaptionStyle]:
    """Built-ins + registry `caption_style` manifests (a manifest may override a
    built-in by id or add a brand-new style — no code change, per A2.6)."""
    from .. import capabilities

    styles = dict(_BUILTIN_STYLES)
    for cap in capabilities.list_caps("caption_style"):
        overrides = {k: v for k, v in cap.data.items() if k in _STYLE_FIELDS}
        base = styles.get(cap.id)
        if base is not None and not overrides:
            continue  # plain builtin registration
        merged = {**(base.__dict__ if base else _BUILTIN_STYLES[DEFAULT_STYLE].__dict__),
                  **overrides, "id": cap.id, "name": cap.name}
        styles[cap.id] = CaptionStyle(**merged)
    return styles


# Back-compat alias used by tests and build_ass.
CAPTION_STYLES = _BUILTIN_STYLES


def _ass_ts(ms: int) -> str:
    ms = max(0, ms)
    cs = (ms % 1000) // 10
    s = (ms // 1000) % 60
    m = (ms // 60_000) % 60
    h = ms // 3_600_000
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return (text.replace("\\", "").replace("{", "(").replace("}", ")")
            .replace("\n", r"\N"))


def _style_line(s: CaptionStyle, h: int) -> str:
    size = max(10, round(s.size_frac * h))
    margin_v = round(s.margin_v_frac * h)
    return (f"Style: {s.id},{s.font},{size},{s.primary},&H00FFFFFF,"
            f"{s.outline_colour},{s.back_colour},{s.bold},0,0,0,100,100,0,0,"
            f"{s.border_style},{s.outline},{s.shadow},{s.align},60,60,{margin_v},1")


def build_ass(
    captions: list[tuple[int, int, str, str | None]],  # (start, end, text, style)
    width: int,
    height: int,
    window: tuple[int, int] | None = None,
) -> str | None:
    """ASS document for captions overlapping `window` [t0,t1), times re-based
    to the window start (chunk-local). None when nothing is visible."""
    t0, t1 = window or (0, 1 << 62)
    all_styles = caption_styles()
    events = []
    for start, end, text, style_id in captions:
        vis0, vis1 = max(start, t0), min(end, t1)
        if vis0 >= vis1 or not text.strip():
            continue
        style = all_styles.get(style_id or "", all_styles[DEFAULT_STYLE])
        events.append(
            f"Dialogue: 0,{_ass_ts(vis0 - t0)},{_ass_ts(vis1 - t0)},"
            f"{style.id},,0,0,0,,{_esc(text)}"
        )
    if not events:
        return None
    styles = "\n".join(_style_line(s, height) for s in all_styles.values())
    return _ASS_HEADER.format(w=width, h=height, styles=styles) + "\n".join(events) + "\n"
