"""Durable local text-to-speech asset generation using CutLab's Piper voice."""
from __future__ import annotations

from pathlib import Path

from ..db import dumps
from ..util import paths
from ..util.ffprobe import probe
from .ingest import _register_in_edl, _waveform
from .queue import JobContext
from ..engines.tts import synthesize


def text_to_sound_handler(ctx: JobContext) -> None:
    project_id = ctx.input["project_id"]
    output_id = ctx.input["output_asset_id"]
    project_dir = Path(ctx.input["project_dir"])
    text = str(ctx.input["text"]).strip()
    if not text:
        raise ValueError("text is required")
    output = paths.media_dir(project_dir) / f"{output_id}_voice.wav"
    def make_voice() -> dict[str, str]:
        provider = synthesize(text, output)
        return {"file": str(output), "provider": provider}
    ctx.run_stage("synthesize", make_voice)
    ctx.set_progress(0.75)
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
