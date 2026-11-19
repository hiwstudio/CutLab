"""Durable audio extraction from a ready video asset."""
from __future__ import annotations

from pathlib import Path

from ..db import dumps
from ..util import paths
from ..util.ffprobe import probe
from ..util.ffrun import run_ffmpeg
from .ingest import _register_in_edl, _waveform
from .queue import JobContext


def extract_audio_handler(ctx: JobContext) -> None:
    project_id = ctx.input["project_id"]
    asset_id = ctx.input["asset_id"]
    output_id = ctx.input["output_asset_id"]
    project_dir = Path(ctx.input["project_dir"])
    row = ctx.queue.db.query_one(
        "SELECT src FROM assets WHERE project_id=? AND asset_id=?",
        (project_id, asset_id),
    )
    if not row:
        raise RuntimeError("source video asset missing")
    src = paths.safe_join(project_dir, row["src"])
    source_info = probe(src)
    if not source_info.has_audio:
        raise RuntimeError("source video has no audio stream")

    output = paths.media_dir(project_dir) / f"{output_id}_extracted.m4a"

    def extract() -> str:
        run_ffmpeg([
            "-i", str(src), "-map", "0:a:0", "-vn", "-c:a", "aac",
            "-b:a", "192k", "-movflags", "+faststart", str(output),
        ])
        return str(output)

    ctx.run_stage("extract_audio", extract)
    ctx.set_progress(0.65)
    info = probe(output)
    peaks = paths.peaks_path(project_dir, output_id)
    ctx.run_stage("waveform", lambda: _waveform(output, peaks, info))
    ctx.queue.db.execute(
        "INSERT OR IGNORE INTO assets "
        "(project_id,asset_id,kind,src,duration_ms,probe_json,status) "
        "VALUES (?,?,?,?,?,?,'ready')",
        (project_id, output_id, "audio", f"media/{output.name}", info.duration_ms,
         dumps(info.raw)),
    )
    _register_in_edl(
        ctx, project_id, output_id, "audio", f"media/{output.name}", None, info,
    )
    ctx.set_progress(1.0)
