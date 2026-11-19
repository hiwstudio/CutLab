"""Stage: publishing assets — social captions + thumbnail concepts.

Runs AFTER the recap video is assembled so every finished project is not just
production-ready but PUBLISHING-ready. Two deliverables:

  1. generate_captions()   -> captions.json + "Social Media Captions.txt":
       platform-native captions (YouTube, TikTok, Facebook, X) that share one
       core message but match each platform's voice.
  2. generate_thumbnails() -> thumbnails/ folder: several thumbnail concepts,
       each anchored to a real, high-impact frame pulled from the source video,
       with why-it-works, a suggested headline/hook, and composition notes.

Both stages reuse the pluggable brain (story.call_brain -> openrouter | manual)
and cache to the workdir, so a rerun resumes instead of regenerating. They run
last, so the finished recap.mp4 is never blocked on them.
"""
import json
from pathlib import Path

import config
from engine import story
from engine.utils import die, log, parse_json_loose, run_ffmpeg


# ---------------------------------------------------------------------------
# 1. Social media captions
# ---------------------------------------------------------------------------

CAPTIONS_SYSTEM = (
    "You are a senior social media manager who writes scroll-stopping, "
    "platform-native captions. You receive a recap video's story outline and "
    "its narration. Write captions that all carry the SAME core message but "
    "match each platform's native voice, length, and hashtag norms. Be specific "
    "to the actual content (no generic filler). Output JSON only."
)


def generate_captions(outline: dict, script, video_title: str,
                      workdir: Path) -> dict:
    """Produce platform-ready captions -> captions.json (+ readable .txt).

    Cached: if captions.json exists it is reused (and the readable file is
    rebuilt from it if missing), so reruns don't re-call the brain.
    """
    out = workdir / "captions.json"
    readable = workdir / "Social Media Captions.txt"
    if out.exists():
        log("captions.json already exists, skipping captions")
        data = json.loads(out.read_text(encoding="utf-8"))
        if not readable.exists():
            _write_captions_readable(data, readable, video_title)
        return data

    logline = (outline.get("logline") or "").strip()
    ending = (outline.get("ending") or "").strip()
    narration = " ".join(
        (b.get("narration") or "").strip() for b in _beats(script)).strip()
    # Keep the prompt compact: the outline + a slice of narration is plenty.
    narration = narration[:2500]

    platforms = ", ".join(p.upper() for p in config.CAPTION_PLATFORMS)
    prompt = f"""Write social captions for a story-recap video.

SOURCE TITLE (for context only, rewrite freely): {video_title}

CORE STORY (logline): {logline}

HOW IT ENDS: {ending}

NARRATION EXCERPT:
{narration}

Write captions for these platforms: {platforms}.
All must share the SAME core message but feel native to each platform:
  - youtube:  a punchy clickable title (<=70 chars) AND a 2-4 sentence
              description that sets up the hook without fully spoiling, ending
              with a few relevant hashtags.
              TITLE RULE (measured 2026-09-03 across the top 25 titles of the
              five leading recap channels - the film's name appeared in ZERO of
              them): do NOT name the film, and do not use the word "recap", in
              the TITLE. Write the premise as a curiosity-gap logline about what
              happens to someone - "500+ IQ Retiree Outsmarts the Lottery and
              Cashes In $27M", "They Killed His Daughter... Now This Quiet Chef
              Is Hunting Everyone Responsible". The film may be named in the
              DESCRIPTION, where people look for it.
  - tiktok:   one short, high-energy caption (1-2 lines) + 3-6 trend-style
              hashtags.
  - facebook: a warm, conversational caption (2-3 sentences) that invites
              comments, light emoji ok.
  - x:        a single tweet, <=280 chars, punchy, at most 1-2 hashtags.

Return JSON exactly in this shape (hashtags as arrays of strings WITH the #):
{{
  "core_message": "one sentence",
  "youtube":  {{"title": "...", "description": "...", "hashtags": ["#..."]}},
  "tiktok":   {{"caption": "...", "hashtags": ["#..."]}},
  "facebook": {{"caption": "...", "hashtags": ["#..."]}},
  "x":        {{"caption": "..."}}
}}"""

    raw = story.call_brain(prompt, CAPTIONS_SYSTEM, "captions", workdir)
    try:
        data = parse_json_loose(raw)
    except ValueError as e:
        die(f"captions: could not parse the brain's response ({e}).")
    if not isinstance(data, dict):
        die("captions: expected a JSON object from the brain.")

    out.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    _write_captions_readable(data, readable, video_title)
    log(f"Captions: wrote {readable.name} ({platforms}).")
    return data


