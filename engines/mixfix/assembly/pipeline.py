"""ASSEMBLY pipeline — select a section of a long episode, then FIX it.

Two halves, and only the first is new code:

  FRONT  captions-first intake, a plan stage choosing which windows of one
         episode survive, a range-fetch of just those windows, and a cut that
         joins them behind a hook lifted from inside the section.
  BACK   FIX, unchanged. `timing_map`, `fix_shots`, `research_extract`,
         `generate_visuals`, `timeline`, `assemble` (render_fix), `render_qa`
         and `export` are the same code FIX and MIX run.

FIX already does the expensive half — it plays a video and replaces the picture
for planned windows while stream-copying the original audio. What it cannot do
is CHOOSE a section: `fix_intake` ingests a whole upload, so a 3-hour podcast
costs 3 hours of download and transcription. The front half is exactly that
missing step, and `assembly_cut` hands the back half the one thing it wants —
a video file at `input/source.mp4`.

Two deliberate departures from FIX's stage list:

- **`generate_visuals` is included** (FIX omits it). Cutaways here are a mix:
  sourced footage, a generated still, or a timed generated sequence. The core
  visual_plan contract already models all three as `visual_type`
  video|image|generate, so the stage exists — FIX simply never used it because
  `replace_plan` hardcodes "video".
- **`insert_plan` replaces `replace_plan`.** Same output contract, different
  doctrine: FIX covers wherever useful within its limits, this places a small
  fixed number of high-value cutaways and leaves the rest of the runtime alone.

The timing map is NOT synthesised here. `assembly_cut` writes the real cut, and
the core `timing_map` stage whispers it — 15-20 minutes of audio rather than the
3 hours the untrimmed episode would have cost. That buys word-level timings,
which is what lets a cutaway land on the right beat instead of a second late.
"""
from __future__ import annotations

import json

from mixfix import timing
from mixfix.ai.schemas import SchemaError
from mixfix.pipeline import Pipeline
from mixfix.research import cut_section, make_source, media_covers, video_id_from

from .cut import build_cut

ASSEMBLY_STAGES = ["assembly_intake", "assembly_plan", "assembly_extract",
                   "assembly_cut", "timing_map", "fix_shots", "insert_plan",
                   "research_extract", "generate_visuals", "timeline",
                   "assemble", "render_qa", "export"]

def _insert_band(a: dict, total_ms: int) -> dict:
    """How many cutaways this particular cut should carry.

    Scaled by runtime, not fixed: the same count over a 12-minute cut and a
    25-minute one makes the long one feel unedited. The band is kept wide enough
    that the planner can still decline a weak cutaway rather than pad to a
    quota — the floor is a floor on OPPORTUNITY, not a demand for filler.
    """
    lo_c, hi_c = int(a["min_inserts"]), int(a["max_inserts"])
    target = (total_ms / 60000.0) * float(a.get("inserts_per_min", 0.9))
    lo = max(lo_c, min(hi_c, int(target * 0.85)))
    hi = max(lo, min(hi_c, int(target * 1.25) + 1))
    return {"min_inserts": lo, "max_inserts": hi}


ASSEMBLY_KNOBS = {"assembly_plan": ["assembly"],
                  "assembly_extract": ["research"],
                  "assembly_cut": ["render"],
                  "timing_map": ["transcriber", "whisper_model"],
                  "insert_plan": ["assembly", "fix"],
                  "research_extract": ["research"],
                  "assemble": ["render", "fix"]}


