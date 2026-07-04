"""Understanding job (kind='understanding') — Phase 1.

Analyzes one asset into a per-asset understanding artifact:
    probe -> scenes -> silence -> transcript -> beats -> saliency -> assemble

Every stage is checkpointed to its own partial JSON file (the same resume-on-disk
convention as ingest and as the source engines). On crash-resume, a stage whose
partial artifact exists and is non-empty is skipped — an interrupted whisper pass
never re-runs the scene/silence work already done. The `assemble` stage composes
the partials into `understanding/{asset}.understanding.json`, updates the asset,
and registers the path in the EDL via the `set_understanding` op.

Input: {project_id, asset_id, kind, src, project_dir}.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..db import dumps
from ..edl.engine import Conflict, Engine, Rejected
from ..profiles import saliency_config
from ..understanding import beats as beats_mod
from ..understanding import saliency as saliency_mod
from ..understanding import scenes as scenes_mod
from ..understanding import silence as silence_mod
from ..understanding import transcribe as transcribe_mod
from ..understanding.schema import (
    UNDERSTANDING_VERSION,
    ActiveRange,
    Provenance,
    Scene,
    SilenceSpan,
    Transcript,
    Understanding,
)
from ..util import paths
from .queue import JobContext


def _u_dir(project_dir: Path) -> Path:
    d = project_dir / "understanding"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, obj) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_facts(db, project_id: str, asset_id: str, project_dir: Path) -> tuple[int, bool]:
    """(duration_ms, has_audio) from the ingest probe row, probing if needed."""
    row = db.query_one(
        "SELECT duration_ms, probe_json FROM assets WHERE project_id=? AND asset_id=?",
        (project_id, asset_id),
    )
    duration_ms = (row or {}).get("duration_ms") or 0
    has_audio = False
    if row and row["probe_json"]:
        raw = json.loads(row["probe_json"])
        has_audio = any(s.get("codec_type") == "audio" for s in raw.get("streams", []))
    return int(duration_ms or 0), has_audio


def understanding_handler(ctx: JobContext) -> None:
    inp = ctx.input
    project_id: str = inp["project_id"]
    asset_id: str = inp["asset_id"]
    kind: str = inp["kind"]
    project_dir = Path(inp["project_dir"])
    src = paths.safe_join(project_dir, inp["src"])
    db = ctx.queue.db

    if not src.exists():
        raise FileNotFoundError(f"source missing: {inp['src']}")

    udir = _u_dir(project_dir)
    duration_ms, has_audio = _asset_facts(db, project_id, asset_id, project_dir)
    is_video = kind == "video"
    analyze_audio = has_audio and kind in ("video", "audio")

    scenes_file = udir / f"{asset_id}.scenes.json"
    silence_file = udir / f"{asset_id}.silence.json"
    transcript_file = udir / f"{asset_id}.transcript.json"
    beats_file = udir / f"{asset_id}.beats.json"
    saliency_file = udir / f"{asset_id}.saliency.json"
    final_file = udir / f"{asset_id}.understanding.json"

    total = 6

    # Stage 1: scenes (video only).
    def do_scenes() -> str:
        scenes = scenes_mod.detect_scenes(str(src), duration_ms) if is_video else []
        return _write_json(scenes_file, {
            "scenes": [s.model_dump() for s in scenes],
            "provenance": scenes_mod.provenance() if is_video else None,
        })

    ctx.run_stage("scenes", do_scenes)
    ctx.set_progress(1 / total)

    # Stage 2: silence + active ranges (audio-bearing only).
    def do_silence() -> str:
        if analyze_audio:
            spans = silence_mod.silence_spans(str(src), duration_ms)
            ranges = silence_mod.active_ranges(duration_ms, spans)
            prov = silence_mod.provenance()
        else:
            spans, ranges, prov = [], [], None
        return _write_json(silence_file, {
            "silence": [s.model_dump() for s in spans],
            "active_ranges": [r.model_dump() for r in ranges],
            "provenance": prov,
        })

    ctx.run_stage("silence", do_silence)
    ctx.set_progress(2 / total)

    # Stage 3: transcript (audio-bearing only) — the slow whisper pass.
    def do_transcript() -> str:
        if analyze_audio:
            tr = transcribe_mod.transcribe_video(str(src), str(udir))
            prov = transcribe_mod.provenance()
        else:
            tr, prov = Transcript(), None
        return _write_json(transcript_file, {
            "transcript": tr.model_dump(), "provenance": prov,
        })

    ctx.run_stage("transcript", do_transcript)
    ctx.set_progress(3 / total)

    # Stage 4: beats (audio-bearing only).
    def do_beats() -> str:
        if analyze_audio:
            beats_ms, tempo = beats_mod.detect_beats(str(src))
            prov = beats_mod.provenance()
        else:
            beats_ms, tempo, prov = [], None, None
        return _write_json(beats_file, {
            "beats_ms": beats_ms, "tempo_bpm": tempo, "provenance": prov,
        })

    ctx.run_stage("beats", do_beats)
    ctx.set_progress(4 / total)

    # Stage 5: saliency (pure; folds the prior stages together).
    def do_saliency() -> str:
        profile = _project_profile(db, project_id)
        window_ms, weights = saliency_config(profile)
        scenes = [Scene(**s) for s in _read_json(scenes_file)["scenes"]]
        sil = _read_json(silence_file)
        spans = [SilenceSpan(**s) for s in sil["silence"]]
        tr_data = _read_json(transcript_file)["transcript"]
        transcript = Transcript(**tr_data) if tr_data.get("segments") else None
        beats_ms = _read_json(beats_file)["beats_ms"]
        sal = saliency_mod.compute_saliency(
            duration_ms, profile, weights, transcript, scenes, spans, beats_ms,
            window_ms=window_ms,
        )
        return _write_json(saliency_file, sal.model_dump())

    ctx.run_stage("saliency", do_saliency)
    ctx.set_progress(5 / total)

    # Stage 6: assemble + register.
    def do_assemble() -> str:
        u = _compose(asset_id, kind, duration_ms, scenes_file, silence_file,
                     transcript_file, beats_file, saliency_file)
        final_file.write_text(
            u.model_dump_json(exclude_none=True, indent=1), encoding="utf-8"
        )
        rel = str(final_file.relative_to(project_dir)).replace("\\", "/")
        db.execute(
            "UPDATE assets SET understanding=? WHERE project_id=? AND asset_id=?",
            (rel, project_id, asset_id),
        )
        _register(ctx, project_id, asset_id, rel)
        return str(final_file)

    ctx.run_stage("assemble", do_assemble)
    ctx.set_progress(1.0)


def _compose(asset_id, kind, duration_ms, scenes_file, silence_file,
             transcript_file, beats_file, saliency_file) -> Understanding:
    sc = _read_json(scenes_file)
    sil = _read_json(silence_file)
    trd = _read_json(transcript_file)
    bt = _read_json(beats_file)
    sal = _read_json(saliency_file)

    transcript = None
    if trd["transcript"].get("segments"):
        transcript = Transcript(**trd["transcript"])

    prov = Provenance(
        transcribe=trd.get("provenance"),
        scenes=sc.get("provenance"),
        silence=sil.get("provenance"),
        beats=bt.get("provenance"),
    )
    return Understanding(
        version=UNDERSTANDING_VERSION,
        asset_id=asset_id,
        kind=kind,
        duration_ms=duration_ms,
        transcript=transcript,
        scenes=[Scene(**s) for s in sc["scenes"]],
        silence=[SilenceSpan(**s) for s in sil["silence"]],
        active_ranges=[ActiveRange(**r) for r in sil["active_ranges"]],
        beats_ms=bt["beats_ms"],
        tempo_bpm=bt.get("tempo_bpm"),
        saliency=sal if sal.get("windows") else None,
        provenance=prov,
    )


def _project_profile(db, project_id: str) -> str:
    # The profile lives in the EDL; default when unavailable.
    row = db.query_one(
        "SELECT edl_json FROM revisions r JOIN projects p ON p.id=r.project_id "
        "AND p.head_rev=r.rev WHERE r.project_id=?",
        (project_id,),
    )
    if row:
        try:
            return json.loads(row["edl_json"])["project"].get("profile", "default")
        except Exception:
            pass
    return "default"


def _register(ctx: JobContext, project_id: str, asset_id: str, rel: str) -> None:
    """Set asset.understanding in the EDL via the set_understanding op."""
    engine = Engine(ctx.queue.db, projects_dir=Path(ctx.input["project_dir"]).parent)
    op = {"op": "set_understanding", "asset": asset_id, "understanding": rel}
    for _ in range(5):
        head = engine.get_project(project_id)["head_rev"]
        try:
            engine.apply(project_id, head, [op])
            return
        except Conflict:
            continue
        except Rejected as e:
            # Asset gone or already points here — nothing to do.
            if any(i.code in ("E_REF", "E_NOOP") for i in e.issues):
                return
            raise
    raise RuntimeError("could not register understanding in EDL after 5 attempts")
