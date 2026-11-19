"""ASSEMBLY's own tests. The plan contract is where this format lives or dies —
a bad window selection is not a crash, it is a video nobody watches — so most
of these guard the schema.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import assembly  # noqa: F401 — importing registers the mode
from assembly.pipeline import ASSEMBLY_STAGES, AssemblyPipeline
from assembly.schema import validate_assembly_plan, validate_insert_plan
from mixfix import modes
from mixfix.ai.schemas import SchemaError


def _ctx(n: int = 40, seg_ms: int = 30_000) -> dict:
    """n caption lines, seg_ms each, back to back."""
    ids = [f"seg_{i:04d}" for i in range(n)]
    return {
        "segment_bounds": {s: [i * seg_ms, (i + 1) * seg_ms]
                           for i, s in enumerate(ids)},
        "segment_order": {s: i for i, s in enumerate(ids)},
        "min_window_ms": 45_000,
        "min_total_ms": 15 * 60_000,
        "max_total_ms": 25 * 60_000,
        "hook_min_ms": 8_000,
        "hook_max_ms": 35_000,
        "hook_min_depth_ms": 120_000,
    }


def _plan(*groups: list[str], title: str = "Teddy Roosevelt: The Wildest President",
          hook: list[str] | None = None) -> dict:
    """A valid plan. Default hook is one 30s line 5 minutes into the body —
    inside the first window, past the depth floor, inside the length band."""
    return {"title": title,
            "hook": {"segment_ids": hook if hook is not None else ["seg_0010"],
                     "why": "names a number and a stake, lands with no setup"},
            "windows": [{"id": f"win_{i:03d}", "segment_ids": g,
                         "why": "pays off the promise"}
                        for i, g in enumerate(groups)]}


def _ids(lo: int, hi: int) -> list[str]:
    return [f"seg_{i:04d}" for i in range(lo, hi)]


# ---- registration ---------------------------------------------------------

def test_mode_registers_itself_into_the_core():
    assert modes.stages_for("assembly") == ASSEMBLY_STAGES
    assert modes.RENDERERS["assembly"] is not None
    assert modes.cli_for("assembly") == "python -m assembly"


def test_core_holds_no_assembly_specific_code():
    """The whole point of the registry: mixfix/ must not know this mode exists."""
    from pathlib import Path
    core = Path(__file__).resolve().parents[2] / "mixfix"
    hits = [p.name for p in core.rglob("*.py")
            if "assembly" in p.read_text(encoding="utf-8").lower()
            # `assembly/` is also the name of the render working directory that
            # every mode writes into, so those references are not mode leakage.
            and "assembly_plan" in p.read_text(encoding="utf-8").lower()]
    assert hits == [], f"assembly-specific code leaked into core: {hits}"


# ---- the plan contract ----------------------------------------------------

def test_accepts_a_well_formed_plan():
    validate_assembly_plan(_plan(_ids(0, 20), _ids(22, 40)), _ctx())


def test_rejects_a_missing_or_empty_title():
    with pytest.raises(SchemaError):
        validate_assembly_plan(_plan(_ids(0, 40), title="   "), _ctx())


def test_rejects_non_consecutive_segments_in_one_window():
    """A window is one continuous stretch. Scattered ids would splice
    half-sentences from minutes apart and jump-cut the audio mid-breath."""
    scattered = _ids(0, 10) + _ids(20, 32)
    with pytest.raises(SchemaError, match="consecutive"):
        validate_assembly_plan(_plan(scattered), _ctx())


def test_rejects_a_segment_used_by_two_windows():
    with pytest.raises(SchemaError, match="more than one window"):
        validate_assembly_plan(_plan(_ids(0, 20), _ids(19, 40)), _ctx())


def test_rejects_a_window_below_the_minimum():
    """45s floor: one caption line is a soundbite, not a segment."""
    with pytest.raises(SchemaError, match="shorter than"):
        validate_assembly_plan(_plan(_ids(0, 30), _ids(31, 32)), _ctx())


def test_rejects_a_runtime_outside_the_published_band():
    """Rejected BEFORE anything is downloaded — that is the point of checking
    the band in the schema rather than after extraction."""
    with pytest.raises(SchemaError, match="outside the"):
        validate_assembly_plan(_plan(_ids(0, 4)), _ctx())      # 2 min
    with pytest.raises(SchemaError, match="outside the"):
        validate_assembly_plan(_plan(_ids(0, 80)), _ctx(n=80))  # 40 min


def test_rejects_an_unknown_segment_id():
    with pytest.raises(SchemaError, match="unknown segment"):
        validate_assembly_plan(_plan(_ids(0, 20) + ["seg_9999"]), _ctx())


def test_rejects_duplicate_window_ids():
    plan = _plan(_ids(0, 20), _ids(22, 40))
    plan["windows"][1]["id"] = plan["windows"][0]["id"]
    with pytest.raises(SchemaError, match="duplicate window id"):
        validate_assembly_plan(plan, _ctx())


# ---- the hook -------------------------------------------------------------
# The hook is lifted to the front and plays twice. Everything here guards the
# ways that goes wrong: promising material the video does not contain, or
# replaying so soon it reads as a stutter.

def test_accepts_a_valid_hook():
    validate_assembly_plan(_plan(_ids(0, 20), _ids(22, 40)), _ctx())


def test_rejects_a_missing_hook():
    plan = _plan(_ids(0, 20), _ids(22, 40))
    del plan["hook"]
    with pytest.raises(SchemaError, match="hook is required"):
        validate_assembly_plan(plan, _ctx())


def test_rejects_a_hook_outside_every_selected_window():
    """seg_0020 and seg_0021 are the gap between the two windows — material
    that was cut. A teaser from there promises something never delivered."""
    with pytest.raises(SchemaError, match="inside ONE selected window"):
        validate_assembly_plan(
            _plan(_ids(0, 20), _ids(22, 40), hook=["seg_0020"]), _ctx())


def test_rejects_a_hook_too_near_the_start():
    """seg_0001 is 30s into the body, under the 120s floor — it would replay
    within a minute of itself."""
    with pytest.raises(SchemaError, match="into the body"):
        validate_assembly_plan(
            _plan(_ids(0, 20), _ids(22, 40), hook=["seg_0001"]), _ctx())


def test_rejects_a_hook_outside_the_length_band():
    # three 30s lines = 90s: no longer a teaser, the video starts twice
    with pytest.raises(SchemaError, match="outside the"):
        validate_assembly_plan(
            _plan(_ids(0, 20), _ids(22, 40),
                  hook=["seg_0010", "seg_0011", "seg_0012"]), _ctx())


def test_rejects_a_spliced_hook():
    with pytest.raises(SchemaError, match="consecutive"):
        validate_assembly_plan(
            _plan(_ids(0, 20), _ids(22, 40), hook=["seg_0005", "seg_0015"]),
            _ctx())


def test_hook_host_window_is_resolvable_for_the_cut():
    """cut.py lifts the hook out of whichever window contains it."""
    from assembly.cut import hook_source
    plan = {"hook": {"source_start_ms": 300_000, "source_end_ms": 330_000},
            "windows": [{"id": "win_000", "source_start_ms": 0,
                         "source_end_ms": 600_000},
                        {"id": "win_001", "source_start_ms": 660_000,
                         "source_end_ms": 1_200_000}]}
    assert hook_source(plan)["id"] == "win_000"

    plan["hook"] = {"source_start_ms": 610_000, "source_end_ms": 640_000}
    with pytest.raises(ValueError, match="not inside any selected window"):
        hook_source(plan)


# ---- state ----------------------------------------------------------------

def test_a_new_mode_needs_no_database_migration(tmp_path):
    """The runs.mode CHECK constraint used to reject every mode added after it.
    Nothing should now stand between a registered mode and a run row."""
    from mixfix.state import State
    st = State(tmp_path / "t.db")
    run_id = st.create_run("proj", "assembly", "operator", None, ASSEMBLY_STAGES)
    assert st.latest_run("proj")["mode"] == "assembly"
    # and a mode that does not exist yet is equally fine at the DB layer —
    # the registry is what rejects it, well before this point
    st.create_run("proj2", "some-future-mode", "operator", None, ["a"])


def test_legacy_database_with_the_old_constraint_is_rebuilt(tmp_path):
    """An existing mixfix.db carries the old CHECK. Opening it must drop the
    constraint and preserve the rows, not fail on the first assembly run."""
    import sqlite3

    from mixfix.state import State
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, project TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('mix','fix','split')),
            brain TEXT NOT NULL CHECK (brain IN ('operator','api')),
            input_ref TEXT, status TEXT NOT NULL DEFAULT 'running',
            template TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        INSERT INTO runs VALUES
            ('run_old','proj','mix','operator',NULL,'done',NULL,1.0,1.0);
    """)
    conn.commit()
    conn.close()

    st = State(db)
    kept = st.conn.execute(
        "SELECT run_id, mode FROM runs WHERE run_id='run_old'").fetchone()
    assert tuple(kept) == ("run_old", "mix"), "existing rows must survive"
    st.create_run("proj", "assembly", "operator", None, ASSEMBLY_STAGES)


