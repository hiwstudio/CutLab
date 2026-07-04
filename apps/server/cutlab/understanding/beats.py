"""Beat / tempo detection (P1).

Spec (A11) names librosa. On this machine's Python 3.14, librosa's numba
dependency may not have a wheel; so this module uses librosa when importable and
otherwise falls back to a numpy-only onset-envelope + tempo estimator over
decoded PCM. Both return the same shape: (beats_ms, tempo_bpm). See DECISIONS.md.

Beats feed the saliency scorer (musical energy) and, later, beat-synced cuts.
"""
from __future__ import annotations

import importlib.util
import subprocess

import numpy as np

from .. import config
from .schema import seconds_to_ms

SAMPLE_RATE = 22050
HOP = 512

HAVE_LIBROSA = importlib.util.find_spec("librosa") is not None


def decode_pcm(path: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Decode any media's first audio stream to mono float32 in [-1, 1]."""
    cmd = [
        config.FFMPEG, "-hide_banner", "-v", "error", "-i", str(path),
        "-map", "a:0?", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=1800)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros(0, dtype=np.float32)
    samples = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def _onset_envelope(samples: np.ndarray, sr: int, hop: int) -> np.ndarray:
    """Half-wave-rectified energy flux — a light onset strength signal."""
    if samples.size < hop:
        return np.zeros(0, dtype=np.float32)
    n = samples.size // hop
    frames = samples[: n * hop].reshape(n, hop)
    energy = np.sqrt((frames ** 2).mean(axis=1) + 1e-9)
    flux = np.diff(energy, prepend=energy[:1])
    return np.maximum(flux, 0.0)


def _tempo_bpm(env: np.ndarray, sr: int, hop: int) -> float:
    """Autocorrelation tempo estimate (50–200 BPM), with a log-normal prior
    centered at 120 BPM to resolve the octave ambiguity of a regular pulse
    train (a 0.5s and 1.0s lag are equally strong without it)."""
    if env.size < 4:
        return 0.0
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[env.size - 1:]
    frame_rate = sr / hop
    min_lag = max(1, int(frame_rate * 60.0 / 200.0))
    max_lag = min(int(frame_rate * 60.0 / 50.0), ac.size - 1)
    if max_lag <= min_lag:
        return 0.0
    lags = np.arange(min_lag, max_lag + 1)
    bpms = 60.0 * frame_rate / lags
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.7) ** 2)
    scored = ac[min_lag : max_lag + 1] * prior
    lag = int(lags[int(np.argmax(scored))])
    return round(60.0 * frame_rate / lag, 2) if lag else 0.0


def _peak_beats_ms(env: np.ndarray, sr: int, hop: int, tempo: float) -> list[int]:
    """Onset-envelope peaks spaced at least ~0.4× the tempo period apart."""
    if env.size == 0:
        return []
    frame_rate = sr / hop
    period_frames = (frame_rate * 60.0 / tempo) if tempo > 0 else frame_rate * 0.4
    min_dist = max(1, int(period_frames * 0.4))
    thresh = env.mean() + 0.5 * env.std()

    beats: list[int] = []
    last = -min_dist
    for i in range(1, env.size - 1):
        if env[i] > thresh and env[i] >= env[i - 1] and env[i] > env[i + 1]:
            if i - last >= min_dist:
                beats.append(seconds_to_ms(i * hop / sr))
                last = i
    return beats


def detect_beats_numpy(path: str) -> tuple[list[int], float]:
    samples = decode_pcm(path)
    if samples.size == 0:
        return [], 0.0
    env = _onset_envelope(samples, SAMPLE_RATE, HOP)
    tempo = _tempo_bpm(env, SAMPLE_RATE, HOP)
    beats = _peak_beats_ms(env, SAMPLE_RATE, HOP, tempo)
    # Prefer a tempo consistent with the beats we actually placed — this both
    # sharpens the estimate and corrects any residual octave error.
    if len(beats) >= 3:
        median_gap = float(np.median(np.diff(beats)))
        if median_gap > 0:
            tempo = round(60000.0 / median_gap, 2)
    return beats, tempo


def detect_beats_librosa(path: str) -> tuple[list[int], float]:
    import librosa

    y = decode_pcm(path)
    if y.size == 0:
        return [], 0.0
    tempo, frames = librosa.beat.beat_track(y=y, sr=SAMPLE_RATE, hop_length=HOP)
    times = librosa.frames_to_time(frames, sr=SAMPLE_RATE, hop_length=HOP)
    beats = [seconds_to_ms(float(t)) for t in times]
    tempo_val = float(np.atleast_1d(tempo)[0])
    return beats, round(tempo_val, 2)


def detect_beats(path: str) -> tuple[list[int], float]:
    """(beats_ms, tempo_bpm). Uses librosa if available, else the numpy fallback."""
    if HAVE_LIBROSA:
        try:
            return detect_beats_librosa(path)
        except Exception:  # noqa: BLE001 - fall back rather than fail the whole job
            pass
    return detect_beats_numpy(path)


def provenance() -> dict[str, str]:
    return {"tool": "librosa.beat_track" if HAVE_LIBROSA else "numpy onset+autocorr"}
