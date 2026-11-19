"""Assembly MixFix CLI — `python -m assembly run --project <name>`.

Deliberately thin: it reuses MixFix's argument handling, config loading and
state, and differs only in running AssemblyPipeline over ASSEMBLY_STAGES.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mixfix import cli as mixcli
from mixfix.config import load_config
from mixfix.state import State

from .pipeline import ASSEMBLY_STAGES, AssemblyPipeline


def cmd_run(args: argparse.Namespace) -> None:
    cfg = load_config(Path.cwd())
    brain = args.brain or cfg["brain"]
    state, router = mixcli._build(cfg, brain)
    project_dir = Path(cfg["root"]) / cfg["paths"]["projects"] / args.project
    (project_dir / "input").mkdir(parents=True, exist_ok=True)

    run = state.latest_run(args.project)
    if run and run["status"] in ("paused", "running", "failed") and not args.new:
        run_id = run["run_id"]
        if run["brain"] != brain:
            sys.exit(f"ERROR: run {run_id} was started with brain={run['brain']}; "
                     f"refusing to switch mid-run. Use --new for a fresh run.")
        if run["mode"] != "assembly":
            sys.exit(f"ERROR: project {args.project} has a {run['mode']} run open. "
                     f"Use `{mixcli_for(run['mode'])}` for it, or --new here.")
        print(f"Resuming assembly run {run_id} (brain={brain})")
        state.ensure_stages(run_id, ASSEMBLY_STAGES)
        state.set_run_status(run_id, "running")
    else:
        run_id = state.create_run(args.project, "assembly", brain, None,
                                  ASSEMBLY_STAGES)
        print(f"Started assembly run {run_id} (brain={brain})")

    result = AssemblyPipeline(state, router, cfg, run_id, project_dir,
                              "assembly").run()
    sys.exit(0 if result in ("done", "paused") else 1)


def mixcli_for(mode: str) -> str:
    from mixfix import modes
    return modes.cli_for(mode)


def cmd_preview(args: argparse.Namespace) -> None:
    from mixfix.preview import serve
    cfg = load_config(Path.cwd())
    state = State(Path(cfg["root"]) / cfg["paths"]["db"])
    run = state.latest_run(args.project)
    if run is None:
        sys.exit(f"ERROR: no runs for project {args.project}")
    project_dir = Path(cfg["root"]) / cfg["paths"]["projects"] / args.project
    serve(project_dir, state, run["run_id"], port=args.port, cfg=cfg)


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                               line_buffering=True)
    p = argparse.ArgumentParser(
        prog="assembly",
        description="Assembly MixFix — themed long-form cuts from one episode")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="start or resume an assembly run")
    run_p.add_argument("--project", required=True)
    run_p.add_argument("--brain", choices=["operator", "api"])
    run_p.add_argument("--new", action="store_true",
                       help="force a fresh run instead of resuming")
    run_p.set_defaults(func=cmd_run)

    prev_p = sub.add_parser("preview", help="serve the review board")
    prev_p.add_argument("--project", required=True)
    prev_p.add_argument("--port", type=int, default=8765)
    prev_p.set_defaults(func=cmd_preview)

    status_p = sub.add_parser("status", help="show runs, stages, pending tasks")
    status_p.set_defaults(func=mixcli.cmd_status)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