# ---- config ---------------------------------------------------------------

def test_defaults_and_template_register_without_touching_core_config():
    from mixfix.config import DEFAULTS
    from mixfix.templates import builtins
    assert DEFAULTS["assembly"]["min_window_s"] == 45
    assert DEFAULTS["assembly"]["min_total_s"] == 15 * 60
    names = [t["name"] for t in builtins()]
    assert "assembly" in names
    tpl = next(t for t in builtins() if t["name"] == "assembly")
    assert [s["name"] for s in tpl["stages"]] == ASSEMBLY_STAGES
    assert json.dumps(tpl)          # template must be serialisable for the UI


# --- section fetch: a stalled attempt is retried, not fatal -------------------
# Guards the fix for the 2026-08-26 stall: a 631s window scaled to a 1,893s
# timeout, and one transient stall failed the whole run. Measured: the same
# window stalled once and pulled 4.46MB in 60s on the next attempt.

def _src(tmp_path, **kw):
    from mixfix.research import Cache, Politeness, YtDlpSource
    from mixfix.state import State
    st = State(tmp_path / "s.db")
    return YtDlpSource(Cache(st), Politeness(min_interval_s=0),
                       archive_dir=tmp_path / "arch", **kw)


def test_a_stalled_section_fails_fast_and_is_not_retried(tmp_path, monkeypatch):
    """A stall must NOT be retried here.

    An earlier version retried up to SECTION_ATTEMPTS on the theory that stalls
    are transient. Against a 631s window that scales to a ~1,895s budget, three
    attempts turned a 31-minute failure into a 95-minute one — while re-asking
    what turned out to be a rate limit, which deepens it. One attempt, then
    surface it so the operator checks link health.
    """
    from mixfix import research
    src = _src(tmp_path)
    calls = []

    def stall(fn, args, timeout=None, progress_glob=None):
        calls.append(timeout)
        raise research.NetworkTimeout("network call timed out after 1895s")

    monkeypatch.setattr(src.polite, "call", stall)
    with pytest.raises(research.NetworkTimeout):
        src.fetch_segment("https://youtu.be/abc123", 60_000, 70_000)
    assert len(calls) == 1, f"a stall must not be retried in place: {calls}"


