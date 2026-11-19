"""Runtime configuration: paths, ports, and ffmpeg/ffprobe resolution."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

def _load_env_file(env_path: Path) -> None:
    """Load a simple dotenv file into os.environ (existing values win). Supports
    KEY=value lines, # comments, and optional surrounding quotes.
    ponytail: stdlib parser, not python-dotenv — no export/multiline/varsub."""
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)  # real env takes precedence


_load_env_file(Path(__file__).resolve().parents[1] / ".env")
_load_env_file(Path.home() / ".env")

SERVER_HOST = os.environ.get("CUTLAB_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("CUTLAB_PORT", "8787"))

# Repo root = three levels up from this file (cutlab/ -> server/ -> apps/ -> root)
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CUTLAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "cutlab.db"
PROJECTS_DIR = DATA_DIR / "projects"
CUTOUT_MODEL = Path(os.environ.get(
    "CUTLAB_CUTOUT_MODEL",
    DATA_DIR / "models" / "u2netp.onnx",
)).resolve()
SOUND_LIBRARY_ROOT = Path(os.environ.get(
    "CUTLAB_SOUND_LIBRARY_ROOT", DATA_DIR / "sounds",
)).resolve()
MIXFIX_ROOT = Path(os.environ.get(
    "CUTLAB_MIXFIX_ROOT", REPO_ROOT / "engines" / "mixfix",
)).resolve()

PROXY_HEIGHT = 540
RENDER_CHUNK_MS = 60_000
JOB_MAX_ATTEMPTS = 3

# --- AI Director (P2) ---
# Backend: "manual" (default; no key, writes the prompt to a file for a human /
# Claude to answer, resumes) | "openrouter" | "anthropic". The automatic backends
# read their key from the env; CutLab never stores or logs it.
LLM_BACKEND = os.environ.get("CUTLAB_LLM_BACKEND", "manual")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("CUTLAB_LLM_MODEL", "anthropic/claude-sonnet-4.5")

# --- Text to Sound ----------------------------------------------------------
TTS_ENGINE = os.environ.get("CUTLAB_TTS_ENGINE", "fish")
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
FISH_MODEL = os.environ.get("CUTLAB_FISH_MODEL", "s2.1-pro-free")
FISH_SPEED = float(os.environ.get("CUTLAB_FISH_SPEED", "0.85"))
FISH_RETRIES = int(os.environ.get("CUTLAB_FISH_RETRIES", "4"))


def _resolve_ff(tool: str) -> str:
    """Resolve an ffmpeg-family binary.

    Env override (CUTLAB_FFMPEG / CUTLAB_FFPROBE) wins. Otherwise prefer the
    binary that lives next to ffprobe on PATH, since another package may place
    an incompatible ffmpeg earlier in PATH.
    """
    env = os.environ.get(f"CUTLAB_{tool.upper()}")
    if env:
        return env
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        sibling = Path(ffprobe).with_name(f"{tool}.exe" if os.name == "nt" else tool)
        if sibling.exists():
            return str(sibling)
    found = shutil.which(tool)
    if found:
        return found
    raise RuntimeError(
        f"{tool} not found on PATH. Install FFmpeg (e.g. `winget install Gyan.FFmpeg` "
        f"on Windows or `apt install ffmpeg` on Linux) and restart, or set "
        f"CUTLAB_{tool.upper()} to the binary path."
    )


FFMPEG = _resolve_ff("ffmpeg")
FFPROBE = _resolve_ff("ffprobe")


def verify_ffmpeg() -> None:
    """Fail loud at startup if ffmpeg/ffprobe are missing or broken."""
    for name, exe in (("ffmpeg", FFMPEG), ("ffprobe", FFPROBE)):
        try:
            out = subprocess.run(
                [exe, "-version"], capture_output=True, text=True, timeout=15
            )
        except OSError as e:
            raise RuntimeError(f"{name} at {exe} failed to run: {e}") from e
        if out.returncode != 0:
            raise RuntimeError(f"{name} at {exe} exited {out.returncode}: {out.stderr[:400]}")


def ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id
