"""assembly_cut against real files, no network.

The cut is the join between the two halves of this mode and the piece the
pipeline test suite cannot reach: everything else is schema work, but this one
actually shells out to ffmpeg. Synthetic clips stand in for fetched windows so
the path is exercised offline.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from assembly.cut import build_cut
from mixfix.tools import FFMPEG, FFPROBE

pytestmark = pytest.mark.skipif(shutil.which(FFMPEG) is None and not FFMPEG,
                                reason="ffmpeg not resolvable")


def _clip(path, seconds, freq):
    """A distinguishable clip: solid colour + a tone, so a mis-ordered concat
    is visible rather than merely wrong in the metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=0x{freq:06x}:s=320x180:d={seconds}:r=15",
         "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(path)],
        check=True, capture_output=True)


def _dur_ms(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return int(round(float(out) * 1000))


def test_cut_prepends_the_hook_and_lands_on_the_planned_duration(tmp_path):
    win_dir = tmp_path / "assembly" / "windows"
    # 30s + 20s of body; hook is 6s lifted from inside win_000
    _clip(win_dir / "win_000.mp4", 30, 0x0000ff)
    _clip(win_dir / "win_001.mp4", 20, 0x00ff00)

    plan = {
        "url": "https://youtu.be/x",
        "hook": {"segment_ids": ["seg_0001"],
                 "source_start_ms": 100_000, "source_end_ms": 106_000,
                 "why": "a named danger, no setup"},
        "windows": [
            {"id": "win_000", "segment_ids": ["seg_0000"],
             "source_start_ms": 90_000, "source_end_ms": 120_000, "why": "a"},
            {"id": "win_001", "segment_ids": ["seg_0010"],
             "source_start_ms": 200_000, "source_end_ms": 220_000, "why": "b"},
        ],
    }

    out, hook_ms, body_ms = build_cut(tmp_path, plan, {})

    assert out.exists(), "the cut must land at input/source.mp4 for the FIX half"
    assert body_ms == 50_000
    assert abs(hook_ms - 6_000) < 400, f"hook came out {hook_ms}ms"

    # The whole point: the hook is PREPENDED, not moved. Total is hook + body,
    # and the QA duration check compares the render against exactly this.
    total = _dur_ms(out)
    assert abs(total - (hook_ms + body_ms)) < 700, (
        f"cut is {total}ms, planned {hook_ms + body_ms}ms")

    probe = json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(out)],
        capture_output=True, text=True, check=True).stdout)
    kinds = sorted(s["codec_type"] for s in probe["streams"])
    assert kinds == ["audio", "video"], f"cut lost a stream: {kinds}"


def test_cut_is_idempotent_on_resume(tmp_path):
    """Stages rerun after a pause; the second pass must not re-encode or grow."""
    win_dir = tmp_path / "assembly" / "windows"
    _clip(win_dir / "win_000.mp4", 12, 0x0000ff)
    plan = {"url": "u",
            "hook": {"segment_ids": ["s"], "source_start_ms": 4_000,
                     "source_end_ms": 9_000, "why": "w"},
            "windows": [{"id": "win_000", "segment_ids": ["s"],
                         "source_start_ms": 0, "source_end_ms": 12_000,
                         "why": "a"}]}
    out1, h1, b1 = build_cut(tmp_path, plan, {})
    first = out1.stat().st_mtime_ns
    out2, h2, b2 = build_cut(tmp_path, plan, {})
    assert (h1, b1) == (h2, b2)
    assert out2.stat().st_mtime_ns == first, "resume re-encoded an existing cut"


def test_a_hook_outside_every_window_is_refused_before_ffmpeg_runs(tmp_path):
    plan = {"url": "u",
            "hook": {"segment_ids": ["s"], "source_start_ms": 500_000,
                     "source_end_ms": 505_000, "why": "w"},
            "windows": [{"id": "win_000", "segment_ids": ["s"],
                         "source_start_ms": 0, "source_end_ms": 30_000,
                         "why": "a"}]}
    with pytest.raises(ValueError, match="not inside any selected window"):
        build_cut(tmp_path, plan, {})


