"""Timing Map — canonical ms-based timing schema (timing-map skill).

Built once per project from YouTube auto-captions (segments layer only) or
from whisper (words + segments). Selection reads segments; per-clip subtitle
timing comes later from whisper on each downloaded segment (words layer,
clip-local map).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


def from_caption_events(events: list, duration_ms: int, project: str) -> dict:
    """YouTube json3 caption events -> Timing Map (segments layer).

    YouTube's auto-captions are rolling: each event often repeats and extends
    the previous line's text, so raw events overlap heavily by design (not
    malformed data). Clip every segment's end to the next event's start so
    segments tile the timeline instead of overlapping; drop what collapses
    to near-zero duration (duplicate/rolling re-issues of the same line).
    """
    events = sorted(events, key=lambda e: e["start_ms"])
    segments = []
    for i, ev in enumerate(events):
        end = min(ev["end_ms"], duration_ms) if duration_ms else ev["end_ms"]
        if i + 1 < len(events):
            end = min(end, events[i + 1]["start_ms"])
        if end - ev["start_ms"] < 100:
            continue
        segments.append({"id": f"seg_{len(segments) + 1:04d}", "text": ev["text"],
                         "start_ms": ev["start_ms"], "end_ms": end})
    return {
        "version": "1.0",
        "source": {"audio_path": "", "duration_ms": duration_ms,
                   "transcriber": "youtube-auto-captions", "model": ""},
        "segments": segments,
        "meta": {"project": project, "brand": "clipinn",
                 "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    }


@lru_cache(maxsize=1)
def _whisper_model(name: str, device: str, compute: str):
    """Load once per process — render transcribes every clip separately, and
    reloading the model per clip costs more than the transcription itself."""
    from faster_whisper import WhisperModel
    from .utils import log
    log(f"Loading whisper '{name}' (first run downloads it)...")
    return WhisperModel(name, device=device, compute_type=compute)


def from_whisper(audio_path: Path, project: str) -> dict:
    """Transcribe with faster-whisper -> Timing Map (words + segments)."""
    from . import config
    from .utils import log

    model = _whisper_model(config.WHISPER_MODEL, config.WHISPER_DEVICE,
                           config.WHISPER_COMPUTE)

    def _transcribe(vad: bool):
        seg_iter, info = model.transcribe(str(audio_path), word_timestamps=True,
                                          vad_filter=vad)
        words, segments = [], []
        for seg in seg_iter:
            w0 = len(words)
            for w in (seg.words or []):
                words.append({"text": w.word.strip(),
                              "start_ms": int(w.start * 1000),
                              "end_ms": int(w.end * 1000),
                              "confidence": round(getattr(w, "probability", 1.0) or 1.0, 3)})
            segments.append({"id": f"seg_{len(segments) + 1:04d}",
                             "text": seg.text.strip(),
                             "start_ms": int(seg.start * 1000),
                             "end_ms": int(seg.end * 1000),
                             "word_indices": [w0, len(words) - 1] if len(words) > w0 else []})
        return words, segments, info

    words, segments, info = _transcribe(True)
    if not segments:
        # Silero VAD can reject an entire file (measured: music-heavy audio yields
        # zero segments with VAD on, a full transcript with it off). Losing the
        # whole source is worse than transcribing some silence.
        log("VAD returned no speech — retrying transcription without it")
        words, segments, info = _transcribe(False)
    return {
        "version": "1.0",
        "source": {"audio_path": str(audio_path),
                   "duration_ms": int(info.duration * 1000),
                   "transcriber": "faster-whisper", "model": str(info)[:0] or ""},
        "words": words,
        "segments": segments,
        "meta": {"project": project, "brand": "clipinn",
                 "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    }


def validate(tm: dict) -> list:
    """Return a list of problems; empty list = valid. Mandatory before use."""
    errs = []
    if not tm.get("segments") and not tm.get("words"):
        errs.append("needs words or segments layer")
    dur = tm.get("source", {}).get("duration_ms") or 0
    prev_end, seen = -1, set()
    for s in tm.get("segments", []):
        if s["id"] in seen:
            errs.append(f"duplicate id {s['id']}")
        seen.add(s["id"])
        if not (isinstance(s["start_ms"], int) and isinstance(s["end_ms"], int)):
            errs.append(f"{s['id']}: times must be int ms")
        if s["end_ms"] <= s["start_ms"]:
            errs.append(f"{s['id']}: end<=start")
        if s["start_ms"] < prev_end - 1000:  # auto-captions may slightly overlap
            errs.append(f"{s['id']}: heavy overlap with previous segment")
        prev_end = s["end_ms"]
        if dur and s["end_ms"] > dur + 3000:
            errs.append(f"{s['id']}: beyond source duration")
    return errs


def save(tm: dict, path: Path) -> Path:
    problems = validate(tm)
    if problems:
        raise ValueError("invalid timing map: " + "; ".join(problems[:5]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tm, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    tm = json.loads(path.read_text(encoding="utf-8-sig"))
    problems = validate(tm)
    if problems:
        raise ValueError(f"{path} is invalid: " + "; ".join(problems[:5]))
    return tm
