"""P1.2 + P1.3: ffmpeg-based scene and silence detection on synthetic media."""
from __future__ import annotations

from pathlib import Path

import pytest

from cutlab.understanding import scenes as scenes_mod
from cutlab.understanding import silence as silence_mod
from cutlab.understanding.schema import SilenceSpan
from tests.media_fixtures import make_hardcut_video, make_tone_silence_tone, make_video


@pytest.mark.slow
def test_detect_scenes_finds_hard_cuts(tmp_path: Path):
    # Three 2s segments -> cuts near 2s and 4s, total 6s.
    v = make_hardcut_video(tmp_path / "cuts.mp4", seg_seconds=2.0)
    scenes = scenes_mod.detect_scenes(str(v), duration_ms=6000)
    assert len(scenes) == 3, [(s.start_ms, s.end_ms) for s in scenes]
    # Boundaries land near the true cuts (allow half-second slack for encoder GOP).
    assert scenes[0].start_ms == 0
    assert abs(scenes[1].start_ms - 2000) < 500
    assert abs(scenes[2].start_ms - 4000) < 500
    # Contiguous, ordered, indexed.
    for i in range(1, len(scenes)):
        assert scenes[i].start_ms == scenes[i - 1].end_ms
        assert scenes[i].index == i
    assert scenes[-1].end_ms == 6000


@pytest.mark.slow
def test_single_shot_video_is_one_scene(tmp_path: Path):
    v = make_video(tmp_path / "single.mp4", seconds=3.0)
    scenes = scenes_mod.detect_scenes(str(v), duration_ms=3000)
    assert len(scenes) == 1
    assert scenes[0].start_ms == 0 and scenes[0].end_ms == 3000


@pytest.mark.slow
def test_short_shots_merged(tmp_path: Path):
    v = make_hardcut_video(tmp_path / "cuts.mp4", seg_seconds=2.0)
    # With a 10s min-len, every shot is "too short" -> all merged into one scene.
    scenes = scenes_mod.detect_scenes(str(v), duration_ms=6000, min_len_ms=10_000)
    assert len(scenes) == 1
    assert scenes[0].start_ms == 0 and scenes[0].end_ms == 6000


@pytest.mark.slow
def test_detect_silence_middle_span(tmp_path: Path):
    # tone(2s) - silence(2s) - tone(2s)
    v = make_tone_silence_tone(tmp_path / "tst.mp4", seg_seconds=2.0)
    spans = silence_mod.silence_spans(str(v), duration_ms=6000)
    assert len(spans) == 1, [(s.start_ms, s.end_ms) for s in spans]
    span = spans[0]
    assert abs(span.start_ms - 2000) < 300
    assert abs(span.end_ms - 4000) < 300


@pytest.mark.slow
def test_active_ranges_complement_silence(tmp_path: Path):
    v = make_tone_silence_tone(tmp_path / "tst.mp4", seg_seconds=2.0)
    spans = silence_mod.silence_spans(str(v), duration_ms=6000)
    ranges = silence_mod.active_ranges(6000, spans)
    # Two active spans (the two tones) around the middle silence.
    assert len(ranges) == 2
    assert ranges[0].start_ms == 0
    assert ranges[1].end_ms == 6000
    # The gap between them straddles ~2000-4000.
    assert ranges[0].end_ms < ranges[1].start_ms
    assert 1500 < ranges[0].end_ms < 2600
    assert 3400 < ranges[1].start_ms < 4500


@pytest.mark.slow
def test_audio_only_silence(tmp_path: Path):
    v = make_tone_silence_tone(tmp_path / "aud.m4a", seg_seconds=2.0, with_video=False)
    spans = silence_mod.silence_spans(str(v), duration_ms=6000)
    assert len(spans) == 1


# -- pure logic (no ffmpeg) --------------------------------------------------


def test_active_ranges_all_silent_falls_back_to_full():
    ranges = silence_mod.active_ranges(
        5000, [SilenceSpan(start_ms=0, end_ms=5000)]
    )
    assert len(ranges) == 1
    assert ranges[0].start_ms == 0 and ranges[0].end_ms == 5000


def test_active_ranges_no_silence_is_whole():
    ranges = silence_mod.active_ranges(5000, [])
    assert ranges == [ranges[0]]
    assert ranges[0].start_ms == 0 and ranges[0].end_ms == 5000


def test_active_ranges_merges_close_gaps():
    # Two tiny silences 100ms apart get bridged after padding+merge.
    spans = [
        SilenceSpan(start_ms=1000, end_ms=1100),
        SilenceSpan(start_ms=1200, end_ms=1300),
    ]
    ranges = silence_mod.active_ranges(3000, spans, pad_ms=0, min_keep_ms=50, merge_gap_ms=250)
    # The 100ms active sliver at 1100-1200 merges with its neighbours.
    assert len(ranges) == 1
    assert ranges[0].start_ms == 0 and ranges[0].end_ms == 3000