def _write_captions_readable(data: dict, path: Path, video_title: str) -> None:
    """Render captions.json into a copy-paste-friendly text file."""
    lines = ["SOCIAL MEDIA CAPTIONS", f"For: {video_title}", "=" * 60, ""]
    core = (data.get("core_message") or "").strip()
    if core:
        lines += [f"Core message: {core}", ""]

    titles = {
        "youtube": "YOUTUBE", "tiktok": "TIKTOK",
        "facebook": "FACEBOOK", "x": "X (TWITTER)",
    }
    for key in config.CAPTION_PLATFORMS:
        block = data.get(key)
        if block is None:
            continue
        lines.append(titles.get(key, key.upper()))
        lines.append("-" * 60)
        if isinstance(block, str):
            lines.append(block.strip())
        elif isinstance(block, dict):
            if block.get("title"):
                lines.append(f"Title: {block['title'].strip()}")
            text = (block.get("caption") or block.get("description") or "").strip()
            if text:
                lines.append(text)
            tags = block.get("hashtags") or []
            if tags:
                lines.append("")
                lines.append(" ".join(str(t) for t in tags))
        lines += ["", ""]

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. Thumbnail concepts
# ---------------------------------------------------------------------------

THUMBS_SYSTEM = (
    "You are a YouTube thumbnail strategist. You pick the single strongest "
    "FRAMES from a video to use as thumbnail starting points: high-emotion, "
    "high-clarity, visually arresting moments. You receive the story outline "
    "and a list of the video's scenes (with timestamps and any dialogue). For "
    "each concept choose a precise timestamp, explain why it grabs attention, "
    "suggest a short overlay headline/hook, and note composition/focal point. "
    "Output JSON only."
)


