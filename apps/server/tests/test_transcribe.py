"""P1.4: transcription — schema conversion via an injected fake whisper model,
plus a real faster-whisper run gated on the dependency being installed."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest

from cutlab.understanding.transcribe import transcribe_audio, transcribe_video
from tests.media_fixtures import make_video


@dataclass
class FakeWord:
    start: float
    end: float
    word: str


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    words: list
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.05


@dataclass
class FakeInfo:
    language: str = "en"
    duration: float = 3.0


class FakeModel:
    def __init__(self, segments, info):
        self._segments = segments
        self._info = info
        self.calls: list[dict] = []

    def transcribe(self, audio, **kw):
        self.calls.append(kw)
        return iter(self._segments), self._info


def test_transcribe_converts_to_ms_schema():
    seg = FakeSegment(
        start=1.2, end=2.8, text="hello world",
        words=[FakeWord(1.2, 1.5, " hello"), FakeWord(1.6, 2.8, " world")],
    )
    model = FakeModel([seg], FakeInfo(language="en"))
    tr = transcribe_audio("ignored.wav", load_model=lambda: model)

    assert tr.language == "en"
    assert len(tr.segments) == 1
    s = tr.segments[0]
    assert (s.start_ms, s.end_ms) == (1200, 2800)
    assert s.text == "hello world"
    assert [(w.start_ms, w.end_ms, w.word) for w in s.words] == [
        (1200, 1500, "hello"), (1600, 2800, "world")
    ]
    assert tr.word_count() == 2
    # The whisper flags the engines rely on are actually passed.
    assert model.calls[0]["word_timestamps"] is True
    assert model.calls[0]["vad_filter"] is True


def test_transcribe_handles_missing_word_timings():
    seg = FakeSegment(start=0.0, end=1.0, text="mm", words=[])
    tr = transcribe_audio("x.wav", load_model=lambda: FakeModel([seg], FakeInfo()))
    assert tr.segments[0].words == []
    assert tr.word_count() == 0


def test_transcribe_passes_selected_language_to_whisper():
    model = FakeModel([], FakeInfo(language="es"))
    tr = transcribe_audio("x.wav", load_model=lambda: model, language="es")
    assert tr.language == "es"
    assert model.calls[0]["language"] == "es"


def test_no_speech_prob_clamped():
    seg = FakeSegment(start=0.0, end=1.0, text="x", words=[], no_speech_prob=1.7)
    tr = transcribe_audio("x.wav", load_model=lambda: FakeModel([seg], FakeInfo()))
    assert tr.segments[0].no_speech_prob == 1.0


@pytest.mark.slow
@pytest.mark.skipif(
    importlib.util.find_spec("faster_whisper") is None,
    reason="faster-whisper not installed",
)
def test_real_transcription_extracts_audio(tmp_path: Path):
    # testsrc2 has no speech; assert the pipeline runs end-to-end and returns a
    # valid (possibly empty) transcript, and that audio extraction happened.
    v = make_video(tmp_path / "clip.mp4", seconds=3.0, tone_hz=440)
    tr = transcribe_video(str(v), str(tmp_path))
    assert (tmp_path / "audio.wav").exists()
    assert tr.language is not None or tr.segments == []
