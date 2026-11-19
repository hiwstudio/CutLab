"""MIX pipeline — intake → script → voiceover → timing → scenes → visual plan →
research/extract.

Each stage is idempotent and returns 'done' or 'paused'. The orchestrator runs
stages in sequence; a pause exits cleanly (resume with `mixfix run`).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import shutil

from . import (assemble, generate, match, modes, qa as qamod,
               timeline as tlmod, timing)
from .tools import FFMPEG
from .ai.router import Router
from .ai.schemas import SchemaError
from .library import (MIN_SOURCE_HEIGHT, Library, clip_duration_ms,
                      clip_height, sample_frames)
from .preview import ensure_gate
from .research import ResearchError, cut_section, is_offline_error, make_source
from .state import State

MIX_STAGES = ["intake", "script", "voiceover", "timing_map", "scenes",
              "visual_plan", "research_extract", "generate_visuals", "timeline",
              "assemble", "render_qa", "export"]
FIX_STAGES = ["fix_intake", "timing_map", "fix_shots", "replace_plan",
              "research_extract", "timeline", "assemble", "render_qa", "export"]
# Which config.yaml sections each stage actually reads. Drives the node
# parameter editor — without it every node would offer every knob in the file.
STAGE_KNOBS = {
    "timing_map": ["transcriber", "whisper_model"],
    "research_extract": ["research"],
    "generate_visuals": ["render"],
    "replace_plan": ["fix"],
    "assemble": ["render"],
    "render_qa": ["render", "qa"],
    "export": ["render"],
}
CONFIDENCE_THRESHOLD = 70
MAX_CANDIDATES_PER_SCENE = 4
# How many candidates get downloaded and judged together. Editors pick from the
# 3rd-4th search result on average and prefer browsing a shortlist to a single
# automated pick (B-Script, arXiv 1902.11216) — see SOURCING.md.
SHORTLIST_SIZE = 3
# Where the post-fight/outro tail of a long upload begins, as a fraction of
# runtime. Measured: the three windows that wrongly landed on talking instead
# of action sat at 93%, 95% and 96.5%; good action windows sat at 36% and 59%.
TAIL_FRACTION = 0.80
# 11-char YouTube id, wherever it appears in a watch/short/youtu.be URL
_VIDEO_ID = re.compile(r"(?:v=|be/|shorts/|embed/)([\w-]{11})")


def merge_params(cfg: dict, params: dict) -> dict:
    """config.yaml with a stage's parameters overlaid — nested, non-mutating.

    A shallow update would drop the rest of a section: overriding
    `render.transition_s` would take `width`, `height` and `fps` with it.
    """
    if not params:
        return cfg
    out = dict(cfg)
    for k, v in params.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_params(out[k], v)
        else:
            out[k] = v
    return out


def burn_candidate(err: object) -> bool:
    """Should this fetch failure count against the candidate?

    A timeout is never evidence about the footage. It used to be treated as the
    candidate's fault ("a stalled CDN read on that window") and only a *streak*
    was blamed on the link — but that premise is measurably wrong here. YouTube
    throttles by request RATE: windows that timed out at 300s inside a run were
    each fetched in 35-54s by an out-of-band pre-fetch, unchanged, minutes later
    (`lessons/youtube-throttling.md`). Burning on the first timeouts therefore
    shredded candidate lists for a reason no candidate caused — scene_005 of
    voyager-1 reached `exhausted` without a single frame ever being judged.

    So a timeout keeps the candidate and a later run retries it, warmed by
    `prefetch_clips.py`. Only a definite failure (bad format, unavailable video)
    counts against the footage; true offline signals never do.

    This also retires the consecutive-timeout streak counter entirely. It only
    ever existed to decide when a timeout stopped counting against a candidate;
    now that a timeout never counts, the counter was dead state whose only
    remaining behaviour was the latching bug it kept being patched for.

    ponytail: a permanently unfetchable window now retries every run instead of
    being dropped. That is the safer failure — it is visible in the log and the
    operator can hand-pick — but if it ever loops noisily, track attempts per
    candidate in progress.json and burn after N runs rather than N seconds.
    """
    if is_offline_error(err) or "timed out after" in str(err).lower():
        return False
    return True


def window_fraction(cand: dict) -> float | None:
    """How far into its upload a window starts, 0..1. None when unknown."""
    try:
        dur = float(cand.get("duration_s") or 0)
    except (TypeError, ValueError):
        return None
    if dur <= 0:
        return None
    return (cand["clip_start_ms"] / 1000.0) / dur


# One score, not a stack of partitions. Four separate ordering rules grew here —
# position, archive, depth, lexical — and each new one needed a hand-written rule
# for composing with the others (prefer_shallow had to be taught about `moment`
# so it would stop undoing prefer_position). Weights make the dominance order a
# single visible fact instead of an emergent property of call order.
#
#   right EVENT  >  right PART of it  >  fetchable  >  lexical similarity
#
# The gap is deliberate: no amount of lexical score can outrank being from the
# archive, and nothing but the archive can outrank being in the right part of
# the upload.
ARCHIVE_WEIGHT = 100.0
POSITION_WEIGHT = 10.0


def position_score(cand: dict, moment: str) -> float:
    """1.0 when the window sits in the part of the upload the scene wants.

    A full-length upload is entrances, then the event, then post-event
    interviews. The words a talking-head source uses ABOUT an event are spoken in
    that tail, not over the action — so lexical ranking alone sends action scenes
    to the closing interview every time (measured: 93%, 95%, 96.5%).

    Unknown duration scores 1.0: never penalise on a guess.
    """
    if moment not in ("action", "talking"):
        return 1.0
    f = window_fraction(cand)
    if f is None:
        return 1.0
    in_tail = f >= TAIL_FRACTION
    return 1.0 if (in_tail if moment == "talking" else not in_tail) else 0.0


def candidate_score(cand: dict, moment: str = "any",
                    archive_ids: frozenset | set = frozenset()) -> float:
    """Total order over candidate windows. Higher is better.

    There is deliberately no depth term. One existed while whole uploads were
    downloaded and a deep seek was expensive, but windows are range-fetched now
    and depth costs nothing — measured on the same upload, a window 25 minutes in
    arrived in 36s/1.97MB against 69s/1.84MB for one 10 minutes in. Keeping the
    penalty would bias every scene toward the opening of an upload, which is
    titles and intros, and fight the archive-first doctrine that wants the body.
    """
    lexical = float(cand.get("score") or 0.0)   # cosine in [0,1]: last tie-break
    return (ARCHIVE_WEIGHT * (1.0 if cand.get("video_id") in archive_ids else 0.0)
            + POSITION_WEIGHT * position_score(cand, moment)
            + lexical)


def order_candidates(ranked: list[dict], moment: str = "any",
                     archive_ids: frozenset | set = frozenset()) -> list[dict]:
    """Sort by candidate_score, stably — equal scores keep the ranker's order.

    Nothing is ever dropped: a scene the archive cannot cover still falls through
    to search results, and a scene with only deep windows still gets them.
    """
    return sorted(ranked, key=lambda c: -candidate_score(c, moment, archive_ids))


def _apply_subrange(verdict: dict, staging: Path, scene: dict,
                    report: list, say, sid: str) -> Path:
    """Re-cut a staged clip to the verdict's `best_start_ms`/`best_end_ms`.

    The select_clip/verify_clip schemas ask for an optional tighter sub-range,
    measured from the staged clip's own start — "start after the burned-in
    title card", "stop before it turns into a labelled science plot". The field
    was validated and then silently dropped, so those judgements had no effect
    on the cut and the offending frames shipped anyway.

    Only applied when the sub-range still fills the scene slot. A shorter cut
    would leave the scene under-covered, and the reviewer asked to avoid PART
    of the clip, not to shorten the film.
    """
    b0, b1 = verdict.get("best_start_ms"), verdict.get("best_end_ms")
    if b0 is None or b1 is None or b1 <= b0:
        return staging
    need = scene["end_ms"] - scene["start_ms"]
    if b1 - b0 < need:
        say(report, f"{sid}: sub-range {b0}-{b1}ms ignored — shorter than the "
                    f"{need}ms slot, which would leave the scene uncovered")
        return staging
    cut = staging.with_name(staging.stem + f"_sub{b0}-{b1}.mp4")
    if not cut.exists():
        try:
            cut_section(staging, cut, b0, b1)
        except subprocess.CalledProcessError:
            cut.unlink(missing_ok=True)
            return staging
    if not _playable(cut):
        cut.unlink(missing_ok=True)
        return staging
    say(report, f"{sid}: cut to requested sub-range {b0}-{b1}ms")
    return cut


def _deep_link(url: str, start_ms: int) -> str:
    """A YouTube link that opens AT the window — so the human's check is a click
    on the exact moment, not a scrub through the whole video."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={max(0, start_ms // 1000)}"


