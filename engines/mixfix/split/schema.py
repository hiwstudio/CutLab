"""SPLIT's AI-task schema, registered into the core validator registry."""
from __future__ import annotations

from mixfix.ai.schemas import require_archive_queries, require_moment, VALIDATORS, _require


def validate_split_plan(result: dict, context: dict) -> None:
    """SPLIT reference plan: what plays in the BOTTOM pane, scene by scene.

    Unlike replace_plan there are no cover limits — the speaker is never hidden,
    they hold the top pane throughout — but coverage must be total: an uncovered
    stretch leaves the bottom pane on a grey card, which reads as a broken video.
    """
    _require(isinstance(result.get("scenes"), list) and result["scenes"],
             "scenes must be a non-empty list")
    # Archive-first: searches for ONE clean full-length upload of the event,
    # offered to every scene so the piece is sourced from one archive instead of
    # five independent searches. Optional — some pieces have no single event.
    require_archive_queries(result)
    seg_bounds = context["segment_bounds"]
    seen_ids: set[str] = set()
    covered: set[str] = set()
    for sc in result["scenes"]:
        for key in ("id", "segment_ids", "visual_intent", "queries"):
            _require(key in sc, f"split scene missing key: {key}")
        _require(sc["id"] not in seen_ids, f"duplicate scene id: {sc['id']}")
        seen_ids.add(sc["id"])
        _require(isinstance(sc["segment_ids"], list) and sc["segment_ids"],
                 f"{sc['id']}: segment_ids must be a non-empty list")
        for sid in sc["segment_ids"]:
            _require(sid in seg_bounds, f"{sc['id']}: unknown segment {sid}")
            _require(sid not in covered, f"segment {sid} in multiple scenes")
            covered.add(sid)
        _require(isinstance(sc["visual_intent"], str) and sc["visual_intent"].strip(),
                 f"{sc['id']}: visual_intent must be a non-empty string")
        _require(isinstance(sc["queries"], list) and sc["queries"]
                 and all(isinstance(q, str) and q.strip() for q in sc["queries"]),
                 f"{sc['id']}: queries must be a non-empty list of strings")
        # Optional: does this scene want the event happening, or someone
        # discussing it? Decides which PART of a long upload to cut from —
        # action lives in the body, talking in the post-fight tail.
        require_moment(sc, sc["id"])
    _require(covered == set(seg_bounds),
             f"every segment needs bottom-pane footage (missing: "
             f"{sorted(set(seg_bounds) - covered)[:5]})")




VALIDATORS["split_plan"] = validate_split_plan
