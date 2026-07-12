"""Render job (kind='render'): plan -> chunk_{n} -> mux, all checkpointed.

Input: {project_id, rev, project_dir, output?}. A render that dies mid-chunk
resumes at the first chunk whose intermediate file is missing/invalid; it
never restarts completed chunks.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import subprocess
from pathlib import Path

from .. import config
from ..edl.engine import Engine
from ..edl.schema import EDL
from ..util.ffrun import run_ffmpeg
from ..util.paths import renders_dir
from .ffgraph import chunk_path, compile_all, compile_chunk, compile_mux, concat_list_content
from .planner import Plan, build_plan, window_plan

log = logging.getLogger("cutlab.render")


def render_handler(ctx) -> None:
    inp = ctx.input
    project_id: str = inp["project_id"]
    rev: int = inp["rev"]
    project_dir = Path(inp["project_dir"])
    output_name: str = inp.get("output") or f"{project_id}_r{rev}"

    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)
    edl = EDL.model_validate(engine.get_edl(project_id, rev))
    if edl.computed_duration_ms() == 0:
        raise ValueError("empty timeline: nothing to render")

    asset_audio = _resolve_asset_audio(ctx.queue.db, edl, project_id, project_dir)
    plan = build_plan(edl, asset_audio)
    # L1 segment preview: window the plan and use the fast encode path.
    range_ms = inp.get("range_ms")
    if range_ms:
        plan = window_plan(plan, int(range_ms[0]), int(range_ms[1]), quality="preview")

    out_dir = renders_dir(project_dir)
    work_dir = out_dir / f"{output_name}.work"
    work_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{output_name}.mp4"

    # Stage: plan — persist the normalized plan + every compiled command.
    def do_plan() -> dict:
        plan_file = work_dir / "plan.json"
        plan_file.write_text(
            json.dumps(dataclasses.asdict(plan), indent=2), encoding="utf-8"
        )
        cmds_file = work_dir / "commands.json"
        cmds = compile_all(plan, project_dir, work_dir, out_file)
        cmds_file.write_text(json.dumps(cmds, indent=2), encoding="utf-8")
        return {"plan": str(plan_file), "commands": str(cmds_file)}

    ctx.run_stage("plan", do_plan)

    # Stages: chunk_{n} — each <=60s piece is one checkpointed ffmpeg run.
    chunks = plan.chunks
    for i in range(len(chunks)):
        args = compile_chunk(plan, i, project_dir, work_dir)

        def do_chunk(args=args, i=i) -> dict:
            run_ffmpeg(args)
            return {"file": str(chunk_path(work_dir, i)), "_cmd": _cmdline(args)}

        ctx.run_stage(f"chunk_{i}", do_chunk)
        ctx.set_progress((i + 1) / (len(chunks) + 1))

    # Stage: mux — concat demux (stream copy) + faststart.
    def do_mux() -> dict:
        list_file = work_dir / "concat.txt"
        files = [chunk_path(work_dir, i) for i in range(len(chunks))]
        list_file.write_text(concat_list_content(files), encoding="utf-8")
        args = compile_mux(list_file, out_file)
        run_ffmpeg(args)
        return {"file": str(out_file), "_cmd": _cmdline(args)}

    ctx.run_stage("mux", do_mux)
    ctx.set_progress(1.0)


def _cmdline(args: list[str]) -> str:
    return subprocess.list2cmdline([config.FFMPEG, "-hide_banner", "-y", *args])


def _resolve_asset_audio(db, edl: EDL, project_id: str, project_dir: Path) -> dict[str, bool]:
    """Does each referenced asset's file carry an audio stream? Prefer the
    ingest probe stored in the assets table; fall back to a live ffprobe."""
    used = {c.asset for t in edl.tracks for c in t.clips if hasattr(c, "asset")}
    result: dict[str, bool] = {}
    for asset_id in used:
        asset = edl.assets[asset_id]
        if asset.kind == "image":
            result[asset_id] = False
            continue
        row = db.query_one(
            "SELECT probe_json FROM assets WHERE project_id=? AND asset_id=?",
            (project_id, asset_id),
        )
        if row and row["probe_json"]:
            raw = json.loads(row["probe_json"])
            result[asset_id] = any(
                s.get("codec_type") == "audio" for s in raw.get("streams", [])
            )
            continue
        try:
            from ..util.ffprobe import probe

            result[asset_id] = probe(project_dir / asset.src).has_audio
        except Exception:
            log.warning("could not probe %s for audio; assuming none", asset.src)
            result[asset_id] = False
    return result
