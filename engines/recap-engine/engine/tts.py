"""Stage: voiceover synthesis (Piper local, or the Fish Audio API).

synthesize(beats, workdir) renders one narration wav per beat, loudness-
normalises it, measures its real duration, and fills `audio` + `audio_seconds`
back into each beat (and edit.json). The measured durations are what the
assembler fits scenes to, and what the length-reconcile loop checks.

TTS_ENGINE picks the backend: "piper" (free, local, CPU) or "fish" (Fish Audio
HTTP API - a far more natural narration voice, needs FISH_API_KEY). Either way a
missing prerequisite fails with a clear, actionable message instead of crashing.
"""
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import config
from engine.utils import die, log, probe_duration, run_ffmpeg

PIPER_HELP = (
    "Local TTS needs Piper + a voice model.\n"
    "  1. Install Piper:   pip install piper-tts   (or download a release binary)\n"
    "  2. Get a voice:     a .onnx voice + its .onnx.json from\n"
    "                      https://huggingface.co/rhasspy/piper-voices\n"
    "  3. Point to it:     set PIPER_VOICE=<path to the .onnx> in .env"
)

FISH_HELP = (
    "Fish Audio TTS needs an API key.\n"
    "  1. Get a key:   https://fish.audio -> API keys\n"
    "  2. Point to it: FISH_API_KEY=... in ~/.env (global) or this project's .env\n"
    "  3. Optional:    FISH_MODEL (default s2.1-pro-free) and, on a PAID model\n"
    "                  only, FISH_VOICE_ID=<reference id of the voice>"
)
FISH_URL = "https://api.fish.audio/v1/tts"


