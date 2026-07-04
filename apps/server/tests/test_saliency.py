"""P1.6: saliency v1 — pure, deterministic scoring with per-profile weights."""
from __future__ import annotations

from cutlab.profiles import saliency_config
from cutlab.understanding.saliency import DEFAULT_WEIGHTS, compute_saliency
from cutlab.understanding.schema import (
    Scene,
    SilenceSpan,
    Transcript,
    TranscriptSegment,
    Word,
)


def speech_transcript(spans_ms):
    words = [Word(start_ms=s, end_ms=e, word="w") for s, e in spans_ms]
    return Transcript(
        language="en",
        segments=[TranscriptSegment(start_ms=spans_ms[0][0], end_ms=spans_ms[-1][1],
                                    text="w " * len(words), words=words)],
    )


def test_empty_media_no_windows():
    sal = compute_saliency(0, "default", DEFAULT_WEIGHTS, None, [], [], [])
    assert sal.windows == []


def test_window_partition_covers_duration():
    sal = compute_saliency(5000, "default", DEFAULT_WEIGHTS, None, [], [], [], window_ms=2000)
    assert [(w.start_ms, w.end_ms) for w in sal.windows] == [
        (0, 2000), (2000, 4000), (4000, 5000)
    ]
    assert sal.window_ms == 2000
    assert sal.weights["speech"] == 1.0


def test_speech_beats_silence():
    # Window 0-2000 full of speech; window 2000-4000 fully silent.
    transcript = speech_transcript([(0, 2000)])
    silence = [SilenceSpan(start_ms=2000, end_ms=4000)]
    sal = compute_saliency(4000, "default", DEFAULT_WEIGHTS, transcript, [], silence, [],
                           window_ms=2000)
    speech_win, silent_win = sal.windows
    assert speech_win.score > 0.5
    assert silent_win.score == 0.0  # fully silent, no speech -> floored at 0
    assert sal.peak() is speech_win


def test_scene_change_raises_score():
    scenes = [Scene(index=0, start_ms=0, end_ms=2500),
              Scene(index=1, start_ms=2500, end_ms=5000)]
    # No speech anywhere; only the scene cut at 2500 distinguishes window 2.
    sal = compute_saliency(5000, "default", DEFAULT_WEIGHTS, None, scenes, [], [],
                           window_ms=2500)
    assert sal.windows[0].score == 0.0        # no cut opens inside (start 0 ignored)
    assert sal.windows[1].score > 0.0         # cut at 2500 opens here


def test_beats_contribute():
    beats = [100, 600, 1100, 1600]  # 4 beats in the first 2s window
    sal = compute_saliency(2000, "default", DEFAULT_WEIGHTS, None, [], [], beats,
                           window_ms=2000)
    assert sal.windows[0].score > 0.0


def test_profile_weights_change_ranking():
    # A montage profile that ignores speech and prizes scene cuts should score a
    # cut-only window above a speech-only window; the speech profile does the reverse.
    transcript = speech_transcript([(0, 2000)])
    scenes = [Scene(index=0, start_ms=0, end_ms=2000),
              Scene(index=1, start_ms=2000, end_ms=4000)]
    speech_w = {"speech": 1.0, "scene": 0.1, "beat": 0.0, "silence": 0.8}
    montage_w = {"speech": 0.0, "scene": 1.0, "beat": 0.5, "silence": 0.2}

    speechy = compute_saliency(4000, "p", speech_w, transcript, scenes, [], [], window_ms=2000)
    montage = compute_saliency(4000, "p", montage_w, transcript, scenes, [], [], window_ms=2000)

    # Speech profile: window 0 (speech) beats window 1 (cut only).
    assert speechy.windows[0].score > speechy.windows[1].score
    # Montage profile: window 1 (the cut) beats window 0 (speech it ignores).
    assert montage.windows[1].score > montage.windows[0].score


def test_saliency_config_from_default_profile():
    window_ms, weights = saliency_config("default")
    assert window_ms == 2000
    assert weights["speech"] == 1.0 and weights["silence"] == 0.8


def test_saliency_config_unknown_profile_falls_back():
    window_ms, weights = saliency_config("does-not-exist")
    assert window_ms == 2000
    assert set(weights) == set(DEFAULT_WEIGHTS)
