"""Build ASS subtitle files: word-group captions + a top caption/hook overlay.

Subtitle timing:
  - "word"  (default): each word appears exactly when it is spoken (live feel),
                       and clears during pauses so it never sits there waiting.
  - "phrase": small groups of words shown together (older behaviour).

The top overlay can be transient (clip mode) or persistent (reframe modes); when
a `hook_box` is given it is auto-sized and centered inside the top blurred band.
Pass subtitles_on=False to render only the caption (no word subtitles).
"""
from pathlib import Path

import config
from engine.utils import ass_ts

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,2,2,60,60,420,1
Style: Hook,{font},{hooksize},&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,2,8,80,80,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# how long a single live word may linger after it ends before the screen clears
MAX_WORD_HOLD = 0.6


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


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


def _fit_caption(text: str, box_w: float, box_h: float):
    for fs in range(68, 37, -4):  # cap at 68 → caption stays ≤15% of screen height
        max_chars = max(6, int((box_w * 0.92) / (0.52 * fs)))
        lines = _wrap_to_lines(text, max_chars)
        block_h = len(lines) * 1.28 * fs
        longest = max(len(ln) for ln in lines)
        if block_h <= box_h * 0.9 and longest <= max_chars:
            return "\\N".join(lines), fs
    fs = 38
    max_chars = max(6, int((box_w * 0.92) / (0.52 * fs)))
    return "\\N".join(_wrap_to_lines(text, max_chars)), fs


def _clip_words(segments: list, clip_start: float, clip_end: float) -> list:
    """All words within the clip window, times re-based to clip-local 0."""
    words = []
    for seg in segments:
        for w in seg["words"]:
            if w["start"] >= clip_start - 0.05 and w["end"] <= clip_end + 0.05:
                words.append({
                    "start": max(0.0, w["start"] - clip_start),
                    "end": max(0.0, w["end"] - clip_start),
                    "word": w["word"].strip(),
                })
    return words


def build_ass(segments: list, clip_start: float, clip_end: float,
              hook: str, out_path: Path, hook_persist: bool = False,
              hook_box: float = None, subtitles_on: bool = True) -> Path:
    """Write an ASS file. subtitles_on=False -> only the caption is drawn."""
    lines = [ASS_HEADER.format(
        w=config.OUT_WIDTH, h=config.OUT_HEIGHT,
        font=config.SUB_FONT, fontsize=config.SUB_FONT_SIZE,
        hooksize=int(config.SUB_FONT_SIZE * 0.72),
    )]

    if hook:
        hook_end = max(0.5, clip_end - clip_start) if hook_persist else config.HOOK_SECONDS
        htext = _esc(hook) if hook_persist else _esc(hook.upper())

        # Split style gets a special caption: placed just under the divider line
        # and styled with a bold pop/motion treatment. Other styles keep the
        # normal top/bottom caption behavior.
        if hook_persist and getattr(config, "STYLE", "").strip().lower() == "split":
            split_ratio = max(0.1, min(0.9, getattr(config, "SPLIT_RATIO", 0.5)))
            divider_y = int(config.OUT_HEIGHT * split_ratio)
            y = divider_y + getattr(config, "SPLIT_CAPTION_OFFSET", 105)
            wrapped, fs = _fit_caption(htext, config.OUT_WIDTH, 260)
            cx = config.OUT_WIDTH // 2
            # ASS animation: fast fade-in + subtle scale pop, with heavy outline
            # and shadow so the caption reads clearly over the bottom image.
            override = (
                f"{{\\an5\\pos({cx},{y})\\fs{fs}\\b1"
                f"\\c&H00FFFF&\\3c&H000000&\\4c&H000000&"
                f"\\bord12\\shad4\\blur0.6\\fad(160,220)"
                f"\\fscx100\\fscy100\\t(0,280,\\fscx108\\fscy108)"
                f"\\t(280,560,\\fscx100\\fscy100)}}"
            )
            lines.append(
                f"Dialogue: 1,{ass_ts(0)},{ass_ts(hook_end)},Hook,,0,0,0,,{override}{wrapped}\n"
            )
        elif hook_box and hook_box > 40:
            caption_pos = getattr(config, "CAPTION_POSITION", "top")
            caption_pos = caption_pos if caption_pos in ("top", "bottom") else "top"
            wrapped, fs = _fit_caption(htext, config.OUT_WIDTH, hook_box)
            cx = config.OUT_WIDTH // 2
            cy = int(hook_box / 2) if caption_pos == "top" else int(config.OUT_HEIGHT - hook_box / 2)
            override = f"{{\\an5\\pos({cx},{cy})\\fs{fs}}}"
            lines.append(
                f"Dialogue: 1,{ass_ts(0)},{ass_ts(hook_end)},Hook,,0,0,0,,{override}{wrapped}\n"
            )
        else:
            style = getattr(config, "STYLE", "blur").strip().lower()
            if style == "face":
                # Top of frame so the hook stays clear of the tracked face.
                # Fit into a virtual top band (~15% of height).
                top_band = max(160, int(config.OUT_HEIGHT * 0.15))
                wrapped, fs = _fit_caption(htext, config.OUT_WIDTH, top_band)
                cx = config.OUT_WIDTH // 2
                cy = int(top_band / 2)
                override = f"{{\\an5\\pos({cx},{cy})\\fs{fs}}}"
                lines.append(
                    f"Dialogue: 1,{ass_ts(0)},{ass_ts(hook_end)},Hook,,0,0,0,,{override}{wrapped}\n"
                )
            else:
                caption_pos = getattr(config, "CAPTION_POSITION", "top")
                if caption_pos == "bottom":
                    htext = f"{{\\an2}}{htext}"
                lines.append(
                    f"Dialogue: 1,{ass_ts(0)},{ass_ts(hook_end)},Hook,,0,0,0,,{htext}\n"
                )

    if subtitles_on:
        words = _clip_words(segments, clip_start, clip_end)
        style = config.SUB_STYLE.strip().lower()
        if style == "phrase":
            _emit_phrases(lines, words)
        else:
            _emit_live_words(lines, words)

    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path


def _emit_live_words(lines: list, words: list) -> None:
    """One word at a time, each shown exactly when spoken; clears during pauses."""
    n = len(words)
    for i, w in enumerate(words):
        text = _esc(w["word"])
        if not text:
            continue
        start = w["start"]
        nxt = words[i + 1]["start"] if i + 1 < n else w["end"] + 0.3
        # hold the word until the next one starts, but not across a long pause
        if nxt - w["end"] > MAX_WORD_HOLD:
            end = w["end"] + 0.3
        else:
            end = nxt
        if end - start < 0.12:
            end = start + 0.12
        lines.append(
            f"Dialogue: 0,{ass_ts(start)},{ass_ts(end)},Sub,,0,0,0,,{text}\n"
        )


def _emit_phrases(lines: list, words: list) -> None:
    group: list = []
    for w in words:
        group.append(w)
        if len(group) >= config.SUB_MAX_WORDS or w["word"].rstrip().endswith((".", "?", "!", ",")):
            _emit_group(lines, group)
            group = []
    if group:
        _emit_group(lines, group)


def _emit_group(lines: list, group: list) -> None:
    start, end = group[0]["start"], group[-1]["end"]
    if end - start < 0.15:
        end = start + 0.15
    text = _esc(" ".join(w["word"].strip() for w in group).strip())
    if not text:
        return
    lines.append(
        f"Dialogue: 0,{ass_ts(start)},{ass_ts(end)},Sub,,0,0,0,,{text}\n"
    )
