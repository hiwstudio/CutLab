"""Transcription via local faster-whisper (P1).

Adapted from the owner's viral-clip-engine / recap-engine `engine/transcribe.py`
(the reuse source per CLAUDE.md): same model defaults and flags
(`word_timestamps=True, vad_filter=True`), audio pre-extracted as 16 kHz mono
pcm_s16le. Output is converted to the CutLab understanding schema (integer ms).

The whisper model is injected (`load_model` param) so the pipeline is testable
without the multi-hundred-MB dependency and model download; production passes the
real faster-whisper loader.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Protocol

from .. import config
from ..util.ffrun import run_ffmpeg
from .schema import Transcript, TranscriptSegment, Word, seconds_to_ms

WHISPER_MODEL = os.environ.get("CUTLAB_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("CUTLAB_WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.environ.get("CUTLAB_WHISPER_COMPUTE", "auto")


class _Model(Protocol):
    def transcribe(self, audio: str, **kw: Any) -> tuple[Any, Any]: ...


def extract_audio(video: str, out_wav: str) -> str:
    """16 kHz mono pcm_s16le — whisper's native input rate."""
    if Path(out_wav).exists() and Path(out_wav).stat().st_size > 0:
        return out_wav
    run_ffmpeg([
        "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(out_wav),
    ])
    return out_wav


def _load_faster_whisper() -> _Model:
    from faster_whisper import WhisperModel  # lazy: slow, heavy import

    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def transcribe_audio(
    audio_wav: str, load_model: Callable[[], _Model] | None = None
) -> Transcript:
    """Transcribe a prepared wav into a CutLab Transcript (ms units).

    `load_model` defaults to the real faster-whisper loader, resolved by name at
    call time so tests (and the understanding job) can monkeypatch it."""
    model = (load_model or _load_faster_whisper)()
    segments_iter, info = model.transcribe(
        str(audio_wav), word_timestamps=True, vad_filter=True
    )

    segments: list[TranscriptSegment] = []
    for seg in segments_iter:
        words = [
            Word(
                start_ms=seconds_to_ms(w.start),
                end_ms=seconds_to_ms(w.end),
                word=(w.word or "").strip(),
            )
            for w in (getattr(seg, "words", None) or [])
            if w.start is not None and w.end is not None
        ]
        segments.append(
            TranscriptSegment(
                start_ms=seconds_to_ms(seg.start),
                end_ms=seconds_to_ms(seg.end),
                text=(seg.text or "").strip(),
                words=words,
                avg_logprob=round(getattr(seg, "avg_logprob", 0.0) or 0.0, 3),
                no_speech_prob=round(
                    min(1.0, max(0.0, getattr(seg, "no_speech_prob", 0.0) or 0.0)), 3
                ),
            )
        )

    language = getattr(info, "language", None)
    return Transcript(language=language, segments=segments)


def transcribe_video(
    video: str, workdir: str, load_model: Callable[[], _Model] | None = None
) -> Transcript:
    wav = extract_audio(video, str(Path(workdir) / "audio.wav"))
    return transcribe_audio(wav, load_model=load_model)


def provenance() -> dict[str, str]:
    return {
        "tool": "faster-whisper",
        "model": WHISPER_MODEL,
        "device": WHISPER_DEVICE,
        "compute": WHISPER_COMPUTE,
        "word_timestamps": "true",
        "vad_filter": "true",
    }