def _playable(path: Path) -> bool:
    """True if the file is a real, decodable clip with a duration.

    Container metadata is not enough: an interrupted download can leave a valid
    moov atom over corrupt H.264 ("Invalid NAL unit size"), which passes a size
    and duration check and then breaks frame extraction downstream. Decode the
    whole thing — ~0.5s for a 480p section clip, far cheaper than spending a
    download slot and an AI verification on a file that cannot be used."""
    try:
        if path.stat().st_size <= 10_000 or clip_duration_ms(path) <= 0:
            return False
    except Exception:
        return False
    return subprocess.run(
        [FFMPEG, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        capture_output=True).returncode == 0


class Pipeline:
    def __init__(self, state: State, router: Router, cfg: dict,
                 run_id: str, project_dir: Path, mode: str = "mix"):
        self.state = state
        self.router = router
        self.cfg = cfg
        self.run_id = run_id
        self.project_dir = project_dir
        self.mode = mode
        self.messages: list[str] = []

    def say(self, msg: str) -> None:
        self.messages.append(msg)
        print(msg)

    # ---- stages ----
    def stage_intake(self) -> str:
        topic_file = self.project_dir / "input" / "topic.json"
        if not topic_file.exists():
            self.say(f"PAUSED — create {topic_file} with at least "
                     '{"topic": "..."} (optionally research, angle, facts).')
            return "paused"
        topic = json.loads(topic_file.read_text(encoding="utf-8"))
        if not topic.get("topic"):
            self.say(f"PAUSED — {topic_file} needs a non-empty \"topic\" field.")
            return "paused"
        self.state.stage_finish(self.run_id, "intake", "done", {"topic": topic["topic"]})
        return "done"

    def stage_script(self) -> str:
        topic = json.loads(
            (self.project_dir / "input" / "topic.json").read_text(encoding="utf-8"))
        try:
            result = self.router.fulfill(
                self.run_id, "script", "write_script", payload=topic)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "script", "write_script")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"
        vo = self.project_dir / "voiceover"
        vo.mkdir(parents=True, exist_ok=True)
        (vo / "elevenlabs_script.txt").write_text(
            result["elevenlabs_script"], encoding="utf-8")
        (vo / "aistudio_script.txt").write_text(
            result["aistudio_script"], encoding="utf-8")
        (vo / "narration.txt").write_text(result["narration"], encoding="utf-8")
        self.state.stage_finish(self.run_id, "script", "done",
                                {"scripts": ["elevenlabs", "aistudio"]})
        self.say(f"Voiceover scripts written to {vo}/")
        return "done"

    def stage_voiceover(self) -> str:
        voice = self.project_dir / "voiceover" / "voice.mp3"
        if not voice.exists():
            self.say(f"PAUSED — generate the voiceover externally "
                     f"(ElevenLabs / Google AI Studio) and save it as {voice}")
            return "paused"
        digest = hashlib.sha1(voice.read_bytes()).hexdigest()
        self.state.add_asset(digest, self.run_id, "voiceover", "voiceover",
                             str(voice))
        self.state.stage_finish(self.run_id, "voiceover", "done", {"sha1": digest})
        return "done"

    def stage_timing_map(self) -> str:
        voice = self.project_dir / "voiceover" / "voice.mp3"
        tmap = timing.transcribe(voice, self.cfg, self.project_dir)
        out = self.project_dir / "timing" / "timing_map.json"
        timing.save(tmap, out)
        digest = hashlib.sha1(out.read_bytes()).hexdigest()
        self.state.add_asset(digest, self.run_id, "timing_map", "timing_map",
                             str(out), {"segments": len(tmap["segments"])})
        self.state.stage_finish(self.run_id, "timing_map", "done",
                                {"segments": len(tmap["segments"]),
                                 "duration_ms": tmap["source"]["duration_ms"]})
        self.say(f"Timing Map validated: {len(tmap['segments'])} segments, "
                 f"{tmap['source']['duration_ms']}ms")
        return "done"

    def stage_scenes(self) -> str:
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        payload = {
            "segments": [{"id": s["id"], "text": s["text"],
                          "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                         for s in tmap["segments"]],
        }
        context = {"segment_ids": [s["id"] for s in tmap["segments"]]}
        try:
            result = self.router.fulfill(
                self.run_id, "scenes", "scene_breakdown",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "scenes", "scene_breakdown")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"
        tmap = timing.attach_scenes(tmap, result)
        timing.save(tmap, self.project_dir / "timing" / "timing_map.json")
        self.state.stage_finish(self.run_id, "scenes", "done",
                                {"scenes": len(tmap["scenes"])})
        self.say(f"Scenes layer attached: {len(tmap['scenes'])} scenes")
        return "done"

    def stage_visual_plan(self) -> str:
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        prefs = {}
        prefs_file = self.project_dir / "input" / "topic.json"
        if prefs_file.exists():
            prefs = json.loads(prefs_file.read_text(encoding="utf-8")).get(
                "visual_preferences", "decide")
        topic = {}
        if prefs_file.exists():
            t = json.loads(prefs_file.read_text(encoding="utf-8"))
            topic = {k: t.get(k) for k in ("topic", "angle") if t.get(k)}
        segmap = {s["id"]: s for s in tmap["segments"]}
        payload = {
            "visual_preferences": prefs,
            "project": topic,
            "scenes": [{"id": sc["id"],
                        "text": " ".join(
                            s["text"] for s in tmap["segments"]
                            if s["id"] in sc["segment_ids"]),
                        "visual_intent": sc["visual_intent"],
                        "start_ms": sc["start_ms"], "end_ms": sc["end_ms"],
                        "duration_ms": sc["end_ms"] - sc["start_ms"],
                        # segment-level timing so 'generate' beats can be placed
                        "segments": [{"start_ms": segmap[i]["start_ms"],
                                      "end_ms": segmap[i]["end_ms"],
                                      "text": segmap[i]["text"]}
                                     for i in sc["segment_ids"]]}
                       for sc in tmap["scenes"]],
        }
        context = {"scene_ids": [sc["id"] for sc in tmap["scenes"]],
                   "scene_bounds": {sc["id"]: [sc["start_ms"], sc["end_ms"]]
                                    for sc in tmap["scenes"]}}
        try:
            result = self.router.fulfill(
                self.run_id, "visual_plan", "visual_plan",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "visual_plan", "visual_plan")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"
        plan_path = self.project_dir / "research" / "visual_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        prompts_dir = self.project_dir / "imagery" / "prompts"
        n_img = 0
        for p in result["plans"]:
            if p["visual_type"] == "image":  # legacy single-still
                prompts_dir.mkdir(parents=True, exist_ok=True)
                (prompts_dir / f"{p['scene_id']}.txt").write_text(
                    p["image_prompt"], encoding="utf-8")
                n_img += 1
        gen = [p for p in result["plans"] if p["visual_type"] == "generate"]
        if gen:
            generate.emit_flowdeck_jobs(
                self.project_dir, result, result.get("style_lock", ""))
        vid = sum(1 for p in result["plans"] if p["visual_type"] == "video")
        self.state.stage_finish(
            self.run_id, "visual_plan", "done",
            {"plans": len(result["plans"]), "video": vid, "generate": len(gen)})
        self.say(f"Visual plan ready: {len(result['plans'])} scenes — "
                 f"{vid} stock-video, {len(gen)} custom-generate"
                 + (f", {n_img} single-image" if n_img else ""))
        if gen:
            self.say(f"  FlowDeck jobs written to "
                     f"{prompts_dir} for {len(gen)} generate scene(s).")
        return "done"

    def stage_generate_visuals(self) -> str:
        """Build montage clips for 'generate' scenes from dropped images.
        No-op when the plan has no generate scenes. Pauses (with the FlowDeck
        jobs written) for any scene whose images haven't been dropped yet."""
        plan_path = self.project_dir / "research" / "visual_plan.json"
        if not plan_path.exists():
            self.state.stage_finish(self.run_id, "generate_visuals", "done", {})
            return "done"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        gen = [p for p in plan["plans"] if p.get("visual_type") == "generate"]
        if not gen:
            self.state.stage_finish(self.run_id, "generate_visuals", "done",
                                    {"generated": 0})
            return "done"
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        scmap = {s["id"]: s for s in tmap["scenes"]}
        library = Library(self.state, Path(self.cfg["root"]) / "library")
        r = self.cfg["render"]
        w, h, fps = r["width"], r["height"], r["fps"]
        trans = int(float(r.get("transition_s", 0.4)) * 1000)
        mdir = self.project_dir / "assembly" / "montages"
        mdir.mkdir(parents=True, exist_ok=True)
        built, waiting = 0, []
        for p in gen:
            sid = p["scene_id"]
            sc = scmap[sid]
            if sc.get("assets"):  # already built (idempotent resume)
                continue
            imgs = generate.scene_images(self.project_dir, sid, len(p["segments"]))
            if imgs is None:
                # Generate them rather than stopping to ask a human for images.
                # The FlowDeck hand-off below now only applies when this fails.
                g = self.cfg.get("generate", {})
                made, err = generate.ensure_images(
                    self.project_dir, p, plan.get("style_lock", ""),
                    g.get("image_tool", ""), g.get("image_model", ""))
                if made:
                    self.say(f"  {sid}: generated {made} image(s)")
                if err:
                    self.say(f"  {sid}: image generation stopped — {err}")
                imgs = generate.scene_images(self.project_dir, sid,
                                             len(p["segments"]))
            if imgs is None:
                waiting.append((sid, len(p["segments"])))
                continue
            durs = generate.montage_durations(p["segments"], sc["end_ms"])
            out = mdir / f"{sid}.mp4"
            if out.exists():
                out.unlink()
            assemble.build_scene_montage(imgs, durs, out, w, h, fps, trans)
            ing = library.ingest_clip(out, self.run_id, {
                "scene_id": sid, "source_url": "custom-generated (Google Flow)",
                "source_title": f"{len(imgs)} custom images", "channel": "custom",
                "clip_start_ms": 0, "clip_end_ms": sc["end_ms"] - sc["start_ms"],
                "confidence": 100})
            sc["assets"] = [{"asset_id": ing["asset_id"], "kind": "clip",
                             "path": ing["path"], "confidence": 100}]
            built += 1
            self.say(f"  {sid}: {len(imgs)} images → montage")
        timing.save(tmap, self.project_dir / "timing" / "timing_map.json")
        if waiting:
            generate.emit_flowdeck_jobs(
                self.project_dir, plan, plan.get("style_lock", ""))
            need = ", ".join(f"{s} ({n} imgs)" for s, n in waiting)
            self.say(
                f"PAUSED — {len(waiting)} scene(s) need generated images: {need}. "
                f"Run the FlowDeck jobs in {self.project_dir / 'imagery' / 'prompts'}, "
                f"drop the images into imagery/incoming/<scene_id>/ (named "
                f"<scene_id>_<n>), then rerun.")
            return "paused"
        self.state.stage_finish(self.run_id, "generate_visuals", "done",
                                {"generated": built})
        if built:
            self.say(f"Custom visuals built for {built} scene(s).")
        return "done"

    def proven_sources(self, limit: int = 12) -> list[dict]:
        """Channels whose footage has been accepted before, newest first.

        The engine gets better at sourcing by remembering what actually worked.
        No new storage: every accepted clip already writes its channel, title and
        tier into the asset's provenance, so this is a read over the library.
        """
        rows = self.state.conn.execute(
            "SELECT meta_json FROM assets WHERE kind='clip' AND meta_json IS NOT NULL"
            " ORDER BY created_at DESC LIMIT 200").fetchall()
        seen, out = set(), []
        for row in rows:
            try:
                meta = json.loads(row["meta_json"])
            except (TypeError, ValueError):
                continue
            channel = (meta.get("channel") or "").strip()
            if not channel or channel in seen:
                continue
            seen.add(channel)
            out.append({"channel": channel,
                        "example_title": meta.get("source_title", ""),
                        "tier": meta.get("tier", "")})
            if len(out) >= limit:
                break
        return out

    def _source_video_ids(self) -> set[str]:
        """The video this run is built FROM, so research never sources from it.

        FIX and SPLIT both start from an existing video, and a search for what
        the speaker is talking about very often ranks that same upload first —
        its transcript matches the narration perfectly, because it IS the
        narration. In SPLIT that puts identical footage in both panes; in FIX it
        covers the speaker with themselves. Cheap to exclude, expensive to catch
        by eye later.
        """
        url_file = self.project_dir / "input" / "source.txt"
        if not url_file.exists():
            return set()
        return set(_VIDEO_ID.findall(url_file.read_text(encoding="utf-8")))

    def archive_candidates(self, source, plan: dict, progress: dict,
                           exclude_ids: set) -> list[dict]:
        """Resolve the event's archive ONCE per run, not once per scene.

        Measured on the split-podcast pilot: two scenes were served by windows at
        160s and 457s of a single clean upload, while the scenes that searched
        independently kept landing in the derivative layer — reaction videos,
        phone captures of a television, re-uploads, talk-show segments. A popular
        event has a deep derivative ecosystem sitting on top of very few clean
        archives, so per-scene search rediscovers the junk every time.

        Editors work the other way round: find the archive, then pull every shot
        from it (SOURCING.md — Ken Burns / IDA archival practice). Cached in
        progress under `_archive` so a resume never re-searches.
        """
        queries = plan.get("archive_queries") or []
        if not queries:
            return []
        cached = progress.get("_archive")
        if cached is not None:
            return cached["candidates"]
        found: list[dict] = []
        for q in queries:
            for c in source.search(q, n=4):
                if c["video_id"] in exclude_ids:
                    continue
                if c["video_id"] not in {x["video_id"] for x in found}:
                    found.append(c)
        progress["_archive"] = {"queries": queries, "candidates": found}
        return found

    def _report(self, report: list, line: str) -> None:
        """Record and print immediately — a long research stage must not
        look like a hang while it works through scenes."""
        report.append(line)
        self.say("  " + line)

    def stage_research_extract(self) -> str:
        """Per video-scene: search → transcript-rank → extract top candidate →
        verify via AI task → accept into library or move to next candidate.
        Idempotent: verified scenes are skipped on resume; all pending verify
        tasks are raised before pausing so the operator can batch them."""
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        plan = json.loads((self.project_dir / "research" / "visual_plan.json")
                          .read_text(encoding="utf-8"))
        source, cache = make_source(self.cfg, self.state)
        library = Library(self.state, Path(self.cfg["root"]) / "library")
        rdir = self.project_dir / "research"
        progress_path = rdir / "progress.json"
        progress = (json.loads(progress_path.read_text(encoding="utf-8"))
                    if progress_path.exists() else {})
        scenes_by_id = {sc["id"]: sc for sc in tmap["scenes"]}
        exclude_ids = self._source_video_ids()
        waiting, report = [], []
        archive = self.archive_candidates(source, plan, progress, exclude_ids)
        if archive:
            self._report(report, f"archive: {len(archive)} full-length upload(s) "
                         "resolved once, offered to every scene")

        for p in plan["plans"]:
            if p["visual_type"] != "video":
                continue
            sid = p["scene_id"]
            scene = scenes_by_id[sid]
            st = progress.setdefault(sid, {"status": "new", "candidate_idx": 0,
                                           "candidates": []})
            if st["status"] == "accepted":
                continue
            try:
                if st["status"] in ("new",):
                    # A fresh search throws the old candidate list away, so any
                    # verify task still open against it can never be consumed.
                    self.router.queue.supersede(
                        self.run_id, f"research_extract:{sid}_",
                        f"{sid} re-searched with new queries")
                    # Archive first: the event's own clean upload is a candidate
                    # for EVERY scene, so one search serves the whole piece and
                    # the ranker picks each scene's window inside it.
                    candidates = list(archive)
                    transcripts = {}
                    for q in p["queries"]:
                        for c in source.search(q, n=4):
                            if c["video_id"] in exclude_ids:
                                continue  # never source from the run's own video
                            if c["video_id"] not in {x["video_id"] for x in candidates}:
                                candidates.append(c)
                    for c in candidates:
                        transcripts[c["video_id"]] = source.transcript(
                            c["video_id"], c["url"])
                    scene_text = " ".join(s["text"] for s in tmap["segments"]
                                          if s["id"] in scene["segment_ids"])
                    # Rank wider than we keep: the archive must survive the trim
                    # to be preferred, and the ranker trims internally.
                    # "illustrative" scenes only have to SHOW the thing that was
                    # named, so captionless footage is fair game and is ranked by
                    # title with a positional window. The default stays "exact":
                    # a scene that must show the event itself is confirmed by its
                    # transcript, and title-matching would let anything through.
                    ranked = match.rank_candidates(
                        {**scene, "text": scene_text}, candidates, transcripts,
                        top_k=MAX_CANDIDATES_PER_SCENE * 3,
                        allow_captionless=p.get("sourcing") == "illustrative")
                    # One ordering, one place: archive > position > depth >
                    # lexical, by weight rather than by call order.
                    ranked = order_candidates(
                        ranked, p.get("moment", "any"),
                        {c["video_id"] for c in archive}
                    )[:MAX_CANDIDATES_PER_SCENE]
                    if not ranked:
                        st["status"] = "no_candidates"
                        self._report(report, f"{sid}: no transcript-matched candidates — "
                                      "needs new queries or an image instead")
                        continue
                    st["candidates"] = ranked
                    st["status"] = "verifying"

                if st["status"] == "verifying":
                    # Build a SHORTLIST and judge it in one go. Auditioning one
                    # candidate per run turned a single decision into N rounds,
                    # and those rounds were the bottleneck (see SOURCING.md).
                    usable, files = [], {}
                    # Drops caused by the NETWORK are not evidence about the
                    # candidates. If the shortlist empties purely because fetches
                    # timed out, the scene must stay open and retry — marking it
                    # exhausted would burn a perfectly good candidate list over a
                    # bad five minutes of link.
                    fetch_failures = 0
                    # start at candidate_idx, not 0: the review board advances it
                    # when the user rejects or swaps a clip, and that scene must
                    # come back with different candidates, not the same shortlist
                    start = st["candidate_idx"]
                    # candidates were already ordered by candidate_score at rank
                    # time — depth is priced in there, so no second filter here
                    window = st["candidates"][start:start + SHORTLIST_SIZE]
                    # A clip the reviewer hand-picked or explicitly swapped to is
                    # a decision, not a suggestion. Fetch that one and judge only
                    # it — auditioning it against candidates they already passed
                    # over wastes downloads and re-opens a settled choice.
                    if window and (window[0].get("manual")
                                   or window[0].get("chosen")):
                        window = window[:1]
                    for i, cand in enumerate(window, start):
                        if cand["video_id"] in exclude_ids:
                            self._report(report, f"{sid}: c{i} skipped — same "
                                         "video as this run's source")
                            continue
                        # keyed by video id + window, never candidate index:
                        # re-queried scenes must not reuse a stale clip
                        clip_key = f"{sid}_{cand['video_id']}_{cand['clip_start_ms']}"
                        # STAGE 3 — a cheap visual gate that downloads NO window.
                        # Storyboard tiles (the scrubber previews, whole video in
                        # one ~200KB fetch) show whether the moment is the subject
                        # or a title card / talking head / watermark, which title
                        # and transcript cannot. The real window is fetched later,
                        # for the ONE candidate that wins — so a shortlist costs
                        # one board per video instead of N range-fetches, and the
                        # 245s window timeouts leave the sourcing loop entirely.
                        # A hand-picked/swapped clip is a decision, not a
                        # suggestion: skip the preview and fetch it directly.
                        staging, frames = None, []
                        handpicked = cand.get("manual") or cand.get("chosen")
                        if not handpicked:
                            frames = source.storyboard_tiles(
                                cand["url"], cand["video_id"],
                                cand["clip_start_ms"], cand["clip_end_ms"],
                                cand.get("duration_s"),
                                rdir / "staging" / f"{clip_key}_sb")
                        if not frames:
                            # No storyboard (or a hand-picked clip) — fall back to
                            # the real download-and-frame path for this candidate.
                            staging = rdir / "staging" / f"{clip_key}.mp4"
                            if not staging.exists():
                                try:
                                    source.extract_section(
                                        cand["url"], cand["clip_start_ms"],
                                        cand["clip_end_ms"], staging)
                                except ResearchError as e:
                                    if handpicked:
                                        raise
                                    fetch_failures += 1
                                    self._report(report, f"{sid}: c{i} fetch failed "
                                                 f"({e}) — dropped from shortlist")
                                    continue
                            # yt-dlp can exit 0 yet leave a truncated/undecodable
                            # file (a 262-byte stub); verify before we trust it.
                            if not _playable(staging):
                                sz = staging.stat().st_size if staging.exists() else -1
                                staging.unlink(missing_ok=True)
                                self._report(report, f"{sid}: c{i} download unusable "
                                             f"(bytes={sz}) — dropped from shortlist")
                                continue
                            height = clip_height(staging)
                            if height < MIN_SOURCE_HEIGHT:
                                staging.unlink(missing_ok=True)
                                self._report(report, f"{sid}: c{i} too low-res "
                                             f"({height}p) — dropped from shortlist")
                                continue
                            frames_dir = rdir / "staging" / f"{clip_key}_frames"
                            frames = (sorted(frames_dir.glob("frame_*.jpg"))
                                      or sample_frames(staging, frames_dir))
                        slot = len(usable)
                        for f in frames:
                            files[f"c{slot}_{f.name}"] = f
                        usable.append((i, cand, staging))

                    if not usable:
                        if fetch_failures:
                            self._report(report,
                                f"{sid}: {fetch_failures} candidate fetch(es) "
                                "failed — nothing was judged, candidates kept, "
                                "rerun to retry")
                            waiting.append(sid)
                            continue
                        st["status"] = "exhausted"
                        self._report(report, f"{sid}: no usable candidates "
                                     "downloaded — needs new queries or an image")
                        continue

                    # label keyed by the shortlist's contents, so a re-queried
                    # scene can never consume a verdict about different clips
                    shortlist_key = "-".join(
                        f"{c['video_id']}@{c['clip_start_ms']}" for _, c, _ in usable)
                    task_label = (f"research_extract:{sid}_"
                                  + hashlib.sha1(shortlist_key.encode()).hexdigest()[:10])
                    try:
                        verdict = self.router.fulfill(
                            self.run_id, task_label, "select_clip",
                            payload={"scene_id": sid,
                                     "scene_text": " ".join(
                                         s["text"] for s in tmap["segments"]
                                         if s["id"] in scene["segment_ids"]),
                                     "visual_intent": scene["visual_intent"],
                                     "shortlist": [
                                         {"index": slot,
                                          "watch_at": _deep_link(
                                              c["url"], c["clip_start_ms"]),
                                          **{k: c[k] for k in
                                             ("title", "channel", "url",
                                              "clip_start_ms", "clip_end_ms")}}
                                         for slot, (_, c, _) in enumerate(usable)]},
                            context={"shortlist_size": len(usable)},
                            files=files)
                    except SchemaError as e:
                        self.say(f"REJECTED — {e}")
                        waiting.append(sid)
                        continue
                    if verdict is None:
                        waiting.append(sid)
                        continue
                    if verdict["choice"] is None:
                        st["status"] = "exhausted"
                        self._report(report, f"{sid}: shortlist of {len(usable)} "
                                     f"all rejected ({verdict['reason']})")
                        continue
                    abs_idx, cand, staging = usable[verdict["choice"]]
                    # AUTONOMOUS SAFETY VALVE. A storyboard tile is 160x90 and
                    # cannot rule out a thin lower-third or a corner watermark that
                    # is in the real footage. When there is no human at stage 4
                    # (brain == api) and the judge flags a caution on a pick made
                    # from tiles (staging is None => not yet downloaded), do NOT
                    # ship it: drop it from this render and record the deep-link so
                    # a human can confirm and re-add it. The run still completes —
                    # a missing cutaway is a smaller failure than a shipped banner.
                    # Operator mode already has a human fulfilling, so there the
                    # caution rides along on the clip's provenance instead.
                    caution = verdict.get("caution")
                    if caution and staging is None and self.router.brain == "api":
                        st["status"] = "held_for_review"
                        st["held"] = {"candidate_idx": abs_idx, "reason": caution,
                                      "watch_at": _deep_link(
                                          cand["url"], cand["clip_start_ms"])}
                        self._report(report, f"{sid}: HELD for human — {caution} → "
                                     + _deep_link(cand["url"], cand["clip_start_ms"]))
                        continue
                    # The winner was judged on a storyboard preview, so its real
                    # window has not been fetched yet — fetch exactly this one now.
                    # This is the whole saving: one download per scene (the pick),
                    # not one per shortlisted candidate. The download-time quality
                    # gates (truncated file, too low-res) move here with it; if the
                    # winner fails one, advance past it and let the scene retry.
                    if staging is None:
                        clip_key = f"{sid}_{cand['video_id']}_{cand['clip_start_ms']}"
                        staging = rdir / "staging" / f"{clip_key}.mp4"
                        try:
                            if not staging.exists():
                                source.extract_section(
                                    cand["url"], cand["clip_start_ms"],
                                    cand["clip_end_ms"], staging)
                        except ResearchError as e:
                            st["candidate_idx"] = abs_idx + 1
                            self._report(report, f"{sid}: chosen c{abs_idx} fetch "
                                         f"failed ({e}) — advancing to next candidate")
                            waiting.append(sid)
                            continue
                        bad = (not _playable(staging)
                               or clip_height(staging) < MIN_SOURCE_HEIGHT)
                        if bad:
                            h = clip_height(staging) if staging.exists() else -1
                            staging.unlink(missing_ok=True)
                            st["candidate_idx"] = abs_idx + 1
                            self._report(report, f"{sid}: chosen c{abs_idx} unusable "
                                         f"({h}p) — advancing to next candidate")
                            waiting.append(sid)
                            continue
                    staging = _apply_subrange(verdict, staging, scene, report,
                                              self._report, sid)
                    ingest = library.ingest_clip(
                        staging, self.run_id,
                        {"scene_id": sid, "source_url": cand["url"],
                         "source_title": cand["title"], "channel": cand["channel"],
                         "clip_start_ms": cand["clip_start_ms"],
                         "clip_end_ms": cand["clip_end_ms"],
                         "confidence": verdict["confidence"],
                         "tier": verdict["tier"],
                         # a caution the judge raised but that did not hold the
                         # clip (operator mode, or a downloaded pick) rides along
                         # so the review board can flag it for a human glance
                         "caution": verdict.get("caution"),
                         # .get: a hand-picked window never went through the
                         # ranker, so it has no lexical score
                         "match_score": cand.get("score")})
                    scene["assets"] = [{"asset_id": ingest["asset_id"],
                                        "kind": "clip", "path": ingest["path"],
                                        "confidence": verdict["confidence"]}]
                    st["status"] = "accepted"
                    # record the ABSOLUTE index so a later reject in the review
                    # board advances past this clip rather than re-offering it
                    st["candidate_idx"] = abs_idx
                    st["accepted"] = {"asset_id": ingest["asset_id"],
                                      "candidate_idx": abs_idx,
                                      "tier": verdict["tier"],
                                      "duplicate": ingest["duplicate"]}
                    self.router.queue.supersede(
                        self.run_id, f"research_extract:{sid}_",
                        f"{sid} settled on shortlist choice {verdict['choice']}")
                    self._report(report,
                        f"{sid}: accepted c{abs_idx} of {len(usable)} shortlisted "
                        f"[{verdict['tier']}] ({verdict['confidence']}%) "
                        f"{'[library hit]' if ingest['duplicate'] else ''}")
            except subprocess.CalledProcessError as e:
                # ffmpeg/yt-dlp blew up on THIS scene only — skip the
                # candidate, keep the run alive for every other scene
                idx0 = st.get("candidate_idx", 0)
                st["candidate_idx"] = idx0 + 1
                self._report(report, f"{sid}: c{idx0} tool error "
                             f"({str(e)[:90]}) — trying next candidate")
                waiting.append(sid)
            except ResearchError as e:
                tried = st.get("candidate_idx", 0)
                cands = st.get("candidates", [])
                cur = cands[tried] if 0 <= tried < len(cands) else {}
                # A human's pick is never burned by a FETCH failure. Advancing
                # here would silently discard the window the reviewer chose in
                # the board and move to one they passed over — and nothing about
                # the clip was ever judged, the transfer just stalled. Deep
                # offsets are exactly the picks most likely to hit this.
                if cur.get("manual") or cur.get("chosen"):
                    self._report(report, f"{sid}: c{tried} is your pick — kept, "
                                 f"rerun to retry the fetch ({e})")
                elif not burn_candidate(e):
                    self._report(report, f"{sid}: c{tried} fetch failed, never "
                                 f"evaluated — candidate kept, rerun to retry "
                                 f"({e})")
                else:
                    st["candidate_idx"] = tried + 1
                    self._report(report, f"{sid}: network error on c{tried} ({e}) — "
                                  "trying next candidate")
                waiting.append(sid)
            finally:
                # persist after every scene so a later failure never discards
                # verified acceptances/rankings already made earlier this run
                progress_path.parent.mkdir(parents=True, exist_ok=True)
                progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")
                timing.save(tmap, self.project_dir / "timing" / "timing_map.json")
        if hasattr(cache, "hits"):
            self.say(f"  cache: {cache.hits} hits / {cache.misses} misses; "
                     f"dedup hits: {library.dedup_hits}")
        if waiting:
            self.say(f"PAUSED — {len(waiting)} scene(s) awaiting clip verification "
                     f"(pending AI tasks listed by `mixfix status`). Rerun after "
                     "fulfilling them.")
            return "paused"
        # .get: progress also holds the run-level `_archive` entry, which has no status
        accepted = sum(1 for s in progress.values() if s.get("status") == "accepted")
        video_scenes = sum(1 for p in plan["plans"] if p["visual_type"] == "video")
        self.state.stage_finish(self.run_id, "research_extract", "done",
                                {"accepted": accepted, "video_scenes": video_scenes,
                                 "misses": video_scenes - accepted})
        self.say(f"Clips extracted: {accepted}/{video_scenes} video scenes covered.")
        return "done"

    def stage_timeline(self) -> str:
        """Build/refresh the timeline, then block on the approval gate.
        Edits that reject a clip send its scene back to research (progress.json
        status 'verifying'); re-run that stage inline before rebuilding."""
        prog_path = self.project_dir / "research" / "progress.json"
        if prog_path.exists():
            progress = json.loads(prog_path.read_text(encoding="utf-8"))
            if any(st.get("status") == "verifying" for st in progress.values()):
                self.say("Re-sourcing rejected/swapped scenes...")
                if self.stage_research_extract() == "paused":
                    return "paused"
        tl = tlmod.build(self.project_dir)
        s = tl["score"]
        self.say(f"Timeline built: {len(tl['scenes'])} scenes — coverage "
                 f"{s['coverage_pct']}%, max gap {s['max_uncovered_stretch_ms']}ms, "
                 f"variety {s['variety_index']}, confidence floor "
                 f"{s['confidence_floor']}")
        # ponytail: in-session gate only; Telegram gate when bot creds configured
        gate = ensure_gate(self.state, self.run_id, "timeline_approval")
        if gate["status"] != "approved":
            self.say(f"PAUSED — timeline approval gate pending. Review and "
                     f"approve at: {modes.cli_for(self.mode)} preview --project "
                     f"{self.project_dir.name}")
            return "paused"
        self.state.stage_finish(self.run_id, "timeline", "done",
                                {"scenes": len(tl["scenes"]), "score": s})
        self.say("Timeline approved — ready for assembly (Phase 4).")
        return "done"

    # ---- FIX-mode stages ----
    def stage_fix_intake(self) -> str:
        """Accept input/source.mp4 (local) or input/source.txt (YouTube URL);
        extract its audio to voiceover/voice.mp3 so timing_map runs unchanged."""
        from . import fix
        inp = self.project_dir / "input"
        source = inp / "source.mp4"
        url_file = inp / "source.txt"
        if not source.exists():
            if url_file.exists():
                fix.fetch_source(
                    url_file.read_text(encoding="utf-8").strip(), source,
                    cookies_from_browser=self.cfg.get("research", {}).get(
                        "cookies_from_browser"))
            else:
                self.say(f"PAUSED — drop the video to enhance at {source} "
                         f"(or a YouTube URL in {url_file}).")
                return "paused"
        fix.extract_audio(source, self.project_dir / "voiceover" / "voice.mp3")
        self.state.stage_finish(self.run_id, "fix_intake", "done",
                                {"source": str(source)})
        self.say(f"Source ingested: {source}")
        return "done"

    def stage_fix_shots(self) -> str:
        from . import fix
        source = self.project_dir / "input" / "source.mp4"
        shots = fix.detect_shots(source)
        faces = fix.face_presence(source)
        out = self.project_dir / "research" / "shots.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"shots": shots, "faces": faces}, indent=2),
                       encoding="utf-8")
        self.state.stage_finish(self.run_id, "fix_shots", "done",
                                {"shots": len(shots), "face_samples": len(faces)})
        self.say(f"Shots: {len(shots)}, face samples: {len(faces)}")
        return "done"

    def stage_replace_plan(self) -> str:
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        shots = json.loads((self.project_dir / "research" / "shots.json")
                           .read_text(encoding="utf-8"))
        fx = self.cfg["fix"]
        max_cover_ms = int(fx["max_cover_s"] * 1000)
        min_gap_ms = int(fx["min_return_gap_s"] * 1000)
        payload = {
            "segments": [{"id": s["id"], "text": s["text"],
                          "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                         for s in tmap["segments"]],
            "shots": shots["shots"], "face_samples": shots["faces"],
            "max_cover_ms": max_cover_ms, "min_gap_ms": min_gap_ms,
        }
        context = {"segment_bounds": {s["id"]: [s["start_ms"], s["end_ms"]]
                                      for s in tmap["segments"]},
                   "max_cover_ms": max_cover_ms, "min_gap_ms": min_gap_ms}
        try:
            result = self.router.fulfill(
                self.run_id, "replace_plan", "replace_plan",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "replace_plan",
                                              "replace_plan")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"
        tmap = timing.attach_scenes(tmap, result)
        timing.save(tmap, self.project_dir / "timing" / "timing_map.json")
        plan_path = self.project_dir / "research" / "visual_plan.json"
        plan_path.write_text(json.dumps({"plans": [
            {"scene_id": sc["id"], "visual_type": "video",
             "queries": sc["queries"]} for sc in result["scenes"]]}, indent=2),
            encoding="utf-8")
        self.state.stage_finish(self.run_id, "replace_plan", "done",
                                {"overlays": len(result["scenes"])})
        self.say(f"Replacement plan: {len(result['scenes'])} overlay(s)")
        return "done"

    def stage_assemble(self) -> str:
        tl = tlmod.load(self.project_dir)
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        renderer = modes.RENDERERS.get(self.mode)
        if renderer is not None:
            out = renderer(self.project_dir, tl, tmap, self.cfg,
                           self.project_dir / "input" / "source.mp4")
        elif self.mode == "fix":
            out = assemble.render_fix(self.project_dir, tl, tmap, self.cfg,
                                      self.project_dir / "input" / "source.mp4")
        else:
            out = assemble.render(self.project_dir, tl, tmap, self.cfg)
        self.state.stage_finish(self.run_id, "assemble", "done",
                                {"render": str(out)})
        self.say(f"Rendered: {out}")
        return "done"

    def stage_render_qa(self) -> str:
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        video = self.project_dir / "assembly" / "render.mp4"
        # FIX and SPLIT never touch the original audio, so never judge its
        # loudness; black frames inherited from the source are not defects
        # FIX and every registered mode keep the source audio untouched, so
        # never judge its loudness and never call inherited black frames a defect
        passthrough = self.mode != "mix"
        # The baseline only exists for modes that ingest a whole local source.
        # A mode that joins range-fetched windows has no single source file, and
        # passing a path that is not there turns the black-frame check into an
        # ffprobe crash the moment a render legitimately contains black.
        baseline = self.project_dir / "input" / "source.mp4"
        report = qamod.run_qa(
            video, tmap, self.cfg, check_loudness=not passthrough,
            check_silence=not passthrough,
            baseline_video=baseline if passthrough and baseline.exists() else None)
        report_path = self.project_dir / "assembly" / "qa_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for name, c in report["checks"].items():
            self.say(f"  QA {name}: {'PASS' if c['passed'] else 'FAIL'} "
                     f"{ {k: v for k, v in c.items() if k != 'passed'} }")
        if not report["passed"]:
            self.say(f"PAUSED — render failed QA (see {report_path}). "
                     "Fix the render and rerun.")
            return "paused"
        self.state.stage_finish(self.run_id, "render_qa", "done",
                                {"report": str(report_path)})
        return "done"

    def stage_export(self) -> str:
        tl = tlmod.load(self.project_dir)
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        export = self.project_dir / "export"
        export.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.project_dir / "assembly" / "render.mp4",
                     export / "final.mp4")
        shutil.copy2(self.project_dir / "assembly" / "qa_report.json",
                     export / "qa_report.json")
        manifest = assemble.build_manifest(tl, self.state)
        n_visuals = sum(1 for s in tl["scenes"] if s.get("visual"))
        if len(manifest["visuals"]) != n_visuals:
            raise RuntimeError(
                f"manifest count {len(manifest['visuals'])} != timeline "
                f"visual count {n_visuals}")
        (export / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        if self.cfg["render"].get("captions") == "sidecar":
            assemble.write_srt(tmap, export / "captions.srt")
        digest = hashlib.sha1((export / "final.mp4").read_bytes()).hexdigest()
        self.state.add_asset(digest, self.run_id, "export", "final_video",
                             str(export / "final.mp4"),
                             {"visuals": len(manifest["visuals"])})
        self.state.stage_finish(self.run_id, "export", "done",
                                {"final": str(export / 'final.mp4'),
                                 "visuals": len(manifest["visuals"])})
        self.say(f"Exported: {export / 'final.mp4'} "
                 f"(+ manifest.json, qa_report.json)")
        return "done"

    # ---- orchestrator ----
    def _handlers(self) -> dict:
        """stage name -> the method that runs it.

        A method, not a literal in run(), so a mode living outside this package
        can add its stages by overriding it — see split/pipeline.py.
        """
        return {
            "intake": self.stage_intake,
            "script": self.stage_script,
            "voiceover": self.stage_voiceover,
            "timing_map": self.stage_timing_map,
            "scenes": self.stage_scenes,
            "visual_plan": self.stage_visual_plan,
            "research_extract": self.stage_research_extract,
            "generate_visuals": self.stage_generate_visuals,
            "timeline": self.stage_timeline,
            "fix_intake": self.stage_fix_intake,
            "fix_shots": self.stage_fix_shots,
            "replace_plan": self.stage_replace_plan,
            "assemble": self.stage_assemble,
            "render_qa": self.stage_render_qa,
            "export": self.stage_export,
        }

    def run(self) -> str:
        handlers = self._handlers()
        base_cfg = self.cfg
        for row in self.state.stages(self.run_id):
            name = row["stage_name"]
            if row["status"] == "done":
                continue
            # node parameters are a partial config overlaid on this stage only.
            # Merging here rather than in each stage means every existing
            # `self.cfg[...]` read is overridable without touching 15 methods.
            self.cfg = merge_params(base_cfg, self.state.get_params(self.run_id, name))
            self.state.stage_start(self.run_id, name)
            try:
                status = handlers[name]()
            except Exception as e:  # noqa: BLE001 — stage errors are recorded, run fails cleanly
                self.state.stage_finish(self.run_id, name, "failed", error=str(e))
                self.state.set_run_status(self.run_id, "failed")
                self.say(f"FAILED at {name}: {e}")
                return "failed"
            if status == "paused":
                self.state.stage_finish(self.run_id, name, "paused")
                self.state.set_run_status(self.run_id, "paused")
                return "paused"
        self.state.set_run_status(self.run_id, "done")
        self.say("Pipeline complete for the current phase build.")
        return "done"


# MIX and FIX are this package's own modes; SPLIT registers itself from split/.
modes.register("mix", MIX_STAGES, knobs=STAGE_KNOBS)
modes.register("fix", FIX_STAGES, knobs=STAGE_KNOBS)
