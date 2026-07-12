"""P4: Compaction Engine — candidate generation, rubric scoring, NMS,
selection, and the compact op end-to-end through the engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from cutlab.engines import compaction
from cutlab.understanding.schema import (
    Saliency,
    SaliencyWindow,
    Scene,
    SilenceSpan,
    Transcript,
    TranscriptSegment,
    Understanding,
    Word,
)


def seg(start_s: float, end_s: float, text: str) -> TranscriptSegment:
    words = []
    tokens = text.split()
    if tokens:
        step = (end_s - start_s) / len(tokens)
        words = [
            Word(start_ms=int((start_s + i * step) * 1000),
                 end_ms=int((start_s + (i + 1) * step) * 1000), word=t)
            for i, t in enumerate(tokens)
        ]
    return TranscriptSegment(
        start_ms=int(start_s * 1000), end_ms=int(end_s * 1000), text=text, words=words
    )


def build_u(duration_s: float = 120.0) -> Understanding:
    """2-minute talk: dense speech 10-40s (high saliency), thin speech 60-80s,
    silence 40-60s and 80-120s."""
    segments = [
        seg(10, 25, "the single most important thing nobody tells you about editing " * 3),
        seg(25, 40, "and here is the proof it works watch this closely " * 3),
        seg(60, 80, "some quieter aside"),
    ]
    windows = []
    for t in range(0, 120, 2):
        score = 0.9 if 10 <= t < 40 else (0.3 if 60 <= t < 80 else 0.05)
        windows.append(SaliencyWindow(start_ms=t * 1000, end_ms=(t + 2) * 1000, score=score))
    return Understanding(
        version="1.0", asset_id="ast_cp", kind="video",
        duration_ms=int(duration_s * 1000),
        transcript=Transcript(language="en", segments=segments),
        scenes=[Scene(index=0, start_ms=0, end_ms=40_000),
                Scene(index=1, start_ms=40_000, end_ms=120_000)],
        silence=[SilenceSpan(start_ms=40_000, end_ms=60_000),
                 SilenceSpan(start_ms=80_000, end_ms=120_000)],
        saliency=Saliency(profile="default", window_ms=2000, windows=windows),
    )


def test_candidates_respect_band_and_word_boundaries():
    u = build_u()
    cands = compaction.candidates(u, band=(15_000, 58_000))
    assert cands
    for c in cands:
        assert 10_000 <= c.duration_ms <= 60_000  # snapped bounds may stretch slightly
        # Boundaries never cut inside a transcript segment.
        for s in u.transcript.segments:
            inside_start = s.start_ms < c.start_ms < s.end_ms
            inside_end = s.start_ms < c.end_ms < s.end_ms
            assert not inside_start and not inside_end, (c.start_ms, c.end_ms)
    # Hook text comes from the window's first words.
    assert any(c.hook_text.startswith("the single most important") for c in cands)


def test_scoring_prefers_salient_dense_windows():
    u = build_u()
    cands = compaction.score(compaction.candidates(u), u)
    best = max(cands, key=lambda c: c.score)
    # The best candidate lives in the 10-40s hot zone, not the quiet aside.
    assert best.start_ms < 40_000
    assert best.subscores["saliency"] > 5
    assert "density" in best.subscores and best.rationale


def test_nms_drops_heavy_overlaps():
    u = build_u()
    cands = compaction.score(compaction.candidates(u), u)
    kept = compaction.nms(cands)
    for i, a in enumerate(kept):
        for b in kept[i + 1:]:
            ov = max(0, min(a.end_ms, b.end_ms) - max(a.start_ms, b.start_ms))
            assert ov / min(a.duration_ms, b.duration_ms) <= 0.5


def test_select_hits_target_in_story_order():
    u = build_u()
    cands = compaction.score(compaction.candidates(u), u)
    chosen = compaction.select(cands, target_ms=35_000)
    assert chosen
    total = sum(c.duration_ms for c in chosen)
    assert total <= 40_000  # never wildly over target
    starts = [c.start_ms for c in chosen]
    assert starts == sorted(starts)  # chronological


def test_no_speech_falls_back_to_active_ranges():
    u = Understanding(
        version="1.0", asset_id="ast_na", kind="video", duration_ms=100_000,
        active_ranges=[{"start_ms": 0, "end_ms": 30_000},
                       {"start_ms": 50_000, "end_ms": 90_000}],
    )
    cands = compaction.candidates(u)
    assert cands  # windows built from active ranges


def test_empty_understanding_no_candidates():
    u = Understanding(version="1.0", asset_id="ast_e", kind="video", duration_ms=60_000)
    assert compaction.candidates(u) == []


# -- compact op through the engine ---------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path):
    from cutlab.db import Database
    from cutlab.edl.engine import Engine

    db = Database(tmp_path / "c.db")
    eng = Engine(db, projects_dir=tmp_path / "projects")
    yield eng
    eng.db.close()


def test_compact_op_end_to_end(engine):
    u = build_u()
    pid = engine.create_project("Comp", {"width": 1280, "height": 720, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "long.mp4").write_bytes(b"stub")
    udir = pdir / "understanding"
    udir.mkdir(parents=True, exist_ok=True)
    (udir / "ast_cp.understanding.json").write_text(
        u.model_dump_json(exclude_none=True), encoding="utf-8")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_cp", "kind": "video", "src": "media/long.mp4",
         "duration_ms": 120_000, "width": 1280, "height": 720},
        {"op": "add_track", "kind": "video", "id": "trk_v1"},
        {"op": "add_clip", "track": "trk_v1", "asset": "ast_cp",
         "in_ms": 0, "out_ms": 120_000, "start_ms": 0, "id": "clp_lg"},
        {"op": "set_understanding", "asset": "ast_cp",
         "understanding": "understanding/ast_cp.understanding.json"},
    ])
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, [{"op": "compact", "asset": "ast_cp", "target_ms": 35_000}])
    # The 2-minute timeline compacted to (roughly) the target.
    assert r["edl"]["project"]["duration_ms"] <= 45_000
    assert r["edl"]["project"]["duration_ms"] >= 15_000
    assert "compact" in r["summary"]


def test_compact_without_understanding_rejected(engine):
    pid = engine.create_project("NoU", {"width": 1280, "height": 720, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "v.mp4").write_bytes(b"stub")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_x1", "kind": "video", "src": "media/v.mp4",
         "duration_ms": 60_000, "width": 1280, "height": 720},
    ])
    from cutlab.edl.engine import Rejected

    with pytest.raises(Rejected) as exc:
        engine.apply(pid, engine.get_project(pid)["head_rev"],
                     [{"op": "compact", "asset": "ast_x1", "target_ms": 20_000}])
    assert exc.value.issues[0].code == "E_NO_UNDERSTANDING"
