"""Ingest job (kind='ingest'): probe -> proxy -> waveform -> thumbs.

Input: {project_id, asset_id, kind, src (relative to project dir), project_dir}.
Each stage is checkpointed via ctx.run_stage; on crash-resume, completed stages
are skipped by artifact integrity check. On success the asset row flips to
'ready' and the asset is registered in the EDL through an `add_asset` op.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from .. import config
from ..db import dumps, utcnow
from ..edl.engine import Conflict, Engine
from ..util import paths
from ..util.ffprobe import ProbeResult, probe
from ..util.ffrun import run_ffmpeg
from .queue import JobContext

WAVEFORM_BUCKETS = 1000
WAVEFORM_RATE = 8000


def ingest_handler(ctx: JobContext) -> None:
    inp = ctx.input
    project_id: str = inp["project_id"]
    asset_id: str = inp["asset_id"]
    kind: str = inp["kind"]
    project_dir = Path(inp["project_dir"])
    src = paths.safe_join(project_dir, inp["src"])
    db = ctx.queue.db

    if not src.exists():
        _mark_failed(ctx, project_id, asset_id, f"source file missing: {inp['src']}")
        raise FileNotFoundError(src)

    paths.ensure_project_layout(project_dir)

    try:
        # Stage 1: probe.
        probe_file = paths.probe_path(project_dir, asset_id)

        def do_probe() -> str:
            result = probe(src)
            probe_file.write_text(json.dumps(result.raw, indent=2), encoding="utf-8")
            db.execute(
                "UPDATE assets SET duration_ms=?, width=?, height=?, probe_json=? "
                "WHERE project_id=? AND asset_id=?",
                (result.duration_ms, result.width, result.height,
                 dumps(result.raw), project_id, asset_id),
            )
            return str(probe_file)

        ctx.run_stage("probe", do_probe)
        ctx.set_progress(0.25)
        info = _probe_from_artifact(probe_file)

        # Stage 2: proxy (video only): 540p H.264, 1s keyframes for scrubbing.
        proxy_rel = None
        if kind == "video":
            proxy = paths.proxy_path(project_dir, asset_id)
            gop = max(1, int(round(info.fps or 30)))

            def do_proxy() -> str:
                run_ffmpeg([
                    "-i", str(src),
                    "-vf", f"scale=-2:{config.PROXY_HEIGHT}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                    "-g", str(gop),
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(proxy),
                ])
                return str(proxy)

            ctx.run_stage("proxy", do_proxy)
            proxy_rel = str(proxy.relative_to(project_dir)).replace("\\", "/")
            db.execute(
                "UPDATE assets SET proxy=? WHERE project_id=? AND asset_id=?",
                (proxy_rel, project_id, asset_id),
            )
        ctx.set_progress(0.5)

        # Stage 3: waveform peaks (audio/video).
        if kind in ("audio", "video"):
            peaks_file = paths.peaks_path(project_dir, asset_id)
            ctx.run_stage("waveform", lambda: _waveform(src, peaks_file, info))
            if info.duration_ms is None and info.has_audio:
                peaks = json.loads(peaks_file.read_text(encoding="utf-8"))
                info.duration_ms = peaks.get("duration_ms") or _decoded_audio_duration_ms(src)
                if info.duration_ms <= 0:
                    raise RuntimeError("decoded audio has no measurable duration")
                db.execute(
                    "UPDATE assets SET duration_ms=? WHERE project_id=? AND asset_id=?",
                    (info.duration_ms, project_id, asset_id),
                )
        ctx.set_progress(0.75)

        # Stage 4: thumbnails (video only): 1 frame / 5s, 160px wide.
        if kind == "video":
            tdir = paths.thumbs_dir(project_dir, asset_id)

            def do_thumbs() -> list[str]:
                tdir.mkdir(parents=True, exist_ok=True)
                # select: always the first frame, then one every 5s (plain
                # fps=1/5 can emit nothing at all for very short videos).
                run_ffmpeg([
                    "-i", str(src),
                    "-vf",
                    r"select=isnan(prev_selected_t)+gte(t-prev_selected_t\,5),scale=160:-2",
                    "-vsync", "vfr",
                    "-q:v", "4",
                    str(tdir / "t_%04d.jpg"),
                ])
                return [str(p) for p in sorted(tdir.glob("t_*.jpg"))]

            ctx.run_stage("thumbs", do_thumbs)
        ctx.set_progress(0.95)

        # Finalize: asset ready + registered in the EDL via the op path.
        db.execute(
            "UPDATE assets SET status='ready' WHERE project_id=? AND asset_id=?",
            (project_id, asset_id),
        )
        _register_in_edl(ctx, project_id, asset_id, kind, inp["src"], proxy_rel, info)
        ctx.set_progress(1.0)
    except Exception as e:
        _mark_failed(ctx, project_id, asset_id, str(e)[-500:])
        raise


def _probe_from_artifact(probe_file: Path) -> ProbeResult:
    """Rebuild ProbeResult from the checkpointed probe JSON (resume-safe)."""
    from ..util import ffprobe as _ff

    raw = json.loads(probe_file.read_text(encoding="utf-8"))
    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in raw.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = raw.get("format", {}).get("duration")
    fps = None
    if video:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if rate and rate != "0/0":
            from fractions import Fraction

            f = Fraction(rate)
            fps = float(f) if f > 0 else None
    return ProbeResult(
        duration_ms=int(round(float(dur) * 1000)) if dur else None,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        fps=fps,
        has_video=video is not None,
        has_audio=audio is not None,
        raw=raw,
    )


def _waveform(src: Path, peaks_file: Path, info: ProbeResult) -> str:
    """Decode mono PCM and decimate to WAVEFORM_BUCKETS peak values (0..1)."""
    if not info.has_audio:
        peaks_file.write_text(json.dumps({"buckets": [], "note": "no audio stream"}))
        return str(peaks_file)

    import numpy as np

    cmd = [
        config.FFMPEG, "-hide_banner", "-v", "error",
        "-i", str(src), "-map", "a:0",
        "-ac", "1", "-ar", str(WAVEFORM_RATE), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"waveform decode failed: {proc.stderr[-500:].decode(errors='replace')}")
    samples = np.frombuffer(proc.stdout, dtype=np.int16)
    if samples.size == 0:
        buckets = []
    else:
        n = min(WAVEFORM_BUCKETS, samples.size)
        pad = math.ceil(samples.size / n) * n - samples.size
        padded = np.pad(np.abs(samples.astype(np.int32)), (0, pad))
        buckets = (padded.reshape(n, -1).max(axis=1) / 32768.0).round(4).tolist()
    duration_ms = int(round(samples.size * 1000 / WAVEFORM_RATE))
    peaks_file.write_text(json.dumps({
        "buckets": buckets, "rate": WAVEFORM_RATE, "duration_ms": duration_ms,
    }))
    return str(peaks_file)


def _decoded_audio_duration_ms(src: Path) -> int:
    """Measure duration by decoding when WebM omits container duration metadata."""
    cmd = [
        config.FFMPEG, "-hide_banner", "-v", "error", "-i", str(src),
        "-map", "a:0", "-ac", "1", "-ar", str(WAVEFORM_RATE), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"audio duration decode failed: {proc.stderr[-500:].decode(errors='replace')}")
    sample_count = len(proc.stdout) // 2
    return int(round(sample_count * 1000 / WAVEFORM_RATE))


def _register_in_edl(
    ctx: JobContext, project_id: str, asset_id: str, kind: str,
    src_rel: str, proxy_rel: str | None, info: ProbeResult,
) -> None:
    engine = Engine(ctx.queue.db, projects_dir=Path(ctx.input["project_dir"]).parent)
    op = {
        "op": "add_asset", "asset_id": asset_id, "kind": kind, "src": src_rel,
        "proxy": proxy_rel,
        "duration_ms": info.duration_ms if kind in ("video", "audio") else None,
        "width": info.width if kind in ("video", "image") else None,
        "height": info.height if kind in ("video", "image") else None,
    }
    from ..edl.engine import Rejected

    for _ in range(5):  # optimistic retry against concurrent user edits
        head = engine.get_project(project_id)["head_rev"]
        try:
            engine.apply(project_id, head, [op])
            return
        except Conflict:
            continue
        except Rejected as e:
            if any(i.code == "E_DUP" for i in e.issues):
                return  # already registered (crash-resume after registration)
            raise
    raise RuntimeError("could not register asset in EDL after 5 attempts")


def _mark_failed(ctx: JobContext, project_id: str, asset_id: str, error: str) -> None:
    ctx.queue.db.execute(
        "UPDATE assets SET status='failed' WHERE project_id=? AND asset_id=?",
        (project_id, asset_id),
    )
