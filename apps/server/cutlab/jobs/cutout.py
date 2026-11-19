"""Durable local background removal for still-image assets."""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..engines.cutout import remove_background
from ..util import paths
from .ingest import _register_in_edl
from .queue import JobContext

def cutout_handler(ctx: JobContext) -> None:
    project_id, asset_id = ctx.input["project_id"], ctx.input["asset_id"]
    project_dir = Path(ctx.input["project_dir"])
    row = ctx.queue.db.query_one("SELECT src,width,height FROM assets WHERE project_id=? AND asset_id=?", (project_id, asset_id))
    if not row:
        raise RuntimeError("image asset missing")
    output_id = ctx.input["output_asset_id"]
    out = paths.media_dir(project_dir) / f"{output_id}_cutout.png"
    def run():
        remove_background(paths.safe_join(project_dir, row["src"]), out, config.CUTOUT_MODEL)
        return str(out)
    ctx.run_stage("remove_background", run)
    ctx.queue.db.execute("INSERT OR IGNORE INTO assets (project_id,asset_id,kind,src,width,height,status) VALUES (?,?,?,?,?,?, 'ready')", (project_id,output_id,"image",f"media/{out.name}",row["width"],row["height"]))
    from ..util.ffprobe import probe
    _register_in_edl(ctx, project_id, output_id, "image", f"media/{out.name}", None, probe(out))
    ctx.set_progress(1)
