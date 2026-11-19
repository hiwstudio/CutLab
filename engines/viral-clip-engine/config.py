"""Central configuration for the viral clip engine."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# --- Paths ---
ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"

# --- Transcription (local faster-whisper) ---
# Options: tiny, base, small, medium, large-v3
# "small" is a good speed/accuracy balance on CPU. Use "medium"+ if you have a GPU.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # auto / cpu / cuda
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "auto")  # auto / int8 / float16

# --- LLM via OpenRouter ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4.5")

# --- Intelligence layer: exactly ONE is ever active ---
# OPERATOR mode: Claude Code (or another agent harness) is driving the system
# and IS the intelligence layer, so the engine must NOT also call the LLM API -
# it routes reasoning to the operator by using the seeded moments.json/caption
# path. Auto-detected: Claude Code sets CLAUDECODE=1 for the commands it runs.
# Force with AGENT_OPERATOR=1, or force standalone with AGENT_OPERATOR=0.
_op = os.getenv("AGENT_OPERATOR")
OPERATOR_MODE = (_op not in ("0", "false", "")) if _op is not None \
    else bool(os.getenv("CLAUDECODE"))

# STANDALONE mode: the configured LLM API is the intelligence layer. Enabled
# only with a key, not "~"-disabled in .env, and NOT in operator mode (operator
# always wins - one active layer, never both, no redundant API calls).
LLM_ENABLED = (bool(OPENROUTER_API_KEY)
               and not LLM_MODEL.startswith("~")
               and not OPERATOR_MODE)


def intelligence_layer() -> str:
    """Human-readable name of the single active intelligence layer."""
    if OPERATOR_MODE:
        return "Claude Code / operator (LLM API off; seed moments.json)"
    if LLM_ENABLED:
        return f"LLM API ({LLM_MODEL})"
    return "none - LLM disabled via ~; seed moments.json yourself"

# --- YouTube downloads ---
# Max video resolution to download (the short side / height for landscape).
# 1080 keeps files small & sharp like the original workflow; lower = smaller.
DL_MAX_RES = int(os.getenv("DL_MAX_RES", "1080"))
# Browser to take cookies from when YouTube asks for sign-in.
# Options: chrome, edge, firefox, brave, opera (empty = try them in order)
YT_BROWSER = os.getenv("YT_BROWSER", "")

# --- Clip rules ---
MIN_CLIP_SECONDS = int(os.getenv("CLIP_MIN_SECONDS", "60"))
MAX_CLIP_SECONDS = int(os.getenv("CLIP_MAX_SECONDS", "120"))
# Extra seconds allowed past MAX when needed to finish a sentence/thought.
# Completeness of open/close beats exact duration targets.
CLIP_DURATION_GRACE = int(os.getenv("CLIP_DURATION_GRACE", "20"))
# Quality bar: a clip is only kept if the strict judge scores it >= this.
# Raise it (e.g. 80) for fewer, higher-quality clips; lower (e.g. 65) for more.
MIN_SCORE = int(os.getenv("CLIP_QUALITY_BAR", "72"))
# Hard safety cap on how many clips a single video can produce.
MAX_CLIPS = int(os.getenv("MAX_CLIPS", "12"))

# --- Video output ---
# Default output style: blur | center | split | face (see engine/styles.py).
# Picked per run via the menu or --style; CROP_MODE is the legacy env name.
STYLE = os.getenv("STYLE", os.getenv("CROP_MODE", "blur"))
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
VIDEO_CRF = 21            # quality (lower = better, bigger files)
VIDEO_PRESET = "fast"     # ffmpeg x264 preset

# --- Reframe caption band ---
# Minimum height (px, in 1080x1920 space) reserved at top & bottom in reframe
# modes so the persistent caption always sits in the blurred area, never on the
# video. Larger = video is a bit smaller but more caption room.
CAPTION_BAND_MIN = int(os.getenv("CAPTION_BAND_MIN", "300"))

# --- Blur layout ---
# Share of the frame height the video occupies in blur style (landscape
# sources). 0.5 = 25% blurred band / 50% video / 25% blurred band. Raising it
# makes the video bigger but crops more off its left/right edges.
BLUR_VIDEO_PCT = float(os.getenv("BLUR_VIDEO_PCT", "0.5"))

# --- Face style ---
# Which face to track when several are visible (two-person interviews, etc.):
#   largest  - biggest face in frame (default)
#   right    - person on the right as viewed on screen
#   left     - person on the left as viewed on screen
# When right/left is set, only faces on that half of the frame update the track
# (avoids jumping to the other speaker when both are detected).
FACE_PREFER = os.getenv("FACE_PREFER", "largest").strip().lower()

# --- Split style ---
# Ratio for split style: video portion height as fraction of total (0.5 = half)
# 0.6 = video takes 60%, still image takes 40%
SPLIT_RATIO = float(os.getenv("SPLIT_RATIO", "0.5"))
# In split style only, persistent caption sits just below the divider line.
# Increase to move lower into the bottom image; decrease to move closer to line.
SPLIT_CAPTION_OFFSET = int(os.getenv("SPLIT_CAPTION_OFFSET", "105"))

# --- Caption position ---
# Position of the persistent caption in non-split reframe modes: "top" or "bottom"
CAPTION_POSITION = os.getenv("CAPTION_POSITION", "top").strip().lower()

# --- Cut+Reframe highlight reel ---
# cut-reframe assembles the highest-scored moments (from the LLM/agent, same as
# clip mode) into one short vertical edit that lands in this duration band.
REEL_MIN_SECONDS = int(os.getenv("REEL_MIN_SECONDS", "90"))
REEL_MAX_SECONDS = int(os.getenv("REEL_MAX_SECONDS", "180"))

# --- Cut+Reframe silence removal ---
SILENCE_NOISE_DB = int(os.getenv("SILENCE_NOISE_DB", "-30"))  # quieter than this = silence
SILENCE_MIN_LEN = float(os.getenv("SILENCE_MIN_LEN", "0.6"))  # min silence length to cut (s)
SILENCE_PAD = float(os.getenv("SILENCE_PAD", "0.10"))         # keep a little around speech
SILENCE_MIN_KEEP = float(os.getenv("SILENCE_MIN_KEEP", "0.4"))  # drop kept bits shorter than this

# --- Audio-only inputs ---
# Background colour for the vertical "audio card" made when a reframe input has
# no video stream (e.g. a song/podcast). Hex like 0x0E1116.
AUDIO_CARD_BG = os.getenv("AUDIO_CARD_BG", "0x0E1116")

# --- Fonts ---
FONTS_DIR = ROOT / "fonts"          # drop .ttf/.otf here to add fonts
ACTIVE_FONT_FILE = None             # set at runtime when a custom font is picked

# --- Subtitles ---
SUB_FONT = "Arial"        # any installed font, e.g. "Montserrat ExtraBold"
SUB_FONT_SIZE = 80         # in 1080x1920 coordinate space
SUB_STYLE = os.getenv("SUB_STYLE", "word")  # "word" = live word-by-word, "phrase" = grouped
SUB_MAX_WORDS = 3          # words per group when SUB_STYLE = "phrase"
HOOK_SECONDS = 3.0         # how long the hook overlay stays on screen