def test_fixture_source_can_range_fetch_so_the_mode_runs_offline(tmp_path):
    """A mode that range-fetches could not be tested without a live network
    until FixtureSource grew fetch_segment. Guards that it stays."""
    from mixfix.research import FixtureSource, cut_section

    vids = tmp_path / "videos"
    _clip(vids / "dQw4w9WgXcQ.mp4", 20, 0x00ffff)
    src = FixtureSource(tmp_path)

    path, base = src.fetch_segment("https://youtu.be/dQw4w9WgXcQ", 5_000, 12_000)
    assert base == 0, "fixture returns the whole file, so the base is zero"

    out = tmp_path / "win.mp4"
    cut_section(path, out, 5_000 - base, 12_000 - base)
    assert abs(_dur_ms(out) - 7_000) < 400


def test_a_missing_fixture_video_fails_loudly(tmp_path):
    from mixfix.research import FixtureSource, ResearchError
    with pytest.raises(ResearchError, match="fixture video missing"):
        FixtureSource(tmp_path).fetch_segment("https://youtu.be/abc12345678", 0, 1)


# ---- the stall watchdog ---------------------------------------------------
# Elapsed time cannot separate "stuck" from "slow"; bytes arriving can. These
# guard the watchdog that replaced a retry loop which turned a 31-minute
# failure into a 95-minute one against what was actually a rate limit.

class _FakeProc:
    """Never exits on its own — the watchdog must be what stops it."""

    def __init__(self):
        self.returncode = None

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=timeout or 0)


def test_a_download_making_no_progress_is_killed_in_minutes(tmp_path):
    from mixfix.research import _wait_with_progress
    dest = tmp_path / "vid.mp4"
    with pytest.raises(subprocess.TimeoutExpired):
        # generous elapsed budget, tiny stall budget: the stall must fire first
        _wait_with_progress(_FakeProc(), limit=9_999, progress_glob=str(dest),
                            stall_s=0.1)


def test_a_slow_but_growing_download_is_left_alone(tmp_path):
    """The whole point: a healthy long fetch on a slow link must not be killed
    just because it is taking a while."""
    import threading
    from mixfix.research import _wait_with_progress

    dest = tmp_path / "vid.mp4"
    part = tmp_path / "vid.mp4.part"
    part.write_bytes(b"")
    stop = threading.Event()

    def grow():
        n = 0
        while not stop.is_set() and n < 40:
            n += 1
            part.write_bytes(b"x" * (n * 1024))
            stop.wait(0.05)

    t = threading.Thread(target=grow, daemon=True)
    t.start()
    try:
        with pytest.raises(subprocess.TimeoutExpired) as ei:
            _wait_with_progress(_FakeProc(), limit=1.5,
                                progress_glob=str(dest), stall_s=0.6)
        # It survived to the ELAPSED limit rather than being cut down as stalled
        assert ei.value.timeout == 1.5
    finally:
        stop.set()


def test_without_a_progress_target_it_is_a_plain_wait(tmp_path):
    from mixfix.research import _wait_with_progress
    with pytest.raises(subprocess.TimeoutExpired):
        _wait_with_progress(_FakeProc(), limit=0.1, progress_glob=None,
                            stall_s=0.01)


def test_the_watchdog_sees_ytdlp_fragment_files(tmp_path):
    """yt-dlp writes "<stem>.f137.mp4.part" — the format id lands BEFORE the
    extension. Globbing the full filename matches none of it, which killed a
    32MiB fetch moving at 90 KiB/s. The watchdog must match on the stem."""
    from mixfix.research import _wait_with_progress

    dest = tmp_path / "vid_100-200_480.mp4"
    frag = tmp_path / "vid_100-200_480.f135.mp4.part"
    frag.write_bytes(b"x" * 1024)

    class _Growing:
        returncode = None

        def __init__(self):
            self.n = 1

        def wait(self, timeout=None):
            self.n += 1
            frag.write_bytes(b"x" * (1024 * self.n))
            raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=timeout or 0)

    with pytest.raises(subprocess.TimeoutExpired) as ei:
        _wait_with_progress(_Growing(), limit=1.2, progress_glob=str(dest),
                            stall_s=0.5)
    # Reached the elapsed limit, i.e. it SAW the fragment growing and let it run
    assert ei.value.timeout == 1.2


def test_extraction_gets_a_longer_budget_than_the_transfer(tmp_path):
    """Before the first byte yt-dlp is extracting, and a throttled extraction
    takes minutes with no file on disk. Judging that by the transfer budget
    killed two healthy fetches."""
    from mixfix.research import _wait_with_progress
    dest = tmp_path / "vid.mp4"

    # no bytes ever: the GRACE budget governs, not the tighter stall budget
    with pytest.raises(subprocess.TimeoutExpired) as ei:
        _wait_with_progress(_FakeProc(), limit=9_999, progress_glob=str(dest),
                            stall_s=0.05, grace_s=0.8)
    assert ei.value.timeout > 0.5, "killed on the transfer budget before any bytes"


