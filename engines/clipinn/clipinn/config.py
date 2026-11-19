"""Central configuration for Clipinn.

Module-level globals (env-overridable) — the proven VCE pattern. Runtime
choices (style, font, placements) are set on this module by the CLI.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# --- Paths ---
ROOT = Path(__file__).parent.parent
PROJECTS_DIR = ROOT / "projects"
FONTS_DIR = ROOT / "fonts"
DB_PATH = ROOT / "clipinn.db"

# --- Transcription (local faster-whisper, per-clip so it stays fast) ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "auto")

# --- Intelligence layer: exactly ONE is ever active ---
# Operator mode: Claude Code drives and IS the brain (no LLM API calls).
# Auto-detected via CLAUDECODE=1; force with AGENT_OPERATOR=1/0.
_op = os.getenv("AGENT_OPERATOR")
OPERATOR_MODE = (_op not in ("0", "false", "")) if _op is not None \
    else bool(os.getenv("CLAUDECODE"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-5")
# Candidates are scored independently, so they parallelize cleanly.
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "8"))
# Reasoning models bill thinking against max_tokens and return empty content when the
# budget runs out before the answer. 200 was enough for a plain model and starved
# deepseek-v4-flash on 3 of 12 verifications.
VERIFY_MAX_TOKENS = int(os.getenv("VERIFY_MAX_TOKENS", "900"))
LLM_ENABLED = (bool(OPENROUTER_API_KEY)
               and not LLM_MODEL.startswith("~")
               and not OPERATOR_MODE)


def intelligence_layer() -> str:
    if OPERATOR_MODE:
        return "Claude Code / operator (LLM API off; fulfil the select task)"
    if LLM_ENABLED:
        return f"LLM API ({LLM_MODEL})"
    return ("manual — pauses at select_task.json for you (or an agent) to "
            "score by hand; set OPENROUTER_API_KEY for automatic LLM scoring")


# --- YouTube ---
# 720 matches MixFix, and for the default blur style it costs nothing: the
# source is scaled to 1080 wide either way, so a 1280x720 source produces the
# same 1080x608 inset as a 1920x1080 one. But the 720p stream is ~3x smaller
# (294MB vs 864MB for a 35min video), so a section pulls ~3x fewer fragments —
# 3x faster and far less likely to drop one. Raise it for center/face styles,
# which crop into the source and do benefit from the extra pixels.
DL_MAX_RES = int(os.getenv("DL_MAX_RES", "720"))
# Single cookie source. firefox is the proven one on this machine — Chrome/Edge
# cookie DBs can't be read while running (DPAPI/app-bound encryption).
YT_BROWSER = os.getenv("YT_BROWSER", "firefox")
YT_MIN_INTERVAL_S = float(os.getenv("YT_MIN_INTERVAL_S", "2.0"))
SEGMENT_PAD_S = float(os.getenv("SEGMENT_PAD_S", "1.5"))  # extra media around each clip

# --- Clip rules ---
MIN_CLIP_SECONDS = int(os.getenv("CLIP_MIN_SECONDS", "30"))
MAX_CLIP_SECONDS = int(os.getenv("CLIP_MAX_SECONDS", "180"))
# Candidate windows are cut at these target lengths (clamped into the band
# above), so for the SAME starting moment the scorer sees a tight version and
# a long version and can pick whichever the content actually earns. Without
# this the engine would only ever propose one length per moment.
CANDIDATE_TARGETS_S = [30, 45, 60, 90, 120, 180]
# Hard cap on how many candidates get scored (one LLM call each).
CANDIDATE_LIMIT = int(os.getenv("CANDIDATE_LIMIT", "180"))
MIN_SCORE = float(os.getenv("CLIP_QUALITY_BAR", "6.5"))   # weighted rubric 0-10
MAX_CLIPS = int(os.getenv("MAX_CLIPS", "10"))
# Titles are generative and will invent events a cheap model never saw. Verified
# against the clip's own transcript before export; off only if you enjoy surprises.
VERIFY_TITLES = os.getenv("VERIFY_TITLES", "1") not in ("0", "false", "")
# Votes per title. The check is cheap and non-deterministic; any single "unsupported"
# verdict flags it, so more votes means better recall and a few more false flags.
VERIFY_VOTES = int(os.getenv("VERIFY_VOTES", "3"))


def validate() -> None:
    """Fail fast with a readable message instead of an obscure crash later."""
    problems = []
    if MIN_CLIP_SECONDS < 1:
        problems.append("CLIP_MIN_SECONDS must be >= 1")
    if MAX_CLIP_SECONDS <= MIN_CLIP_SECONDS:
        problems.append(
            f"CLIP_MAX_SECONDS ({MAX_CLIP_SECONDS}) must be greater than "
            f"CLIP_MIN_SECONDS ({MIN_CLIP_SECONDS})")
    if not 0 <= MIN_SCORE <= 10:
        problems.append(f"CLIP_QUALITY_BAR ({MIN_SCORE}) must be 0-10")
    if MAX_CLIPS < 1:
        problems.append("MAX_CLIPS must be >= 1")
    if CANDIDATE_LIMIT < 1:
        problems.append("CANDIDATE_LIMIT must be >= 1")
    if problems:
        raise ValueError("bad configuration:\n  - " + "\n  - ".join(problems))

# --- Adaptive visual analysis ---
# Candidates the scorer flags as needs_visual get a low-res sample + frames
# and a vision review pass; everything else stays transcript-only (no cost).
VISUAL_GRACE = 1.0          # flagged clips may sit this far below the bar
                            # until the visual review resolves them
VISUAL_SAMPLE_RES = 360     # sample download height (cheap, analysis-only)
VISUAL_FRAMES = 6           # frames extracted per flagged clip

# Rubric weights (clip-scoring skill; tune here, never fork the rubric)
RUBRIC_WEIGHTS = {
    "hook": 3.0, "self_containment": 3.0, "payoff": 2.0,
    "emotion": 1.5, "quotability": 1.0, "density": 1.0, "duration_fit": 1.0,
}

# --- Video output ---
STYLE = os.getenv("STYLE", "blur")   # blur | center | split | face
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
VIDEO_CRF = 21
VIDEO_PRESET = "fast"
CAPTION_BAND_MIN = int(os.getenv("CAPTION_BAND_MIN", "300"))
# Blur layout: share of frame height the video fills (landscape sources).
# 0.5 = 25% blurred / 50% video / 25% blurred. Higher = bigger video but more
# cropped off its left/right edges.
BLUR_VIDEO_PCT = float(os.getenv("BLUR_VIDEO_PCT", "0.5"))
SPLIT_RATIO = float(os.getenv("SPLIT_RATIO", "0.5"))
SPLIT_CAPTION_OFFSET = int(os.getenv("SPLIT_CAPTION_OFFSET", "105"))
AUDIO_CARD_BG = os.getenv("AUDIO_CARD_BG", "0x0E1116")

# --- Text overlays (set per run by the CLI) ---
# Caption = the hook text overlay. Subtitles = the spoken words.
# Position: "top" | "middle" | "bottom" | None (= off).
CAPTION_POSITION = None
SUBTITLE_POSITION = None
SUB_FONT = "Arial"
SUB_FONT_SIZE = 80
SUB_STYLE = os.getenv("SUB_STYLE", "word")  # word | phrase
SUB_MAX_WORDS = 3
ACTIVE_FONT_FILE = None
# Per-layer look (clipinn.textstyle spec) - colours, background box, fonts, case,
# karaoke timing. None = "classic", the original hard-coded look, byte for byte.
TEXT_STYLE = None
