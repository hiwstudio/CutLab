"""ASSEMBLY's AI-task schema, registered into the core validator registry."""
from __future__ import annotations

from mixfix.ai.schemas import VALIDATORS, _require


def validate_assembly_plan(result: dict, context: dict) -> None:
    """ASSEMBLY plan: which windows of ONE source episode make the cut, and the
    single promise they pay off.

    Windows are expressed as caption segment ids, never as raw timestamps, and
    the times are derived from those segments downstream. That is the whole
    reason this contract exists: a hand-typed millisecond opens mid-sentence,
    and a window that opens mid-sentence reads as a broken upload no matter how
    good the moment inside it is.

    Unlike replace_plan and split_plan there is no coverage requirement — the
    point of an assembly is that most of the episode is LEFT OUT.
    """
    _require(isinstance(result.get("title"), str) and result["title"].strip(),
             "title must be a non-empty string — it is the promise the "
             "assembly pays off, and every window has to serve it")
    _require(isinstance(result.get("windows"), list) and result["windows"],
             "windows must be a non-empty list")

    order = context["segment_order"]          # segment id -> position in the episode
    bounds = context["segment_bounds"]        # segment id -> [start_ms, end_ms]
    min_window_ms = context["min_window_ms"]
    min_total_ms = context["min_total_ms"]
    max_total_ms = context["max_total_ms"]

    seen_ids: set[str] = set()
    used_segments: set[str] = set()
    spans: list[tuple[int, int, str]] = []

    for w in result["windows"]:
        for key in ("id", "segment_ids", "why"):
            _require(key in w, f"window missing key: {key}")
        wid = w["id"]
        _require(wid not in seen_ids, f"duplicate window id: {wid}")
        seen_ids.add(wid)
        _require(isinstance(w["segment_ids"], list) and w["segment_ids"],
                 f"{wid}: segment_ids must be a non-empty list")
        _require(isinstance(w["why"], str) and w["why"].strip(),
                 f"{wid}: why must be a non-empty string — name what this "
                 f"window contributes to the promise in the title")

        positions = []
        for sid in w["segment_ids"]:
            _require(sid in bounds, f"{wid}: unknown segment {sid}")
            _require(sid not in used_segments,
                     f"segment {sid} appears in more than one window")
            used_segments.add(sid)
            positions.append(order[sid])

        # A window is one continuous stretch of the episode. Scattered segment
        # ids would stitch together half-sentences from minutes apart and the
        # audio would jump-cut mid-breath.
        _require(sorted(positions) == list(range(min(positions), max(positions) + 1)),
                 f"{wid}: segment_ids must be consecutive in the episode "
                 f"(got {len(positions)} segments spanning "
                 f"{max(positions) - min(positions) + 1} positions)")

        start = min(bounds[s][0] for s in w["segment_ids"])
        end = max(bounds[s][1] for s in w["segment_ids"])
        _require(end > start, f"{wid}: end before start")
        _require(end - start >= min_window_ms,
                 f"{wid}: {(end - start) / 1000:.1f}s is shorter than the "
                 f"{min_window_ms / 1000:.0f}s minimum — a window that short "
                 f"is a soundbite, not a segment of an assembly")
        spans.append((start, end, wid))

    spans.sort()
    for (a_start, a_end, a_id), (b_start, b_end, b_id) in zip(spans, spans[1:]):
        _require(b_start >= a_end, f"{a_id} and {b_id} overlap in the source")

    total = sum(e - s for s, e, _ in spans)
    _require(min_total_ms <= total <= max_total_ms,
             f"assembled runtime {total / 60000:.1f} min is outside the "
             f"{min_total_ms / 60000:.0f}-{max_total_ms / 60000:.0f} min band "
             f"(windows: {len(spans)})")

    _validate_hook(result, context, order, bounds, spans)


