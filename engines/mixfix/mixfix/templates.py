"""Pipeline templates — a named stage list + per-stage parameters + inputs.

A template is what makes a graph reusable: pick one, name the project, fill its
inputs, and you have a run ready for `mixfix run`. The built-in MIX and FIX
templates are derived from the pipeline's own stage constants, so they can never
drift from it; anything saved from a real run lands in `templates/<name>.json`.

Shape:
    {"name": "mix", "title": "...", "mode": "mix",
     "stages": [{"name": "intake"}, {"name": "assemble", "params": {...}}],
     "inputs": [{"key": "topic", "label": "Topic", "path": "input/topic.json",
                 "field": "topic"}]}       # omit "field" to write raw text
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .pipeline import FIX_STAGES, MIX_STAGES
from .state import State

# project names become directory names — never let a request pick the path
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

MIX_INPUTS = [{"key": "topic", "label": "Topic",
               "path": "input/topic.json", "field": "topic",
               "hint": "What the documentary is about."}]
FIX_INPUTS = [{"key": "source", "label": "Source video URL",
               "path": "input/source.txt",
               "hint": "YouTube URL — or drop input/source.mp4 yourself."}]


# Templates contributed by engines outside this package (see split/defaults.py).
EXTRA: list[dict] = []


def builtins() -> list[dict]:
    return [
        {"name": "mix", "title": "MIX — documentary from a topic", "mode": "mix",
         "builtin": True, "inputs": MIX_INPUTS,
         "stages": [{"name": s} for s in MIX_STAGES]},
        {"name": "fix", "title": "FIX — overlays on an existing video",
         "mode": "fix", "builtin": True, "inputs": FIX_INPUTS,
         "stages": [{"name": s} for s in FIX_STAGES]},
        *EXTRA,
    ]


def templates_dir(root: Path) -> Path:
    return Path(root) / "templates"


def load_all(root: Path) -> list[dict]:
    """Built-ins first, then saved templates. A saved name shadows a built-in."""
    out = {t["name"]: t for t in builtins()}
    d = templates_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                # one broken file must not hide every other template
                out[p.stem] = {"name": p.stem, "title": f"{p.stem} (unreadable)",
                               "error": str(e), "stages": [], "inputs": []}
                continue
            t["name"] = p.stem
            t.setdefault("mode", "mix")
            t.setdefault("inputs", [])
            t["builtin"] = False
            out[p.stem] = t
    return list(out.values())


def get(root: Path, name: str) -> dict:
    for t in load_all(root):
        if t["name"] == name:
            return t
    raise KeyError(f"no template named {name}")


def save_from_run(root: Path, state: State, run_id: str, name: str,
                  title: str | None = None) -> Path:
    """Capture a run's stage list and parameters as a reusable template."""
    if not SAFE_NAME.fullmatch(name):
        raise ValueError("template name: letters, digits, dot, dash, underscore")
    run = state.get_run(run_id)
    if run is None:
        raise KeyError(f"no such run: {run_id}")
    stages = []
    for row in state.stages(run_id):
        s = {"name": row["stage_name"]}
        params = state.get_params(run_id, row["stage_name"])
        if params:
            s["params"] = params
        stages.append(s)
    tpl = {"title": title or f"{name} (from {run['project']})",
           "mode": run["mode"], "stages": stages,
           # fix and split both start from a source video, so both take FIX_INPUTS
           "inputs": MIX_INPUTS if run["mode"] == "mix" else FIX_INPUTS}
    d = templates_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.json"
    path.write_text(json.dumps(tpl, indent=2), encoding="utf-8")
    return path


def write_inputs(project_dir: Path, template: dict, values: dict) -> list[str]:
    """Write the template's input files. Never overwrites — returns what it skipped.

    User-dropped input is sacred (see the project rules): an existing file with
    different content is reported, not replaced.
    """
    skipped = []
    for spec in template.get("inputs", []):
        val = (values.get(spec["key"]) or "").strip()
        if not val:
            continue
        p = project_dir / spec["path"]
        body = json.dumps({spec["field"]: val}, indent=2) if spec.get("field") else val
        if p.exists() and p.read_text(encoding="utf-8").strip() != body.strip():
            skipped.append(spec["path"])
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return skipped


def create_project(root: Path, projects_dir: str, state: State, template: dict,
                   project: str, values: dict, brain: str) -> dict:
    """Materialise a template into a real run — the canvas's 'New project'.

    Creates the stage rows and parameters only. Execution stays with
    `mixfix run`, which fulfils AI tasks and needs a terminal.
    """
    if not SAFE_NAME.fullmatch(project):
        raise ValueError("project name: letters, digits, dot, dash, underscore")
    if not template.get("stages"):
        raise ValueError(f"template {template.get('name')} has no stages")
    existing = state.latest_run(project)
    if existing and existing["status"] != "done":
        raise ValueError(
            f"project {project} already has an open run ({existing['run_id']}, "
            f"{existing['status']}) — resume it or pick another name")

    project_dir = Path(root) / projects_dir / project
    (project_dir / "input").mkdir(parents=True, exist_ok=True)
    skipped = write_inputs(project_dir, template, values)

    names = [s["name"] for s in template["stages"]]
    run_id = state.create_run(project, template["mode"], brain, None, names)
    state.set_template(run_id, template["name"])
    for s in template["stages"]:
        if s.get("params"):
            state.set_params(run_id, s["name"], s["params"])
    return {"run_id": run_id, "project": project, "mode": template["mode"],
            "skipped_inputs": skipped,
            "command": f"python -m mixfix.cli run --mode {template['mode']} "
                       f"--project {project} --brain {brain}"}