def test_the_fetch_hands_the_watchdog_its_destination(tmp_path, monkeypatch):
    """Progress is measured on the file being written, so the fetch has to say
    which file that is — without it the watchdog silently degrades to a plain
    elapsed-time wait."""
    from mixfix import research
    src = _src(tmp_path)
    seen = {}

    def capture(fn, args, timeout=None, progress_glob=None):
        seen["glob"] = progress_glob
        raise research.NetworkTimeout("stalled")

    monkeypatch.setattr(src.polite, "call", capture)
    with pytest.raises(research.NetworkTimeout):
        src.fetch_segment("https://youtu.be/abc123", 60_000, 70_000)
    assert seen["glob"] and seen["glob"].endswith(".mp4")


def test_the_ffmpeg_reader_is_given_a_stall_timeout():
    """-rw_timeout is what separates 'stuck' from 'slow'. Without it a hung read
    burns the whole elapsed budget and fails the run; the budget itself cannot be
    tightened without killing healthy long fetches."""
    import inspect

    from mixfix.research import YtDlpSource
    src = inspect.getsource(YtDlpSource.fetch_segment)
    assert "-rw_timeout" in src
    assert "-reconnect 1" in src, "reconnect must survive alongside the timeout"


def test_candidate_search_still_fails_fast_on_a_stall(tmp_path, monkeypatch):
    """Politeness must NOT retry timeouts — search has other candidates and
    retrying in place burned 15 min each. Only fetch_segment retries."""
    from mixfix.research import NetworkTimeout, Politeness
    p = Politeness(min_interval_s=0)
    n = []

    def boom(*a, **k):
        n.append(1)
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=600)

    with pytest.raises(NetworkTimeout):
        p.call(boom)
    assert len(n) == 1, "a timeout must not be retried inside Politeness"


