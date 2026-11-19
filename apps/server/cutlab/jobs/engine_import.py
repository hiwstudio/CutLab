"""Checkpointed MixFix import and isolated scene-update proposals."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from ..db import dumps
from ..edl.engine import Engine
from ..integrations import mixfix
from ..util import paths
from ..util.ffprobe import probe
from .ingest import ingest_handler
from .queue import JobContext


def ident(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:12]


def write_json(path: Path, data: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return str(path)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class IngestContext:
    """Reuse all ingest stages under the parent's durable checkpoint namespace."""
    def __init__(self, parent: JobContext, asset_id: str, kind: str, rel: str):
        self.parent, self.queue = parent, parent.queue
        self.input = {**parent.input, "asset_id": asset_id, "kind": kind, "src": rel}
        self.asset_id = asset_id

    def run_stage(self, name, fn):
        return self.parent.run_stage(f"{self.asset_id}_{name}", fn)

    def set_progress(self, progress):
        self.parent.check_cancelled()


def import_asset(ctx: JobContext, source: Path, kind: str) -> tuple[str, dict]:
    project_dir = Path(ctx.input["project_dir"])
    # Content addressing prevents stale files and deduplicates repeated footage.
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            ctx.check_cancelled()
            digest.update(chunk)
    aid = "ast_" + digest.hexdigest()[:12]
    dest = project_dir / "media" / f"{aid}{source.suffix.lower()}"
    def copy():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".partial")
        shutil.copyfile(source, tmp)
        if file_digest(tmp) != digest.hexdigest():
            tmp.unlink()
            raise ValueError("Source media changed during import; retry with a stable project")
        tmp.replace(dest)
        return str(dest)
    ctx.run_stage(f"copy_{aid}", copy)
    rel = dest.relative_to(project_dir).as_posix()
    ctx.queue.db.execute("INSERT OR IGNORE INTO assets (project_id,asset_id,kind,src,status) VALUES (?,?,?,?,'ingesting')",
                         (ctx.project_id, aid, kind, rel))
    row = ctx.queue.db.query_one("SELECT * FROM assets WHERE project_id=? AND asset_id=?", (ctx.project_id, aid))
    if row["status"] != "ready":
        ingest_handler(IngestContext(ctx, aid, kind, rel))
    # Resume may find a ready DB row before its add_asset revision completed.
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)
    if aid not in engine.get_edl(ctx.project_id)["assets"]:
        ingest_handler(IngestContext(ctx, aid, kind, rel))
    return aid, engine.get_edl(ctx.project_id)["assets"][aid]


def visual_asset(ctx: JobContext, scene: dict, duration: int, canvas: dict) -> tuple[str, int, dict]:
    vis = scene.get("visual")
    if not vis:
        raise ValueError(f"scene {scene['id']} has no ready visual; complete it in MixFix first")
    source = Path(vis["path"])
    signature = f"{source.stat().st_size}:{source.stat().st_mtime_ns}"
    if vis.get("file_signature") and vis["file_signature"] != signature:
        raise ValueError(f"Source visual changed after snapshot in {scene['id']}; start a fresh import/update")
    tin = int(vis.get("trim_in_ms", 0))
    kind = "image" if vis["kind"] == "image" else "video"
    if kind == "video":
        info = probe(source)
        if not info.has_video or not info.duration_ms or tin >= info.duration_ms:
            raise ValueError(f"invalid source coverage in {scene['id']}")
        if info.duration_ms < tin + duration:
            # Preserve MixFix's real-footage-first / final-frame-hold behavior.
            # FFmpeg quantizes -t to frames. Leave a guard frame so the EDL's
            # exact millisecond endpoint cannot exceed the encoded duration.
            cover_ms = math.ceil((math.ceil(duration * canvas["fps"] / 1000) + 1) * 1000 / canvas["fps"])
            key = ident("", dumps(vis) + str(cover_ms) + dumps(canvas))
            dest = Path(ctx.input["project_dir"]) / "integration" / f"hold_{key}.mp4"
            def prepare():
                dest.parent.mkdir(parents=True, exist_ok=True)
                partial = dest.with_name("partial_" + dest.name)
                mixfix.module("assemble")._segment(scene, cover_ms, partial,
                    canvas["width"], canvas["height"], canvas["fps"])
                partial.replace(dest)
                return str(dest)
            ctx.run_stage(f"hold_{key}", prepare)
            source, tin = dest, 0
    aid, asset = import_asset(ctx, source, kind)
    if kind == "video" and asset["duration_ms"] < tin + duration:
        raise ValueError(f"Prepared visual does not cover scene {scene['id']}")
    return aid, tin, asset


def captions(words: list[dict], total: int) -> list[dict]:
    result, cursor = [], 0
    for i in range(0, len(words), 6):
        group = words[i:i + 6]
        start = max(cursor, int(group[0]["start_ms"]))
        end = min(total, int(group[-1]["end_ms"]))
        text = " ".join(str(w.get("text", "")).strip() for w in group).strip()
        if start < end and text:
            result.append({"op": "add_caption", "track": "trk_mfcaptions", "text": text,
                           "start_ms": start, "end_ms": end})
            cursor = end
    return result


