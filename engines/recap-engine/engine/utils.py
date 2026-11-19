"""Shared helpers: ffmpeg wrappers, logging, time formatting."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(f"[recap-engine] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"[recap-engine] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        die(
            "ffmpeg not found. Install it and make sure it is on your PATH.\n"
            "  Windows:  winget install Gyan.FFmpeg   (then restart the terminal)\n"
            "  Mac:      brew install ffmpeg\n"
            "  Linux:    sudo apt install ffmpeg"
        )


def run_ffmpeg(args: list, desc: str = "", cwd: Path | None = None) -> None:
    """Run an ffmpeg command, raising on failure with stderr shown."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({desc}):\n{result.stderr[-2000:]}")


def probe_duration(video: Path) -> float:
    """Video duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-500:]}")
    return float(json.loads(result.stdout)["format"]["duration"])


def fmt_ts(seconds: float) -> str:
    """Seconds -> HH:MM:SS for human-readable output."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def safe_slug(text: str, max_len: int = 40) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return "-".join(keep.lower().split())[:max_len].strip("-") or "clip"


# --- Tolerant LLM JSON parsing -------------------------------------------------
# LLMs love to wrap JSON in prose, markdown fences, or leave trailing commas.
# parse_json_loose() recovers the intended object/array from all of those.

def _strip_trailing_commas(s: str) -> str:
    """Remove commas that directly precede a closing } or ] (a common LLM slip)."""
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _first_json_block(s: str) -> str | None:
    """Return the first balanced {...} or [...] substring, honouring strings and
    escapes so braces inside quoted text don't throw off the depth count.
    Returns None if there is no balanced block."""
    start = -1
    opener = closer = ""
    for i, ch in enumerate(s):
        if ch in "{[":
            start, opener, closer = i, ch, ("}" if ch == "{" else "]")
            break
    if start == -1:
        return None

    depth = 0
    in_str = esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None  # unbalanced (truncated output)


def parse_json_loose(text: str):
    """Best-effort parse of JSON the model may have wrapped in prose, code
    fences, or left with trailing commas. Returns the parsed object/list, or
    raises ValueError if nothing parseable is found."""
    if not text or not text.strip():
        raise ValueError("empty LLM response - nothing to parse")
    s = text.strip()

    # 1) drop a surrounding markdown code fence, if present
    if s.startswith("```"):
        s = re.sub(r"^```[A-Za-z0-9_-]*\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s).strip()

    # 2) fast path: the whole thing is (almost) clean JSON
    for candidate in (s, _strip_trailing_commas(s)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3) extract the first balanced block and retry, with trailing-comma cleanup
    block = _first_json_block(s)
    if block is not None:
        for candidate in (block, _strip_trailing_commas(block)):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise ValueError(
        f"could not parse JSON from LLM response (first 200 chars): {s[:200]!r}"
    )
