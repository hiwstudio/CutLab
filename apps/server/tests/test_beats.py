"""P1.5: beat/tempo detection on a synthetic click track (deterministic)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cutlab.understanding import beats as beats_mod
from cutlab.understanding.beats import _onset_envelope, _tempo_bpm, detect_beats
from tests.media_fixtures import make_click_track


def test_onset_envelope_nonnegative():
    sig = np.sin(np.linspace(0, 100, 22050)).astype(np.float32)
    env = _onset_envelope(sig, 22050, 512)
    assert env.size > 0
    assert (env >= 0).all()


def test_tempo_of_synthetic_pulse_train():
    # A pulse every 0.5s in a 22050Hz onset envelope -> 120 BPM.
    frame_rate = 22050 / 512
    env = np.zeros(int(frame_rate * 8), dtype=np.float32)
    step = int(frame_rate * 0.5)
    env[::step] = 1.0
    bpm = _tempo_bpm(env, 22050, 512)
    assert abs(bpm - 120) < 8, bpm


@pytest.mark.slow
def test_detect_beats_on_click_track(tmp_path: Path):
    # 120 BPM click -> beats ~0.5s apart, ~16 beats over 8s.
    wav = make_click_track(tmp_path / "click.wav", bpm=120, seconds=8.0)
    beats_ms, tempo = detect_beats(str(wav))
    assert len(beats_ms) >= 12, len(beats_ms)
    # Median inter-beat interval near 500ms.
    diffs = np.diff(beats_ms)
    assert abs(float(np.median(diffs)) - 500) < 90, np.median(diffs)
    assert 100 < tempo < 140, tempo


@pytest.mark.slow
def test_detect_beats_silent_media_empty(tmp_path: Path):
    from tests.media_fixtures import make_tone_silence_tone

    # Pure silence -> no beats, no crash.
    from cutlab.util.ffrun import run_ffmpeg

    silent = tmp_path / "silent.wav"
    run_ffmpeg([
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-t", "3", "-c:a", "pcm_s16le", str(silent),
    ])
    beats_ms, tempo = detect_beats(str(silent))
    assert beats_ms == []


def test_provenance_names_backend():
    p = beats_mod.provenance()
    assert "librosa" in p["tool"] or "numpy" in p["tool"]
