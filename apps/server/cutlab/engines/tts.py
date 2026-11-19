"""Text-to-speech backends adapted from the owner's recap engine."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import config
from ..util.ffrun import run_ffmpeg
from ..jobs.recap import _synth as synth_piper

FISH_URL = "https://api.fish.audio/v1/tts"


def synthesize(text: str, output_wav: Path) -> str:
    """Create a normalized voice WAV and return the backend actually used."""
    if config.TTS_ENGINE == "fish" and config.FISH_API_KEY:
        raw = output_wav.with_suffix(".fish.wav")
        try:
            _run_fish(text, raw)
            run_ffmpeg([
                "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "48000", "-ac", "2", str(output_wav),
            ])
            raw.unlink(missing_ok=True)
            return "fish"
        except Exception:
            raw.unlink(missing_ok=True)
            # The local voice keeps editing unblocked during free-tier outages
            # or exhausted quota. The job artifact records which backend won.
    synth_piper(text, output_wav)
    return "piper"


def _run_fish(text: str, out_path: Path) -> None:
    body: dict = {
        "text": text, "format": "wav", "normalize": True, "latency": "normal",
    }
    if abs(config.FISH_SPEED - 1.0) > 1e-6:
        body["prosody"] = {"speed": config.FISH_SPEED}
    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.FISH_API_KEY}",
        "Content-Type": "application/json",
        "model": config.FISH_MODEL,
    }
    last = ""
    for attempt in range(1, config.FISH_RETRIES + 1):
        req = urllib.request.Request(FISH_URL, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                audio = response.read()
            if not audio:
                raise RuntimeError("Fish Audio returned an empty response")
            out_path.write_bytes(audio)
            return
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:400].decode("utf-8", "replace")
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"Fish Audio HTTP {exc.code}: {detail}") from exc
            last = f"HTTP {exc.code}: {detail}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < config.FISH_RETRIES:
            time.sleep(2 * attempt)
    raise RuntimeError(f"Fish Audio failed after {config.FISH_RETRIES} attempts: {last}")
