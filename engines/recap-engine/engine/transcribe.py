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
from engine.utils import die, log, probe_duration, run_ffmpeg


def extract_audio(video: Path, workdir: Path) -> Path:
    audio = workdir / "audio.wav"
    if audio.exists():
        log("audio.wav already exists, skipping extraction")
        return audio
    log("Extracting audio...")
    # Copy the audio stream first, then resample. Direct mp4->wav on some
    # feature files (Ready or Not, 2026-09-09) hits non-monotonous DTS and
    # writes ~8 min of silence-dropped PCM while ffmpeg reports 95 min.
    tmp = workdir / "audio.src.mkv"
    run_ffmpeg(
        ["-i", str(video), "-vn", "-c:a", "copy", str(tmp)],
        desc="audio stream copy",
    )
    run_ffmpeg(
        ["-i", str(tmp), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(audio)],
        desc="audio extract",
    )
    try:
        tmp.unlink()
    except OSError:
        pass
    wav_dur = probe_duration(audio)
    vid_dur = probe_duration(video)
    if vid_dur > 60 and wav_dur < vid_dur * 0.8:
        audio.unlink(missing_ok=True)
        die(f"audio extract is {wav_dur:.0f}s but the video is {vid_dur:.0f}s "
            "- the wav is truncated. Delete audio.wav and retry.")
    return audio


def transcribe(video: Path, workdir: Path) -> dict:
    """Transcribe video; cache result in workdir/transcript.json."""
    out = workdir / "transcript.json"
    if out.exists():
        log("transcript.json already exists, skipping transcription")
        return json.loads(out.read_text(encoding="utf-8"))

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
    segments_iter, info = model.transcribe(
        str(audio), word_timestamps=True, vad_filter=True,
    )

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
