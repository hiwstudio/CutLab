"""Compaction job (kind='compaction') — P4.

Stages (checkpointed, resume-safe):
  candidates — score clip candidates over the asset's understanding; write the
               full report (clip-scoring output contract) to
               understanding/{asset}.compaction.json
  propose    — apply [{op: compact, ...}] in PROPOSE mode -> proposal revision
               (the human accepts/rejects in Studio or via the Telegram gate);
               writes propose.json {rev}
  gate       — send the Telegram gate request when configured; otherwise the
               proposal simply awaits review in Studio. Never blocks.

Input: {project_id, asset_id, target_ms, project_dir}.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..edl.engine import Engine, Rejected
from ..engines import compaction
from ..gates import telegram
from ..understanding.schema import Understanding
from .queue import JobContext


def compaction_handler(ctx: JobContext) -> None:
    inp = ctx.input
    project_id: str = inp["project_id"]
    asset_id: str = inp["asset_id"]
    target_ms: int = int(inp["target_ms"])
    project_dir = Path(inp["project_dir"])
    engine = Engine(ctx.queue.db, projects_dir=project_dir.parent)

    udir = project_dir / "understanding"
    u_file = udir / f"{asset_id}.understanding.json"
    if not u_file.is_file():
        raise FileNotFoundError(f"asset {asset_id} has no understanding; analyze first")
    u = Understanding.model_validate_json(u_file.read_text(encoding="utf-8"))

    report_file = udir / f"{asset_id}.compaction.json"
    propose_file = udir / f"{asset_id}.compaction.propose.json"
    gate_file = udir / f"{asset_id}.compaction.gate.json"

    def do_candidates() -> str:
        band = (min(compaction.DEFAULT_BAND[0], max(2000, target_ms // 3)),
                min(compaction.DEFAULT_BAND[1], target_ms))
        sweet = (min(compaction.DEFAULT_SWEET[0], band[1]),
                 min(compaction.DEFAULT_SWEET[1], band[1]))
        cands = compaction.score(compaction.candidates(u, band), u, sweet)
        keep = compaction.select(cands, target_ms)
        report = {
            "asset_id": asset_id, "target_ms": target_ms,
            "candidates": [c.to_dict() for c in compaction.nms(cands)],
            "selected": [c.to_dict() for c in keep],
            "kept_ms": sum(c.duration_ms for c in keep),
        }
        report_file.write_text(json.dumps(report, indent=1), encoding="utf-8")
        return str(report_file)

    ctx.run_stage("candidates", do_candidates)
    ctx.set_progress(0.4)

    def do_propose() -> str:
        head = engine.get_project(project_id)["head_rev"]
        try:
            result = engine.apply(project_id, head, [
                {"op": "compact", "asset": asset_id, "target_ms": target_ms},
            ], mode="propose")
            payload = {"rev": result["rev"], "summary": result["summary"]}
        except Rejected as e:
            # A plan that can't apply is a job failure with the real issue.
            raise RuntimeError(f"compact proposal rejected: {e.issues[0].message}") from e
        propose_file.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        return str(propose_file)

    ctx.run_stage("propose", do_propose)
    ctx.set_progress(0.8)

    def do_gate() -> str:
        proposal = json.loads(propose_file.read_text(encoding="utf-8"))
        report = json.loads(report_file.read_text(encoding="utf-8"))
        if telegram.configured():
            gate = telegram.TelegramGate(engine)
            kept_s = report["kept_ms"] / 1000
            n = len(report["selected"])
            gate.send_proposal_gate(
                project_id, proposal["rev"], "compact",
                f"Compacted {asset_id} → {kept_s:.1f}s across {n} segment(s) "
                f"(target {target_ms / 1000:.0f}s).",
                f"Top segment: {report['selected'][0]['rationale'] if n else 'n/a'}",
            )
            status = {"sent": True, "rev": proposal["rev"]}
        else:
            status = {"sent": False, "reason": "telegram not configured",
                      "rev": proposal["rev"]}
        gate_file.write_text(json.dumps(status, indent=1), encoding="utf-8")
        return str(gate_file)

    ctx.run_stage("gate", do_gate)
    ctx.set_progress(1.0)