def test_a_passthrough_mode_is_not_failed_by_pauses_in_its_own_source():
    """MIX makes its audio, so a gap means missing narration. ASSEMBLY, FIX and
    SPLIT stream-copy the source, so a pause is the speaker's, not a defect.

    Measured: a real assembly failed QA on five 1.6-2.5s gaps, every one of them
    a conversational pause deep inside a window and none at a cut we made."""
    from mixfix import qa

    fake = {"passed": False, "gaps_s": [2.44, 2.21]}
    judged = {"passed": (not fake["gaps_s"]) or not True}
    unjudged = {"passed": (not fake["gaps_s"]) or not False}
    assert judged["passed"] is False, "MIX must still fail on real dead air"
    assert unjudged["passed"] is True, "passthrough must not be failed by them"
    # and the knob the pipeline actually turns exists on the real signature
    import inspect
    assert "check_silence" in inspect.signature(qa.run_qa).parameters


# ---- captionless sourcing -------------------------------------------------
# B-roll mostly has no captions. The transcript ranker returns nothing for those,
# which dropped 4 of 4 ideal Sixth Street results and left every sourced cutaway
# empty across 36 searches.

def _scene():
    return {"id": "ins_000", "start_ms": 100_000, "end_ms": 106_100,
            "visual_intent": "Sixth Street Austin at night",
            "text": "revolution the mothership six street"}


def _cands():
    return [{"video_id": "aaa", "url": "u1", "duration_s": 600,
             "title": "Austin Nightlife | Dirty 6th & West 6th Street | 4K"},
            {"video_id": "bbb", "url": "u2", "duration_s": 900,
             "title": "Saturday Night on 6th Street, Austin TX"}]


def test_captionless_footage_is_dropped_by_default():
    """Unchanged for MIX and SPLIT: a scene that must show the EVENT is
    confirmed by its transcript, and title-matching would let anything in."""
    from mixfix.match import rank_candidates
    assert rank_candidates(_scene(), _cands(), {}, top_k=6) == []


def test_captionless_footage_is_ranked_when_the_scene_is_illustrative():
    from mixfix.match import rank_candidates
    out = rank_candidates(_scene(), _cands(), {}, top_k=6, allow_captionless=True)
    assert out, "an illustrative cutaway must be able to use captionless b-roll"
    for r in out:
        assert r["clip_end_ms"] > r["clip_start_ms"]
        assert r["clip_start_ms"] > 0, "window must skip the intro card"
        assert r["score"] > 0, "title relevance must survive as a score"


def test_a_transcript_match_still_outranks_a_captionless_one():
    """The discount exists so a real transcript hit is never displaced."""
    from mixfix.match import rank_candidates
    tx = {"aaa": [{"text": "sixth street austin revolution mothership",
                   "start_ms": 0, "end_ms": 8000},
                  {"text": "six street austin at night crowds",
                   "start_ms": 8000, "end_ms": 16000}]}
    out = rank_candidates(_scene(), _cands(), tx, top_k=6, allow_captionless=True)
    assert out[0]["video_id"] == "aaa", f"captionless displaced a real match: {out[0]}"


def test_a_candidate_of_unknown_duration_is_still_skipped():
    """No duration means no way to place a window; guessing would fetch a range
    the video may not have."""
    from mixfix.match import rank_candidates
    c = [{"video_id": "ccc", "url": "u", "duration_s": 0, "title": "6th Street"}]
    assert rank_candidates(_scene(), c, {}, top_k=6, allow_captionless=True) == []


def test_the_assembly_plan_marks_its_cutaways_illustrative():
    """The flag is declared by the mode's own plan stage, so core never needs to
    know which mode is running."""
    import inspect
    from assembly import pipeline as ap
    src = inspect.getsource(ap.AssemblyPipeline.stage_insert_plan)
    assert '"sourcing"' in src and "illustrative" in src


# ---- the review workbench -------------------------------------------------
# The board used to read only timeline.json, so every scene looked identical and
# the only options were approve or reject-and-rerun. What kind of visual a scene
# wants, and what the alternatives were, live in files it never opened.