# ---- the cutaway contract -------------------------------------------------
# Sparse on purpose. These guard the two ways it stops being sparse (too many,
# too close together) and the mixed asset types the format depends on.

# 5s lines: one line is a legal cutaway under the 8s cover ceiling, two are not.
def _ictx(n: int = 60, seg_ms: int = 5_000, hook_ms: int = 20_000) -> dict:
    ids = [f"seg_{i:04d}" for i in range(n)]
    return {
        "segment_bounds": {s: [i * seg_ms, (i + 1) * seg_ms]
                           for i, s in enumerate(ids)},
        "min_inserts": 4, "max_inserts": 10,
        "max_cover_ms": 8_000, "min_gap_ms": 2_000, "hook_ms": hook_ms,
    }


def _ins(*specs, style_lock: str | None = None) -> dict:
    """specs: (segment_id, visual_type) pairs."""
    scenes = []
    for i, (sid, vt) in enumerate(specs):
        sc = {"id": f"ins_{i:03d}", "segment_ids": [sid],
              "visual_intent": "the thing being named appears", "visual_type": vt}
        if vt == "video":
            sc["queries"] = ["the actual subject 1976 footage"]
            sc["moment"] = "action"
        elif vt == "image":
            sc["image_prompt"] = "a period photograph of the man described"
        else:
            lo = _ictx()["segment_bounds"][sid][0]
            sc["segments"] = [{"start_ms": lo, "delta": "wide shot, slow push in"}]
        scenes.append(sc)
    out = {"scenes": scenes}
    if style_lock:
        out["style_lock"] = style_lock
    return out


def _four(vt: str = "video"):
    return _ins(("seg_0010", vt), ("seg_0020", vt), ("seg_0030", vt),
                ("seg_0040", vt))


def test_accepts_a_sparse_mixed_type_plan():
    plan = _ins(("seg_0010", "video"), ("seg_0020", "generate"),
                ("seg_0030", "video"), ("seg_0040", "generate"))
    plan["style_lock"] = "S" * 60
    validate_insert_plan(plan, _ictx())


def test_rejects_too_many_cutaways():
    """The format is sparse; a cutaway every few seconds is a different show."""
    many = _ins(*[(f"seg_{i:04d}", "video") for i in range(5, 5 + 11)])
    with pytest.raises(SchemaError, match="outside the 4-10 band"):
        validate_insert_plan(many, _ictx())


def test_rejects_too_few_cutaways():
    with pytest.raises(SchemaError, match="outside the 4-10 band"):
        validate_insert_plan(_ins(("seg_0010", "video")), _ictx())


def test_rejects_a_cutaway_inside_the_hook():
    """The cold open plays raw — production on top softens the jolt."""
    plan = _ins(("seg_0000", "video"), ("seg_0020", "video"),
                ("seg_0030", "video"), ("seg_0040", "video"))
    with pytest.raises(SchemaError, match="inside the .* hook"):
        validate_insert_plan(plan, _ictx())


def test_rejects_cutaways_that_never_let_the_speaker_back():
    plan = _ins(("seg_0010", "video"), ("seg_0011", "video"),
                ("seg_0030", "video"), ("seg_0040", "video"))
    with pytest.raises(SchemaError, match="apart, under"):
        validate_insert_plan(plan, _ictx())


