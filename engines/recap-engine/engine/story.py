"""Stage: story understanding + recap script generation (the "brain").

Pipeline (to be implemented incrementally):
  1. summarize_transcript()  - map-reduce the full timestamped transcript into a
     compact STORY OUTLINE (characters, setting, ordered beats, arc, ending).
  2. write_recap_script()    - from the outline, write an ORIGINAL narration
     script split into ordered beats; each beat tagged with the approximate
     source time range it describes and a target spoken length.
  3. match_beats_to_scenes() - assign each narration beat the best source
     scene(s) using its time range + semantic similarity, snapped to shot cuts.

LLM backend is pluggable (config.LLM_BACKEND):
  - "openrouter": automatic API call (like the clip engine).
  - "manual": write the prompt to llm_io/<step>.prompt.txt, pause, and read the
     answer back from llm_io/<step>.response.txt -> lets you run the heavy story
     reasoning through Claude Code / Claude for free with the strongest model.
"""
import json
from pathlib import Path

import numpy as np

import config
from engine.utils import die, fmt_ts, log, parse_json_loose


def call_brain(prompt: str, system: str, step: str, workdir: Path) -> str:
    """Run one LLM call via the configured backend (config.LLM_BACKEND) and
    return the raw text response. Callers parse it themselves (use
    engine.utils.parse_json_loose for JSON steps).

      - "openrouter": automatic OpenAI-compatible API call.
      - "manual":     file hand-off - write the prompt to llm_io/<step>.prompt.txt,
                      wait for the user to drop llm_io/<step>.response.txt next to
                      it, then read it back. Lets the heavy story reasoning run on
                      the strongest model (Claude) for free.
    """
    backend = (config.LLM_BACKEND or "").strip().lower()
    if backend == "openrouter":
        return _call_openrouter(prompt, system, step)
    if backend == "manual":
        return _call_manual(prompt, system, step, workdir)
    die(f"Unknown LLM_BACKEND '{config.LLM_BACKEND}'. Use 'openrouter' or 'manual'.")


def _call_openrouter(prompt: str, system: str, step: str) -> str:
    """One chat completion through OpenRouter's OpenAI-compatible endpoint."""
    if not config.OPENROUTER_API_KEY:
        die("LLM_BACKEND=openrouter but OPENROUTER_API_KEY is not set "
            "(put it in the project .env).")
    try:
        from openai import OpenAI
    except ImportError:
        die("The 'openai' package is required for the openrouter backend.\n"
            "  Run:  pip install openai")

    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)
    log(f"[brain:{step}] calling {config.LLM_MODEL} via OpenRouter...")
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        die(f"[brain:{step}] OpenRouter returned an empty response.")
    return text


def _call_manual(prompt: str, system: str, step: str, workdir: Path) -> str:
    """File hand-off backend: write the prompt, wait for a response file, read it.

    Resumes cleanly - if a non-empty response file is already present we use it
    without prompting, so reruns (and tests) don't block on input().
    """
    io_dir = workdir / "llm_io"
    io_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = io_dir / f"{step}.prompt.txt"
    response_path = io_dir / f"{step}.response.txt"

    prompt_path.write_text(
        f"===== SYSTEM =====\n{system.strip()}\n\n"
        f"===== TASK ({step}) =====\n{prompt.strip()}\n",
        encoding="utf-8",
    )

    def _ready() -> bool:
        return response_path.exists() and bool(
            response_path.read_text(encoding="utf-8").strip())

    if not _ready():
        log("")
        log(f"[brain:{step}] MANUAL MODE - run this prompt through Claude:")
        log(f"   1. Open:  {prompt_path}")
        log(f"   2. Send its contents to Claude (e.g. `claude < \"{prompt_path}\"`).")
        log(f"   3. Save the full reply to:  {response_path}")
        log("")
        while not _ready():
            try:
                input(f"   Press Enter once {response_path.name} is ready "
                      f"(Ctrl-C to abort)... ")
            except (EOFError, KeyboardInterrupt):
                die(f"[brain:{step}] aborted while waiting for {response_path}.")

    text = response_path.read_text(encoding="utf-8").strip()
    log(f"[brain:{step}] got manual response ({len(text)} chars).")
    return text


