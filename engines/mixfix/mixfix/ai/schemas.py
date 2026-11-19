"""AI task output schemas + validation (stdlib only, no jsonschema dependency).

Every task type declares the shape a result.json must satisfy. A result that
fails validation is rejected with a clear error and the task stays pending.
"""
from __future__ import annotations


class SchemaError(ValueError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SchemaError(msg)


def validate_write_script(result: dict) -> None:
    for key in ("narration", "elevenlabs_script", "aistudio_script"):
        _require(key in result, f"missing key: {key}")
        _require(isinstance(result[key], str) and len(result[key].strip()) >= 50,
                 f"{key} must be a non-trivial string (>=50 chars)")


def validate_scene_breakdown(result: dict, context: dict) -> None:
    _require(isinstance(result.get("scenes"), list) and result["scenes"],
             "scenes must be a non-empty list")
    valid_seg_ids = set(context["segment_ids"])
    seen_scene_ids: set[str] = set()
    covered: set[str] = set()
    for sc in result["scenes"]:
        _require(isinstance(sc, dict), "each scene must be an object")
        for key in ("id", "segment_ids", "visual_intent"):
            _require(key in sc, f"scene missing key: {key}")
        _require(sc["id"] not in seen_scene_ids, f"duplicate scene id: {sc['id']}")
        seen_scene_ids.add(sc["id"])
        _require(isinstance(sc["segment_ids"], list) and sc["segment_ids"],
                 f"scene {sc['id']}: segment_ids must be a non-empty list")
        for sid in sc["segment_ids"]:
            _require(sid in valid_seg_ids, f"scene {sc['id']}: unknown segment {sid}")
            _require(sid not in covered, f"segment {sid} assigned to multiple scenes")
            covered.add(sid)
        _require(isinstance(sc["visual_intent"], str) and sc["visual_intent"].strip(),
                 f"scene {sc['id']}: visual_intent must be a non-empty string")
    _require(covered == valid_seg_ids,
             f"scenes must cover every segment exactly once "
             f"(missing: {sorted(valid_seg_ids - covered)[:5]})")


def validate_visual_plan(result: dict, context: dict) -> None:
    _require(isinstance(result.get("plans"), list) and result["plans"],
             "plans must be a non-empty list")
    # Same sourcing contract as SPLIT: MIX pulls footage through the identical
    # research stage, ranker and review board, so it gets the identical fields.
    require_archive_queries(result)
    valid_ids = set(context["scene_ids"])
    bounds = context.get("scene_bounds", {})  # {scene_id: [start_ms, end_ms]}
    covered: set[str] = set()
    has_generate = False
    for p in result["plans"]:
        _require(isinstance(p, dict), "each plan must be an object")
        sid = p.get("scene_id")
        _require(sid in valid_ids, f"unknown scene_id: {sid}")
        _require(sid not in covered, f"duplicate plan for {sid}")
        covered.add(sid)
        vt = p.get("visual_type")
        _require(vt in ("video", "image", "generate"),
                 f"{sid}: visual_type must be video|image|generate, got {vt}")
        if vt == "video":
            _require(isinstance(p.get("queries"), list) and p["queries"]
                     and all(isinstance(q, str) and q.strip() for q in p["queries"]),
                     f"{sid}: video plan needs non-empty queries list")
            require_moment(p, sid)
        elif vt == "image":
            _require(isinstance(p.get("image_prompt"), str)
                     and len(p["image_prompt"].strip()) >= 20,
                     f"{sid}: image plan needs image_prompt (>=20 chars)")
        else:  # generate — segmented custom image sequence timed to narration
            has_generate = True
            segs = p.get("segments")
            _require(isinstance(segs, list) and segs,
                     f"{sid}: generate plan needs a non-empty segments list")
            lo, hi = bounds.get(sid, [None, None])
            prev = -1
            for j, s in enumerate(segs):
                _require(isinstance(s, dict), f"{sid} seg {j}: must be an object")
                st = s.get("start_ms")
                _require(isinstance(st, int) and st >= 0,
                         f"{sid} seg {j}: start_ms must be a non-negative int")
                _require(st > prev,
                         f"{sid} seg {j}: start_ms must strictly ascend")
                if lo is not None:
                    _require(lo <= st < hi,
                             f"{sid} seg {j}: start_ms {st} outside scene "
                             f"[{lo},{hi})")
                prev = st
                _require(isinstance(s.get("delta"), str)
                         and len(s["delta"].strip()) >= 15,
                         f"{sid} seg {j}: delta must describe the specific shot "
                         "(>=15 chars)")
            if lo is not None:
                _require(segs[0]["start_ms"] == lo,
                         f"{sid}: first segment must start at the scene start "
                         f"({lo}ms), got {segs[0]['start_ms']}")
    if has_generate:
        _require(isinstance(result.get("style_lock"), str)
                 and len(result["style_lock"].strip()) >= 60,
                 "style_lock (the byte-identical consistency block prepended to "
                 "every generated prompt) is required when any scene uses "
                 "visual_type 'generate' (>=60 chars)")
    _require(covered == valid_ids,
             f"plans must cover every scene (missing: {sorted(valid_ids - covered)[:5]})")


def validate_replace_plan(result: dict, context: dict) -> None:
    """FIX overlay plan: scenes are overlay windows over a subset of segments.
    Enforces preserve-the-speaker rules from context: max_cover_ms (no overlay
    longer than this) and min_gap_ms (original footage returns between overlays).
    """
    _require(isinstance(result.get("scenes"), list) and result["scenes"],
             "scenes must be a non-empty list")
    seg_bounds = context["segment_bounds"]  # {seg_id: [start_ms, end_ms]}
    max_cover = context["max_cover_ms"]
    min_gap = context["min_gap_ms"]
    seen_ids: set[str] = set()
    used_segs: set[str] = set()
    spans = []
    for sc in result["scenes"]:
        for key in ("id", "segment_ids", "visual_intent", "queries"):
            _require(key in sc, f"overlay scene missing key: {key}")
        _require(sc["id"] not in seen_ids, f"duplicate scene id: {sc['id']}")
        seen_ids.add(sc["id"])
        _require(isinstance(sc["segment_ids"], list) and sc["segment_ids"],
                 f"{sc['id']}: segment_ids must be a non-empty list")
        for sid in sc["segment_ids"]:
            _require(sid in seg_bounds, f"{sc['id']}: unknown segment {sid}")
            _require(sid not in used_segs, f"segment {sid} in multiple overlays")
            used_segs.add(sid)
        _require(isinstance(sc["visual_intent"], str) and sc["visual_intent"].strip(),
                 f"{sc['id']}: visual_intent must be a non-empty string")
        _require(isinstance(sc["queries"], list) and sc["queries"]
                 and all(isinstance(q, str) and q.strip() for q in sc["queries"]),
                 f"{sc['id']}: queries must be a non-empty list of strings")
        start = min(seg_bounds[s][0] for s in sc["segment_ids"])
        end = max(seg_bounds[s][1] for s in sc["segment_ids"])
        _require(end - start <= max_cover,
                 f"{sc['id']}: overlay {end - start}ms exceeds max cover "
                 f"{max_cover}ms — never fully cover the speaker that long")
        spans.append((start, end, sc["id"]))
    spans.sort()
    for (s1, e1, id1), (s2, e2, id2) in zip(spans, spans[1:]):
        _require(s2 - e1 >= min_gap,
                 f"{id1}→{id2}: only {s2 - e1}ms of original footage between "
                 f"overlays — must return to the speaker for >= {min_gap}ms")


def require_archive_queries(result: dict) -> None:
    """Archive-first: searches for ONE clean full-length upload of the event,
    offered to every scene. Optional — some pieces have no single event — but
    if present it must be usable, because `archive_candidates` feeds it
    straight into search."""
    aq = result.get("archive_queries")
    if aq is None:
        return
    _require(isinstance(aq, list)
             and all(isinstance(q, str) and q.strip() for q in aq),
             "archive_queries must be a list of non-empty strings")


def require_moment(scene: dict, label: str) -> None:
    """Which PART of a long upload to cut from. Optional, but a typo would
    silently fall back to 'any' and send every action scene to the tail."""
    if "moment" in scene:
        _require(scene["moment"] in ("action", "talking", "any"),
                 f"{label}: moment must be action|talking|any, "
                 f"got {scene['moment']!r}")


# The relevance ladder (SOURCING.md). Core doctrine, not split's: every mode
# that sources footage judges candidates on it.
RELEVANCE_TIERS = ("exact", "subject", "topic", "generic", "wrong")
ACCEPTABLE_TIERS = ("exact", "subject", "topic")


def validate_select_clip(result: dict, context: dict) -> None:
    """Shortlist verdict: pick the strongest of N candidates, or none.

    See SOURCING.md. `choice` indexes the shortlist; null means nothing was
    usable. A chosen clip must carry an acceptable tier — the engine refuses to
    ingest something the judge itself called generic or wrong.
    """
    n = context.get("shortlist_size", 0)
    choice = result.get("choice")
    _require(choice is None or (isinstance(choice, int) and 0 <= choice < n),
             f"choice must be null or an int 0-{n - 1}, got {choice!r}")
    _require(isinstance(result.get("reason"), str) and result["reason"].strip(),
             "reason must be a non-empty string")
    if choice is None:
        return
    tier = result.get("tier")
    _require(tier in RELEVANCE_TIERS,
             f"tier must be one of {RELEVANCE_TIERS}, got {tier!r}")
    _require(tier in ACCEPTABLE_TIERS,
             f"chose candidate {choice} but tier '{tier}' is a reject tier — "
             "pick an acceptable candidate or set choice to null")
    conf = result.get("confidence")
    _require(isinstance(conf, int) and 0 <= conf <= 100,
             "confidence must be an int 0-100")
    for key in ("best_start_ms", "best_end_ms"):
        if result.get(key) is not None:
            _require(isinstance(result[key], int) and result[key] >= 0,
                     f"{key} must be a non-negative int (ms)")
    # Optional: a risk the low-res storyboard preview cannot resolve — a thin
    # lower-third, a corner watermark, motion the tile froze past. The judge
    # names it here instead of silently accepting; an autonomous run then holds
    # the pick for a human to confirm on the deep-link rather than shipping it.
    if result.get("caution") is not None:
        _require(isinstance(result["caution"], str) and result["caution"].strip(),
                 "caution must be a non-empty string when present")


def validate_verify_clip(result: dict) -> None:
    conf = result.get("confidence")
    _require(isinstance(conf, int) and 0 <= conf <= 100,
             "confidence must be an int 0-100")
    _require(isinstance(result.get("reason"), str) and result["reason"].strip(),
             "reason must be a non-empty string")
    for key in ("best_start_ms", "best_end_ms"):
        if key in result and result[key] is not None:
            _require(isinstance(result[key], int) and result[key] >= 0,
                     f"{key} must be a non-negative int (ms)")


VALIDATORS = {
    "write_script": lambda result, context: validate_write_script(result),
    "scene_breakdown": validate_scene_breakdown,
    "visual_plan": validate_visual_plan,
    "replace_plan": validate_replace_plan,
    "select_clip": validate_select_clip,
    "verify_clip": lambda result, context: validate_verify_clip(result),
}


def validate(task_type: str, result: dict, context: dict | None = None) -> None:
    if task_type not in VALIDATORS:
        raise SchemaError(f"unknown task type: {task_type}")
    VALIDATORS[task_type](result, context or {})