def synthesize(beats: list, workdir: Path) -> list:
    """Render narration audio for each beat; annotate audio path + duration."""
    if config.TTS_ENGINE == "piper":
        if not config.PIPER_VOICE or not Path(config.PIPER_VOICE).exists():
            die(f"Piper voice not found (PIPER_VOICE='{config.PIPER_VOICE}')."
                f"\n{PIPER_HELP}")
        _ensure_piper()
        raw_ext = "wav"
    elif config.TTS_ENGINE == "fish":
        if not config.FISH_API_KEY:
            die(f"FISH_API_KEY is not set.\n{FISH_HELP}")
        raw_ext = config.FISH_FORMAT
    else:
        die(f"TTS_ENGINE='{config.TTS_ENGINE}' is not supported "
            f"(use 'piper' or 'fish').")

    audio_dir = workdir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    for b in beats:
        if b.get("dialogue"):
            # A dialogue beat has no voiceover - the film speaks for itself, so
            # its length IS its footage. Derive that from the scenes rather than
            # trusting `target_seconds` to have survived the trip through
            # edit.json: it does not, and a length of 0 silently drops the beat
            # out of the assembled cut.
            secs = float(b.get("target_seconds") or 0.0)
            if secs <= 0:
                secs = sum(float(s["end"]) - float(s["start"])
                           for s in b.get("scenes") or [])
            if secs <= 0:
                die(f"tts: dialogue beat {b['order']} has no footage to play.")
            b["audio"] = None
            b["audio_seconds"] = round(secs, 3)
            continue
        wav = audio_dir / f"beat_{b['order']:03d}.wav"
        if not wav.exists():
            raw = audio_dir / f"beat_{b['order']:03d}.raw.{raw_ext}"
            if config.TTS_ENGINE == "piper":
                _run_piper(b["narration"], raw)
            else:
                _run_fish(b["narration"], raw)
            _loudnorm(raw, wav)
            raw.unlink(missing_ok=True)
        b["audio"] = str(wav.relative_to(workdir)).replace("\\", "/")
        b["audio_seconds"] = round(probe_duration(wav), 3)

    # persist the filled-in audio fields back to edit.json if present
    edit_path = workdir / "edit.json"
    if edit_path.exists():
        edit_path.write_text(json.dumps(beats, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    spoken = [b for b in beats if not b.get("dialogue")]
    voiced_secs = sum(b["audio_seconds"] for b in spoken)
    total = sum(b["audio_seconds"] for b in beats)
    words = sum(len(b["narration"].split()) for b in spoken)
    wpm = words / (voiced_secs / 60) if voiced_secs else 0
    dlg = len(beats) - len(spoken)
    log(f"TTS ({config.TTS_ENGINE}): {len(spoken)} narration clips, "
        f"{total / 60:.1f} min total"
        + (f" (incl. {dlg} dialogue beats playing the film's own audio)" if dlg else "")
        + f" (measured {wpm:.0f} wpm vs NARRATION_WPM={config.NARRATION_WPM}).")
    return beats


# --- Fish Audio (HTTP API) -----------------------------------------------------

def _run_fish(text: str, out_path: Path) -> None:
    """Synthesize `text` via the Fish Audio HTTP API into out_path.

    Retries transient failures (an SSL EOF or 5xx part-way through a long batch
    is common). A 4xx other than 429 is a real config error, so fail fast with
    the API's own message rather than burning retries.
    """
    body = {"text": text, "format": config.FISH_FORMAT, "normalize": True,
            "latency": "normal"}
    if config.FISH_SPEED and abs(config.FISH_SPEED - 1.0) > 1e-6:
        # Delivery speed. Measured 2026-09-04: the default voice reads recap
        # prose at ~225-247 wpm, well above the 151-205 wpm the professional
        # recap channels actually narrate at - it lands as rushed. 0.85 brings
        # it to ~209. This changes PACE, not length policy: the recap is still
        # however long the narration naturally runs to.
        body["prosody"] = {"speed": config.FISH_SPEED}
    if config.FISH_VOICE_ID:
        body["reference_id"] = config.FISH_VOICE_ID
    payload = json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {config.FISH_API_KEY}",
               "Content-Type": "application/json",
               "model": config.FISH_MODEL}

    last = ""
    for attempt in range(1, config.FISH_RETRIES + 1):
        req = urllib.request.Request(FISH_URL, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                audio = resp.read()
            if not audio:
                raise RuntimeError("Fish Audio returned an empty response")
            out_path.write_bytes(audio)
            return
        except urllib.error.HTTPError as e:
            detail = e.read()[:400].decode("utf-8", "replace")
            if e.code < 500 and e.code != 429:
                die(f"Fish Audio HTTP {e.code}: {detail}{_fish_hint(e.code)}"
                    f"\n{FISH_HELP}")
            last = f"HTTP {e.code}: {detail}"
        except Exception as e:  # network / SSL / timeout
            last = f"{type(e).__name__}: {e}"
        if attempt == config.FISH_RETRIES:
            die(f"Fish Audio failed after {attempt} attempts - {last}")
        log(f"Fish Audio attempt {attempt} failed ({last}); retrying...")
        time.sleep(2 * attempt)


def _fish_hint(code: int) -> str:
    """Turn the two Fish errors we actually hit into an actionable line."""
    if code == 400 and config.FISH_VOICE_ID:
        return ("\nA 400 'Reference not found' means custom voices are not "
                "available on this model - clear FISH_VOICE_ID, or set "
                "FISH_MODEL to a paid model with credit.")
    if code == 402:
        return (f"\nNo API credit for FISH_MODEL='{config.FISH_MODEL}' - use "
                "the free model (s2.1-pro-free) or top up the account.")
    return ""


# --- Piper (local) -------------------------------------------------------------

def _ensure_piper() -> None:
    if _piper_cmd() is None:
        die(f"Piper executable not found on PATH.\n{PIPER_HELP}")


def _piper_cmd() -> list | None:
    """Return the command prefix to invoke Piper, or None if unavailable.
    Prefers a `piper` binary on PATH, falls back to `python -m piper`."""
    exe = shutil.which("piper")
    if exe:
        return [exe]
    try:
        import piper  # noqa: F401
        import sys
        return [sys.executable, "-m", "piper"]
    except ImportError:
        return None


def _run_piper(text: str, out_wav: Path) -> None:
    """Synthesize `text` to out_wav via Piper (text on stdin)."""
    cmd = _piper_cmd() + ["-m", config.PIPER_VOICE, "-f", str(out_wav)]
    proc = subprocess.run(cmd, input=text, text=True,
                          capture_output=True)
    if proc.returncode != 0 or not out_wav.exists():
        die(f"Piper failed to synthesize narration:\n{proc.stderr[-1000:]}")


def _loudnorm(src: Path, dst: Path) -> None:
    """Loudness-normalise narration to a consistent broadcast level (EBU R128)
    and standardise to 48k stereo so all beats concat cleanly."""
    run_ffmpeg(
        ["-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-ar", "48000", "-ac", "2", str(dst)],
        desc="narration loudnorm",
    )