class AssemblyPipeline(Pipeline):
    def _handlers(self) -> dict:
        return {**super()._handlers(),
                "assembly_intake": self.stage_assembly_intake,
                "assembly_plan": self.stage_assembly_plan,
                "assembly_extract": self.stage_assembly_extract,
                "assembly_cut": self.stage_assembly_cut,
                "insert_plan": self.stage_insert_plan}

    # ---- intake -------------------------------------------------------
    def stage_assembly_intake(self) -> str:
        """Fetch auto-captions for the source episode. No video download."""
        inp = self.project_dir / "input"
        inp.mkdir(parents=True, exist_ok=True)
        url_file = inp / "source.txt"
        if not url_file.exists() or not url_file.read_text(encoding="utf-8").strip():
            self.say(f"PAUSED — put the episode URL in {url_file}.")
            return "paused"
        url = url_file.read_text(encoding="utf-8").strip()

        source, _cache = make_source(self.cfg, self.state)
        segments = source.transcript(video_id_from(url), url)
        if not segments:
            self.say("PAUSED — no auto-captions for this episode. This mode "
                     "selects from captions; an episode without them needs a "
                     "different source or a manual transcript at "
                     f"{self.project_dir / 'research' / 'captions.json'}.")
            return "paused"

        # Give every caption line a stable id up front. Everything downstream
        # addresses windows by these ids rather than by timestamps.
        for i, s in enumerate(segments):
            s["id"] = f"seg_{i:04d}"

        out = self.project_dir / "research" / "captions.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"url": url, "segments": segments}, indent=2),
                       encoding="utf-8")
        span_ms = segments[-1]["end_ms"] - segments[0]["start_ms"]
        self.state.stage_finish(self.run_id, "assembly_intake", "done",
                                {"segments": len(segments), "span_ms": span_ms})
        self.say(f"Captions: {len(segments)} lines spanning "
                 f"{span_ms / 60000:.0f} min — no video downloaded yet.")
        return "done"

    # ---- plan ---------------------------------------------------------
    def stage_assembly_plan(self) -> str:
        """Choose the promise, the windows that pay it off, and the hook."""
        caps = json.loads((self.project_dir / "research" / "captions.json")
                          .read_text(encoding="utf-8"))
        segments = caps["segments"]
        a = self.cfg["assembly"]
        limits = {
            "min_window_ms": int(a["min_window_s"] * 1000),
            "min_total_ms": int(a["min_total_s"] * 1000),
            "max_total_ms": int(a["max_total_s"] * 1000),
            "hook_min_ms": int(a["hook_min_s"] * 1000),
            "hook_max_ms": int(a["hook_max_s"] * 1000),
            "hook_min_depth_ms": int(a["hook_min_depth_s"] * 1000),
        }
        theme_file = self.project_dir / "input" / "theme.txt"
        theme = (theme_file.read_text(encoding="utf-8").strip()
                 if theme_file.exists() else "")

        payload = {
            "theme": theme or "(none given — choose the strongest thread)",
            "target_runtime": f"{a['min_total_s'] / 60:.0f}-"
                              f"{a['max_total_s'] / 60:.0f} minutes",
            "segments": [{"id": s["id"], "text": s["text"],
                          "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                         for s in segments],
        }
        context = {
            "segment_bounds": {s["id"]: [s["start_ms"], s["end_ms"]]
                               for s in segments},
            "segment_order": {s["id"]: i for i, s in enumerate(segments)},
            **limits,
        }
        try:
            result = self.router.fulfill(
                self.run_id, "assembly_plan", "assembly_plan",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "assembly_plan",
                                              "assembly_plan")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"

        bounds = context["segment_bounds"]

        def span(ids):
            return (min(bounds[s][0] for s in ids),
                    max(bounds[s][1] for s in ids))

        windows = []
        for w in result["windows"]:
            start, end = span(w["segment_ids"])
            windows.append({"id": w["id"], "segment_ids": w["segment_ids"],
                            "source_start_ms": start, "source_end_ms": end,
                            "why": w["why"]})
        windows.sort(key=lambda w: w["source_start_ms"])

        h = result["hook"]
        h_start, h_end = span(h["segment_ids"])
        hook = {"segment_ids": h["segment_ids"], "source_start_ms": h_start,
                "source_end_ms": h_end, "why": h["why"]}

        plan = {"title": result["title"], "url": caps["url"],
                "hook": hook, "windows": windows}
        (self.project_dir / "research" / "windows.json").write_text(
            json.dumps(plan, indent=2), encoding="utf-8")

        total = sum(w["source_end_ms"] - w["source_start_ms"] for w in windows)
        hook_ms = h_end - h_start
        self.state.stage_finish(self.run_id, "assembly_plan", "done",
                                {"windows": len(windows), "total_ms": total,
                                 "hook_ms": hook_ms, "title": result["title"]})
        self.say(f'Plan: "{result["title"]}" — {len(windows)} window(s), '
                 f"{total / 60000:.1f} min body + {hook_ms / 1000:.0f}s hook")
        return "done"

    # ---- extract ------------------------------------------------------
    def stage_assembly_extract(self) -> str:
        """Range-fetch each planned window and cut it to exact bounds.

        Only the chosen windows are downloaded. `fetch_segment` returns a padded
        file (it starts at the pad, not at the requested moment), so the exact
        window is cut locally at an offset — that local re-cut is also what
        makes the boundaries frame-accurate.
        """
        plan = json.loads((self.project_dir / "research" / "windows.json")
                          .read_text(encoding="utf-8"))
        source, _cache = make_source(self.cfg, self.state)
        win_dir = self.project_dir / "assembly" / "windows"
        win_dir.mkdir(parents=True, exist_ok=True)

        for w in plan["windows"]:
            exact = win_dir / f"{w['id']}.mp4"
            dur = w["source_end_ms"] - w["source_start_ms"]
            if exact.exists() and media_covers(exact, dur, require_audio=True):
                continue
            exact.unlink(missing_ok=True)
            seg_path, seg_start_ms = source.fetch_segment(
                plan["url"], w["source_start_ms"], w["source_end_ms"])
            cut_section(seg_path, exact,
                        w["source_start_ms"] - seg_start_ms,
                        w["source_end_ms"] - seg_start_ms)
            if not media_covers(exact, dur, require_audio=True):
                exact.unlink(missing_ok=True)
                raise RuntimeError(
                    f"{w['id']} ended early or lost audio; rerun to refetch")
            self.say(f"  {w['id']}: {dur / 1000:.0f}s cut")

        total = sum(w["source_end_ms"] - w["source_start_ms"]
                    for w in plan["windows"])
        self.state.stage_finish(self.run_id, "assembly_extract", "done",
                                {"windows": len(plan["windows"]),
                                 "total_ms": total})
        self.say(f"Extracted {len(plan['windows'])} window(s), "
                 f"{total / 60000:.1f} min")
        return "done"

    # ---- cut ----------------------------------------------------------
    def stage_assembly_cut(self) -> str:
        """Join the windows behind the hook, producing input/source.mp4.

        From here the run is indistinguishable from a FIX run: there is a video
        file and everything downstream treats it as the source. The hook is
        prepended, NOT moved — it plays twice, once as the teaser and again in
        its natural place, which is what a cold open is.
        """
        from mixfix.fix import extract_audio

        plan = json.loads((self.project_dir / "research" / "windows.json")
                          .read_text(encoding="utf-8"))
        cut_path, hook_ms, body_ms = build_cut(self.project_dir, plan, self.cfg)
        extract_audio(cut_path, self.project_dir / "voiceover" / "voice.mp3")

        # insert_plan reads this to keep cutaways out of the hook: the teaser is
        # a straight lift, and production on top of it softens the jolt.
        (self.project_dir / "research" / "cut.json").write_text(json.dumps(
            {"hook_ms": hook_ms, "body_ms": body_ms,
             "total_ms": hook_ms + body_ms}, indent=2), encoding="utf-8")

        self.state.stage_finish(self.run_id, "assembly_cut", "done",
                                {"hook_ms": hook_ms, "body_ms": body_ms,
                                 "source": str(cut_path)})
        self.say(f"Cut: {hook_ms / 1000:.0f}s hook + {body_ms / 60000:.1f} min "
                 f"body → {cut_path.name}")
        return "done"

    # ---- insert plan --------------------------------------------------
    def stage_insert_plan(self) -> str:
        """Plan a small number of cutaways over the cut.

        Same result contract as replace_plan and split_plan — scenes plus a
        visual plan — so research_extract, generate_visuals, the timeline and
        the review board consume it unchanged. What differs is density and asset
        mix: a handful of high-value moments, each of which may be sourced
        footage, a generated still, or a timed generated sequence.
        """
        tmap = timing.load(self.project_dir / "timing" / "timing_map.json")
        cut = json.loads((self.project_dir / "research" / "cut.json")
                         .read_text(encoding="utf-8"))
        a, fx = self.cfg["assembly"], self.cfg["fix"]
        limits = {
            **_insert_band(a, tmap["source"]["duration_ms"]),
            "max_cover_ms": int(fx["max_cover_s"] * 1000),
            "min_gap_ms": int(fx["min_return_gap_s"] * 1000),
            "hook_ms": int(cut["hook_ms"]),
            # Sourcing budget: few but longer. Sourced cutaways are the only
            # ones that cost a YouTube fetch, so they are capped and given a
            # longer ceiling; generated visuals carry the rest.
            "max_sourced": int(a.get("max_sourced", 4)),
            "sourced_min_ms": int(float(a.get("sourced_min_s", 10.0)) * 1000),
            "sourced_max_ms": int(float(a.get("sourced_max_s", 20.0)) * 1000),
        }
        payload = {
            "segments": [{"id": s["id"], "text": s["text"],
                          "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                         for s in tmap["segments"]],
            "channel_style": (a.get("channel_style") or "").strip()
                             or "(none set — infer from the material)",
            "proven_sources": self.proven_sources(),
            **limits,
        }
        context = {"segment_bounds": {s["id"]: [s["start_ms"], s["end_ms"]]
                                      for s in tmap["segments"]},
                   **limits}
        try:
            result = self.router.fulfill(
                self.run_id, "insert_plan", "insert_plan",
                payload=payload, context=context)
        except SchemaError as e:
            self.say(f"REJECTED — {e}")
            return "paused"
        if result is None:
            task = self.state.pending_ai_task(self.run_id, "insert_plan",
                                              "insert_plan")
            self.say(f"PAUSED — AI task pending (operator mode): "
                     f"{task['request_dir']}/request.json → write result.json there.")
            return "paused"

        tmap = timing.attach_scenes(tmap, result)
        timing.save(tmap, self.project_dir / "timing" / "timing_map.json")

        plans = []
        for sc in result["scenes"]:
            p = {"scene_id": sc["id"], "visual_type": sc["visual_type"]}
            if sc["visual_type"] == "video":
                p["queries"] = sc["queries"]
                p["moment"] = sc.get("moment", "any")
                # A cutaway illustrates something the speaker named; it is not
                # required to be the event's own upload. Most footage that fits
                # (street scenes, stadium shots, walking tours) has no captions,
                # and the transcript ranker drops those — measured at 0 usable
                # candidates from 36 searches before this flag existed.
                p["sourcing"] = "illustrative"
            elif sc["visual_type"] == "image":
                p["image_prompt"] = sc["image_prompt"]
            else:
                p["segments"] = sc["segments"]
            plans.append(p)
        doc = {"plans": plans,
               "archive_queries": result.get("archive_queries") or []}
        if result.get("style_lock"):
            doc["style_lock"] = result["style_lock"]
        (self.project_dir / "research" / "visual_plan.json").write_text(
            json.dumps(doc, indent=2), encoding="utf-8")

        kinds: dict[str, int] = {}
        for p in plans:
            kinds[p["visual_type"]] = kinds.get(p["visual_type"], 0) + 1
        self.state.stage_finish(self.run_id, "insert_plan", "done",
                                {"inserts": len(plans), **kinds})
        self.say(f"Inserts: {len(plans)} cutaway(s) — "
                 + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())))
        return "done"
