"""Templates: a stage list + parameters, materialised into a runnable run."""
import json

import pytest

from mixfix import templates
from mixfix.pipeline import MIX_STAGES
from mixfix.state import State


def _cfg(tmp_path):
    return State(tmp_path / "t.db"), str(tmp_path)


def test_builtins_track_the_pipeline_constants(tmp_path):
    mix = next(t for t in templates.load_all(tmp_path) if t["name"] == "mix")
    assert [s["name"] for s in mix["stages"]] == MIX_STAGES
    assert mix["mode"] == "mix" and mix["builtin"] is True


def test_create_project_writes_stages_params_and_input(tmp_path):
    st, root = _cfg(tmp_path)
    tpl = {"name": "custom", "mode": "mix",
           "stages": [{"name": "intake"},
                      {"name": "assemble", "params": {"render": {"fps": 60}}}],
           "inputs": [{"key": "topic", "label": "Topic",
                       "path": "input/topic.json", "field": "topic"}]}

    r = templates.create_project(root, "projects", st, tpl, "demo",
                                 {"topic": "bronze gears"}, "operator")

    assert [s["stage_name"] for s in st.stages(r["run_id"])] == ["intake", "assemble"]
    assert st.get_params(r["run_id"], "assemble") == {"render": {"fps": 60}}
    assert st.get_run(r["run_id"])["template"] == "custom"
    topic = tmp_path / "projects" / "demo" / "input" / "topic.json"
    assert json.loads(topic.read_text()) == {"topic": "bronze gears"}
    assert "--project demo" in r["command"]


def test_template_run_keeps_its_stage_list_on_resume(tmp_path):
    """The reason runs.template exists: ensure_stages must not back-fill."""
    st, root = _cfg(tmp_path)
    tpl = {"name": "short", "mode": "mix",
           "stages": [{"name": "intake"}, {"name": "export"}], "inputs": []}
    r = templates.create_project(root, "projects", st, tpl, "demo", {}, "operator")

    st.ensure_stages(r["run_id"], MIX_STAGES)   # what `mixfix run` does on resume

    assert [s["stage_name"] for s in st.stages(r["run_id"])] == ["intake", "export"]


def test_ensure_stages_still_backfills_a_normal_run(tmp_path):
    st, _ = _cfg(tmp_path)
    run_id = st.create_run("p", "mix", "operator", None, ["intake"])
    st.ensure_stages(run_id, ["intake", "export"])
    assert [s["stage_name"] for s in st.stages(run_id)] == ["intake", "export"]


@pytest.mark.parametrize("name", ["../escape", "a/b", "", ".hidden", "x" * 65])
def test_project_names_that_could_escape_the_projects_dir_are_refused(tmp_path, name):
    st, root = _cfg(tmp_path)
    tpl = {"name": "mix", "mode": "mix", "stages": [{"name": "intake"}], "inputs": []}
    with pytest.raises(ValueError):
        templates.create_project(root, "projects", st, tpl, name, {}, "operator")


def test_existing_user_input_is_never_overwritten(tmp_path):
    proj = tmp_path / "p"
    (proj / "input").mkdir(parents=True)
    mine = proj / "input" / "source.txt"
    mine.write_text("https://youtu.be/mine", encoding="utf-8")
    tpl = {"inputs": [{"key": "source", "label": "s", "path": "input/source.txt"}]}

    skipped = templates.write_inputs(proj, tpl, {"source": "https://youtu.be/theirs"})

    assert skipped == ["input/source.txt"]
    assert mine.read_text() == "https://youtu.be/mine"


def test_creating_over_an_open_run_is_refused(tmp_path):
    st, root = _cfg(tmp_path)
    tpl = {"name": "mix", "mode": "mix", "stages": [{"name": "intake"}], "inputs": []}
    templates.create_project(root, "projects", st, tpl, "demo", {}, "operator")
    with pytest.raises(ValueError, match="open run"):
        templates.create_project(root, "projects", st, tpl, "demo", {}, "operator")


def test_save_from_run_round_trips_through_the_loader(tmp_path):
    st, root = _cfg(tmp_path)
    run_id = st.create_run("proj", "mix", "operator", None, ["intake", "assemble"])
    st.set_params(run_id, "assemble", {"render": {"transition_s": 0.9}})

    templates.save_from_run(root, st, run_id, "my_look", "My look")
    loaded = templates.get(root, "my_look")

    assert loaded["title"] == "My look" and loaded["builtin"] is False
    assert loaded["stages"] == [{"name": "intake"},
                                {"name": "assemble",
                                 "params": {"render": {"transition_s": 0.9}}}]


def test_a_broken_template_file_does_not_hide_the_others(tmp_path):
    d = templates.templates_dir(tmp_path)
    d.mkdir()
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    names = {t["name"] for t in templates.load_all(tmp_path)}
    assert {"mix", "fix", "broken"} <= names
