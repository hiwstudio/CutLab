"""Config loading. config.yaml at repo root; env vars for secrets (names only in config)."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULTS = {
    "brain": "operator",              # operator | api
    "ffmpeg_dir": None,               # dir prepended to PATH (pick a modern ffmpeg)
    "transcriber": "faster-whisper",  # faster-whisper | json
    "whisper_model": "small",
    "llm": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
        "max_calls_per_run": 200,
    },
    "generate": {
        # Optional local image tool. Empty keeps generation as an explicit
        # operator hand-off so a fresh install never points at another machine.
        "image_tool": os.environ.get("MIXFIX_IMAGE_TOOL", ""),
        "image_model": "",         # blank = whatever the tool defaults to
    },
    "fix": {
        "max_cover_s": 8.0,        # never fully cover the speaker longer
        "min_return_gap_s": 2.0,   # original footage returns between overlays
    },
    "research": {
        "source": "yt-dlp",        # yt-dlp | fixture
        "fixture_dir": "fixtures/research",
        "min_interval_s": 2.0,
        "cookies_from_browser": None,
        "max_height": 720,
        "archive_dir": "archives",
        "section_pad_s": 8.0,
        "download_timeout_s": 300.0,
        "stall_s": 240.0,
        "first_byte_grace_s": 240.0,
        "download_timeout_per_s": 3.0,
        "chunk_s": 200.0,
        "ytdlp_ffmpeg_dir": None,
    },
    "render": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "captions": "sidecar",   # sidecar | burn | none
        "transition_s": 0.4,     # MIX scene crossfade (0 = hard cuts)
        "caption_size": 24,
        "target_lufs": -16,
    },
    "paths": {
        "projects": "projects",
        "ai_tasks": "ai_tasks",
        "db": "mixfix.db",
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(root: Path) -> dict:
    cfg = dict(DEFAULTS)
    path = root / "config.yaml"
    if path.exists():
        try:
            import yaml  # type: ignore
            with open(path, encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            cfg = _merge(cfg, user)
        except ModuleNotFoundError:
            pass  # no pyyaml -> defaults; config.yaml is optional
    cfg["root"] = str(root)
    # other tools (ImageMagick) can shadow PATH with an ancient ffmpeg; pin ours
    ff = cfg.get("ffmpeg_dir")
    if ff and Path(ff).is_dir() and not os.environ["PATH"].startswith(str(ff)):
        os.environ["PATH"] = str(ff) + os.pathsep + os.environ["PATH"]
    return cfg


def resolve_api_key(cfg: dict) -> str | None:
    return os.environ.get(cfg["llm"]["api_key_env"])
