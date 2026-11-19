"""Node parameters and downstream invalidation.

The graph-shaping tests moved to GRID (node-production-os/tests) with the code.
"""
from pathlib import Path

import pytest

from mixfix.pipeline import STAGE_KNOBS, merge_params
from mixfix.state import State


def _run(tmp_path):
    st = State(tmp_path / "t.db")
    run_id = st.create_run("p", "mix", "operator", None, ["voiceover", "timing_map"])
    st.stage_start(run_id, "voiceover")
    st.stage_finish(run_id, "voiceover", "done", {"ok": True})
    return st, run_id


# ---- node parameters ----

def test_params_overlay_config_without_dropping_siblings(tmp_path):
    cfg = {"render": {"width": 1920, "height": 1080, "fps": 30}, "brain": "operator"}
    merged = merge_params(cfg, {"render": {"fps": 60}})

    assert merged["render"] == {"width": 1920, "height": 1080, "fps": 60}
    assert merged["brain"] == "operator"
    assert cfg["render"]["fps"] == 30  # the caller's config is never mutated


def test_params_round_trip_and_reach_the_graph(tmp_path):
    st, run_id = _run(tmp_path)
    assert st.get_params(run_id, "timing_map") == {}
    st.set_params(run_id, "timing_map", {"whisper_model": "large-v3"})
    assert st.get_params(run_id, "timing_map") == {"whisper_model": "large-v3"}

    st.set_params(run_id, "timing_map", {})   # clearing returns to defaults
    assert st.get_params(run_id, "timing_map") == {}
    # which knobs a node offers is GRID's side of this; see its adapter tests


def test_stage_knobs_only_name_sections_the_config_really_has(tmp_path):
    """A typo here would silently offer a node no parameters at all."""
    from mixfix.config import load_config
    cfg = load_config(Path(__file__).resolve().parents[1])
    for stage, sections in STAGE_KNOBS.items():
        for s in sections:
            assert s in cfg or s == "qa", f"{stage} names a missing section: {s}"


def test_set_params_rejects_an_unknown_stage(tmp_path):
    st, run_id = _run(tmp_path)
    with pytest.raises(KeyError):
        st.set_params(run_id, "not_a_stage", {"x": 1})


# ---- downstream invalidation ----

def test_invalidate_resets_downstream_and_leaves_upstream_alone(tmp_path):
    st = State(tmp_path / "t.db")
    names = ["a", "b", "c"]
    run_id = st.create_run("p", "mix", "operator", None, names)
    for n in names:
        st.stage_start(run_id, n)
        st.stage_finish(run_id, n, "done", {"out": n})
    st.set_run_status(run_id, "done")

    affected = st.invalidate_from(run_id, "b")
    assert affected == ["b", "c"]

    got = {r["stage_name"]: r for r in st.stages(run_id)}
    assert got["a"]["status"] == "done" and got["a"]["output_json"] is not None
    for n in ("b", "c"):
        assert got[n]["status"] == "pending"
        assert got[n]["output_json"] is None and got[n]["finished_at"] is None
        assert got[n]["attempt"] == 1  # history is kept, not reset
    # a done run must reopen or the CLI would start a fresh run instead
    assert st.get_run(run_id)["status"] == "paused"


def test_invalidate_reopens_the_gate_guarding_regenerated_content(tmp_path):
    st = State(tmp_path / "t.db")
    run_id = st.create_run("p", "mix", "operator", None, ["timeline", "export"])
    st.conn.execute("INSERT INTO gates (gate_id, run_id, name, status, created_at,"
                    " decided_at) VALUES ('g1',?,'timeline_approval','approved',0,9)",
                    (run_id,))
    st.conn.commit()

    st.invalidate_from(run_id, "timeline")
    gate = st.conn.execute("SELECT * FROM gates WHERE gate_id='g1'").fetchone()

    # approval was for the OLD timeline; leaving it approved would let
    # unreviewed content walk through a human checkpoint
    assert gate["status"] == "pending"
    assert gate["decided_at"] is None


def test_invalidate_rejects_an_unknown_stage(tmp_path):
    st, run_id = _run(tmp_path)
    with pytest.raises(KeyError):
        st.invalidate_from(run_id, "not_a_stage")


def test_a_saved_param_actually_reaches_the_running_stage(tmp_path):
    """The whole point: edit a node, and the pipeline runs with that value."""
    from mixfix.pipeline import Pipeline

    st = State(tmp_path / "t.db")
    run_id = st.create_run("p", "mix", "operator", None, ["assemble", "export"])
    st.set_params(run_id, "export", {"render": {"fps": 60}})
    cfg = {"root": str(tmp_path), "render": {"fps": 30, "width": 1920}}
    pipe = Pipeline(st, None, cfg, run_id, tmp_path, "mix")

    # run() builds its handler dict from self.stage_* at call time, so swapping
    # the methods here records the config each stage was actually handed
    seen = {}
    for name in ("assemble", "export"):
        setattr(pipe, f"stage_{name}",
                lambda n=name: (seen.update({n: dict(pipe.cfg["render"])}), "done")[1])
    assert pipe.run() == "done"

    assert seen["assemble"] == {"fps": 30, "width": 1920}  # untouched node
    assert seen["export"] == {"fps": 60, "width": 1920}    # override, sibling kept
    assert cfg["render"]["fps"] == 30                      # base config unharmed