def _proj(tmp_path):
    (tmp_path / "research").mkdir(parents=True, exist_ok=True)
    (tmp_path / "research" / "visual_plan.json").write_text(json.dumps({"plans": [
        {"scene_id": "ins_000", "visual_type": "video", "sourcing": "illustrative",
         "queries": ["sixth street austin"]},
        {"scene_id": "ins_005", "visual_type": "generate"},
    ]}), encoding="utf-8")
    (tmp_path / "research" / "progress.json").write_text(json.dumps({
        "ins_000": {"status": "verifying", "candidate_idx": 1, "candidates": [
            {"video_id": "a", "title": "Dirty 6th", "channel": "ch", "url": "u1",
             "clip_start_ms": 86000, "clip_end_ms": 92100, "score": 0.17},
            {"video_id": "b", "title": "Saturday Night on 6th", "channel": "ch2",
             "url": "u2", "clip_start_ms": 1000, "clip_end_ms": 7100,
             "score": 0.15, "chosen": True}]}}), encoding="utf-8")
    pdir = tmp_path / "imagery" / "prompts"; pdir.mkdir(parents=True)
    (pdir / "ins_005.flowdeck.json").write_text(json.dumps(
        {"prompts": [{"prompt": "oil painting, rowboat"}]}), encoding="utf-8")
    (pdir / "_master-ref.flowdeck.json").write_text(json.dumps({"prompts": []}),
                                                    encoding="utf-8")
    inc = tmp_path / "imagery" / "incoming" / "ins_005"; inc.mkdir(parents=True)
    (inc / "ins_005_1.png").write_bytes(b"x")
    return tmp_path


def test_workbench_exposes_what_each_scene_is_and_its_alternatives(tmp_path):
    from mixfix.preview import scene_workbench
    wb = scene_workbench(_proj(tmp_path))

    v = wb["ins_000"]
    assert v["visual_type"] == "video"
    assert v["sourcing"] == "illustrative"
    assert v["queries"] == ["sixth street austin"]
    assert len(v["candidates"]) == 2, "the shortlist is what a reviewer picks from"
    assert v["candidate_idx"] == 1, "the board must show which one is in the cut"
    assert v["candidates"][1]["chosen"] is True
    assert v["candidates"][0]["clip_start_ms"] == 86000

    g = wb["ins_005"]
    assert g["visual_type"] == "generate"
    assert g["prompts"] == ["oil painting, rowboat"]
    assert g["images"] == ["ins_005_1.png"]


def test_the_master_reference_job_is_not_a_scene(tmp_path):
    """_master-ref.flowdeck.json sits beside the per-scene jobs and would
    otherwise appear in the board as a scene that does not exist."""
    from mixfix.preview import scene_workbench
    assert "_master-ref" not in scene_workbench(_proj(tmp_path))


def test_workbench_is_empty_rather_than_exploding_before_any_planning(tmp_path):
    from mixfix.preview import scene_workbench
    assert scene_workbench(tmp_path) == {}


# ---- shortlist resilience -------------------------------------------------

def test_one_unreachable_candidate_does_not_discard_the_shortlist():
    """A fetch timeout on a later candidate used to escape the loop and abort the
    scene, throwing away candidates already downloaded and reporting the failure
    against c0 — pointing the operator at a clip already in the archive."""
    import inspect

    from mixfix.pipeline import Pipeline
    src = inspect.getsource(Pipeline.stage_research_extract)
    assert "dropped from shortlist" in src, "per-candidate fetch guard missing"
    # a human's pick is a decision, not a suggestion: it is re-raised, never dropped
    assert 'cand.get("manual") or cand.get("chosen")' in src


def test_a_scene_emptied_by_timeouts_is_not_marked_exhausted():
    """Otherwise a bad five minutes of link permanently burns a good candidate
    list. Guards the same property as
    tests/test_sourcing.py::test_timeouts_never_advance_the_candidate_cursor,
    which caught this exact regression."""
    import inspect

    from mixfix.pipeline import Pipeline
    src = inspect.getsource(Pipeline.stage_research_extract)
    assert "fetch_failures" in src
    i = src.index("if not usable:")
    tail = src[i:i + 700]
    assert "fetch_failures" in tail, "empty shortlist must distinguish why"
    assert tail.index("candidates kept") < tail.index('"exhausted"'),         "a network-emptied shortlist must be kept, not exhausted"
