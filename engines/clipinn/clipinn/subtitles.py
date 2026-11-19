"""ASS subtitle builder — live word subtitles + a caption (hook) overlay,
each independently placeable top / middle / bottom (config.CAPTION_POSITION /
config.SUBTITLE_POSITION; None = off). The CLI guarantees they never collide.

Ported from VCE's proven builder; input is now a clip-local Timing Map
(ms words) instead of whisper segments.
"""
from pathlib import Path

from . import config, textstyle
from .utils import ass_ts

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{sub_line}
{hook_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

MAX_WORD_HOLD = 0.6  # s a live word may linger after it ends


def _pos_y(position: str) -> int:
    """Vertical anchor for a placement zone in 1080x1920 space."""
    h = config.OUT_HEIGHT
    return {"top": int(h * 0.14), "middle": int(h * 0.50),
            "bottom": int(h * 0.83)}[position]


def _esc(text: str) -> str:
    return (text.replace("\\", "").replace("{", "(")
            .replace("}", ")").replace("\n", " "))


def _wrap_to_lines(text: str, max_chars: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [text]


def _fit_caption(text: str, box_w: float, box_h: float, max_fs: int = 68,
                 char_w: float = 0.52):
    # char_w is the average glyph width as a share of font size; capitals run wider.
    for fs in range(max_fs, 37, -4):
        max_chars = max(6, int((box_w * 0.92) / (char_w * fs)))
        lines = _wrap_to_lines(text, max_chars)
        if len(lines) * 1.28 * fs <= box_h * 0.9:
            return "\\N".join(lines), fs
    fs = 38
    max_chars = max(6, int((box_w * 0.92) / (char_w * fs)))
    return "\\N".join(_wrap_to_lines(text, max_chars)), fs


def build_ass(clip_tm: dict, caption: str, duration_s: float, out_path: Path,
              caption_box: float = None) -> Path:
    """Write the ASS file for one clip.

    clip_tm: clip-local Timing Map (words layer, ms from clip start).
    caption_box: px height of a safe band (blur style top band); when the
    caption sits "top" and a band exists, it is auto-fitted inside it.
    """
    # config.TEXT_STYLE None resolves to "classic" - the exact original look.
    st = textstyle.resolve(getattr(config, "TEXT_STYLE", None))
    cap, sub = st["caption"], st["subtitles"]
    sub_fs = textstyle.scaled(sub, config.SUB_FONT_SIZE)
    cap_max = textstyle.scaled(cap, textstyle.CAPTION_FIT_MAX)
    lines = [ASS_HEADER.format(
        w=config.OUT_WIDTH, h=config.OUT_HEIGHT,
        sub_line=textstyle.style_line(
            "Sub", sub, textstyle.family(sub["font"], config.SUB_FONT), sub_fs, 60,
            textstyle.box_pad(sub_fs)),
        # the Hook's style size is a placeholder: every caption carries its own \fs
        hook_line=textstyle.style_line(
            "Hook", cap, textstyle.family(cap["font"], config.SUB_FONT),
            int(config.SUB_FONT_SIZE * 0.72), 80, textstyle.box_pad(cap_max)))]

    cap_pos = config.CAPTION_POSITION
    if caption and cap_pos:
        cx = config.OUT_WIDTH // 2
        text = _case(_esc(caption), cap["upper"])
        char_w = 0.6 if cap["upper"] else 0.52
        if cap_pos == "top" and caption_box and caption_box > 40:
            wrapped, fs = _fit_caption(text, config.OUT_WIDTH, caption_box, cap_max, char_w)
            cy = int(caption_box / 2)
        else:
            wrapped, fs = _fit_caption(text, config.OUT_WIDTH, 300, cap_max, char_w)
            cy = _pos_y(cap_pos)
        override = f"{{\\an5\\pos({cx},{cy})\\fs{fs}\\fad(160,0)}}"
        lines.append(f"Dialogue: 1,{ass_ts(0)},{ass_ts(max(0.5, duration_s))},"
                     f"Hook,,0,0,0,,{override}{wrapped}\n")

    sub_pos = config.SUBTITLE_POSITION
    if sub_pos:
        words = [{"start": w["start_ms"] / 1000, "end": w["end_ms"] / 1000,
                  "word": w["text"]} for w in clip_tm.get("words", [])]
        override = f"{{\\an5\\pos({config.OUT_WIDTH // 2},{_pos_y(sub_pos)})}}"
        timing = (sub["timing"] or config.SUB_STYLE).strip().lower()
        if timing == "phrase":
            _emit_phrases(lines, words, override, sub["upper"])
        elif timing == "karaoke":
            _emit_karaoke(lines, words, override, sub["upper"],
                          textstyle.ass_inline_color(sub["highlight"]))
        else:
            _emit_live_words(lines, words, override, sub["upper"])

    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path


def _case(text: str, upper: bool) -> str:
    return text.upper() if upper else text


def _emit_live_words(lines: list, words: list, override: str, upper: bool = False) -> None:
    n = len(words)
    for i, w in enumerate(words):
        text = _case(_esc(w["word"]), upper)
        if not text:
            continue
        nxt = words[i + 1]["start"] if i + 1 < n else w["end"] + 0.3
        end = w["end"] + 0.3 if nxt - w["end"] > MAX_WORD_HOLD else nxt
        end = max(end, w["start"] + 0.12)
        lines.append(f"Dialogue: 0,{ass_ts(w['start'])},{ass_ts(end)},"
                     f"Sub,,0,0,0,,{override}{text}\n")


def _groups(words: list) -> list:
    """Phrases: close at SUB_MAX_WORDS words or on punctuation."""
    groups, group = [], []
    for w in words:
        group.append(w)
        if (len(group) >= config.SUB_MAX_WORDS
                or w["word"].rstrip().endswith((".", "?", "!", ","))):
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    return groups


def _emit_phrases(lines: list, words: list, override: str, upper: bool = False) -> None:
    for group in _groups(words):
        _emit_group(lines, group, override, upper)


def _emit_karaoke(lines: list, words: list, override: str, upper: bool,
                  highlight: str) -> None:
    """The whole phrase stays up; the word being spoken takes the highlight colour.

    One event per word, back to back, so the phrase never blinks between words.
    Words are escaped before the colour tag is added, so transcript text can never
    inject its own ASS overrides.
    """
    for group in _groups(words):
        start = group[0]["start"]
        end = max(group[-1]["end"], start + 0.15)
        tokens = [_case(_esc(w["word"].strip()), upper) for w in group]
        for k, w in enumerate(group):
            if not tokens[k]:
                continue
            a = start if k == 0 else w["start"]
            b = group[k + 1]["start"] if k + 1 < len(group) else end
            if b <= a:
                continue
            text = " ".join("{\\c" + highlight + "}" + t + "{\\r}" if i == k else t
                            for i, t in enumerate(tokens) if t)
            lines.append(f"Dialogue: 0,{ass_ts(a)},{ass_ts(b)},"
                         f"Sub,,0,0,0,,{override}{text}\n")


def _emit_group(lines: list, group: list, override: str, upper: bool = False) -> None:
    start, end = group[0]["start"], max(group[-1]["end"], group[0]["start"] + 0.15)
    text = _case(_esc(" ".join(w["word"].strip() for w in group).strip()), upper)
    if text:
        lines.append(f"Dialogue: 0,{ass_ts(start)},{ass_ts(end)},"
                     f"Sub,,0,0,0,,{override}{text}\n")
