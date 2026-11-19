"""Step 1-2: extract audio and transcribe with local faster-whisper.

Produces transcript.json:
{
  "language": "en",
  "duration": 3621.5,
  "segments": [
    {"start": 1.2, "end": 4.8, "text": "...",
     "words": [{"start": 1.2, "end": 1.5, "word": "So"}, ...]},
    ...
  ]
}
"""
import json
from pathlib import Path

import config
from engine.utils import log, run_ffmpeg


def extract_audio(video: Path, workdir: Path) -> Path:
    audio = workdir / "audio.wav"
    if audio.exists():
        log("audio.wav already exists, skipping extraction")
        return audio
    log("Extracting audio...")
    run_ffmpeg(
        ["-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(audio)],
        desc="audio extraction",
    )
    return audio


def transcribe(video: Path, workdir: Path) -> dict:
    """Transcribe video; cache result in workdir/transcript.json."""
    out = workdir / "transcript.json"
    if out.exists():
        cached = json.loads(out.read_text(encoding="utf-8-sig"))
        # An EMPTY cached transcript is a cached failure: every later run skips
        # transcription, finds nothing to analyse, and fails identically forever.
        # Only a transcript with content is worth trusting.
        if cached.get("segments"):
            log("transcript.json already exists, skipping transcription")
            return cached
        log("cached transcript is empty — transcribing again")

    audio = extract_audio(video, workdir)

    from faster_whisper import WhisperModel  # imported lazily (slow import)

    log(f"Loading Whisper model '{config.WHISPER_MODEL}' "
        f"(first run downloads the model)...")
    model = WhisperModel(
        config.WHISPER_MODEL,
        device=config.WHISPER_DEVICE,
        compute_type=config.WHISPER_COMPUTE,
    )

    log("Transcribing (this can take a while on CPU)...")

    def _run(vad):
        segs, info = model.transcribe(str(audio), word_timestamps=True, vad_filter=vad)
        return list(segs), info

    # Silero VAD can reject an ENTIRE file — music, heavy backing track, unusual
    # mix — and hand back zero segments while whisper itself transcribes it fine.
    # Measured on the same class of source in clipinn. Retry without it rather
    # than reporting a video as having no speech.
    segments_iter, info = _run(True)
    if not segments_iter:
        log("VAD returned no speech — retrying transcription without it")
        segments_iter, info = _run(False)

    segments = []
    for seg in segments_iter:
        words = [
            {"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()}
            for w in (seg.words or [])
        ]
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
            # confidence signals used to judge how clear the speech is
            "avg_logprob": round(getattr(seg, "avg_logprob", 0.0) or 0.0, 3),
            "no_speech_prob": round(getattr(seg, "no_speech_prob", 0.0) or 0.0, 3),
        })
        # lightweight progress
        if len(segments) % 50 == 0:
            log(f"  ...transcribed up to {int(seg.end)}s")

    result = {
        "language": info.language,
        "duration": round(info.duration, 2),
        "segments": segments,
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Transcription done: {len(segments)} segments, language={info.language}")
    return result