def _validate_hook(result: dict, context: dict, order: dict, bounds: dict,
                   spans: list[tuple[int, int, str]]) -> None:
    """The teaser lifted to the front of the video.

    It plays twice — once cold, once in its natural place — so it must come from
    inside the section. A teaser promising something the video never delivers is
    punished at the exact moment the viewer notices.
    """
    hook = result.get("hook")
    _require(isinstance(hook, dict), "hook is required — the video opens on it")
    for key in ("segment_ids", "why"):
        _require(key in hook, f"hook missing key: {key}")
    _require(isinstance(hook["segment_ids"], list) and hook["segment_ids"],
             "hook.segment_ids must be a non-empty list")
    _require(isinstance(hook["why"], str) and hook["why"].strip(),
             "hook.why must say what makes this line stop a scroll")

    positions = []
    for sid in hook["segment_ids"]:
        _require(sid in bounds, f"hook: unknown segment {sid}")
        positions.append(order[sid])
    _require(sorted(positions) == list(range(min(positions), max(positions) + 1)),
             "hook.segment_ids must be consecutive — a hook spliced from "
             "non-adjacent lines is not a thing anybody actually said")

    h_start = min(bounds[s][0] for s in hook["segment_ids"])
    h_end = max(bounds[s][1] for s in hook["segment_ids"])
    dur = h_end - h_start
    lo, hi = context["hook_min_ms"], context["hook_max_ms"]
    _require(lo <= dur <= hi,
             f"hook is {dur / 1000:.1f}s, outside the {lo / 1000:.0f}-"
             f"{hi / 1000:.0f}s band — too short does not land, too long stops "
             f"being a teaser and becomes the video starting twice")

    # Inside a selected window, not merely inside the episode.
    host = next((wid for s, e, wid in spans if s <= h_start and h_end <= e), None)
    _require(host is not None,
             "hook must fall entirely inside ONE selected window — it is lifted "
             "from the section, never from material that was cut")

    # Distance from the top of the body. A hook pulled from the first minute
    # replays within a minute of itself and reads as a stutter, not a callback.
    body_offset, depth = 0, None
    for s, e, wid in spans:
        if s <= h_start <= e:
            depth = body_offset + (h_start - s)
            break
        body_offset += e - s
    need = context["hook_min_depth_ms"]
    _require(depth is not None and depth >= need,
             f"hook sits {(depth or 0) / 1000:.0f}s into the body, less than the "
             f"{need / 1000:.0f}s minimum — pull it from deeper so the teaser "
             f"and its natural placement are not on top of each other")


VALIDATORS["assembly_plan"] = validate_assembly_plan