def test_rejects_a_cutaway_longer_than_the_cover_ceiling():
    plan = _four()
    plan["scenes"][0]["segment_ids"] = ["seg_0010", "seg_0011"]  # 10s > 8s
    with pytest.raises(SchemaError, match="over the"):
        validate_insert_plan(plan, _ictx())


def test_rejects_an_unknown_visual_type():
    plan = _four()
    plan["scenes"][0]["visual_type"] = "montage"
    with pytest.raises(SchemaError, match="visual_type must be"):
        validate_insert_plan(plan, _ictx())


def test_each_visual_type_must_carry_its_own_keys():
    for vt, missing, pattern in [("video", "queries", "queries list"),
                                 ("generate", "segments", "segments list")]:
        plan = _four(vt)
        if vt == "generate":
            plan["style_lock"] = "S" * 60
        del plan["scenes"][0][missing]
        with pytest.raises(SchemaError, match=pattern):
            validate_insert_plan(plan, _ictx())


def test_generated_cutaways_require_a_style_lock():
    """Without it the generated shots drift apart visually across one video."""
    plan = _four("generate")
    with pytest.raises(SchemaError, match="style_lock is required"):
        validate_insert_plan(plan, _ictx())


def test_sourced_only_plans_need_no_style_lock():
    validate_insert_plan(_four("video"), _ictx())


def test_sourced_cutaways_are_capped_by_the_budget():
    """Sourcing is the slow, throttle-prone half: every video cutaway is a
    search plus a range-fetch. The plan may be dense, but only a few of them
    may come off the network — the rest must be generated."""
    ctx = {**_ictx(), "max_sourced": 2}
    # 4 sourced is over a budget of 2
    over = _ins(("seg_0006", "video"), ("seg_0008", "video"),
                ("seg_0010", "video"), ("seg_0012", "video"))
    with pytest.raises(SchemaError, match="sourced"):
        validate_insert_plan(over, ctx)
    # same count, but only 2 sourced and the rest generated — accepted
    ok = _ins(("seg_0006", "video"), ("seg_0008", "video"),
              ("seg_0010", "generate"), ("seg_0012", "generate"))
    ok["style_lock"] = "S" * 70
    validate_insert_plan(ok, ctx)


def test_a_sourced_cutaway_may_run_longer_than_a_generated_one():
    """Few-but-longer: real footage needs room to read, so a sourced clip gets a
    longer ceiling. A generated still held that long is dead air, so it keeps
    the tight one."""
    ctx = {**_ictx(), "min_inserts": 1, "max_inserts": 10,
           "max_sourced": 4, "sourced_max_ms": 20_000}
    # three 5s segments = 15s: fine for video, over the 8s cap for a still
    long_video = _ins(("seg_0006", "video"))
    long_video["scenes"][0]["segment_ids"] = ["seg_0006", "seg_0007", "seg_0008"]
    validate_insert_plan(long_video, ctx)

    long_gen = _ins(("seg_0006", "generate"), style_lock="S" * 70)
    long_gen["scenes"][0]["segment_ids"] = ["seg_0006", "seg_0007", "seg_0008"]
    with pytest.raises(SchemaError, match="ceiling"):
        validate_insert_plan(long_gen, ctx)


def test_image_visual_type_is_rejected_because_it_renders_nothing():
    """'image' is MIX legacy: assembly's generate_visuals only builds montages
    for 'generate', so an image cutaway used to validate, plan, and then render
    NOTHING — it silently cost a real video 5 of its 13 cutaways. A one-shot
    still is a 'generate' with a single segment."""
    ctx = {**_ictx(), "min_inserts": 1, "max_inserts": 10, "max_sourced": 4}
    bad = _ins(("seg_0006", "image"))
    with pytest.raises(SchemaError, match="legacy"):
        validate_insert_plan(bad, ctx)
    # the supported one-shot still: a single-segment generate
    ok = _ins(("seg_0006", "generate"), style_lock="x" * 70)
    validate_insert_plan(ok, ctx)
