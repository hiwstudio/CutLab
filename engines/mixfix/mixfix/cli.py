"""mixfix CLI — run / resume / status."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .ai.llm_adapter import LLMAdapter
from .ai.router import Router
from .ai.tasks import TaskQueue
from . import modes
from .config import load_config, resolve_api_key
from .pipeline import FIX_STAGES, MIX_STAGES, Pipeline
from .state import State

STAGES_FOR = {"mix": MIX_STAGES, "fix": FIX_STAGES}
MODE_MENU = [
    ("mix", "documentary from a topic"),
    ("fix", "contextual overlays on an existing video"),
]


def _root() -> Path:
    return Path.cwd()


def _ask_mode() -> str:
    """Driven by hand with no --mode: offer the three modes rather than fail.

    Reads whatever stdin has instead of gating on isatty — that check is
    unreliable under Git Bash/MSYS and would refuse piped input that is
    perfectly usable. No input at all raises EOFError and exits below.
    """
    print("What are we making?")
    for i, (name, desc) in enumerate(MODE_MENU, 1):
        print(f"  {i}) {name:<6} {desc}")
    names = [m[0] for m in MODE_MENU]
    while True:
        try:
            choice = input(f"mode [1-{len(names)}]: ").strip().lower()
        except EOFError:  # isatty lies under Git Bash / MSYS; fail, never hang
            sys.exit("ERROR: --mode is required (mix | fix). Split screen: python -m split run --project <name>")
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return names[int(choice) - 1]
        if choice in names:
            return choice
        print(f"Pick 1-{len(names)}, or type {' / '.join(names)}.")


def _build(cfg: dict, brain: str) -> tuple[State, Router]:
    root = Path(cfg["root"])
    state = State(root / cfg["paths"]["db"])
    queue = TaskQueue(state, root / cfg["paths"]["ai_tasks"])
    adapter = None
    if brain == "api":
        key = resolve_api_key(cfg)
        if not key:
            sys.exit(f"ERROR: brain=api requires the {cfg['llm']['api_key_env']} "
                     "environment variable. Set it, or run with --brain operator.")
        adapter = LLMAdapter(cfg, key)
    return state, Router(brain, queue, adapter)


def cmd_run(args: argparse.Namespace) -> None:
    cfg = load_config(_root())
    brain = args.brain or cfg["brain"]
    args.mode = args.mode or _ask_mode()
    stages = STAGES_FOR[args.mode]
    if args.vertical:  # shorts framing without editing config.yaml for one run
        r = cfg["render"]
        cfg["render"] = {**r, "width": min(r["width"], r["height"]),
                         "height": max(r["width"], r["height"])}
    state, router = _build(cfg, brain)
    project_dir = Path(cfg["root"]) / cfg["paths"]["projects"] / args.project
    (project_dir / "input").mkdir(parents=True, exist_ok=True)

    run = state.latest_run(args.project)
    if run and run["status"] in ("paused", "running", "failed") and not args.new:
        run_id = run["run_id"]
        if run["brain"] != brain:
            sys.exit(f"ERROR: run {run_id} was started with brain={run['brain']}; "
                     f"refusing to switch mid-run. Use --new for a fresh run.")
        print(f"Resuming run {run_id} (brain={brain})")
        state.ensure_stages(run_id, stages)
        state.set_run_status(run_id, "running")
    else:
        run_id = state.create_run(args.project, args.mode, brain, None, stages)
        print(f"Started run {run_id} (mode={args.mode}, brain={brain})")

    mode = state.get_run(run_id)["mode"]
    result = Pipeline(state, router, cfg, run_id, project_dir, mode).run()
    sys.exit(0 if result in ("done", "paused") else 1)


def cmd_status(args: argparse.Namespace) -> None:
    cfg = load_config(_root())
    state = State(Path(cfg["root"]) / cfg["paths"]["db"])
    runs = state.conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC LIMIT 10").fetchall()
    if not runs:
        print("No runs yet.")
        return
    for run in runs:
        print(f"\nrun {run['run_id']}  project={run['project']}  mode={run['mode']}"
              f"  brain={run['brain']}  status={run['status']}")
        for st in state.stages(run["run_id"]):
            mark = {"done": "x", "running": ">", "paused": "…",
                    "failed": "!", "skipped": "-"}.get(st["status"], " ")
            err = f"  error: {st['error']}" if st["error"] else ""
            print(f"  [{mark}] {st['stage_name']}{err}")
    pending = state.all_pending_ai_tasks()
    if pending:
        print(f"\nPending AI tasks ({len(pending)}) — active brain fulfills these:")
        for t in pending:
            print(f"  {t['task_id']}  {t['task_type']}  → {t['request_dir']}/request.json")
    gates = state.conn.execute(
        "SELECT * FROM gates WHERE status='pending' ORDER BY created_at").fetchall()
    for g in gates:
        run = state.get_run(g["run_id"])
        print(f"\nPending gate: {g['name']} (run {g['run_id']}) — approve via "
              f"`{modes.cli_for(run['mode'])} preview --project {run['project']}`")


def cmd_preview(args: argparse.Namespace) -> None:
    from .preview import serve
    cfg = load_config(_root())
    state = State(Path(cfg["root"]) / cfg["paths"]["db"])
    run = state.latest_run(args.project)
    if run is None:
        sys.exit(f"ERROR: no runs for project {args.project}")
    project_dir = Path(cfg["root"]) / cfg["paths"]["projects"] / args.project
    serve(project_dir, state, run["run_id"], port=args.port, cfg=cfg)


GRID_ROOT = Path(os.environ["MIXFIX_GRID_ROOT"]).expanduser().resolve() if os.environ.get("MIXFIX_GRID_ROOT") else None


def cmd_graph(args: argparse.Namespace) -> None:
    """The node canvas lives in GRID now — one app across every project."""
    if GRID_ROOT is None or not (GRID_ROOT / "grid" / "server.py").exists():
        sys.exit("ERROR: the optional GRID canvas is not configured. Set MIXFIX_GRID_ROOT "
                 "to a GRID checkout, or continue with the MixFix timeline review board.")
    sys.path.insert(0, str(GRID_ROOT))
    from grid.server import serve
    serve(port=args.port, root=GRID_ROOT)


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        # line_buffering is not optional: reconfigure() otherwise resets stdout
        # to BLOCK buffering whenever output is redirected, so a long run prints
        # nothing until it exits and there is no way to tell progress from hang.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                               line_buffering=True)
    p = argparse.ArgumentParser(prog="mixfix", description="MixFix Engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="start or resume a production run")
    run_p.add_argument("--mode", choices=["mix", "fix"],
                       help="omit and you will be asked which mode")
    run_p.add_argument("--project", required=True)
    run_p.add_argument("--vertical", action="store_true",
                       help="render portrait (shorts) for this run")
    run_p.add_argument("--brain", choices=["operator", "api"],
                       help="intelligence layer (default from config.yaml)")
    run_p.add_argument("--new", action="store_true",
                       help="force a fresh run instead of resuming")
    run_p.set_defaults(func=cmd_run)

    sub.add_parser("resume", help="alias for run on the latest paused run")
    status_p = sub.add_parser("status", help="show runs, stages, pending AI tasks")
    status_p.set_defaults(func=cmd_status)

    prev_p = sub.add_parser("preview", help="serve the timeline review board")
    prev_p.add_argument("--project", required=True)
    prev_p.add_argument("--port", type=int, default=8765)
    prev_p.set_defaults(func=cmd_preview)

    graph_p = sub.add_parser("graph", help="open GRID, the node canvas")
    graph_p.add_argument("--port", type=int, default=8770)
    graph_p.set_defaults(func=cmd_graph)

    args = p.parse_args(argv)
    if args.cmd == "resume":
        sys.exit("Use: mixfix run --mode mix --project <name>  (it auto-resumes)")
    args.func(args)


if __name__ == "__main__":
    main()
