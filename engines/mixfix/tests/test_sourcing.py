"""Sourcing doctrine (SOURCING.md): the relevance ladder, the shortlist schema,
and that a scene settles in ONE round instead of one candidate per run."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix.ai.schemas import SchemaError, validate_select_clip
from mixfix.pipeline import SHORTLIST_SIZE

CTX = {"shortlist_size": 3}


def _v(**kw):
    base = {"choice": 0, "tier": "subject", "confidence": 80, "reason": "r"}
    base.update(kw)
    return base


@pytest.mark.parametrize("tier", ["exact", "subject", "topic"])
def test_acceptable_tiers_pass(tier):
    """'subject' and 'topic' are not consolation prizes — they are what editors
    cut with most of the time."""
    validate_select_clip(_v(tier=tier), CTX)


@pytest.mark.parametrize("tier", ["generic", "wrong"])
def test_reject_tiers_cannot_be_chosen(tier):
    """Choosing a clip you just called generic or wrong is contradictory —
    the engine must not ingest it."""
    with pytest.raises(SchemaError, match="reject tier"):
        validate_select_clip(_v(tier=tier), CTX)


def test_unknown_tier_rejected():
    with pytest.raises(SchemaError, match="tier must be one of"):
        validate_select_clip(_v(tier="pretty_good"), CTX)


def test_choice_null_needs_no_tier():
    validate_select_clip({"choice": None, "reason": "all filmed off a TV"}, CTX)


def test_choice_out_of_range_rejected():
    with pytest.raises(SchemaError, match="choice must be"):
        validate_select_clip(_v(choice=3), CTX)


def test_reason_is_required():
    with pytest.raises(SchemaError, match="reason"):
        validate_select_clip({"choice": None}, CTX)


def test_caution_is_optional_and_may_be_null():
    """The autonomous safety valve: a judge may flag a doubt the low-res tile
    cannot resolve. Absent or null is the clean-frame default."""
    validate_select_clip(_v(caution="possible lower-third, confirm on the clip"), CTX)
    validate_select_clip(_v(caution=None), CTX)
    validate_select_clip(_v(), CTX)          # absent entirely


def test_caution_when_present_must_say_something():
    with pytest.raises(SchemaError, match="caution"):
        validate_select_clip(_v(caution="   "), CTX)


def _pipeline(tmp_path):
    from tests.test_phase6 import _research_pipeline
    return _research_pipeline(tmp_path)


def test_scene_settles_in_one_round_from_a_shortlist(tmp_path):
    """The bottleneck this replaces: one candidate per run meant N rounds per
    scene. The shortlist is judged in a single task."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _answer, _research_pipeline

    pipe, state = _research_pipeline(tmp_path)
    prog = tmp_path / "proj" / "research" / "progress.json"

    assert pipe.stage_research_extract() == "paused"
    open_tasks = state.all_pending_ai_tasks()
    assert len(open_tasks) == 1, "one shortlist task, not one task per candidate"
    req = json.loads(
        (Path(open_tasks[0]["request_dir"]) / "request.json").read_text(encoding="utf-8"))
    assert req["task_type"] == "select_clip"
    shortlist = req["payload"]["shortlist"]
    assert 1 <= len(shortlist) <= SHORTLIST_SIZE
    # frames are namespaced per candidate so the judge can tell them apart
    names = [p.name for p in Path(open_tasks[0]["request_dir"]).glob("c*_frame_*.jpg")]
    assert names, "candidate frames must be attached"
    assert all(n.startswith("c") for n in names)

    _answer(state, 78, choice=0, tier="topic")
    assert pipe.stage_research_extract() == "done"
    st = json.loads(prog.read_text())["scene_001"]
    assert st["status"] == "accepted"
    assert st["accepted"]["tier"] == "topic"
    assert state.all_pending_ai_tasks() == []