def engine_import_handler(ctx: JobContext) -> None:
    project_dir = Path(ctx.input["project_dir"])
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)
    snapshot_path = project_dir / "integration" / f"{ctx.job_id}_source.json"
    def snap():
        return write_json(snapshot_path, ctx.input.get("manifest") or mixfix.snapshot(ctx.input["source_project"], ctx.input["mode"], ctx.input["canvas"]))
    ctx.run_stage("source_snapshot", snap)
    manifest = mixfix.read_json(snapshot_path)
    canvas, total = manifest["canvas"], manifest["total_ms"]
    ops, mapping = [], {}
    tracks = [("trk_mfvisual", "video", "MixFix · Footage", "footage"),
              ("trk_mfvoice", "audio", "MixFix · Narration", "voiceover"),
              ("trk_mfcaptions", "caption", "MixFix · Captions", "captions")]
    if manifest["mode"] == "fix":
        tracks.insert(0, ("trk_mfbase", "video", "MixFix · Original video", "footage"))
    for tid, kind, name, role in tracks:
        ops.append({"op": "add_track", "id": tid, "kind": kind, "name": name, "role": role})
    audio = Path(manifest["voice"] or manifest["base_video"])
    aid, asset = import_asset(ctx, audio, "audio" if manifest["mode"] == "mix" else "video")
    if asset["duration_ms"] < total - 100:
        raise ValueError("source audio/video does not cover the timeline duration")
    # A sub-frame endpoint mismatch is handled without extending beyond media.
    end = min(total, asset["duration_ms"])
    ops.append({"op": "add_clip", "id": "clp_mfvoice", "track": "trk_mfvoice", "asset": aid,
                "in_ms": 0, "out_ms": end, "start_ms": 0})
    if manifest["mode"] == "fix":
        ops.append({"op": "add_clip", "id": "clp_mfbase", "track": "trk_mfbase", "asset": aid,
                    "in_ms": 0, "out_ms": end, "start_ms": 0, "gain_db": -60})
        # Narration track carries original audio; picture is effectively silent.
    for i, scene in enumerate(manifest["scenes"]):
        start, finish = scene["slot_start_ms"], scene["slot_end_ms"]
        sid, cid = ident("scn_", scene["id"]), ident("clp_", scene["id"])
        title = scene.get("title") or scene.get("narration") or scene.get("visual_intent") or scene["id"]
        ops.append({"op": "add_scene", "id": sid, "title": title[:120], "start_ms": start, "end_ms": finish})
        if scene.get("visual"):
            asset_id, tin, _ = visual_asset(ctx, scene, finish - start, canvas)
            ops.append({"op": "add_clip", "id": cid, "track": "trk_mfvisual", "asset": asset_id,
                        "in_ms": tin, "out_ms": tin + finish - start, "start_ms": start, "gain_db": -60})
            mapping[sid] = {"source_scene_id": scene["id"], "clip_id": cid}
        elif manifest["mode"] == "mix":
            raise ValueError(f"MIX scene {scene['id']} has no ready visual")
        ctx.set_progress((i + 1) / (len(manifest["scenes"]) + 2))
    ops += captions(manifest["words"], total)
    link_path = project_dir / "integration" / "mixfix_link.json"
    link = {"manifest": manifest, "scenes": mapping}
    write_json(link_path, link)
    ops.append({"op": "set_project", "engine_source": {"engine": "mixfix", "source_project": manifest["source_project"],
        "mode": manifest["mode"], "link": "integration/mixfix_link.json", "snapshot_hash": manifest["snapshot_hash"]}})
    def assemble():
        # Deterministic track IDs close the crash window after revision commit.
        edl = engine.get_edl(ctx.project_id)
        if not any(t["id"] == "trk_mfvisual" for t in edl["tracks"]):
            if edl["tracks"] or edl.get("scenes"):
                raise ValueError("Import target was edited before assembly; import into a fresh project")
            result = engine.apply(ctx.project_id, engine.get_project(ctx.project_id)["head_rev"], ops)
            rev = result["rev"]
        else:
            rev = engine.get_project(ctx.project_id)["head_rev"]
        return write_json(project_dir / "integration" / "import_result.json", {"rev": rev, "warnings": manifest["warnings"]})
    ctx.run_stage("assemble", assemble)
    ctx.set_progress(1)