def validate_insert_plan(result: dict, context: dict) -> None:
    """ASSEMBLY cutaway plan: a HANDFUL of inserts over the cut.

    Deliberately unlike replace_plan, which covers wherever it usefully can.
    Here the source plays essentially untouched and a small number of moments
    get a picture change — enough that the video is produced rather than a flat
    lift, not so much that it stops feeling like the podcast.

    Result shape is the union of the scene contract (so timing.attach_scenes
    takes it) and the visual plan contract (so research_extract,
    generate_visuals and the timeline take it) — one plan, three consumers.
    """
    scenes = result.get("scenes")
    _require(isinstance(scenes, list) and scenes, "scenes must be a non-empty list")
    lo, hi = context["min_inserts"], context["max_inserts"]
    _require(lo <= len(scenes) <= hi,
             f"{len(scenes)} cutaways is outside the {lo}-{hi} band — this "
             f"format is sparse on purpose")

    bounds = context["segment_bounds"]
    max_cover_ms = context["max_cover_ms"]
    min_gap_ms = context["min_gap_ms"]
    hook_ms = context["hook_ms"]

    seen: set[str] = set()
    used: set[str] = set()
    spans: list[tuple[int, int, str]] = []

    for sc in scenes:
        for key in ("id", "segment_ids", "visual_intent", "visual_type"):
            _require(key in sc, f"cutaway missing key: {key}")
        sid = sc["id"]
        _require(sid not in seen, f"duplicate cutaway id: {sid}")
        seen.add(sid)
        _require(isinstance(sc["segment_ids"], list) and sc["segment_ids"],
                 f"{sid}: segment_ids must be a non-empty list")
        _require(isinstance(sc["visual_intent"], str) and sc["visual_intent"].strip(),
                 f"{sid}: visual_intent must say what appears on screen")
        for s in sc["segment_ids"]:
            _require(s in bounds, f"{sid}: unknown segment {s}")
            _require(s not in used, f"segment {s} used by more than one cutaway")
            used.add(s)

        start = min(bounds[s][0] for s in sc["segment_ids"])
        end = max(bounds[s][1] for s in sc["segment_ids"])
        # A SOURCED clip earns a longer ceiling than a generated one: real
        # footage needs room to read, and few-but-longer is deliberately cheaper
        # than many-but-short (one fetch instead of three). Generated visuals
        # keep the tight ceiling — a still held for 20s is dead air.
        cap = (context.get("sourced_max_ms", max_cover_ms)
               if sc.get("visual_type") == "video" else max_cover_ms)
        _require(end - start <= cap,
                 f"{sid}: covers {(end - start) / 1000:.1f}s, over the "
                 f"{cap / 1000:.0f}s ceiling for a "
                 f"{sc.get('visual_type')} cutaway")
        # The hook is a straight lift. Production on top of the teaser softens
        # the jolt that makes it work.
        _require(start >= hook_ms,
                 f"{sid}: starts inside the {hook_ms / 1000:.0f}s hook — the "
                 f"cold open plays raw")
        spans.append((start, end, sid))

        vt = sc["visual_type"]
        # "image" is MIX's legacy single-still type and NOTHING in the assembly
        # render path consumes it: generate_visuals only builds montages for
        # "generate", so an image cutaway validates, plans, and then silently
        # renders nothing. That cost a real video 5 of its 13 cutaways. Reject it
        # here rather than let it disappear — a one-shot still is a "generate"
        # with a single segment.
        _require(vt in ("video", "generate"),
                 f"{sid}: visual_type must be video or generate, got {vt!r}"
                 + (" — 'image' is legacy and never renders in this mode; use "
                    "'generate' with a single segment for a one-shot still"
                    if vt == "image" else ""))
        if vt == "video":
            _require(isinstance(sc.get("queries"), list) and sc["queries"]
                     and all(isinstance(q, str) and q.strip() for q in sc["queries"]),
                     f"{sid}: a sourced cutaway needs a non-empty queries list")
        elif vt == "image":
            _require(isinstance(sc.get("image_prompt"), str)
                     and len(sc["image_prompt"].strip()) >= 20,
                     f"{sid}: an image cutaway needs image_prompt (>=20 chars)")
        else:
            segs = sc.get("segments")
            _require(isinstance(segs, list) and segs,
                     f"{sid}: a generated cutaway needs a non-empty segments list")
            prev = -1
            for j, s in enumerate(segs):
                _require(isinstance(s, dict), f"{sid} seg {j}: must be an object")
                st = s.get("start_ms")
                _require(isinstance(st, int) and st > prev,
                         f"{sid} seg {j}: start_ms must be an ascending int")
                _require(start <= st < end,
                         f"{sid} seg {j}: start_ms {st} outside the cutaway "
                         f"[{start},{end})")
                prev = st
                _require(isinstance(s.get("delta"), str)
                         and len(s["delta"].strip()) >= 15,
                         f"{sid} seg {j}: delta must describe the shot (>=15 chars)")
            _require(segs[0]["start_ms"] == start,
                     f"{sid}: first generated segment must start at the cutaway "
                     f"start ({start}ms), got {segs[0]['start_ms']}")

    # Hard budget on SOURCED cutaways. Every one is a YouTube search plus a
    # range-fetch, and range-fetches are the slow, throttle-prone part of the
    # whole pipeline — a plan full of them cannot finish on a rate-limited link.
    # Generated visuals cost no YouTube bandwidth, so the plan is allowed to be
    # dense as long as only a few of them come off the network.
    max_sourced = context.get("max_sourced")
    if max_sourced is not None:
        n_video = sum(1 for sc in scenes if sc["visual_type"] == "video")
        _require(n_video <= max_sourced,
                 f"{n_video} sourced (video) cutaways is over the "
                 f"{max_sourced} budget — sourcing is the slow half; use "
                 f"image/generate for the rest and spend the sourced slots on "
                 f"moments where real footage genuinely matters")

    if any(sc["visual_type"] == "generate" for sc in scenes):
        _require(isinstance(result.get("style_lock"), str)
                 and len(result["style_lock"].strip()) >= 60,
                 "style_lock is required when any cutaway is generated — it is "
                 "the byte-identical block prepended to every prompt, and "
                 "without it the generated shots drift apart visually")

    spans.sort()
    for (a_s, a_e, a_id), (b_s, b_e, b_id) in zip(spans, spans[1:]):
        _require(b_s - a_e >= min_gap_ms,
                 f"{a_id} and {b_id} are {(b_s - a_e) / 1000:.1f}s apart, under "
                 f"the {min_gap_ms / 1000:.0f}s minimum — the original has to "
                 f"return between cutaways")


VALIDATORS["insert_plan"] = validate_insert_plan