def test_rejecting_the_whole_shortlist_exhausts_the_scene(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _answer, _research_pipeline

    pipe, state = _research_pipeline(tmp_path)
    prog = tmp_path / "proj" / "research" / "progress.json"
    assert pipe.stage_research_extract() == "paused"
    _answer(state, 0, choice=None)
    pipe.stage_research_extract()
    assert json.loads(prog.read_text())["scene_001"]["status"] == "exhausted"


def test_accepted_index_is_absolute_so_a_reject_advances(tmp_path):
    """The review board rejects a clip by advancing candidate_idx. If the
    shortlist recorded its own slot number instead of the absolute index, the
    next pass would re-offer the same clip forever."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _answer, _research_pipeline

    pipe, state = _research_pipeline(tmp_path)
    prog = tmp_path / "proj" / "research" / "progress.json"
    assert pipe.stage_research_extract() == "paused"
    _answer(state, 85, choice=1)          # second clip of the shortlist
    assert pipe.stage_research_extract() == "done"
    st = json.loads(prog.read_text())["scene_001"]
    assert st["accepted"]["candidate_idx"] == 1
    assert st["candidate_idx"] == 1, "cursor must sit on the accepted clip"


def test_proven_sources_reads_back_accepted_channels(tmp_path):
    """The learning loop: what worked before is offered to the next plan."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _research_pipeline

    pipe, state = _research_pipeline(tmp_path)
    assert pipe.proven_sources() == []
    state.add_asset("a1", "r1", "research_extract", "clip", "x.mp4",
                    {"channel": "BoxNetSports", "source_title": "T", "tier": "subject"})
    state.add_asset("a2", "r1", "research_extract", "clip", "y.mp4",
                    {"channel": "BoxNetSports", "source_title": "T2", "tier": "topic"})
    got = pipe.proven_sources()
    assert [g["channel"] for g in got] == ["BoxNetSports"], "deduped by channel"
    assert got[0]["tier"] in ("subject", "topic")


def test_manifest_carries_the_relevance_tier(tmp_path):
    """Provenance answers 'was that the real moment or a stand-in?' — so the
    tier has to travel with the cut, not just live in the DB."""
    from mixfix import assemble
    from mixfix.state import State

    state = State(tmp_path / "s.db")
    state.create_run("p", "split", "operator", None, ["research_extract"])
    state.add_asset("a1", state.latest_run("p")["run_id"], "research_extract",
                    "clip", "c.mp4",
                    {"channel": "Ch", "source_url": "u", "source_title": "T",
                     "clip_start_ms": 0, "clip_end_ms": 1000, "tier": "subject"})
    tl = {"project": "p", "total_ms": 1000, "scenes": [
        {"id": "s1", "start_ms": 0, "end_ms": 1000,
         "visual": {"kind": "clip", "asset_id": "a1", "path": "c.mp4",
                    "confidence": 76}}]}
    m = assemble.build_manifest(tl, state)
    assert m["visuals"][0]["tier"] == "subject"


def test_a_timeout_never_burns_a_candidate():
    """A timeout says nothing about the footage — YouTube throttles by request
    RATE, so the same window that times out inside a run downloads fine minutes
    later out-of-band (measured: 300s timeout -> 35-54s via prefetch_clips.py).
    Burning on it shredded candidate lists for a reason no candidate caused.

    Regression guard: this test previously asserted the OPPOSITE ("a lone
    timeout burns its candidate"). It encoded the wrong premise, so it passed
    while real runs drove good scenes to `exhausted` without judging a frame.
    """
    from mixfix.pipeline import burn_candidate
    from mixfix.research import ResearchError

    timeout = ResearchError("network call timed out after 600s")
    offline = ResearchError("getaddrinfo failed")
    unusable = ResearchError("Requested format is not available")

    assert burn_candidate(timeout) is False
    # a real offline signal never burns a candidate either
    assert burn_candidate(offline) is False
    # but a definite failure still counts — otherwise nothing ever advances
    assert burn_candidate(unusable) is True


# ---- archive-first ----

def test_archive_queries_are_optional_but_must_be_strings():
    from split.schema import validate_split_plan

    ctx = {"segment_bounds": {"seg_001": [0, 1000]}}
    scene = {"id": "s1", "segment_ids": ["seg_001"],
             "visual_intent": "i", "queries": ["q"]}
    validate_split_plan({"scenes": [scene]}, ctx)                      # omitted
    validate_split_plan({"archive_queries": [], "scenes": [scene]}, ctx)
    validate_split_plan(
        {"archive_queries": ["Ali vs Foreman full fight"], "scenes": [scene]}, ctx)
    with pytest.raises(SchemaError, match="archive_queries"):
        validate_split_plan({"archive_queries": [""], "scenes": [scene]}, ctx)
    with pytest.raises(SchemaError, match="archive_queries"):
        validate_split_plan({"archive_queries": "a string", "scenes": [scene]}, ctx)


class _RecordingSource:
    """Counts searches so the test can prove the archive is resolved once."""

    def __init__(self):
        self.searches = []

    def search(self, q, n=4):
        self.searches.append(q)
        return [{"video_id": f"vid_{abs(hash(q)) % 1000}", "url": "u",
                 "title": q, "channel": "ch"}]


def test_archive_is_resolved_once_and_cached(tmp_path):
    """One search for the event, reused by every scene and across resumes —
    that is the whole point. Re-searching per scene is the bottleneck."""
    from mixfix.pipeline import Pipeline

    pipe = Pipeline.__new__(Pipeline)
    src = _RecordingSource()
    plan = {"archive_queries": ["Mayweather Ortiz full fight"]}
    progress = {}

    first = pipe.archive_candidates(src, plan, progress, set())
    assert first and len(src.searches) == 1
    assert progress["_archive"]["candidates"] == first, "must persist for resume"

    again = pipe.archive_candidates(src, plan, progress, set())
    assert again == first
    assert len(src.searches) == 1, "cached — no second search"


def test_no_archive_queries_means_no_search(tmp_path):
    from mixfix.pipeline import Pipeline

    pipe = Pipeline.__new__(Pipeline)
    src = _RecordingSource()
    assert pipe.archive_candidates(src, {}, {}, set()) == []
    assert pipe.archive_candidates(src, {"archive_queries": []}, {}, set()) == []
    assert src.searches == [], "no event, no wasted search"


def test_archive_never_returns_the_runs_own_source(tmp_path):
    """The source-video guard has to cover the archive path too."""
    from mixfix.pipeline import Pipeline

    pipe = Pipeline.__new__(Pipeline)
    src = _RecordingSource()
    hits = pipe.archive_candidates(src, {"archive_queries": ["q"]}, {}, set())
    own = {hits[0]["video_id"]}
    assert pipe.archive_candidates(src, {"archive_queries": ["q"]}, {}, own) == []


# Real numbers from the split-archive run: the Boxing Legacy upload is 512s and
# 478.7s (93.5%) was the post-fight window that kept beating the action.
_ARCH = 512


def _w(start_s, dur=_ARCH, vid="a"):
    return {"video_id": vid, "duration_s": str(dur),
            "clip_start_ms": int(start_s * 1000)}


def test_window_fraction_handles_missing_and_bad_durations():
    from mixfix.pipeline import window_fraction

    assert abs(window_fraction(_w(478.7)) - 0.935) < 0.005
    assert window_fraction({"clip_start_ms": 1000}) is None
    assert window_fraction({"clip_start_ms": 1000, "duration_s": "0"}) is None
    assert window_fraction({"clip_start_ms": 1000, "duration_s": "abc"}) is None


# ---- one scoring function, replacing four interacting partition rules ----

def test_dominance_order_is_archive_then_position_then_depth():
    """The weights encode a strict priority, so no combination of weaker signals
    can outrank a stronger one. This is the property four separate partition
    functions could only achieve by getting their call order right."""
    from mixfix.pipeline import candidate_score

    arch = {"arch"}
    # a non-archive clip that is perfect on everything else
    best_non_archive = {"video_id": "other", "duration_s": _ARCH,
                        "clip_start_ms": 1000, "score": 1.0}
    # an archive clip that is bad on everything else
    worst_archive = {"video_id": "arch", "duration_s": _ARCH,
                     "clip_start_ms": 60 * 60 * 1000, "score": 0.0}
    assert (candidate_score(worst_archive, "action", arch)
            > candidate_score(best_non_archive, "action", arch)), \
        "wrong event beats nothing — archive must dominate"

    # within the archive, position beats depth+lexical
    deep_body = {"video_id": "arch", "duration_s": 3427,
                 "clip_start_ms": 2090_000, "score": 0.0}      # 61%, 34.8 min
    shallow_tail = {"video_id": "arch", "duration_s": _ARCH,
                    "clip_start_ms": 478_700, "score": 1.0}    # 93.5%, 8 min
    assert (candidate_score(deep_body, "action", arch)
            > candidate_score(shallow_tail, "action", arch)), \
        "a slow correct window beats a fast wrong one"


def test_how_deep_a_window_sits_no_longer_costs_it_anything():
    """Depth used to be penalised because a deep seek meant a slow, timeout-prone
    download. Windows are range-fetched now and depth is free — measured on one
    upload, 25 minutes in arrived in 36s/1.97MB against 69s/1.84MB for 10 minutes
    in. The penalty must not come back: it would pull every scene toward the
    opening of an upload (titles, intros, sponsor reads) and fight archive-first,
    which exists precisely to cut from the BODY of a long archive."""
    from mixfix.pipeline import candidate_score

    arch = {"arch"}
    deep_body = {"video_id": "arch", "duration_s": 3427,
                 "clip_start_ms": 2090_000, "score": 0.5}
    shallow_body = {"video_id": "arch", "duration_s": _ARCH,
                    "clip_start_ms": 100_000, "score": 0.5}    # 19.5%
    assert (candidate_score(shallow_body, "action", arch)
            == candidate_score(deep_body, "action", arch))


def test_scoring_reproduces_the_measured_scene_001_reordering():
    """End-to-end on the real candidate list that produced the bug: the two
    post-fight windows must fall below the two body windows."""
    from mixfix.pipeline import order_candidates

    arch = {"golden", "legacy"}
    ranked = [
        {"video_id": "legacy", "duration_s": 512, "clip_start_ms": 478_700,
         "score": 0.45, "tag": "93%"},
        {"video_id": "legacy", "duration_s": 512, "clip_start_ms": 495_000,
         "score": 0.44, "tag": "97%"},
        {"video_id": "golden", "duration_s": 3427, "clip_start_ms": 2090_000,
         "score": 0.30, "tag": "61%"},
        {"video_id": "golden", "duration_s": 3427, "clip_start_ms": 2660_000,
         "score": 0.28, "tag": "78%"},
    ]
    out = [c["tag"] for c in order_candidates(ranked, "action", arch)]
    assert out[:2] == ["61%", "78%"], f"body windows must lead, got {out}"
    assert out[2:] == ["93%", "97%"], "tail windows kept, just demoted"


def test_moment_any_and_unknown_duration_never_penalised():
    from mixfix.pipeline import order_candidates, position_score

    body, tail = _w(187), _w(478.7)
    # 'any' ignores position entirely, so the ranker's order survives on ties
    assert position_score(tail, "any") == 1.0
    assert position_score({"clip_start_ms": 1}, "action") == 1.0  # no duration
    ordered = order_candidates([tail, body], "any")
    assert len(ordered) == 2


def test_talking_scenes_score_the_tail_higher():
    from mixfix.pipeline import candidate_score

    body, tail = _w(187), _w(478.7)
    assert candidate_score(tail, "talking") > candidate_score(body, "talking")
    assert candidate_score(body, "action") > candidate_score(tail, "action")


def test_ordering_never_drops_a_candidate():
    from mixfix.pipeline import order_candidates

    ranked = [_w(100), _w(478.7), {"video_id": "x", "clip_start_ms": 5}]
    for moment in ("action", "talking", "any"):
        assert len(order_candidates(ranked, moment, {"a"})) == len(ranked)


# ---- review board v2 ----

def test_timeline_exposes_the_current_source_link(tmp_path):
    """The board must show the link and window of what is playing NOW, not just
    a filename — you cannot judge a clip you cannot open."""
    import json as _json
    from mixfix import timeline as tlmod

    proj = tmp_path / "p"
    (proj / "timing").mkdir(parents=True)
    (proj / "research").mkdir(parents=True)
    tmap = {"version": "1.0",
            "source": {"audio_path": "a.mp3", "duration_ms": 5000,
                       "transcriber": "json", "model": "n/a"},
            "words": [{"text": "hi", "start_ms": 0, "end_ms": 900}],
            "segments": [{"id": "seg_001", "text": "hi.", "start_ms": 0,
                          "end_ms": 900, "word_indices": [0, 0]}],
            "scenes": [{"id": "scene_001", "segment_ids": ["seg_001"],
                        "start_ms": 0, "end_ms": 900, "visual_intent": "x",
                        "assets": [{"asset_id": "a1", "kind": "clip",
                                    "path": str(tmp_path / "c.mp4"),
                                    "confidence": 80}]}],
            "meta": {"project": "p"}}
    (proj / "timing" / "timing_map.json").write_text(_json.dumps(tmap), encoding="utf-8")
    (proj / "research" / "progress.json").write_text(_json.dumps({
        "scene_001": {"status": "accepted", "candidate_idx": 1,
                      "accepted": {"candidate_idx": 1},
                      "candidates": [
                          {"video_id": "a", "url": "https://y/a", "title": "A",
                           "channel": "ChA", "clip_start_ms": 0, "clip_end_ms": 1000},
                          {"video_id": "b", "url": "https://y/b", "title": "B",
                           "channel": "ChB", "clip_start_ms": 5000,
                           "clip_end_ms": 6000, "manual": True}]}}), encoding="utf-8")

    tl = tlmod.build(proj)
    src = tl["scenes"][0]["visual"]["source"]
    assert src["url"] == "https://y/b", "must expose the ACCEPTED candidate's link"
    assert src["title"] == "B" and src["channel"] == "ChB"
    assert (src["clip_start_ms"], src["clip_end_ms"]) == (5000, 6000)
    assert src["manual"] is True, "a hand-picked window must be visible as such"
    # the other candidate stays available as an alternative
    assert [a["candidate_idx"] for a in tl["scenes"][0]["alternatives"]] == [0]


def _mini_project(tmp_path):
    """Smallest project the timeline builder accepts, with one accepted clip."""
    import json as _json
    proj = tmp_path / "p"
    (proj / "timing").mkdir(parents=True)
    (proj / "research").mkdir(parents=True)
    (proj / "timing" / "timing_map.json").write_text(_json.dumps({
        "version": "1.0",
        "source": {"audio_path": "a.mp3", "duration_ms": 5000,
                   "transcriber": "json", "model": "n/a"},
        "words": [{"text": "hi", "start_ms": 0, "end_ms": 900}],
        "segments": [{"id": "seg_001", "text": "hi.", "start_ms": 0,
                      "end_ms": 900, "word_indices": [0, 0]}],
        "scenes": [{"id": "scene_001", "segment_ids": ["seg_001"],
                    "start_ms": 0, "end_ms": 900, "visual_intent": "x",
                    "assets": []}],
        "meta": {"project": "p"}}), encoding="utf-8")
    (proj / "research" / "progress.json").write_text(_json.dumps({
        "scene_001": {"status": "accepted", "candidate_idx": 0,
                      "accepted": {"candidate_idx": 0},
                      "candidates": [{"video_id": "a", "url": "https://y/a",
                                      "title": "A", "channel": "ChA",
                                      "clip_start_ms": 0, "clip_end_ms": 1000,
                                      "score": 0.5}]}}), encoding="utf-8")
    return proj


def test_set_window_appends_a_manual_candidate_and_resources(tmp_path):
    """'Use 1:10–1:15 of that video' is not a trim — it is a window nothing has
    fetched. It must queue a new candidate and send the scene back to research."""
    from mixfix import timeline as tlmod

    proj = _mini_project(tmp_path)
    tl = tlmod.build(proj)
    tlmod.apply_edit(proj, tl, {
        "action": "set_window", "scene_id": "scene_001",
        "url": "https://www.youtube.com/watch?v=J6Zert5VaWk",
        "start_ms": 70_500, "end_ms": 80_000})

    st = json.loads((proj / "research" / "progress.json").read_text())["scene_001"]
    assert st["status"] == "verifying", "must go back to research to be fetched"
    assert "accepted" not in st, "the old acceptance must not survive"
    cand = st["candidates"][-1]
    assert cand["manual"] is True
    assert cand["video_id"] == "J6Zert5VaWk"
    assert (cand["clip_start_ms"], cand["clip_end_ms"]) == (70_500, 80_000)
    assert st["candidate_idx"] == len(st["candidates"]) - 1, \
        "cursor must point at the hand-picked window, not an earlier candidate"


def test_a_manual_window_is_never_reordered_by_the_scorer(tmp_path):
    """A human choice must not be demoted by the machine — even when it scores
    badly on position and depth."""
    from mixfix.pipeline import candidate_score

    manual = {"video_id": "m", "duration_s": 512, "clip_start_ms": 500_000,
              "manual": True}
    # the scorer has no opinion it can act on: manual candidates are placed by
    # candidate_idx, which set_window pins, so ordering never reaches them
    assert candidate_score(manual, "action") >= 0


@pytest.mark.parametrize("bad", [
    {"url": "not-a-link", "start_ms": 0, "end_ms": 1000},
    {"url": "https://www.youtube.com/watch?v=J6Zert5VaWk", "start_ms": 900, "end_ms": 900},
    {"url": "https://www.youtube.com/watch?v=J6Zert5VaWk", "start_ms": -1, "end_ms": 5},
    {"url": "https://www.youtube.com/watch?v=J6Zert5VaWk", "start_ms": "x", "end_ms": 5},
])
def test_set_window_refuses_bad_input(tmp_path, bad):
    from mixfix import timeline as tlmod

    proj = _mini_project(tmp_path)
    tl = tlmod.build(proj)
    with pytest.raises(tlmod.EditError):
        tlmod.apply_edit(proj, tl, dict(bad, action="set_window",
                                        scene_id="scene_001"))
    # a refused edit must leave the scene exactly as it was
    st = json.loads((proj / "research" / "progress.json").read_text())["scene_001"]
    assert st["status"] == "accepted" and len(st["candidates"]) == 1


# ---- segment granularity ----

def _words(spec):
    """spec: list of (text, start_s, end_s)."""
    return [{"text": t, "start_ms": int(a * 1000), "end_ms": int(b * 1000)}
            for t, a, b in spec]


def test_a_run_on_speaker_is_split_into_usable_segments():
    """Measured: a 41s interview came back as ONE 37.7s segment because the
    transcriber punctuated almost nothing. Scenes are built from segments, so
    that is one reference clip for 37 seconds."""
    from mixfix.timing import MAX_SEGMENT_MS, _group_sentences

    # 30 words, no terminal punctuation, 1s each => a single 30s run
    segs = _group_sentences(_words([(f"w{i}", i, i + 0.9) for i in range(30)]))
    assert len(segs) > 1, "a 30s unpunctuated run must not stay one segment"
    for s in segs:
        assert s["end_ms"] - s["start_ms"] <= MAX_SEGMENT_MS, s


def test_splitting_preserves_the_timing_map_invariants():
    """validate() requires each segment's bounds to match its word range, and
    ids to be unique and ordered — a split that breaks this corrupts the map."""
    from mixfix.timing import _group_sentences, validate

    words = _words([(f"w{i}", i * 0.8, i * 0.8 + 0.7) for i in range(40)])
    segs = _group_sentences(words)
    tmap = {"version": "1.0",
            "source": {"audio_path": "a", "duration_ms": 40_000,
                       "transcriber": "json", "model": "n/a"},
            "words": words, "segments": segs, "meta": {}}
    validate(tmap)                      # raises if the invariants broke

    assert [s["id"] for s in segs] == [f"seg_{i:03d}" for i in range(1, len(segs) + 1)]
    # contiguous, non-overlapping, covering every word exactly once
    covered = []
    for s in segs:
        lo, hi = s["word_indices"]
        covered.extend(range(lo, hi + 1))
    assert covered == list(range(len(words))), "word coverage must be exact"


def test_it_splits_at_the_longest_pause():
    """The cut should land where the speaker drew breath, not at the midpoint."""
    from mixfix.timing import _group_sentences

    # a clear 3s gap after w4; everything else is tight
    spec = [(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(5)]
    spec += [(f"w{i}", 5.5 + (i - 5) * 0.5, 5.5 + (i - 5) * 0.5 + 0.4)
             for i in range(5, 30)]
    segs = _group_sentences(_words(spec))
    assert segs[0]["word_indices"][1] == 4, \
        f"first segment should end at the pause, got {segs[0]['word_indices']}"


def test_punctuated_speech_is_left_alone():
    """Short, properly punctuated sentences must not be re-cut."""
    from mixfix.timing import _group_sentences

    words = _words([("Hello", 0, 0.4), ("there.", 0.5, 0.9),
                    ("How", 1.0, 1.3), ("are", 1.4, 1.6), ("you?", 1.7, 2.0)])
    segs = _group_sentences(words)
    assert [s["text"] for s in segs] == ["Hello there.", "How are you?"]


def test_splits_are_balanced_not_fragments():
    """Regression: splitting at the globally largest gap peeled two-word chunks
    off the front — a 37.7s run became 49 segments averaging 0.6s."""
    from mixfix.timing import MAX_SEGMENT_MS, _group_sentences

    # 127 words at ~0.3s each, no punctuation: the measured failure case
    words = _words([(f"w{i}", i * 0.32, i * 0.32 + 0.28) for i in range(127)])
    segs = _group_sentences(words)
    durs = [(s["end_ms"] - s["start_ms"]) / 1000 for s in segs]
    assert all(d <= MAX_SEGMENT_MS / 1000 + 0.01 for d in durs), durs
    assert min(durs) >= 1.5, f"no stub segments allowed, got {min(durs):.2f}s"
    assert len(segs) <= 12, f"{len(segs)} segments for 40s is fragmentation"


def test_a_swap_is_honoured_not_re_auditioned(tmp_path):
    """A reviewer's swap must mark the clip as chosen, so the shortlist offers
    it alone rather than downloading two candidates they already passed over."""
    from mixfix import timeline as tlmod

    proj = _mini_project(tmp_path)
    # give the scene three candidates so a shortlist would normally take three
    prog = proj / "research" / "progress.json"
    st = json.loads(prog.read_text())
    st["scene_001"]["candidates"] += [
        {"video_id": "b", "url": "https://y/b", "title": "B", "channel": "c",
         "clip_start_ms": 0, "clip_end_ms": 1000, "score": 0.4},
        {"video_id": "c", "url": "https://y/c", "title": "C", "channel": "c",
         "clip_start_ms": 0, "clip_end_ms": 1000, "score": 0.3}]
    prog.write_text(json.dumps(st))

    tl = tlmod.build(proj)
    tlmod.apply_edit(proj, tl, {"action": "swap_alternative",
                                "scene_id": "scene_001", "candidate_idx": 1})
    st = json.loads(prog.read_text())["scene_001"]
    assert st["candidate_idx"] == 1
    assert st["candidates"][1]["chosen"] is True
    assert not st["candidates"][0].get("chosen"), "only the picked one is chosen"
    assert not st["candidates"][2].get("chosen")


def test_retries_are_passed_to_ytdlp():
    """Fragment retries are what let a lossy link finish a section; without
    them one dropped fragment fails the whole download."""
    import inspect
    from mixfix.research import YtDlpSource

    src = inspect.getsource(YtDlpSource._ytdlp)
    for flag in ("--retries", "--fragment-retries", "--extractor-retries"):
        assert flag in src, f"{flag} missing from the yt-dlp invocation"


def test_a_manual_candidate_survives_ingest_without_a_score():
    """A hand-picked window never went through the ranker, so it has no lexical
    score. Every consumer must use .get — a KeyError here crashed a whole run
    after the clips had already been downloaded and judged."""
    import inspect
    from mixfix import pipeline, timeline

    for mod in (pipeline, timeline):
        src = inspect.getsource(mod)
        assert '["score"]' not in src.replace('tl["score"]', ''), \
            f"{mod.__name__} indexes candidate['score'] directly"


def test_concat_paths_resolve_from_the_concat_file(tmp_path):
    """Two traps, both hit for real: the demuxer resolves entries against the
    CONCAT FILE's directory (a relative project dir gave
    'assembly/projects/<name>/assembly/...'), and on Windows a drive letter is
    NOT treated as absolute, so 'C:/...' got the same prefix bolted on."""
    import os
    from mixfix.assemble import _write_concat

    seg = tmp_path / "assembly" / "segments"
    seg.mkdir(parents=True)
    pieces = []
    for i in range(2):
        f = seg / f"{i:03d}.mp4"
        f.write_bytes(b"x")
        pieces.append(f)
    concat = tmp_path / "assembly" / "concat.txt"

    for given in (pieces,                                   # absolute
                  [p.relative_to(tmp_path) for p in pieces]):  # relative
        cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            _write_concat(concat, given)
        finally:
            os.chdir(cwd)
        for line in concat.read_text().splitlines():
            entry = line.split("'")[1]
            assert not entry.startswith("/"), entry
            assert ":" not in entry, f"drive letter is not portable here: {entry}"
            # the demuxer will join this to the concat file's directory
            assert (concat.parent / entry).exists(), f"does not resolve: {entry}"


def test_a_fetch_failure_never_discards_a_human_pick(tmp_path, monkeypatch):
    """A stalled download says nothing about the clip. Advancing the cursor past
    a hand-picked window would drop the reviewer's choice for a candidate they
    already passed over — and deep offsets, the picks most likely to stall, are
    exactly the ones a human chooses deliberately."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _research_pipeline

    from mixfix.research import ResearchError

    pipe, state = _research_pipeline(tmp_path)
    prog_path = tmp_path / "proj" / "research" / "progress.json"
    pipe.stage_research_extract()                      # seed candidates
    prog = json.loads(prog_path.read_text(encoding="utf-8"))
    st = prog["scene_001"]
    st["candidates"][0]["manual"] = True
    st["candidate_idx"] = 0
    st["status"] = "verifying"
    prog_path.write_text(json.dumps(prog), encoding="utf-8")

    def stall(*a, **kw):
        raise ResearchError("clipinn download timed out after 600s")

    monkeypatch.setattr(pipe, "_source_video_ids", lambda: set())
    import mixfix.research as research
    monkeypatch.setattr(research.FixtureSource, "extract_section", stall)

    pipe.stage_research_extract()
    after = json.loads(prog_path.read_text(encoding="utf-8"))["scene_001"]
    assert after["candidate_idx"] == 0, "the human's pick must survive a stall"
    assert after["candidates"][0].get("manual") is True




# ---- fetching: range-fetch the window, never the whole upload ----

def _section_source(tmp_path, monkeypatch, calls, pad_s=8.0):
    """A YtDlpSource whose network call is faked but whose logic is real."""
    from mixfix import research

    src = research.YtDlpSource(
        cache=None, politeness=research.Politeness(min_interval_s=0.0),
        archive_dir=tmp_path / "archives", max_height=480, section_pad_s=pad_s)

    def fake_ytdlp(args, timeout=None, progress_glob=None):
        calls.setdefault("ytdlp", []).append(args)
        Path(args[args.index("-o") + 1]).write_bytes(b"z" * 200_000)
        return ""

    monkeypatch.setattr(src, "_ytdlp", fake_ytdlp)
    # The fake payload is not decodable; media integrity is exercised separately.
    monkeypatch.setattr(research, "media_covers",
                        lambda p, required_ms, **kw:
                        p.exists() and p.stat().st_size >= 100_000)
    monkeypatch.setattr(
        research, "cut_section",
        lambda s, o, a, b: (calls.setdefault("cut", []).append((s, o, a, b)), o)[1])
    return src


def test_ytdlp_uses_its_configured_ffmpeg_without_changing_render_path(
        tmp_path, monkeypatch):
    """Range extraction uses its compatible FFmpeg; rendering keeps the Gyan pin."""
    import os
    from mixfix import research

    compatible = tmp_path / "compatible-ffmpeg"
    render = tmp_path / "render-ffmpeg"
    compatible.mkdir()
    render.mkdir()
    initial_path = os.pathsep.join((str(render), str(compatible), "tail"))
    monkeypatch.setenv("PATH", initial_path)
    src = research.YtDlpSource(
        cache=None, politeness=None, archive_dir=tmp_path / "archives",
        ytdlp_ffmpeg_dir=str(compatible))
    seen = {}

    class FinishedProcess:
        returncode = 0

        @staticmethod
        def wait(timeout=None):
            return 0

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return FinishedProcess()

    monkeypatch.setattr(research.subprocess, "Popen", fake_popen)
    src._ytdlp(["--version"])

    assert seen["env"]["PATH"].split(os.pathsep)[0] == str(compatible)
    assert seen["env"]["PATH"].split(os.pathsep)[1:] == [str(render), "tail"]
    assert os.environ["PATH"] == initial_path, "render process PATH must stay untouched"
    assert "--ffmpeg-location" not in seen["cmd"]


def test_only_the_requested_window_is_fetched_never_the_whole_upload(tmp_path, monkeypatch):
    """The core rule: if we need 8 seconds, we do not download 20 minutes.
    The fetch is a --download-sections range covering the window plus the pad,
    and the exact window is then cut at an OFFSET from the segment start —
    because the file begins at the pad, not at the requested moment."""
    calls = {}
    src = _section_source(tmp_path, monkeypatch, calls)

    src.extract_section("https://youtu.be/abcdefghijk", 71000, 79000,
                        tmp_path / "clip.mp4")

    args = calls["ytdlp"][0]
    assert "--download-sections" in args, "the whole upload must never be fetched"
    assert args[args.index("--download-sections") + 1] == "*63.00-87.00", \
        "8s pad either side of a 71-79s window"
    assert calls["cut"][0][2:] == (8000, 16000), \
        "the window is cut at its offset inside the padded segment"


def test_the_pad_lets_a_moved_window_be_served_from_disk(tmp_path, monkeypatch):
    """Why the pad exists. A reviewer nudging a window, or a second scene
    wanting a nearby moment of the same source, must not touch the network."""
    calls = {}
    src = _section_source(tmp_path, monkeypatch, calls)

    src.extract_section("https://youtu.be/abcdefghijk", 71000, 79000, tmp_path / "a.mp4")
    # nudged 3s later, still inside the padded segment — and a share-link URL
    src.extract_section("https://www.youtube.com/watch?v=abcdefghijk?si=xyz",
                        74000, 82000, tmp_path / "b.mp4")

    assert len(calls["ytdlp"]) == 1, "a nudge inside the pad is a local re-cut"
    assert calls["cut"][1][2:] == (11000, 19000), "offset tracks the same segment"


def test_a_window_beyond_the_pad_fetches_its_own_section(tmp_path, monkeypatch):
    """The flip side: the cache is keyed by window, not just by video, so a
    genuinely different moment of the same upload is a new (small) fetch."""
    calls = {}
    src = _section_source(tmp_path, monkeypatch, calls)

    src.extract_section("https://youtu.be/abcdefghijk", 1000, 5000, tmp_path / "a.mp4")
    src.extract_section("https://youtu.be/abcdefghijk", 900000, 905000, tmp_path / "b.mp4")
    assert len(calls["ytdlp"]) == 2


def test_section_format_forces_h264_and_honours_the_quality_floor():
    """THE regression guard for this engine's worst failure mode. yt-dlp's
    default sort picks AV1, and AV1 ignores a --download-sections seek: it
    streams from the start of the file, so a deep window downloads the entire
    upload and never finishes. That is what was once misdiagnosed as
    "range-fetching does not work". ext=mp4 does NOT discriminate — AV1 ships in
    mp4 too — so the codec filter is the fix and must not be dropped.

    Every branch keeps a height cap so the selector can never fall through to an
    audio-only format (yt-dlp merges it and exits 0). The MIN_SOURCE_HEIGHT floor
    sits on the preferred branch only, so a low-res upload still arrives and gets
    judged rather than failing selection with no file to look at."""
    from mixfix.library import MIN_SOURCE_HEIGHT
    from mixfix.research import YtDlpSource

    src = YtDlpSource.__new__(YtDlpSource)
    src.max_height = 480
    branches = src._section_format().split("/")
    assert "avc1" in branches[0]
    assert f"height>={MIN_SOURCE_HEIGHT}" in branches[0]
    assert all("height<=480" in b for b in branches), "the cap applies everywhere"


def test_live_browser_cookies_win_over_an_old_export(tmp_path):
    """Tyson: an exported jar got CDN 403; Firefox fetched the same 20s range."""
    from mixfix.research import YtDlpSource

    cookiefile = tmp_path / "cookies.txt"
    cookiefile.write_text("saved export", encoding="utf-8")
    src = YtDlpSource(cache=None, politeness=None,
                      archive_dir=tmp_path / "archives",
                      cookies_from_browser="firefox")
    assert src.cookie_args == ["--cookies-from-browser", "firefox"]

    fallback = YtDlpSource(cache=None, politeness=None,
                           archive_dir=tmp_path / "archives")
    assert fallback.cookie_args == ["--cookies", str(cookiefile)]

    from mixfix.research import explain_ytdlp_error
    assert "sign-in" in explain_ytdlp_error(
        "[https] HTTP error 403 Forbidden", "firefox")


def test_media_coverage_rejects_early_video_or_dropped_audio(tmp_path):
    """yt-dlp can exit 0 with a real video stream but missing final fragments."""
    from mixfix.research import media_covers
    from mixfix.tools import FFMPEG

    good = tmp_path / "good.mp4"
    bad_audio = tmp_path / "bad-audio.mp4"
    for out, audio_s in ((good, 3), (bad_audio, 1)):
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc2=s=640x360:r=24:d=3", "-f", "lavfi", "-i",
             f"sine=frequency=440:duration={audio_s}", "-c:v", "mpeg4",
             "-c:a", "aac", str(out)], check=True, capture_output=True)

    assert media_covers(good, 2800, require_audio=True)
    assert not media_covers(good, 5000, require_audio=True)
    assert not media_covers(bad_audio, 2800, require_audio=True)


def test_incomplete_cached_section_is_removed_before_retry(tmp_path, monkeypatch):
    """yt-dlp can skip an existing final filename even if the media is short."""
    from mixfix import research

    src = research.YtDlpSource(
        cache=None, politeness=research.Politeness(min_interval_s=0.0),
        archive_dir=tmp_path / "archives", section_pad_s=0.0)
    dest = src.archive_dir / "abcdefghijk_1000-5000_720.mp4"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"short")
    calls = []

    def fake_ytdlp(args, **kw):
        calls.append(1)
        out = Path(args[args.index("-o") + 1])
        if not out.exists():
            out.write_bytes(b"complete")
        return ""

    monkeypatch.setattr(src, "_ytdlp", fake_ytdlp)
    monkeypatch.setattr(research, "media_covers",
                        lambda p, required_ms, **kw:
                        p.exists() and p.read_bytes() == b"complete")
    result, base = src.fetch_segment("https://youtu.be/abcdefghijk", 1000, 5000)
    assert calls == [1]
    assert result == dest and base == 1000
    assert result.read_bytes() == b"complete"


def test_section_fetches_go_through_the_politeness_gate(tmp_path, monkeypatch):
    """YouTube throttles a client that spends requests too fast, and a throttled
    fetch is answered with sleeps that outlast any wall clock. Spacing is the
    only thing that prevents it, so it must not be bypassed."""
    from mixfix import research

    seen = []

    class Spy(research.Politeness):
        def call(self, fn, *a, **kw):
            seen.append(fn)
            return fn(*a, **kw)

    src = research.YtDlpSource(cache=None, politeness=Spy(min_interval_s=0.0),
                               archive_dir=tmp_path / "archives")
    monkeypatch.setattr(src, "_ytdlp", lambda args, timeout=None, progress_glob=None: (
        Path(args[args.index("-o") + 1]).write_bytes(b"z" * 200_000), "")[1])
    monkeypatch.setattr(research, "media_covers", lambda p, required_ms, **kw: True)
    src.fetch_segment("https://youtu.be/abcdefghijk", 1000, 5000)
    assert seen, "the section fetch must be spaced by the politeness gate"


def test_a_section_that_comes_back_without_video_is_retried_then_fails_loudly(
        tmp_path, monkeypatch):
    """When the CDN drops video fragments mid-section, yt-dlp merges what it got
    and exits 0 — an audio-only mp4 that looks like success and breaks frame
    extraction much later. It is transient, so retry; but bounded, or one bad
    window eats the stage's whole budget."""
    from mixfix import research

    src = research.YtDlpSource(
        cache=None, politeness=research.Politeness(min_interval_s=0.0),
        archive_dir=tmp_path / "archives")
    tries = []
    monkeypatch.setattr(src, "_ytdlp", lambda args, timeout=None, progress_glob=None: (
        tries.append(1),
        Path(args[args.index("-o") + 1]).write_bytes(b"z" * 200_000), "")[2])
    monkeypatch.setattr(research, "media_covers",
                        lambda p, required_ms, **kw: False)  # audio-only

    with pytest.raises(research.ResearchError, match="came back incomplete"):
        src.fetch_segment("https://youtu.be/abcdefghijk", 1000, 5000)
    assert len(tries) == research.SECTION_ATTEMPTS, "bounded retries, not endless"


def test_video_id_survives_share_links_and_non_youtube_urls():
    """Picks arrive from the review board as youtu.be/...?si=... share links;
    keying the archive on the raw URL would fetch the same file twice."""
    from mixfix.research import video_id_from

    vid = "dXq8P_37lMg"
    for url in (f"https://www.youtube.com/watch?v={vid}",
                f"https://youtu.be/{vid}?si=RizPDs1Mwvw4XzwI",
                f"https://www.youtube.com/embed/{vid}",
                f"https://www.youtube.com/shorts/{vid}"):
        assert video_id_from(url) == vid, url
    assert video_id_from("https://example.com/x.mp4").startswith("url_")


def test_a_locked_part_file_fails_one_candidate_not_the_whole_stage(tmp_path, monkeypatch):
    """Found by an end-to-end run: a stray yt-dlp (orphaned when its parent was
    killed) still held a .part file, the pre-download purge hit WinError 32,
    and the raw OSError propagated out of research_extract — failing the whole
    stage and discarding every other scene's completed work. It must degrade to
    a single burned candidate."""
    from mixfix import research

    src = research.YtDlpSource(
        cache=None, politeness=research.Politeness(min_interval_s=0.0),
        archive_dir=tmp_path / "archives", section_pad_s=8.0)
    (tmp_path / "archives").mkdir()
    stale = tmp_path / "archives" / "abcdefghijk_0-13000_720.f135.mp4.part"
    stale.write_bytes(b"partial")

    real_unlink = Path.unlink

    def locked(self, *a, **kw):
        if self.name.endswith(".part"):
            raise PermissionError(32, "in use")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(research.ResearchError, match="locked by another download"):
        src.fetch_segment("https://youtu.be/abcdefghijk", 1000, 5000)


# ---- MIX and SPLIT source footage the same way ----

def test_mix_gets_the_same_sourcing_doctrine_as_split():
    """MIX pulls clips through the same research stage, the same ranker and the
    same review board as SPLIT. For a long time only SPLIT was TOLD how to
    source — the engine already read `archive_queries` and `moment`, but MIX's
    planner was never asked for either, so the machinery sat idle for half the
    modes. One doctrine, both prompts."""
    import split  # noqa: F401 — registers split_plan
    from mixfix.ai import sourcing
    from mixfix.ai.tasks import TASK_INSTRUCTIONS

    for task in ("visual_plan", "split_plan"):
        text = TASK_INSTRUCTIONS[task]
        for name in ("ARCHIVE_FIRST", "WRITING_QUERIES", "AIM_FOR_SUPPORT",
                     "MOMENT", "PROVEN_SOURCES"):
            block = getattr(sourcing, name)
            assert block in text, f"{task} is missing {name}"


def test_the_doctrine_has_exactly_one_copy():
    """Two copies drift. The whole point of mixfix/ai/sourcing.py is that the
    text lives once and both prompts reference it."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    needle = "the trap that wastes the most candidates"
    hits = [f.name for pkg in ("mixfix", "split")
            for f in (root / pkg).rglob("*.py")
            if needle in f.read_text(encoding="utf-8")]
    assert hits == ["sourcing.py"], f"doctrine duplicated in {hits}"


def test_visual_plan_takes_archive_queries_and_moment():
    """The MIX-side contract for the fields the engine already consumes."""
    from mixfix.ai.schemas import SchemaError, validate_visual_plan

    ctx = {"scene_ids": {"scene_001"}, "scene_bounds": {"scene_001": [0, 5000]}}
    plan = {"archive_queries": ["apollo 11 full broadcast"],
            "plans": [{"scene_id": "scene_001", "visual_type": "video",
                       "queries": ["apollo 11 launch replay"], "moment": "action"}]}
    validate_visual_plan(plan, ctx)

    plan["plans"][0]["moment"] = "acton"          # a typo must not pass silently
    with pytest.raises(SchemaError, match="moment must be"):
        validate_visual_plan(plan, ctx)

    plan["plans"][0]["moment"] = "action"
    plan["archive_queries"] = "not a list"
    with pytest.raises(SchemaError, match="archive_queries"):
        validate_visual_plan(plan, ctx)


def test_mix_archive_queries_reach_the_archive_resolver(tmp_path):
    """End of the wire: a MIX visual_plan carrying archive_queries must make
    the core resolve that archive once and offer it to every scene."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase6 import _research_pipeline

    pipe, _ = _research_pipeline(tmp_path)
    seen = {}

    class FakeSource:
        def search(self, q, n=4):
            seen.setdefault("queries", []).append(q)
            return [{"video_id": "arch1234567", "url": "u", "title": "t",
                     "channel": "c", "duration_s": 3600}]

    got = pipe.archive_candidates(
        FakeSource(), {"archive_queries": ["the whole event, full broadcast"]},
        {}, exclude_ids=set())
    assert seen["queries"] == ["the whole event, full broadcast"]
    assert [c["video_id"] for c in got] == ["arch1234567"]


def test_timeouts_never_advance_the_candidate_cursor(tmp_path, monkeypatch):
    """A run where every fetch times out must leave every candidate list intact.

    This replaces a test that asserted the opposite (a timeout should burn its
    candidate and advance). That premise was measurably wrong: YouTube throttles
    by request RATE, so the windows a run times out on are fetched fine minutes
    later out-of-band. Burning on timeout walked scenes to `exhausted` without a
    single frame ever being judged — the failure this now guards against.

    One healthy scene is kept in the mix to prove a success still settles
    normally while its neighbours are timing out.
    """
    import json as _json

    from mixfix import research
    from mixfix.research import ResearchError
    from tests.test_phase6 import _research_pipeline

    pipe, _ = _research_pipeline(tmp_path)
    proj = tmp_path / "proj"
    tmap_path = proj / "timing" / "timing_map.json"
    plan_path = proj / "research" / "visual_plan.json"

    n = 5
    tmap = _json.loads(tmap_path.read_text(encoding="utf-8"))
    seg, scene = tmap["segments"][0], tmap["scenes"][0]
    tmap["segments"], tmap["scenes"], plans = [], [], []
    for i in range(1, n + 1):
        sid, gid = f"scene_{i:03d}", f"seg_{i:03d}"
        tmap["segments"].append({**seg, "id": gid,
                                 "start_ms": (i - 1) * 5000, "end_ms": i * 5000})
        tmap["scenes"].append({**scene, "id": sid, "segment_ids": [gid],
                               "start_ms": (i - 1) * 5000, "end_ms": i * 5000})
        plans.append({"scene_id": sid, "visual_type": "video",
                      "queries": ["bronze gears"]})
    tmap_path.write_text(_json.dumps(tmap), encoding="utf-8")
    plan_path.write_text(_json.dumps({"plans": plans}), encoding="utf-8")

    # every scene times out EXCEPT the one right after the streak is reached,
    # whose success must clear the streak for the scenes that follow. This has to
    # be in place for the FIRST pass: candidates are seeded and fetched in the
    # same sweep, so patching afterwards would find every scene already staged.
    healthy = "scene_004"
    real_extract = research.FixtureSource.extract_section

    def flaky(self, url, start_ms, end_ms, out_path):
        if healthy in out_path.name:
            return real_extract(self, url, start_ms, end_ms, out_path)
        raise ResearchError("network call timed out after 300s")

    monkeypatch.setattr(pipe, "_source_video_ids", lambda: set())
    monkeypatch.setattr(research.FixtureSource, "extract_section", flaky)

    pipe.stage_research_extract()

    prog = _json.loads((proj / "research" / "progress.json")
                       .read_text(encoding="utf-8"))
    for i in range(1, n + 1):
        sid = f"scene_{i:03d}"
        if sid == healthy:
            continue
        assert prog[sid]["candidate_idx"] == 0, (
            f"{sid} timed out and must KEEP its candidate — advancing discards "
            "footage that was never judged, for a reason no candidate caused")
        assert prog[sid]["status"] != "exhausted", (
            f"{sid} reached 'exhausted' purely from network timeouts")


def test_every_playable_output_is_faststart():
    """moov must precede mdat in anything the review board plays.

    Regression (2026-08-22): the draft preview was muxed without
    `-movflags +faststart`, so ffmpeg wrote the index at the END of the file —
    measured, moov at byte 25,933,475 of 26,395,914. The board then loaded the
    video fine but scenes would not play, because selecting a scene is a SEEK
    and a seek needs moov. It looked like a broken player; it was the muxer.

    Asserted against the source rather than a rendered file so it holds without
    running ffmpeg in CI.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for rel in ("mixfix/assemble.py", "split/render.py"):
        src = (root / rel).read_text(encoding="utf-8")
        # every ffmpeg invocation that writes render.mp4 / preview.mp4 output
        writes_final = re.findall(r'"assembly"\s*/\s*"(render|preview)\.mp4"', src)
        assert writes_final, f"{rel}: expected a final-output mux to exist"
        assert '"+faststart"' in src, (
            f"{rel} muxes a file the review board plays but never passes "
            "-movflags +faststart; moov lands after mdat and seeking breaks")


# ---- a stalled section is retried only when the link is healthy ----

def _stalling_source(tmp_path, healthy, calls):
    """A source whose section fetch always stalls, with a stubbed health probe."""
    from mixfix import research

    src = research.YtDlpSource(
        cache=None, politeness=research.Politeness(min_interval_s=0.0),
        archive_dir=tmp_path / "archives", section_pad_s=8.0)
    (tmp_path / "archives").mkdir(exist_ok=True)

    def always_stall(*a, **kw):
        calls.append(1)
        raise research.NetworkTimeout("network call timed out after 240s")

    src._ytdlp = always_stall
    src._link_healthy = lambda url, **kw: healthy
    return src


def test_a_stalled_section_is_retried_once_when_the_link_is_healthy(tmp_path):
    """Measured repeatedly: on a healthy link one window stalls at zero bytes
    while the same window, re-asked with fresh URLs, downloads at full speed.
    That is a CDN edge going dark, and failing the run over it throws away
    every window already fetched."""
    from mixfix import research
    calls = []
    src = _stalling_source(tmp_path, healthy=True, calls=calls)
    with pytest.raises(research.NetworkTimeout):
        src.fetch_segment("https://youtu.be/abcdefghijk", 100_000, 130_000)
    assert len(calls) == 2, "healthy link should get exactly one retry, not zero or many"


def test_a_stalled_section_is_not_retried_when_the_link_is_throttled(tmp_path):
    """The opposite failure, and the reason blind retries were removed before:
    re-asking a throttled endpoint turned a 31-minute failure into a 95-minute
    one. The probe is what keeps that from coming back."""
    from mixfix import research
    calls = []
    src = _stalling_source(tmp_path, healthy=False, calls=calls)
    with pytest.raises(research.NetworkTimeout):
        src.fetch_segment("https://youtu.be/abcdefghijk", 100_000, 130_000)
    assert len(calls) == 1, "a throttled link must not be re-asked"