def generate_thumbnails(outline: dict, scene_cards: list, video: Path,
                        workdir: Path) -> dict:
    """Propose several thumbnail concepts and extract each chosen frame.

    `scene_cards` are the index.build_scene_cards() entries (index/start/end/
    dialogue), so the brain sees what is actually on screen and being said when
    choosing high-impact frames.

    Writes thumbnails/thumbnails.json (data) + thumbnails/Thumbnail Concepts.txt
    (readable) + one extracted JPG per concept. Cached on thumbnails.json.
    """
    scenes = scene_cards
    thumbs_dir = workdir / "thumbnails"
    out = thumbs_dir / "thumbnails.json"
    readable = thumbs_dir / "Thumbnail Concepts.txt"
    if out.exists():
        log("thumbnails/thumbnails.json already exists, skipping thumbnails")
        data = json.loads(out.read_text(encoding="utf-8"))
        if not readable.exists():
            _write_thumbs_readable(data, readable)
        return data
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    duration = max((float(s.get("end", 0.0)) for s in scenes), default=0.0)
    n = config.THUMBNAIL_COUNT
    logline = (outline.get("logline") or "").strip()
    scene_lines = _scene_digest(scenes)

    prompt = f"""Pick the {n} strongest THUMBNAIL frames for this recap video.

STORY (logline): {logline}

VIDEO LENGTH: {duration:.0f} seconds.

SCENES (index | start-end seconds | dialogue/visual note):
{scene_lines}

Choose {n} DISTINCT moments that would each make a scroll-stopping thumbnail.

WHAT ACTUALLY WINS IN THIS NICHE (measured 2026-09-03 from the 11 top-performing
thumbnails of the five leading recap channels): ONE subject doing ONE legible
thing, framed close or medium, high contrast, simple background, and NO TEXT
anywhere in the image. Every winner is a single extreme image that poses a
question by itself - a man sitting on a mountain of cash, a couple asleep buried
in banknotes, a lone robber walking out through a police cordon, a hand putting
a mysterious pill on a tongue, an old man lighting a homemade fuse. Prefer the
most physically striking or most absurd-out-of-context moment in the film over
the most important one. A frame that needs a caption to make sense is the wrong
frame.

Spread them across the video; don't pick {n} near-identical frames.

For each concept return:
  "timestamp":   exact seconds to grab the frame (a float within the video),
  "scene_index": the index of the scene it comes from,
  "moment":      a short label for what's on screen,
  "why":         1-2 sentences on why this frame attracts clicks,
  "headline":    a short punchy overlay text/hook (<=6 words; "" if none fits),
  "composition": where the focal point sits and any framing/crop advice.

Return JSON: {{"concepts": [ {{"timestamp","scene_index","moment","why","headline","composition"}} ]}}
Order the concepts strongest-first."""

    raw = story.call_brain(prompt, THUMBS_SYSTEM, "thumbnails", workdir)
    try:
        parsed = parse_json_loose(raw)
    except ValueError as e:
        die(f"thumbnails: could not parse the brain's response ({e}).")
    concepts = parsed.get("concepts", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(concepts, list) or not concepts:
        die("thumbnails: the brain returned no concepts.")

    out_concepts = []
    for i, c in enumerate(concepts, start=1):
        try:
            ts = float(c.get("timestamp"))
        except (TypeError, ValueError):
            ts = 0.0
        ts = min(max(ts, 0.0), max(duration - 0.1, 0.0))
        jpg = thumbs_dir / f"thumb_{i:02d}.jpg"
        if not jpg.exists():
            _extract_thumb(video, ts, jpg)
        out_concepts.append({
            "rank": i,
            "timestamp": round(ts, 2),
            "scene_index": c.get("scene_index"),
            "moment": (c.get("moment") or "").strip(),
            "why": (c.get("why") or "").strip(),
            "headline": (c.get("headline") or "").strip(),
            "composition": (c.get("composition") or "").strip(),
            "frame_file": jpg.name,
        })

    data = {"count": len(out_concepts), "concepts": out_concepts}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    _write_thumbs_readable(data, readable)
    log(f"Thumbnails: {len(out_concepts)} concepts + frames -> "
        f"{thumbs_dir.name}/")
    return data


# ---------------------------------------------------------------------------
# 3. Thumbnail enhancement prompts (image-generation prompts per concept)
# ---------------------------------------------------------------------------

THUMB_PROMPTS_SYSTEM = (
    "You are a YouTube thumbnail art director who writes precise prompts for an "
    "image-generation / image-to-image model. You are given thumbnail CONCEPTS "
    "that were already chosen from a video (each with its moment, why it works, "
    "headline, and composition). For EACH concept write ONE prompt that ELEVATES "
    "that exact frame into a polished, high-performing YouTube thumbnail while "
    "PRESERVING its original idea, subject, and composition. Never invent a new "
    "concept, never change what the thumbnail is about. The TASK section states "
    "this channel's text policy - either an exact overlay style to bake in, or "
    "no lettering at all - and it is authoritative: follow it and nothing else. "
    "Output JSON only."
)


def generate_thumbnail_enhancements(thumbs_data: dict, video_title: str,
                                    workdir: Path,
                                    youtube_title: str = "") -> dict:
    """Write an image-generation ENHANCEMENT prompt per thumbnail concept.

    Runs after generate_thumbnails(). For each concept it produces a prompt that
    refines/elevates that exact frame into a professional YouTube thumbnail
    (stronger framing, lighting/contrast, expression, subject focus, depth,
    richer-but-not-oversaturated color, cleaner background, more impact). Text
    follows config.THUMBNAIL_TEXT_STYLE: a style string bakes that overlay into
    the image, and the DEFAULT (empty) forbids lettering entirely - measured
    2026-09-03, none of the 11 top thumbnails across the five reference channels
    carried a single word. Stays consistent with config.THUMBNAIL_ART_STYLE and
    keeps the original idea/composition intact.

    `youtube_title` (from captions.json) is passed in as context so each overlay
    stays on-message with how the video is actually titled.

    Writes thumbnails/enhancements.json + "Thumbnail Enhancement Prompts.txt".
    Cached on enhancements.json, so reruns don't re-call the brain.
    """
    thumbs_dir = workdir / "thumbnails"
    out = thumbs_dir / "enhancements.json"
    readable = thumbs_dir / "Thumbnail Enhancement Prompts.txt"
    if out.exists():
        log("thumbnails/enhancements.json already exists, skipping enhancements")
        data = json.loads(out.read_text(encoding="utf-8"))
        if not readable.exists():
            _write_enhancements_readable(data, readable, video_title)
        return data

    concepts = thumbs_data.get("concepts", []) if isinstance(thumbs_data, dict) else []
    if not concepts:
        die("thumbnail enhancements: no thumbnail concepts to enhance.")
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    style = config.THUMBNAIL_ART_STYLE.strip()
    text_style = config.THUMBNAIL_TEXT_STYLE.strip()
    concept_lines = _concept_digest(concepts)
    n = len(concepts)
    title_line = (youtube_title or video_title or "").strip()
    # Thumbnail TEXT is OFF by default, on measured evidence: of 11 top
    # thumbnails across the five reference channels (2026-09-03), ZERO carried
    # any text - each is one extreme, legible image, and the title carries the
    # words. Set config.THUMBNAIL_TEXT_STYLE to re-enable overlays.
    if text_style:
        text_style_block = (
            "TEXT / OVERLAY STYLE (use this EXACT style on every thumbnail, so "
            "the channel looks consistent):\n" + text_style + "\n")
        text_requirement = (
            "The prompt MUST ALSO render a bold YouTube-style TEXT OVERLAY baked "
            "into the image, in the TEXT / OVERLAY STYLE above. Decide a short, "
            "punchy overlay for each concept (2-4 words, ALL CAPS, refined from "
            "the concept's headline and on-message with the video title). State "
            "the EXACT words to render and place them in the frame's reserved "
            "negative space, never over the main subject or a face. Also return "
            "that exact overlay string as \"overlay_text\".\n")
    else:
        text_style_block = (
            "TEXT: NONE. This channel's thumbnails carry no lettering at all - "
            "the title does the talking and the image does the rest.\n")
        text_requirement = (
            "DO NOT put any text, lettering, caption, logo or watermark in the "
            "image, and have the prompt explicitly forbid them. Spend that effort "
            "instead on making the single subject and its one readable action "
            "unmistakable at thumbnail size: bigger subject, stronger key light, "
            "simpler background, higher contrast, cleaner silhouette. Return "
            "\"overlay_text\": \"\" for every concept.\n")

    prompt = f"""Write ONE image-generation enhancement prompt for EACH of the
{n} thumbnail concepts below. Each prompt refines that exact frame into a
polished, high-performing YouTube thumbnail WITHOUT changing its concept,
subject, or composition.

VIDEO TITLE (keep every overlay on-message with this): {title_line}

ART STYLE to stay consistent with: {style}

{text_style_block}

THUMBNAIL CONCEPTS (rank | frame_file | moment | headline | composition):
{concept_lines}

For each concept, write a single richly-detailed prompt (a paragraph, not a
list) that instructs an image model to ENHANCE the original frame. It MUST
preserve the original idea and composition and MUST push these improvements:
  - stronger composition and framing (respect the concept's stated focal point),
  - better lighting and contrast (clear key light, depth-giving shadows),
  - more expressive characters / facial expressions where a subject is present,
  - clear visual focus on the main subject,
  - improved depth and cinematic quality (foreground/background separation),
  - richer color WITHOUT oversaturation,
  - a cleaner background that supports the subject instead of distracting,
  - more eye-catching visual impact while staying consistent with the art style.
Describe the SPECIFIC subject/scene of that concept, not generic advice.

{text_requirement}

For each concept also return a short "negative_prompt" of things to avoid
(e.g. oversaturation, blown highlights, muddy shadows, extra limbs, misspelled
or garbled text, watermark, distracting clutter).

Return JSON exactly:
{{"prompts": [ {{"rank": <int matching the concept>, "overlay_text": "THE WORDS", "enhancement_prompt": "...", "negative_prompt": "..."}} ]}}
Return them in the same rank order as the concepts."""

    raw = story.call_brain(prompt, THUMB_PROMPTS_SYSTEM, "thumbnail_prompts",
                           workdir)
    try:
        parsed = parse_json_loose(raw)
    except ValueError as e:
        die(f"thumbnail enhancements: could not parse the brain's response ({e}).")
    prompts = parsed.get("prompts", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(prompts, list) or not prompts:
        die("thumbnail enhancements: the brain returned no prompts.")

    # Align returned prompts to concepts by rank, then fall back to position, so
    # a concept never silently loses its enhancement prompt.
    by_rank = {}
    for p in prompts:
        if isinstance(p, dict) and p.get("rank") is not None:
            try:
                by_rank[int(p["rank"])] = p
            except (TypeError, ValueError):
                pass

    out_prompts = []
    for i, c in enumerate(concepts, start=1):
        rank = c.get("rank", i)
        p = by_rank.get(rank)
        if p is None and i - 1 < len(prompts) and isinstance(prompts[i - 1], dict):
            p = prompts[i - 1]
        p = p or {}
        overlay = (p.get("overlay_text") or c.get("headline") or "").strip()
        out_prompts.append({
            "rank": rank,
            "frame_file": c.get("frame_file"),
            "moment": (c.get("moment") or "").strip(),
            "overlay_text": overlay,
            "enhancement_prompt": (p.get("enhancement_prompt") or "").strip(),
            "negative_prompt": (p.get("negative_prompt") or "").strip(),
        })

    data = {"count": len(out_prompts), "art_style": style,
            "text_style": text_style, "video_title": title_line,
            "prompts": out_prompts}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    _write_enhancements_readable(data, readable, video_title)
    log(f"Thumbnail enhancements: {len(out_prompts)} prompts -> "
        f"{thumbs_dir.name}/{readable.name}")
    return data


def _concept_digest(concepts: list) -> str:
    """One line per concept for the enhancement prompt."""
    lines = []
    for c in concepts:
        moment = (c.get("moment") or "").strip() or "(unlabeled moment)"
        headline = (c.get("headline") or "").strip() or "(no headline)"
        comp = (c.get("composition") or "").strip() or "(no composition note)"
        lines.append(f"{c.get('rank')} | {c.get('frame_file')} | {moment} | "
                     f"{headline} | {comp}")
    return "\n".join(lines)


def _write_enhancements_readable(data: dict, path: Path,
                                 video_title: str) -> None:
    """Render enhancements.json into a copy-paste-friendly prompt sheet."""
    text_style = (data.get("text_style") or "").strip()
    lines = ["THUMBNAIL ENHANCEMENT PROMPTS",
             f"For: {video_title}",
             "Feed each prompt (with its frame) to an image model to elevate the "
             "concept into a polished, upload-ready YouTube thumbnail"
             + (" with text baked in." if text_style else "."),
             f"Art style: {data.get('art_style', '')}",
             f"Text style: {text_style or 'none - these thumbnails carry no lettering'}",
             "=" * 60, ""]
    for p in data.get("prompts", []):
        head = f"#{p.get('rank')}  [{p.get('frame_file')}]"
        if p.get("moment"):
            head += f"  — {p['moment']}"
        lines.append(head)
        if p.get("overlay_text"):
            lines.append(f"  Overlay text: \"{p['overlay_text']}\"")
        lines.append("  Enhancement prompt:")
        lines.append(f"    {p.get('enhancement_prompt', '')}")
        if p.get("negative_prompt"):
            lines.append("  Negative prompt:")
            lines.append(f"    {p['negative_prompt']}")
        lines += ["", ""]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _scene_digest(scenes: list, limit: int = 160) -> str:
    """A compact one-line-per-scene digest for the thumbnail prompt. If there are
    very many scenes, sample evenly so the prompt stays small but spans the whole
    video."""
    items = scenes
    if len(scenes) > limit:
        step = len(scenes) / limit
        items = [scenes[int(i * step)] for i in range(limit)]
    lines = []
    for s in items:
        note = (s.get("dialogue") or "").strip().replace("\n", " ")
        if not note:
            note = "(visual / no dialogue)"
        if len(note) > 90:
            note = note[:87] + "..."
        lines.append(f"{s.get('index')} | {float(s.get('start',0)):.1f}-"
                     f"{float(s.get('end',0)):.1f} | {note}")
    return "\n".join(lines)


def _extract_thumb(video: Path, t: float, out_jpg: Path) -> None:
    """Grab a single high-quality frame at time t (native resolution)."""
    run_ffmpeg(
        ["-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1",
         "-q:v", "2", str(out_jpg)],
        desc=f"thumbnail @ {t:.1f}s",
    )


def _write_thumbs_readable(data: dict, path: Path) -> None:
    """Render thumbnails.json into a human-readable concept sheet."""
    lines = ["THUMBNAIL CONCEPTS",
             "Starting points — edit/add text & design yourself.",
             "=" * 60, ""]
    for c in data.get("concepts", []):
        lines.append(f"#{c.get('rank')}  [{c.get('frame_file')}]  "
                     f"@ {c.get('timestamp')}s  (scene {c.get('scene_index')})")
        if c.get("moment"):
            lines.append(f"  Moment:      {c['moment']}")
        if c.get("why"):
            lines.append(f"  Why it works: {c['why']}")
        if c.get("headline"):
            lines.append(f"  Headline:    \"{c['headline']}\"")
        if c.get("composition"):
            lines.append(f"  Composition: {c['composition']}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _beats(script):
    """Accept either a list of beats or a {'beats': [...]} dict."""
    if isinstance(script, dict):
        return script.get("beats", [])
    return script or []
