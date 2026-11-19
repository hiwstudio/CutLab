"""Timing Map — canonical audio-first timing schema (timing-map conventions).

Milliseconds everywhere (integers). Stable string IDs. Enrichment stages append
layers (scenes); they never mutate word/segment timings from the transcriber.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .tools import FFPROBE

VERSION = "1.0"


class TimingMapError(ValueError):
    pass


def audio_duration_ms(audio_path: Path) -> int:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, check=True)
    return int(round(float(out.stdout.strip()) * 1000))


def transcribe(audio_path: Path, cfg: dict, project_dir: Path) -> dict:
    """Build a Timing Map from audio. Transcribers: faster-whisper | json."""
    duration = audio_duration_ms(audio_path)
    method = cfg.get("transcriber", "faster-whisper")
    if method == "json":
        # Test/offline mode: read words from <project>/voiceover/transcript.json
        tpath = project_dir / "voiceover" / "transcript.json"
        if not tpath.exists():
            raise TimingMapError(
                f"transcriber=json requires {tpath} with"
                ' {"words": [{"text","start_ms","end_ms"}]}')
        words = json.loads(tpath.read_text(encoding="utf-8"))["words"]
        transcriber_name = "json"
        model = "n/a"
    elif method == "faster-whisper":
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ModuleNotFoundError as e:
            raise TimingMapError(
                "faster-whisper not installed. Install it, or set"
                " transcriber: json in config.yaml for offline testing.") from e
        model_name = cfg.get("whisper_model", "small")
        wm = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments_iter, _info = wm.transcribe(str(audio_path), word_timestamps=True)
        words = []
        for seg in segments_iter:
            for w in seg.words or []:
                words.append({
                    "text": w.word.strip(),
                    "start_ms": int(round(w.start * 1000)),
                    "end_ms": int(round(w.end * 1000)),
                    "confidence": round(getattr(w, "probability", 1.0), 4),
                })
        transcriber_name = "faster-whisper"
        model = model_name
    else:
        raise TimingMapError(f"unknown transcriber: {method}")

    segments = _group_sentences(words)
    tmap = {
        "version": VERSION,
        "source": {
            "audio_path": str(audio_path),
            "duration_ms": duration,
            "transcriber": transcriber_name,
            "model": model,
        },
        "words": words,
        "segments": segments,
        "meta": {"project": project_dir.name},
    }
    validate(tmap)
    return tmap


MAX_SEGMENT_MS = 8000


def _group_sentences(words: list[dict], max_ms: int = MAX_SEGMENT_MS) -> list[dict]:
    """Group words into sentence segments on terminal punctuation, then split
    any segment that runs too long.

    Punctuation alone is not enough. Transcribers punctuate conversational
    speech sparsely, and one measured 41s interview came back as a single 37.7s
    segment. Everything downstream is capped by this: scenes are built from
    segments, so one segment means one scene, one reference clip, and 37 seconds
    of the same picture. Long segments are split at their longest internal pause
    — a natural breath boundary — until each fits.
    """
    segments, current = [], []
    for i, w in enumerate(words):
        current.append(i)
        if w["text"].rstrip().endswith((".", "!", "?")) or i == len(words) - 1:
            segments.append({"word_indices": [current[0], current[-1]]})
            current = []
    return _finalise(_split_long(segments, words, max_ms), words)


def _split_long(segments: list[dict], words: list[dict],
                max_ms: int) -> list[dict]:
    """Recursively halve over-long segments at a breath pause near the middle.

    The cut must be BALANCED. Splitting at the globally largest gap and
    recursing does not work: in fast speech every gap is roughly equal, so the
    first maximum lands near the start and the routine peels two-word fragments
    off the front — one measured run produced 49 segments averaging 0.6s. So
    only gaps that leave both halves substantial are eligible, and among those
    the longest silence wins.
    """
    min_half = max(1500, max_ms // 4)
    out: list[dict] = []
    queue = list(segments)
    while queue:
        seg = queue.pop(0)
        lo, hi = seg["word_indices"]
        if words[hi]["end_ms"] - words[lo]["start_ms"] <= max_ms or hi - lo < 3:
            out.append(seg)
            continue
        start, end = words[lo]["start_ms"], words[hi]["end_ms"]
        mid = (start + end) // 2
        cut, best = None, None
        for i in range(lo + 1, hi + 1):
            if (words[i - 1]["end_ms"] - start < min_half
                    or end - words[i]["start_ms"] < min_half):
                continue                      # would leave a stub
            gap = words[i]["start_ms"] - words[i - 1]["end_ms"]
            # longest silence wins; ties break toward the middle, or evenly
            # spaced speech gets chopped from the front one chunk at a time
            key = (gap, -abs(words[i]["start_ms"] - mid))
            if best is None or key > best:
                best, cut = key, i
        if cut is None:                       # no balanced pause — halve by count
            cut = lo + (hi - lo + 1) // 2
        queue[:0] = [{"word_indices": [lo, cut - 1]},
                     {"word_indices": [cut, hi]}]
    out.sort(key=lambda s: s["word_indices"][0])
    return out


def _finalise(segments: list[dict], words: list[dict]) -> list[dict]:
    """Number the segments and fill in text and timings from their word range."""
    final = []
    for n, seg in enumerate(segments, 1):
        lo, hi = seg["word_indices"]
        final.append({
            "id": f"seg_{n:03d}",
            "text": " ".join(words[j]["text"] for j in range(lo, hi + 1)),
            "start_ms": words[lo]["start_ms"],
            "end_ms": words[hi]["end_ms"],
            "word_indices": [lo, hi],
        })
    return final


def validate(tmap: dict) -> None:
    """Mandatory before any downstream stage consumes the map."""
    def fail(msg: str):
        raise TimingMapError(f"timing map invalid: {msg}")

    if tmap.get("version") != VERSION:
        fail(f"version must be {VERSION}")
    dur = tmap.get("source", {}).get("duration_ms")
    if not isinstance(dur, int) or dur <= 0:
        fail("source.duration_ms must be a positive int")

    words = tmap.get("words", [])
    if not words and not tmap.get("segments"):
        fail("need words or segments")
    prev_end = 0
    for i, w in enumerate(words):
        for key in ("start_ms", "end_ms"):
            if not isinstance(w.get(key), int):
                fail(f"word {i}: {key} must be int ms")
        if w["start_ms"] < prev_end - 50:  # allow 50ms transcriber jitter
            fail(f"word {i} overlaps previous (start {w['start_ms']} < {prev_end})")
        if w["end_ms"] < w["start_ms"]:
            fail(f"word {i}: end before start")
        if w["end_ms"] > dur + 500:
            fail(f"word {i}: end {w['end_ms']} beyond duration {dur}")
        prev_end = w["end_ms"]

    seg_ids = set()
    for s in tmap.get("segments", []):
        if s["id"] in seg_ids:
            fail(f"duplicate segment id {s['id']}")
        seg_ids.add(s["id"])
        lo, hi = s["word_indices"]
        if words:
            if s["start_ms"] != words[lo]["start_ms"] or s["end_ms"] != words[hi]["end_ms"]:
                fail(f"segment {s['id']} does not cover its word range")

    for sc in tmap.get("scenes", []):
        if not sc.get("segment_ids"):
            fail(f"scene {sc.get('id')} has no segments")
        for sid in sc["segment_ids"]:
            if sid not in seg_ids:
                fail(f"scene {sc['id']} references unknown segment {sid}")
        if not (isinstance(sc.get("start_ms"), int) and isinstance(sc.get("end_ms"), int)):
            fail(f"scene {sc.get('id')}: start_ms/end_ms must be int ms")


def attach_scenes(tmap: dict, scenes_result: dict) -> dict:
    """Append the scenes layer from a validated scene_breakdown result."""
    seg_by_id = {s["id"]: s for s in tmap["segments"]}
    scenes = []
    for sc in scenes_result["scenes"]:
        segs = [seg_by_id[sid] for sid in sc["segment_ids"]]
        scenes.append({
            "id": sc["id"],
            "segment_ids": sc["segment_ids"],
            "start_ms": min(s["start_ms"] for s in segs),
            "end_ms": max(s["end_ms"] for s in segs),
            "visual_intent": sc["visual_intent"],
            "assets": [],
        })
    scenes.sort(key=lambda s: s["start_ms"])
    tmap["scenes"] = scenes
    validate(tmap)
    return tmap


def save(tmap: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tmap, indent=2), encoding="utf-8")


def load(path: Path) -> dict:
    tmap = json.loads(path.read_text(encoding="utf-8"))
    validate(tmap)
    return tmap
