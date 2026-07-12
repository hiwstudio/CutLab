"""P5: Recap Engine — pure logic (chunking, beat parsing, matching, EDL plan)
+ the durable recap job end-to-end with a fake LLM and real Piper TTS."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cutlab.db import Database
from cutlab.edl.engine import Engine
from cutlab.engines import recap
from cutlab.understanding.schema import (
    Scene,
    Transcript,
    TranscriptSegment,
    Understanding,
    Word,
)


def useg(start_s: float, end_s: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(start_ms=int(start_s * 1000), end_ms=int(end_s * 1000),
                             text=text, words=[])


def movie_understanding() -> Understanding:
    """A 10-minute 'film': dialogue across three acts, four scenes."""
    segments = [
        useg(10, 60, "Once upon a time a knight set out to find the dragon."),
        useg(120, 200, "The knight crossed the mountains and met a wizard."),
        useg(300, 400, "The dragon attacked the village at night with fire."),
        useg(480, 560, "In the end the knight and the dragon became friends."),
    ]
    return Understanding(
        version="1.0", asset_id="ast_mv", kind="video", duration_ms=600_000,
        transcript=Transcript(language="en", segments=segments),
        scenes=[
            Scene(index=0, start_ms=0, end_ms=150_000),
            Scene(index=1, start_ms=150_000, end_ms=280_000),
            Scene(index=2, start_ms=280_000, end_ms=450_000),
            Scene(index=3, start_ms=450_000, end_ms=600_000),
        ],
    )


def test_transcript_chunks_cover_and_overlap():
    u = movie_understanding()
    chunks = recap.transcript_chunks(u, max_chars=120, overlap_chars=40)
    assert len(chunks) >= 2
    assert chunks[0]["start"] == 10.0
    assert chunks[-1]["end"] == 560.0
    # Every transcript line appears in some chunk.
    joined = "\n".join(c["text"] for c in chunks)
    assert "dragon became friends" in joined and "knight set out" in joined


def test_parse_beats_normalizes():
    beats = recap.parse_beats({"beats": [
        {"narration": "A knight seeks a dragon.", "approx_start": 10, "approx_end": 60},
        {"narration": "", "approx_start": 0, "approx_end": 0},        # dropped
        {"narration": "They become friends.", "approx_start": 480, "approx_end": 560},
    ]})
    assert [b["order"] for b in beats] == [0, 1]
    assert beats[0]["target_seconds"] == pytest.approx(4 * 60 / 200 / 1, abs=2)


def test_match_beats_time_prior_and_coverage():
    u = movie_understanding()
    beats = recap.parse_beats({"beats": [
        {"narration": "The dragon attacked the village with fire at night.",
         "approx_start": 300, "approx_end": 400},
    ]})
    # Force a long narration so coverage must extend across scenes.
    beats[0]["target_seconds"] = 200.0
    matched = recap.match_beats(beats, u)
    scenes = matched[0]["scenes"]
    # Anchored at the attack scene (index 2), extended to consecutive scenes.
    assert any(s["index"] == 2 for s in scenes)
    covered = sum(s["end_ms"] - s["start_ms"] for s in scenes)
    assert covered >= 200_000
    idxs = [s["index"] for s in scenes]
    assert idxs == sorted(idxs) and idxs == list(range(min(idxs), max(idxs) + 1))


def test_plan_recap_edl_applies_cleanly(tmp_path: Path):
    db = Database(tmp_path / "r.db")
    engine = Engine(db, projects_dir=tmp_path / "projects")
    pid = engine.create_project("Rc", {"width": 1280, "height": 720, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media" / "recap" / "ast_mv").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "film.mp4").write_bytes(b"stub")
    (pdir / "media" / "recap" / "ast_mv" / "beat_000.wav").write_bytes(b"stub")
    engine.apply(pid, 0, [{
        "op": "add_asset", "asset_id": "ast_mv", "kind": "video", "src": "media/film.mp4",
        "duration_ms": 600_000, "width": 1280, "height": 720,
    }])

    beats = [{"order": 0, "narration": "x", "approx_start": 300, "approx_end": 400,
              "target_seconds": 20.0,
              "scenes": [{"index": 2, "start_ms": 280_000, "end_ms": 450_000}]}]
    narration = [recap.RecapAsset(asset_id="ast_rn000",
                                  src="media/recap/ast_mv/beat_000.wav",
                                  duration_ms=20_000)]
    ops = recap.plan_recap_edl("ast_mv", beats, narration)
    head = engine.get_project(pid)["head_rev"]
    r = engine.apply(pid, head, ops, mode="propose")
    edl = r["edl"]
    vid = next(t for t in edl["tracks"] if t["id"] == "trk_recapv")
    aud = next(t for t in edl["tracks"] if t["id"] == "trk_recapn")
    assert len(vid["clips"]) == 1 and len(aud["clips"]) == 1
    clip = vid["clips"][0]
    assert clip["gain_db"] == recap.DUCK_ORIGINAL_DB   # original audio ducked
    assert clip["in_ms"] == 280_000                    # footage from the matched scene
    # Footage timeline length matches the narration length.
    tl = round((clip["out_ms"] - clip["in_ms"]) / clip["speed"])
    assert abs(tl - 20_000) <= 50
    db.close()


def test_speed_fit_slows_short_footage():
    beats = [{"order": 0, "narration": "x", "approx_start": 0, "approx_end": 10,
              "target_seconds": 20.0,
              "scenes": [{"index": 0, "start_ms": 0, "end_ms": 12_000}]}]
    narration = [recap.RecapAsset(asset_id="ast_rn000", src="a.wav", duration_ms=20_000)]
    ops = recap.plan_recap_edl("ast_mv", beats, narration)
    clip = next(o for o in ops if o["op"] == "add_clip" and o["track"] == "trk_recapv")
    assert clip["speed"] == pytest.approx(0.6, abs=0.01)  # 12s span / 20s narration
    assert clip["out_ms"] == 12_000                       # whole span used


# -- job end-to-end -------------------------------------------------------------


class ScriptedBackend:
    """Fake LLM: returns outline beats for map/reduce and a script for script."""

    manual = False

    def complete(self, system: str, user: str) -> str:
        if "Extract the ordered story beats" in user:
            return json.dumps({"beats": [
                {"title": "Setup", "summary": "Knight departs.",
                 "approx_start": 10, "approx_end": 200},
                {"title": "Attack", "summary": "Dragon attacks village.",
                 "approx_start": 300, "approx_end": 400},
            ]})
        if "merge duplicates" in user:
            return json.dumps({
                "logline": "A knight befriends a dragon.",
                "characters": [{"name": "Knight", "description": "brave"}],
                "setting": "a kingdom",
                "beats": [
                    {"title": "Setup", "summary": "Knight departs.",
                     "approx_start": 10, "approx_end": 200},
                    {"title": "Attack", "summary": "Dragon attacks.",
                     "approx_start": 300, "approx_end": 400},
                    {"title": "Truce", "summary": "They become friends.",
                     "approx_start": 480, "approx_end": 560},
                ],
                "ending": "friendship",
            })
        # script
        return json.dumps({"beats": [
            {"narration": "A brave knight sets out on a quest.",
             "approx_start": 10, "approx_end": 200},
            {"narration": "The dragon descends on the village in flames.",
             "approx_start": 300, "approx_end": 400},
        ]})


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("piper") is None, reason="piper not on PATH")
def test_recap_job_end_to_end(tmp_path: Path, monkeypatch):
    from cutlab.director import backends as dbackends
    from cutlab.jobs.queue import JobQueue
    from cutlab.jobs.recap import recap_handler
    from cutlab.jobs.worker import Worker
    from tests.media_fixtures import make_video

    monkeypatch.setattr(dbackends, "make_backend", lambda b=None: ScriptedBackend())

    db = Database(tmp_path / "rj.db")
    engine = Engine(db, projects_dir=tmp_path / "projects")
    pid = engine.create_project("RJob", {"width": 640, "height": 360, "fps": 30})["id"]
    pdir = engine.projects_dir / pid
    (pdir / "media").mkdir(parents=True, exist_ok=True)
    # Real (short) source so ffprobe/render paths stay honest; EDL says 600s but
    # the proposal only references in/out inside the matched scenes' spans —
    # keep the fake duration consistent instead: use a 600s claim with a stub is
    # wrong, so make a real 10s film and scale the understanding to it.
    make_video(pdir / "media" / "film.mp4", seconds=10, size="640x360")
    u = movie_understanding()
    # Scale times 60x down so scenes fit the real 10s file.
    for s in u.scenes:
        s.start_ms //= 60
        s.end_ms //= 60
    for seg in u.transcript.segments:
        seg.start_ms //= 60
        seg.end_ms //= 60
    u.duration_ms //= 60
    udir = pdir / "understanding"
    udir.mkdir(parents=True, exist_ok=True)
    (udir / "ast_mv.understanding.json").write_text(
        u.model_dump_json(exclude_none=True), encoding="utf-8")
    engine.apply(pid, 0, [
        {"op": "add_asset", "asset_id": "ast_mv", "kind": "video", "src": "media/film.mp4",
         "duration_ms": 10_000, "width": 640, "height": 360},
        {"op": "set_understanding", "asset": "ast_mv",
         "understanding": "understanding/ast_mv.understanding.json"},
    ])

    queue = JobQueue(db)
    job_id = queue.enqueue("recap", {
        "project_id": pid, "asset_id": "ast_mv", "target_minutes": 1,
        "project_dir": str(pdir),
    }, project_id=pid)
    worker = Worker(db, queue)
    worker.register("recap", recap_handler)
    assert worker.run_one()
    job = queue.get(job_id)
    assert job["state"] == "done", job["error"]
    assert set(job["artifacts"]) == {"outline", "script", "tts", "match", "propose"}

    # Narration wavs really synthesized by Piper.
    wavs = list((pdir / "media" / "recap" / "ast_mv").glob("beat_*.wav"))
    assert len(wavs) == 2
    from cutlab.util.ffprobe import probe

    assert all(probe(w).duration_ms > 500 for w in wavs)

    # Proposal exists with the recap tracks; accept realizes it.
    proposal = json.loads((pdir / "recap" / "ast_mv" / "propose.json")
                          .read_text(encoding="utf-8"))
    engine.accept_proposal(pid, proposal["rev"])
    edl = engine.get_edl(pid)
    track_ids = {t["id"] for t in edl["tracks"]}
    assert {"trk_recapv", "trk_recapn"} <= track_ids
    assert edl["project"]["duration_ms"] > 3000  # narrated timeline exists
    db.close()
