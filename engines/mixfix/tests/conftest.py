"""Apply config.yaml's ffmpeg_dir PATH pin for all tests (xfade needs ffmpeg 4.3+)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix.config import load_config

load_config(Path(__file__).resolve().parents[1])