def summarize_transcript(transcript: dict, workdir: Path,
                        target_minutes: int = 0) -> dict:
    """Map-reduce the full timestamped transcript into a compact STORY OUTLINE.

    A feature-film transcript will not fit one context window, so we:
      MAP    - split the transcript into time-ordered chunks and summarize each
               into ordered story beats (with approx_start/approx_end).
      REDUCE - fold all chunk beats into one global story bible:
               {logline, characters, setting, beats[], ending}.

    Cached to workdir/outline.json (rerun resumes).
    """
    out = workdir / "outline.json"
    if out.exists():
        log("outline.json already exists, skipping summarize")
        return json.loads(out.read_text(encoding="utf-8"))

    segments = transcript.get("segments", [])
    if not segments:
        die("summarize_transcript: transcript has no segments.")

    chunks = _chunk_segments(segments,
                             config.OUTLINE_CHUNK_CHARS,
                             config.OUTLINE_CHUNK_OVERLAP)
    research = load_research(workdir)
    log(f"Summarize: {len(segments)} segments -> {len(chunks)} chunk(s)"
        f"{'; using research.md' if research else '; NO research.md (see SKILL)'}.")

    # --- MAP: each chunk -> ordered beats ---
    chunk_beats = []
    for i, chunk in enumerate(chunks):
        raw = call_brain(_map_prompt(chunk, i, len(chunks), research),
                         _MAP_SYSTEM, f"outline_map_{i:02d}", workdir)
        data = parse_json_loose(raw)
        beats = data.get("beats", data) if isinstance(data, dict) else data
        if not isinstance(beats, list):
            die(f"summarize_transcript: chunk {i} did not return a beats list.")
        chunk_beats.extend(beats)
        log(f"  chunk {i + 1}/{len(chunks)}: {len(beats)} beats")

    # --- REDUCE: all chunk beats -> one outline ---
    duration = transcript.get("duration", 0.0)
    want_beats = (int(target_minutes * config.OUTLINE_BEATS_PER_MINUTE)
                  if target_minutes else 0)
    raw = call_brain(_reduce_prompt(chunk_beats, duration, research, want_beats),
                     _REDUCE_SYSTEM, "outline_reduce", workdir)
    outline = parse_json_loose(raw)
    if not isinstance(outline, dict) or "beats" not in outline:
        die("summarize_transcript: reduce step did not return an outline object.")

    # normalise beat ordering
    for i, b in enumerate(outline["beats"]):
        b["order"] = i

    out.write_text(json.dumps(outline, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    log(f"Outline: {len(outline['beats'])} global beats "
        f"({len(outline.get('characters', []))} characters).")
    return outline


def _chunk_segments(segments: list, max_chars: int, overlap_chars: int) -> list:
    """Split transcript segments into time-ordered chunks, each roughly max_chars
    of timestamped text. A small tail overlap is repeated at the head of the next
    chunk so a beat straddling a boundary survives. Each chunk is a dict
    {start, end, text}."""
    chunks = []
    cur, cur_len = [], 0
    for seg in segments:
        line = f"[{seg['start']:.1f}] {seg.get('text', '').strip()}"
        if cur and cur_len + len(line) > max_chars:
            chunks.append(cur)
            # carry an overlap tail into the next chunk
            tail, tlen = [], 0
            for prev in reversed(cur):
                tlen += len(prev)
                tail.insert(0, prev)
                if tlen >= overlap_chars:
                    break
            cur, cur_len = list(tail), sum(len(x) for x in tail)
        cur.append(line)
        cur_len += len(line)
    if cur:
        chunks.append(cur)

    out = []
    for lines in chunks:
        # recover start/end from the bracketed timestamps
        first = lines[0]
        start = float(first[1:first.index("]")])
        last = lines[-1]
        end = float(last[1:last.index("]")])
        out.append({"start": start, "end": end, "text": "\n".join(lines)})
    return out


_MAP_SYSTEM = (
    "You are a film story analyst. You receive ONE part of a movie transcript "
    "(timestamped dialogue/narration) and extract the STORY beats that happen in "
    "it, in order. Describe what HAPPENS (plot events), not the wording. Be "
    "faithful: do not invent events that aren't supported by the text. Output "
    "JSON only."
)


def load_research(workdir: Path) -> str:
    """Optional research brief for this title (workdir/research.md).

    Whisper mishears proper nouns constantly (character names, companies,
    places), and a transcript alone cannot tell you what a scene MEANS. So
    before the story stages run, the operator researches the film and drops a
    plain-text brief here; it is prepended to every story prompt as verified
    ground truth. Missing file = empty string, so the pipeline still runs.
    """
    f = workdir / "research.md"
    if not f.exists():
        return ""
    return (
        "VERIFIED BACKGROUND on this exact film, researched from outside the "
        "transcript. Treat it as ground truth: it outranks anything the "
        "transcript seems to say, especially the spelling of names, places and "
        "organisations, and it tells you what the story actually is.\n"
        f"{f.read_text(encoding='utf-8').strip()}\n\n"
        "=== END BACKGROUND ===\n\n"
    )


def _map_prompt(chunk: dict, idx: int, total: int, research: str = "") -> str:
    return (
        research +
        f"This is part {idx + 1} of {total} of a film transcript, covering "
        f"roughly {fmt_ts(chunk['start'])}-{fmt_ts(chunk['end'])}.\n\n"
        "Extract the ordered story beats in THIS part only. For each beat give:\n"
        '  "title": short label, "summary": 1-2 sentences of what happens,\n'
        '  "approx_start": seconds (float) when it begins (use the [timestamps]),\n'
        '  "approx_end": seconds (float) when it ends.\n\n'
        'Return JSON: {"beats": [ {"title","summary","approx_start","approx_end"} ]}\n\n'
        "TRANSCRIPT PART:\n"
        f"{chunk['text']}"
    )


_REDUCE_SYSTEM = (
    "You are a film story editor. You receive ordered story beats extracted from "
    "consecutive parts of a single movie. Merge them into ONE coherent, "
    "deduplicated story bible that covers the whole film beginning to end, "
    "including the ending. Keep chronological order. Output JSON only."
)


def _reduce_prompt(chunk_beats: list, duration: float, research: str = "",
                   want_beats: int = 0) -> str:
    return (
        research +
        f"Below are story beats from a film about {fmt_ts(duration)} long, in "
        "order. Some may overlap at part boundaries - merge duplicates and smooth "
        "the arc into a single outline.\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "logline": "one-sentence summary of the whole film",\n'
        '  "characters": [ {"name","description"} ],\n'
        '  "setting": "where/when the story takes place",\n'
        '  "beats": [ {"title","summary","approx_start","approx_end"} ],\n'
        '  "ending": "how the film resolves"\n'
        "}\n"
        "The beats array must read start-to-finish as the complete plot.\n"
        + (f"\nGRANULARITY: aim for roughly {want_beats} beats. This matters more "
           "than it looks. Each beat becomes ONE stretch of narration over ONE "
           "matched piece of footage, so a handful of fat beats leaves the "
           "picture sitting on a single moment for half a minute while the words "
           "move on past it. Break the story into SMALL, single-event beats - one "
           "thing happening, in one place - instead of merging a whole sequence "
           "into one summary. Keep each beat's approx_start/approx_end tight "
           "around the event it describes.\n" if want_beats else "")
        + "\nEXTRACTED BEATS:\n"
        + f"{json.dumps(chunk_beats, ensure_ascii=False)}"
    )


def write_recap_script(outline: dict, target_minutes: int, workdir: Path,
                       plan: list = None) -> list:
    """Write the ORIGINAL recap narration, beat by beat, AGAINST THE SHOT PLAN.

    Returns / caches script.json:
        [{order, narration, approx_start, approx_end, target_seconds,
          scenes:[...], dialogue:bool}]

    Since 2026-09-03 this is the second half of a two-step direction process:
    `plan_shots` picked each beat's footage first, and this stage writes to those
    specific shots - their real duration and their real dialogue - instead of to
    an abstract plot summary. That is what keeps the words and the picture
    together (see plan_shots for the measurement behind it).

    Passing plan=None falls back to the old blind path: write from the outline
    alone and let match_beats_to_scenes hunt for footage afterwards.
    """
    out = workdir / "script.json"
    if out.exists():
        log("script.json already exists, skipping script")
        return json.loads(out.read_text(encoding="utf-8"))

    # The caller (run.py) has already decided the target: an owner-chosen length
    # or the standard-window midpoint for long sources. Do NOT re-clamp it to the
    # config window here, or a deliberately short recap would be forced back up.
    target_minutes = (max(1, int(target_minutes)) if target_minutes
                      else (config.RECAP_MIN_MINUTES + config.RECAP_MAX_MINUTES) // 2)
    wpm = config.NARRATION_WPM
    budget_words = int(target_minutes * wpm)
    research = load_research(workdir)

    if plan:
        prompt = _directed_script_prompt(outline, plan, wpm, research)
    else:
        prompt = _script_prompt(outline, target_minutes, budget_words, research)
    raw = call_brain(prompt, _SCRIPT_SYSTEM, "script", workdir)
    data = parse_json_loose(raw)
    beats = data.get("beats", data) if isinstance(data, dict) else data
    if not isinstance(beats, list) or not beats:
        die("write_recap_script: brain did not return a non-empty beats list.")

    by_order = {int(p["order"]): p for p in (plan or [])}
    script = []
    for i, b in enumerate(beats):
        narration = (b.get("narration") or "").strip()
        planned = by_order.get(int(b.get("plan_order", i)) if plan else -1)
        is_dialogue = bool(b.get("play_dialogue"))
        if not narration and not is_dialogue:
            continue

        entry = {
            "order": i,
            "narration": narration,
            "approx_start": float(b.get("approx_start", 0.0) or 0.0),
            "approx_end": float(b.get("approx_end", 0.0) or 0.0),
            "target_seconds": round(len(narration.split()) / wpm * 60.0, 2),
        }
        if planned:
            entry["approx_start"] = planned["approx_start"]
            entry["approx_end"] = planned["approx_end"]
            entry["scenes"] = planned["shots"]
        if is_dialogue and planned:
            # A dialogue beat is a scene playing itself: no voiceover, and its
            # length is the footage, not a word count.
            entry["dialogue"] = True
            entry["narration"] = ""
            scene = _pick_dialogue_scene(planned)
            entry["scenes"] = [scene]
            entry["target_seconds"] = round(scene["end"] - scene["start"], 2)
        script.append(entry)

    if not script:
        die("write_recap_script: every beat had empty narration.")
    for i, s in enumerate(script):
        s["order"] = i  # renumber after dropping any empties

    total = sum(s["target_seconds"] for s in script)
    spoken = sum(1 for s in script if not s.get("dialogue"))
    log(f"Script: {len(script)} beats ({spoken} narrated, "
        f"{len(script) - spoken} dialogue), ~{total / 60:.1f} min "
        f"(target {target_minutes} min).")

    out.write_text(json.dumps(script, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return script


def _pick_dialogue_scene(planned: dict) -> dict:
    """For a dialogue beat, use the planned beat's talkiest shot - the one most
    likely to contain a real, quotable line rather than room tone."""
    shots = planned["shots"]
    talky = [s for s in shots if s.get("dialogue")]
    return max(talky or shots, key=lambda s: len(s.get("dialogue") or ""))

_SCRIPT_SYSTEM = (
    "You are a professional story-recap narrator and screenwriter. You write the "
    "ORIGINAL voiceover that retells a film's plot from beginning to end: "
    "chronological, clear, and engaging in a narrator's voice.\n"
    "Rules:\n"
    "- Never copy dialogue verbatim - describe what happens in your own words. A "
    "short direct quote is allowed at a genuinely big line.\n"
    "- Cover the WHOLE story including the ending. This is a full spoiler recap.\n"
    "- Keep it faithful to the outline, and keep naming characters so a viewer "
    "who looked away can find their way back.\n"
    "- WRITE TO THE PICTURE. Every sentence should describe something a viewer "
    "can SEE happening - who does what, where. Detail, rhythm and a narrator's "
    "warmth are wanted; what is not wanted is a line with no image behind it. "
    "Analysis, theme-talk, rhetorical questions and commentary about the film "
    "have no shot to sit under, and that is exactly where the picture starts "
    "drifting from the words. If you cannot point at what is on screen while a "
    "sentence is read, cut the sentence.\n"
    "This is prose, not a shot list: write full, flowing sentences in a real "
    "voice. Short clipped fragments read worse aloud than proper sentences do.\n"
    "Output JSON only."
)


def _script_prompt(outline: dict, target_minutes: int, budget_words: int,
                   research: str = "") -> str:
    """Legacy blind path: write the whole script from the outline, then hunt for
    footage afterwards. Superseded by _directed_script_prompt (see plan_shots);
    kept so a workdir without a shot plan still runs."""
    return (
        research +
        "Write the recap narration for this film, based on the story outline "
        "below.\n\n"
        f"TARGET LENGTH: about {target_minutes} minutes spoken, which is roughly "
        f"{budget_words} words TOTAL across all beats. Stay close to this budget.\n\n"
        "Write ONE narration beat per outline beat, in the same order, keeping "
        "its approx_start/approx_end. The outline has already been cut to the "
        "right granularity: each beat is one moment that gets its own piece of "
        "footage, so do NOT merge several outline beats into one long paragraph "
        "- that is what leaves the picture sitting still while the words move "
        "on. Roughly two to four sentences per beat.\n"
        "Give the story room. The reader should never feel rushed past something "
        "that matters: explain what is happening and why it matters to the people "
        "in it, so a viewer who has not seen the film follows it completely. Let "
        "it read as one continuous told story - carry the thread from beat to "
        "beat, never restart, never re-explain what you just said.\n"
        "For each beat provide:\n"
        '  "narration": the original voiceover prose for this beat,\n'
        '  "approx_start": the source time (seconds) this beat describes,\n'
        '  "approx_end": the source end time (seconds).\n'
        "Carry approx_start/approx_end from the matching outline beats so each "
        "narration beat is anchored to where it happens in the film.\n\n"
        'Return JSON: {"beats": [ {"narration","approx_start","approx_end"} ]}\n\n'
        "STORY OUTLINE:\n"
        f"{json.dumps(outline, ensure_ascii=False)}"
    )


def _directed_script_prompt(outline: dict, plan: list, wpm: int,
                            research: str = "") -> str:
    """Write narration to a shot plan that already exists.

    The beats, their order, their footage and their lengths are DECIDED here.
    The brain's only job is the words for each one - which is precisely what
    stops the narration from describing something the picture is not showing.
    """
    lines = []
    for p in plan:
        words = int(p["target_seconds"] / 60.0 * wpm)
        shots = "; ".join(
            f"[{s['start']:.0f}-{s['end']:.0f}s]"
            + (f' "{s["dialogue"][:90]}"' if s.get("dialogue") else " (no dialogue)")
            for s in p["shots"])
        lines.append(
            f"BEAT {p['order']} - {p['title']}\n"
            f"  story: {p['summary']}\n"
            f"  narration budget: ~{words} words (~{p['target_seconds']:.0f}s)\n"
            f"  shots on screen while it plays: {shots}")

    dialogue_note = (
        f"\n\nDIALOGUE BEATS: choose about {config.DIALOGUE_BEATS} beats where the "
        "film should stop and speak for itself - a confrontation, a threat, a "
        "reveal, a last line. On those, ALSO set \"play_dialogue\": true. The "
        "narrator falls silent and the scene plays its own audio, so write the "
        "beat BEFORE each one so it sets the moment up and hands over cleanly. "
        "Only pick beats whose shots actually carry strong dialogue."
        if config.DIALOGUE_BEATS > 0 else "")

    return (
        research +
        "Write the voiceover for this recap. The edit is already cut: each beat "
        "below lists the exact shots that will be on screen while its narration "
        "plays, and how many words fit.\n\n"
        "Write narration for EVERY beat, in order, describing what happens in "
        "THOSE shots - not the beat's summary in the abstract. The summary tells "
        "you what the beat means; the shots tell you what the viewer is actually "
        "looking at. Stay inside each budget (+/-15%): if a beat has forty "
        "seconds of footage then forty seconds of words go over it, and the story "
        "has to be told at that pace.\n"
        "It must read as ONE continuous story across beats - carry the thread "
        "forward, never restart, never re-explain what you just said."
        + dialogue_note + "\n\n"
        'Return JSON: {"beats": [ {"plan_order": <int>, "narration": "...", '
        '"play_dialogue": false} ]}\n\n'
        "STORY CONTEXT (for names, spellings and where this is going - do not "
        "narrate it directly):\n"
        f"logline: {outline.get('logline', '')}\n"
        f"characters: "
        f"{json.dumps(outline.get('characters', []), ensure_ascii=False)[:1200]}\n"
        f"ending: {outline.get('ending', '')}\n\n"
        "THE EDIT:\n" + "\n\n".join(lines)
    )


def reconcile_length(beats: list, workdir: Path, target_minutes: int,
                     min_minutes: int = None, max_minutes: int = None,
                     synth=None) -> list:
    """Settle the recap's length.

    Owner's policy (default): ACCEPT the natural TTS duration. After TTS each beat
    has a measured `audio_seconds`; we simply keep whatever total the narration
    naturally came in at and move on. We do NOT rewrite/expand/compress beats to
    force a target length - padding or trimming the writing to hit a number is a
    compromise, and the natural length is cleaner. The script is already budgeted
    with Piper's real reading rate (config.NARRATION_WPM), so the natural length
    lands near the requested minutes on its own.

    Legacy: set config.RECONCILE_LENGTH_REWRITE=1 to re-enable the old loop that
    rewrites off-window beats and re-synthesizes (up to RECONCILE_MAX_PASSES).
    The acceptance window is passed in by the caller; it defaults to the config
    window. `synth` is injectable for testing.
    """
    if synth is None:
        from engine import tts
        synth = tts.synthesize

    if min_minutes is None:
        min_minutes = config.RECAP_MIN_MINUTES
    if max_minutes is None:
        max_minutes = config.RECAP_MAX_MINUTES
    if not target_minutes:
        target_minutes = (min_minutes + max_minutes) // 2

    # Default policy: keep the natural length, no rewriting.
    if not config.RECONCILE_LENGTH_REWRITE:
        total = sum(b.get("audio_seconds") or 0.0 for b in beats)
        log(f"Length: {total / 60:.1f} min (natural TTS length, kept as-is; "
            f"requested ~{target_minutes} min).")
        return beats

    lo = min_minutes * 60.0
    hi = max_minutes * 60.0
    desired = min(hi, max(lo, target_minutes * 60.0))
    wpm = config.NARRATION_WPM
    audio_dir = workdir / "audio"

    for p in range(config.RECONCILE_MAX_PASSES):
        total = sum(b.get("audio_seconds") or 0.0 for b in beats)
        if lo <= total <= hi:
            log(f"Length OK: {total / 60:.1f} min within "
                f"{min_minutes}-{max_minutes} min.")
            return beats

        factor = desired / total if total > 0 else 1.0
        log(f"Reconcile pass {p + 1}: {total / 60:.1f} min -> target "
            f"{desired / 60:.1f} min (x{factor:.2f}).")

        changed = False
        for b in beats:
            if b.get("dialogue"):
                continue          # the film's own audio; there is nothing to rewrite
            cur = b.get("audio_seconds") or 0.0
            new_secs = cur * factor
            # skip beats already close to their share (avoid churn)
            if cur > 0 and abs(new_secs - cur) / cur < 0.08:
                continue
            words = max(3, int(round(new_secs / 60.0 * wpm)))
            raw = call_brain(_resize_prompt(b["narration"], words, new_secs),
                             _RESIZE_SYSTEM,
                             f"resize_{b['order']:03d}_p{p}", workdir)
            b["narration"] = _clean_text(raw)
            # invalidate this beat's audio so synth re-renders just it
            (audio_dir / f"beat_{b['order']:03d}.wav").unlink(missing_ok=True)
            b["audio"] = None
            b["audio_seconds"] = None
            changed = True

        if not changed:
            break
        beats = synth(beats, workdir)

    total = sum(b.get("audio_seconds") or 0.0 for b in beats)
    log(f"Reconcile done: {total / 60:.1f} min "
        f"(target {min_minutes}-{max_minutes} min).")
    return beats


_RESIZE_SYSTEM = (
    "You rewrite a single piece of recap voiceover narration to a target length "
    "while keeping the same story content, order, and narrator tone. Keep every "
    "key plot point; only change how concise or expansive the wording is. Return "
    "ONLY the rewritten narration text - no preamble, no quotes, no JSON."
)


def _resize_prompt(narration: str, words: int, seconds: float) -> str:
    return (
        f"Rewrite this narration to about {words} words (~{seconds:.0f} seconds "
        "spoken), preserving all the plot points and the order:\n\n"
        f"{narration}"
    )


def _clean_text(text: str) -> str:
    """Strip code fences / surrounding quotes from a plain-text LLM reply."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        s = s[1:-1].strip()
    return s


def plan_shots(outline: dict, transcript: dict, target_minutes: int,
               workdir: Path) -> list:
    """DIRECT THE RECAP BEFORE WRITING IT: pick each beat's footage first.

    Why this stage exists (measured 2026-09-03, see
    scientist/projects/movie-recap-craft-2026): every professional recap channel
    writes narration as concrete visible action in screen order, roughly one
    clause per shot - which is *why* their words and pictures never drift. We
    used to write the whole script from the outline and only then hunt for
    footage, so lines like "here is the problem with a weapon nobody understands"
    had no shot to sit on and the picture wandered.

    So: for each outline beat, choose the scene run NOW and record what is
    actually in those shots (their dialogue, their real duration). The script
    stage then writes to that shot list instead of to an abstract plot summary,
    which is the editor's order of operations rather than the essayist's.

    Each beat's share of the runtime is proportional to how much SOURCE time it
    covers, so a long sequence gets more narration than a passing moment.
    Cached to shotplan.json.
    """
    out = workdir / "shotplan.json"
    if out.exists():
        log("shotplan.json already exists, skipping shot planning")
        return json.loads(out.read_text(encoding="utf-8"))

    beats = outline.get("beats") or []
    if not beats:
        die("plan_shots: outline has no beats.")

    cards, emb = _load_cards(workdir)
    duration = float(transcript.get("duration") or cards[-1]["end"])

    spans = [max(1.0, float(b.get("approx_end") or 0) - float(b.get("approx_start") or 0))
             for b in beats]
    total_span = sum(spans) or 1.0
    budget = target_minutes * 60.0
    targets = [max(config.PLAN_MIN_BEAT_SECONDS, budget * s / total_span) for s in spans]

    texts = [f"{b.get('title', '')}. {b.get('summary', '')}".strip() for b in beats]
    picks = _assign_scenes(texts, beats, targets, cards, emb)

    plan = []
    for i, (b, chosen, secs) in enumerate(zip(beats, picks, targets)):
        shots = [{"index": j, "start": round(cards[j]["start"], 2),
                  "end": round(cards[j]["end"], 2),
                  "seconds": round(cards[j]["end"] - cards[j]["start"], 1),
                  "dialogue": cards[j]["dialogue"][:220]} for j in chosen]
        plan.append({
            "order": i,
            "title": b.get("title", ""),
            "summary": b.get("summary", ""),
            "approx_start": shots[0]["start"],
            "approx_end": shots[-1]["end"],
            "target_seconds": round(secs, 1),
            "footage_seconds": round(sum(s["seconds"] for s in shots), 1),
            "shots": shots,
        })

    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Shot plan: {len(plan)} beats directed over {fmt_ts(duration)} "
        f"({sum(len(p['shots']) for p in plan)} scenes, "
        f"{sum(p['footage_seconds'] for p in plan) / 60:.1f} min of footage "
        f"for a {target_minutes} min target).")
    return plan


def _load_cards(workdir: Path):
    """Scene cards + their embeddings, validated. Heavy onnx deps load on demand."""
    from engine import embed, index  # noqa: F401  (embed used by callers)

    cards_path = workdir / "scene_cards.json"
    if not cards_path.exists():
        die("scene_cards.json missing - run footage indexing "
            "(engine.index.build_scene_cards) first.")
    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    emb = index.load_embeddings(workdir)
    if not (len(cards) == len(emb["clip_image"]) == len(emb["dialogue_text"])):
        die("scene cards and embeddings are misaligned.")
    return cards, emb


def _first_usable_scene(cards: list) -> int:
    """Index of the first scene the recap is allowed to draw footage from.

    Everything before config.SOURCE_SKIP_SECONDS is studio idents, which a beat
    anchored near t=0 will otherwise match happily - and the recap then opens on
    somebody else's logo.
    """
    skip = config.SOURCE_SKIP_SECONDS
    if skip <= 0:
        return 0
    # First scene with anything left after the cutoff. A scene that STRADDLES it
    # is kept and trimmed by _clamp_scenes, because on a dark film the detector
    # often runs the ident and the opening shot together into one block - drop
    # the whole thing and the recap loses the opening it is narrating.
    for i, c in enumerate(cards):
        if c["end"] > skip:
            return i
    return 0


def _clamp_scenes(scenes: list) -> list:
    """Trim a beat's scenes so none of them reach back into the studio idents."""
    skip = config.SOURCE_SKIP_SECONDS
    if skip <= 0:
        return scenes
    out = []
    for sc in scenes:
        if float(sc["end"]) <= skip:
            continue                      # entirely inside the idents
        sc = dict(sc)
        sc["start"] = max(float(sc["start"]), skip)
        out.append(sc)
    return out or scenes


def _assign_scenes(texts: list, beats: list, targets: list, cards: list,
                   emb: dict) -> list:
    """Pick a contiguous scene run for each beat: coarse time filter, then a
    weighted blend of time proximity, CLIP visual similarity and dialogue
    similarity, then extend across adjacent scenes until the run covers the
    beat's target seconds. Returns one list of scene indices per beat."""
    from engine import embed

    clip_image, dialogue_text = emb["clip_image"], emb["dialogue_text"]
    scene_mid = np.array([(c["start"] + c["end"]) / 2.0 for c in cards])
    has_dlg = np.array([1.0 if c["has_dialogue"] else 0.0 for c in cards])

    beat_clip = embed.clip_text_embed(texts)
    beat_dlg = embed.text_embed(texts)

    floor_i = _first_usable_scene(cards)
    picks = []
    for bi, beat in enumerate(beats):
        b_start = float(beat.get("approx_start") or 0.0)
        b_end = float(beat.get("approx_end") or b_start)
        b_mid = (b_start + b_end) / 2.0

        if b_mid > 0:
            cand = np.where(np.abs(scene_mid - b_mid) <= config.MATCH_TIME_WINDOW)[0]
            if cand.size == 0:
                cand = np.arange(len(cards))
        else:
            cand = np.arange(len(cards))

        vis = embed.cosine_matrix(beat_clip[bi:bi + 1], clip_image[cand])[0]
        dlg = embed.cosine_matrix(beat_dlg[bi:bi + 1], dialogue_text[cand])[0]
        dlg = dlg * has_dlg[cand]                    # no credit to silent scenes
        if b_mid > 0:
            sigma = max(config.MATCH_TIME_WINDOW / 2.0, 1.0)
            tscore = np.exp(-((scene_mid[cand] - b_mid) ** 2) / (2 * sigma ** 2))
        else:
            tscore = np.zeros(cand.size)

        score = (config.MATCH_W_TIME * tscore
                 + config.MATCH_W_VISUAL * _norm01(vis)
                 + config.MATCH_W_DIALOGUE * _norm01(dlg))
        anchor = max(int(cand[int(np.argmax(score))]), floor_i)
        chosen = [i for i in _gather_footage(cards, anchor, float(targets[bi]))
                  if i >= floor_i]
        picks.append(chosen or [floor_i])
    return picks


def match_beats_to_scenes(script: list, scenes: list, transcript: dict,
                          workdir: Path) -> list:
    """Give every narration beat its source scene(s) -> edit.json:
        [{order, narration, scenes:[{start,end}], dialogue, audio, audio_seconds}]

    Scene-first path (the standard one since 2026-09-03): `plan_shots` already
    chose each beat's footage BEFORE the narration was written, so the beat
    arrives carrying its own scenes and they are simply carried through.
    Re-matching here could only move the picture away from the very shots the
    words were written for.

    Legacy path (no shot plan - narration written blind): match each beat by a
    weighted blend of time proximity, CLIP visual similarity and dialogue
    similarity, then extend across adjacent scenes until the footage covers the
    narration. Kept so an old workdir still assembles.
    """
    out = workdir / "edit.json"
    if out.exists():
        log("edit.json already exists, skipping matching")
        return json.loads(out.read_text(encoding="utf-8"))

    cards, emb = _load_cards(workdir)
    duration = float(transcript.get("duration")
                     or (scenes[-1]["end"] if scenes else cards[-1]["end"]))

    if script and all(b.get("scenes") for b in script):
        edit = [{"order": i,
                 "narration": b.get("narration", ""),
                 "scenes": _clamp_scenes([{"start": s["start"], "end": s["end"]}
                                          for s in b["scenes"]]),
                 "dialogue": bool(b.get("dialogue")),
                 "audio": None,
                 "audio_seconds": None}
                for i, b in enumerate(script)]
        source = "carried from the shot plan"
    else:
        picks = _assign_scenes([b["narration"] for b in script], script,
                               [float(b.get("target_seconds") or 0.0) for b in script],
                               cards, emb)
        edit = [{"order": i,
                 "narration": b["narration"],
                 "scenes": _clamp_scenes(
                     [{"start": cards[j]["start"], "end": cards[j]["end"]}
                      for j in chosen]),
                 "dialogue": False,
                 "audio": None,
                 "audio_seconds": None}
                for i, (b, chosen) in enumerate(zip(script, picks))]
        source = "matched"

    out.write_text(json.dumps(edit, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Edit plan: {len(edit)} beats {source} "
        f"(avg {sum(len(e['scenes']) for e in edit) / max(len(edit), 1):.1f} "
        f"scenes/beat) over {fmt_ts(duration)}.")
    return edit


def _norm01(a: np.ndarray) -> np.ndarray:
    """Min-max normalise to [0,1] so CLIP and text cosines are comparable before
    weighting. Constant input -> zeros."""
    a = np.asarray(a, dtype="float32")
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-8:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


def _gather_footage(cards: list, anchor: int, target_seconds: float) -> list:
    """Return chronological scene indices starting at the anchor, extended across
    consecutive scenes until they cover target_seconds. Always >=1.

    IMPORTANT: a scene counts only for the seconds we will actually KEEP from
    it (`config.usable_footage_seconds`: half when DROP_ALTERNATE_SHOTS, else
    at most SHOT_MAX_SECONDS). Counting full scene durations here is what
    produced a silently broken first attempt: a 25s beat was "covered" by two
    28s scenes, so the assembler had nowhere to cut.
    """
    def dur(i):
        return config.usable_footage_seconds(
            cards[i]["end"] - cards[i]["start"])

    chosen = {anchor}
    total = dur(anchor)
    fwd, bwd = anchor + 1, anchor - 1
    cap = max(1, config.MATCH_MAX_SCENES_PER_BEAT)
    while total < target_seconds and len(chosen) < cap and (
            fwd < len(cards) or bwd >= 0):
        if fwd < len(cards):                 # prefer extending forward in time
            chosen.add(fwd); total += dur(fwd); fwd += 1
        elif bwd >= 0:
            chosen.add(bwd); total += dur(bwd); bwd -= 1
    return sorted(chosen)


def ensure_scene_coverage(beats: list, scenes: list, workdir: Path) -> list:
    """Validate + repair the visual timeline BEFORE assembly.

    Matching gathers footage from a word-count *estimate* of each beat's length,
    and the length-reconcile loop then rewrites narration without re-gathering
    footage - so a beat can end up with less footage than its final voiceover,
    which is exactly what makes the picture run out (freeze) while narration keeps
    going. This stage runs once the REAL per-beat audio length is known and, for
    every beat, extends its footage across more consecutive scenes until it fully
    covers the narration (plus COVERAGE_MARGIN_SECONDS). It is not capped, and it
    re-writes edit.json so the assembler can simply trim each beat to length.

    Guarantees checked and logged:
      - each beat's footage >= its narration (or a loud warning if the source has
        no more footage to give),
      - the total visual timeline >= the total narration timeline.
    """
    margin = config.COVERAGE_MARGIN_SECONDS
    n = len(scenes)
    if n == 0:
        die("ensure_scene_coverage: no scenes to draw footage from.")

    # A scene contributes only the seconds the assembler will actually KEEP
    # (half, when DROP_ALTERNATE_SHOTS; else at most SHOT_MAX_SECONDS). Measuring
    # full scene durations here would declare a beat covered while the
    # assembler throws half the picture away.
    def sdur(i):
        return config.usable_footage_seconds(
            float(scenes[i]["end"]) - float(scenes[i]["start"]))

    # map a scene start time back to its global index (scenes tile the timeline)
    idx_by_start = {round(float(s["start"]), 3): i for i, s in enumerate(scenes)}

    def locate(sc):
        i = idx_by_start.get(round(float(sc["start"]), 3))
        if i is not None:
            return i
        # fallback: nearest scene by start time
        return min(range(n),
                   key=lambda k: abs(float(scenes[k]["start"]) - float(sc["start"])))

    changed = False
    short = []
    for b in beats:
        if b.get("dialogue"):
            # A dialogue beat IS its footage - the scene plays at its own length,
            # so there is nothing to cover and nothing to extend.
            continue
        need = float(b.get("audio_seconds") or 0.0) + margin
        cur_idxs = [locate(s) for s in b.get("scenes", [])] or [0]
        lo, hi = min(cur_idxs), max(cur_idxs)
        total = sum(sdur(i) for i in range(lo, hi + 1))

        # extend across consecutive scenes (forward first, then backward) until
        # the footage covers the narration or we run out of source video
        while total < need and (hi + 1 < n or lo - 1 >= 0):
            if hi + 1 < n:
                hi += 1; total += sdur(hi)
            else:
                lo -= 1; total += sdur(lo)

        # Re-derived straight from scenes.json, so the ident trim applied during
        # matching has to be re-applied here or coverage silently undoes it.
        new_scenes = _clamp_scenes(
            [{"start": float(scenes[i]["start"]),
              "end": float(scenes[i]["end"])} for i in range(lo, hi + 1)])
        if new_scenes != b.get("scenes"):
            b["scenes"] = new_scenes
            changed = True
        if total + 1e-3 < float(b.get("audio_seconds") or 0.0):
            short.append((b["order"], total, float(b["audio_seconds"])))

    out = workdir / "edit.json"
    out.write_text(json.dumps(beats, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    total_foot = sum(
        config.usable_footage_seconds(float(s["end"]) - float(s["start"]))
        for b in beats for s in b["scenes"])
    total_narr = sum(float(b.get("audio_seconds") or 0.0) for b in beats)
    log(f"Coverage check: visual {total_foot / 60:.1f} min vs narration "
        f"{total_narr / 60:.1f} min across {len(beats)} beats"
        f"{' (extended)' if changed else ' (already sufficient)'}.")
    if short:
        for order, have, want in short:
            log(f"  WARNING beat {order}: only {have:.1f}s usable footage for "
                f"{want:.1f}s narration - source ran out; "
                f"{'it will slow to fill' if config.DROP_ALTERNATE_SHOTS or config.FIT_BY_SPEED else 'it will loop to fill'}.")
    else:
        log("  All beats have enough footage to cover their narration.")
    return beats
