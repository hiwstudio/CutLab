"""Phase 5 tests: replace_plan schema validation, fix.py shot/audio smoke test,
render_fix end-to-end (duration, audio bit-identity, stream counts)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import assemble, fix
from mixfix.ai.schemas import SchemaError, validate_replace_plan

CONTEXT = {
    "segment_bounds": {"seg_001": [0, 3000], "seg_002": [4000, 6000],
                       "seg_003": [12000, 20500]},
    "max_cover_ms": 8000,
    "min_gap_ms": 2000,
}


def _scene(id_, seg_ids):
    return {"id": id_, "segment_ids": seg_ids,
            "visual_intent": "b-roll of the topic", "queries": ["a query"]}


def test_valid_plan_passes():
    result = {"scenes": [_scene("s1", ["seg_001"])]}
    validate_replace_plan(result, CONTEXT)  # no raise


def test_exceeds_max_cover_raises():
    result = {"scenes": [_scene("s1", ["seg_003"])]}
    with pytest.raises(SchemaError, match="max cover"):
        validate_replace_plan(result, CONTEXT)


def test_min_gap_violation_raises():
    result = {"scenes": [_scene("s1", ["seg_001"]), _scene("s2", ["seg_002"])]}
    with pytest.raises(SchemaError):
        validate_replace_plan(result, CONTEXT)


def test_missing_queries_raises():
    sc = _scene("s1", ["seg_001"])
    del sc["queries"]
    with pytest.raises(SchemaError):
        validate_replace_plan({"scenes": [sc]}, CONTEXT)


def _make_video(path: Path, dur: float, pattern: str = "testsrc2") -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"{pattern}=size=320x180:rate=10:duration={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(path)],
        check=True, capture_output=True)


def test_extract_audio_and_detect_shots(tmp_path):
    video = tmp_path / "src.mp4"
    _make_video(video, 4.0)
    audio = fix.extract_audio(video, tmp_path / "audio.mp3")
    assert audio.exists()
    shots = fix.detect_shots(video)
    assert isinstance(shots, list) and shots
    for s in shots:
        assert isinstance(s["start_ms"], int)
        assert isinstance(s["end_ms"], int)


def _md5_audio(path: Path) -> str:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a",
         "-c", "copy", "-f", "md5", "-"],
        check=True, capture_output=True, text=True)
    return result.stdout.strip()


def test_render_fix_end_to_end(tmp_path):
    proj = tmp_path / "proj"
    (proj / "input").mkdir(parents=True)
    source = proj / "input" / "source.mp4"
    _make_video(source, 8.0)

    overlay = tmp_path / "overlay.mp4"
    _make_video(overlay, 4.0, pattern="smptebars")

    tl = {"project": "p", "total_ms": 8000, "scenes": [
        {"id": "s1", "start_ms": 2000, "end_ms": 5000,
         "visual": {"kind": "clip", "path": str(overlay), "asset_id": "x",
                    "trim_in_ms": 0, "trim_out_ms": 3000}},
    ]}
    tmap = {"source": {"duration_ms": 8000}, "segments": [
        {"id": "seg_001", "text": "x.", "start_ms": 0, "end_ms": 8000}]}
    cfg = {"render": {"width": 320, "height": 180, "fps": 10}}

    out = assemble.render_fix(proj, tl, tmap, cfg, source)
    assert out.exists()

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True)
    dur_ms = float(result.stdout.strip()) * 1000
    assert abs(dur_ms - 8000) <= 300

    assert _md5_audio(source) == _md5_audio(out)

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True)
    kinds = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert kinds.count("video") == 1
    assert kinds.count("audio") == 1