def engine_request_handler(ctx: JobContext) -> None:
    """Durable operator handoff, never an implicit engine gate approval."""
    project_dir = Path(ctx.input["project_dir"])
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)
    edl = engine.get_edl(ctx.project_id, ctx.input["base_rev"])
    source = edl["project"]["engine_source"]
    link = mixfix.read_json(paths.safe_join(project_dir, source["link"]))
    mapping = link["scenes"][ctx.input["scene_id"]]
    scene = next(s for s in link["manifest"]["scenes"] if s["id"] == mapping["source_scene_id"])
    request = {"contract_version": "1.0", "request_id": ctx.job_id, "engine": "mixfix",
        "state": "awaiting_operator", "source_project": source["source_project"], "mode": source["mode"],
        "cutlab_project": ctx.project_id, "base_rev": ctx.input["base_rev"],
        "scene_id": scene["id"], "note": ctx.input["note"], "scene": scene,
        "review_action": {"scene_id": scene["id"], "flag": "regen"},
        "next_step": "Use MixFix's existing operator workflow to replace this scene visual. Then choose Prepare scene update in CutLab. No source file or approval gate was changed."}
    ctx.run_stage("request", lambda: write_json(project_dir / "integration" / f"{ctx.job_id}_request.json", request))
    ctx.set_progress(1)


def engine_refresh_handler(ctx: JobContext) -> None:
    project_dir = Path(ctx.input["project_dir"])
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)
    base = ctx.input["base_rev"]
    edl = engine.get_edl(ctx.project_id, base)
    source = edl["project"].get("engine_source") or {}
    link = mixfix.read_json(paths.safe_join(project_dir, source["link"]))
    scene_id = ctx.input["scene_id"]
    mapping = link["scenes"][scene_id]
    clip = next((c for t in edl["tracks"] for c in t["clips"] if c["id"] == mapping["clip_id"]), None)
    if not clip:
        raise ValueError("Imported clip no longer exists; automatic replacement is unsafe")
    fresh_file = project_dir / "integration" / f"{ctx.job_id}_source.json"
    ctx.run_stage("source_snapshot", lambda: write_json(fresh_file, mixfix.snapshot(source["source_project"], source["mode"], edl["project"]["canvas"])))
    fresh = mixfix.read_json(fresh_file)
    scene = next((s for s in fresh["scenes"] if s["id"] == mapping["source_scene_id"]), None)
    if not scene:
        raise ValueError("Source scene no longer exists")
    # Preserve current timeline start, speed, transform, effects and duration.
    aid, tin, _ = visual_asset(ctx, scene, clip["out_ms"] - clip["in_ms"], edl["project"]["canvas"])
    if clip.get("freeze_frame_at_ms") is not None:
        raise ValueError("Unfreeze this clip before preparing a new visual; its freeze position belongs to the old source")
    current = engine.get_edl(ctx.project_id)
    live = next((c for t in current["tracks"] for c in t["clips"] if c["id"] == clip["id"]), None)
    if live != clip:
        raise ValueError("Selected clip changed while preparing update; request a fresh proposal")
    # Provenance belongs to the proposed revision too, so undo restores it.
    updated_link = json.loads(json.dumps(link))
    updated_link["manifest"]["scenes"] = [scene if s["id"] == scene["id"] else s
                                          for s in link["manifest"]["scenes"]]
    updated_link["latest_source_snapshot_hash"] = fresh["snapshot_hash"]
    updated_link["manifest"].pop("snapshot_hash", None)
    updated_link["manifest"]["snapshot_hash"] = hashlib.sha256(
        json.dumps(updated_link["manifest"], sort_keys=True).encode()).hexdigest()
    update_rel = f"integration/{ctx.job_id}_link.json"
    ctx.run_stage("updated_link", lambda: write_json(project_dir / update_rel, updated_link))
    ops = [{"op": "replace_clip", "clip": clip["id"], "asset": aid,
            "in_ms": tin, "out_ms": tin + clip["out_ms"] - clip["in_ms"]},
           {"op": "set_project", "engine_source": {**source, "link": update_rel,
            "snapshot_hash": updated_link["manifest"]["snapshot_hash"], "update_job": ctx.job_id}}]
    def propose():
        # Find a committed checkpoint's proposal on retry instead of duplicating.
        existing = ctx.queue.db.query_one("SELECT rev FROM revisions WHERE project_id=? AND edl_json LIKE ? ORDER BY rev LIMIT 1",
                                         (ctx.project_id, f'%"update_job":"{ctx.job_id}"%'))
        if existing:
            rev = existing["rev"]
        else:
            head = engine.get_project(ctx.project_id)["head_rev"]
            latest = engine.get_edl(ctx.project_id, head)
            selected = next((c for t in latest["tracks"] for c in t["clips"] if c["id"] == clip["id"]), None)
            if selected != clip or latest["project"].get("engine_source") != source:
                raise ValueError("Imported scene changed during preparation; request a fresh proposal")
            rev = engine.apply(ctx.project_id, head, ops, "propose")["rev"]
            ctx.queue.db.execute("UPDATE revisions SET summary=? WHERE project_id=? AND rev=?",
                (f"MixFix scene update · {scene['id']}", ctx.project_id, rev))
        return write_json(project_dir / "integration" / f"{ctx.job_id}_proposal.json", {"rev": rev, "scene": scene,
            "snapshot_hash": updated_link["manifest"]["snapshot_hash"]})
    ctx.run_stage("proposal", propose)
    ctx.set_progress(1)
