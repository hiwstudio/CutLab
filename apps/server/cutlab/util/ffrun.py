"""ffmpeg process execution: every invocation logged in full."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger("cutlab.ffmpeg")


class FFmpegError(Exception):
    def __init__(self, cmd: list[str], returncode: int, stderr_tail: str):
        super().__init__(f"ffmpeg exited {returncode}: {stderr_tail[-300:]}")
        self.cmd = cmd
        self.returncode = returncode
        self.stderr_tail = stderr_tail


def run_ffmpeg(args: list[str], timeout: int | None = None) -> None:
    """Run ffmpeg with the given args (binary prepended). Raises FFmpegError
    with the stderr tail on failure."""
    from .. import config

    cmd = [config.FFMPEG, "-hide_banner", "-y", *args]
    log.info("ffmpeg: %s", subprocess.list2cmdline(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, (proc.stderr or "")[-2000:])
