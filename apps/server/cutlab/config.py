"""Runtime configuration: paths, ports, and ffmpeg/ffprobe resolution."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SERVER_HOST = os.environ.get("CUTLAB_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("CUTLAB_PORT", "8787"))

# Repo root = three levels up from this file (cutlab/ -> server/ -> apps/ -> root)
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CUTLAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "cutlab.db"
PROJECTS_DIR = DATA_DIR / "projects"

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


def _resolve_ff(tool: str) -> str:
    """Resolve an ffmpeg-family binary.

    Env override (CUTLAB_FFMPEG / CUTLAB_FFPROBE) wins. Otherwise prefer the
    binary that lives next to ffprobe on PATH: on this machine ImageMagick
    ships an ancient ffmpeg that shadows the real install, while ffprobe
    resolves to the current build, so ffprobe's directory is the trustworthy
    anchor.
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
