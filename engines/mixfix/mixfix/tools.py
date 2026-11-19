"""Which ffmpeg the engine actually runs.

This is load-bearing, not tidiness. On this machine the first `ffmpeg` on PATH
is the one bundled with ImageMagick — version 4.2.3, from 2020 — and it does
not behave the same as a current build. Measured difference that broke renders:

    concat demuxer, entries written relative to the concat file
      ffmpeg 4.2.3  -> resolves them against the WORKING DIRECTORY  -> fails
      ffmpeg 8.1.2  -> resolves them against the concat file's dir  -> works

Renders were therefore passing or failing depending on the process's cwd, which
is invisible from the traceback. Resolve explicitly instead: FFMPEG_BIN /
FFPROBE_BIN if set, else the WinGet Gyan build, else whatever is on PATH.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def _resolve(tool: str) -> str:
    env = os.getenv(f"{tool.upper()}_BIN")
    if env and Path(env).exists():
        return env
    local = os.getenv("LOCALAPPDATA", "")
    if local:
        base = Path(local) / "Microsoft" / "WinGet" / "Packages"
        hits = sorted(base.glob(f"Gyan.FFmpeg*/**/{tool}.exe")) if base.exists() else []
        if hits:
            return str(hits[-1])
    return shutil.which(tool) or tool


FFMPEG = _resolve("ffmpeg")
FFPROBE = _resolve("ffprobe")
