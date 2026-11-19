"""Split MixFix CLI — `python -m split run --project <name>`.

Deliberately thin: it reuses MixFix's argument handling, config loading and
state, and differs only in running SplitPipeline over SPLIT_STAGES. Portrait is
the default here because the format is a short.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mixfix import cli as mixcli
from mixfix.config import load_config
from mixfix.state import State

from .pipeline import SPLIT_STAGES, SplitPipeline


def _pin_geometry(state, run_id: str, cfg: dict, landscape: bool) -> None:
    """Record the run's framing as a node parameter on `assemble`.

    A runtime-only flag (the old `--vertical`) is invisible to everything that
    is not the run command: the review board built its draft from config.yaml
    and showed a landscape frame for a portrait short. Storing it means
    assemble, the draft preview and the node canvas all read the same fact, and
    a resumed run keeps the framing it started with.
    """
    if state.get_params(run_id, "assemble"):
        return                                  # already pinned; never override
    r = cfg["render"]
    lo, hi = min(r["width"], r["height"]), max(r["width"], r["height"])
    w, h = (hi, lo) if landscape else (lo, hi)
    state.set_params(run_id, "assemble", {"render": {"width": w, "height": h}})


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
        if run["mode"] != "split":
            sys.exit(f"ERROR: project {args.project} has a {run['mode']} run open. "
                     f"Use `python -m mixfix.cli` for it, or --new here.")
        print(f"Resuming split run {run_id} (brain={brain})")
        state.ensure_stages(run_id, SPLIT_STAGES)
        state.set_run_status(run_id, "running")
    else:
        run_id = state.create_run(args.project, "split", brain, None, SPLIT_STAGES)
        print(f"Started split run {run_id} (brain={brain})")
    _pin_geometry(state, run_id, cfg, landscape=args.landscape)

    result = SplitPipeline(state, router, cfg, run_id, project_dir, "split").run()
    sys.exit(0 if result in ("done", "paused") else 1)


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
        prog="split", description="Split MixFix — split-screen shorts")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="start or resume a split run")
    run_p.add_argument("--project", required=True)
    run_p.add_argument("--landscape", action="store_true",
                       help="render landscape instead of portrait")
    run_p.add_argument("--brain", choices=["operator", "api"])
    run_p.add_argument("--new", action="store_true",
                       help="force a fresh run instead of resuming")
    run_p.set_defaults(func=cmd_run)

    prev_p = sub.add_parser("preview", help="serve the timeline review board")
    prev_p.add_argument("--project", required=True)
    prev_p.add_argument("--port", type=int, default=8765)
    prev_p.set_defaults(func=cmd_preview)

    status_p = sub.add_parser("status", help="show runs, stages, pending tasks")
    status_p.set_defaults(func=mixcli.cmd_status)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
