"""Moment selection — explainable rubric scoring over Timing Map windows.

Follows the clip-scoring skill exactly:
  1. Sliding windows over segments within the platform duration band.
  2. Each candidate scored 0-10 on 7 subscores, weighted numerically here
     (the scorer never applies weights — honest cold-viewer simulation).
  3. Non-max suppression: drop candidates overlapping a better one >50%.

Two intelligence layers (exactly one active):
  operator — Claude Code reads select_task.json and writes moments.json
  LLM      — OpenRouter scores each candidate against the rubric
"""
from __future__ import annotations

import itertools
import json
import re
import time
from pathlib import Path

import os

from . import config
from .utils import log

SUBSCORE_KEYS = list(config.RUBRIC_WEIGHTS)

RUBRIC_PROMPT = """You are scoring ONE candidate short-form clip. The transcript \
window below is your ONLY context — judge it exactly as a cold viewer would, \
with zero knowledge of the rest of the video.

Score each dimension 0-10 (integers). Do NOT compute a total.
- hook: do the first ~2 seconds create a question, bold claim, or pattern-interrupt?
- self_containment: understandable alone? No dangling pronouns, no references to \
earlier content; setup AND payoff inside the window.
- payoff: does it resolve — punchline, reveal, completed mini-arc?
- emotion: surprise, humor, outrage, awe; concrete beats abstract.
- quotability: a line someone would caption or repeat verbatim.
- density: high idea-per-second, no dead air.
- duration_fit: does the clip EARN its length? A tight {lo}s cut and a rich \
{hi}s story can both score 10. Score down padding, rambling, a slow start, or \
a story that stops before its payoff — never length by itself. If the window \
holds one crisp beat, long is wrong; if it holds a full arc, long is right.

Hard disqualifiers (set "disqualified": true and say why): cuts mid-sentence, \
opens with filler ("so, um, anyway"), or makes claims indefensible out of \
context.

Visual dependency: if the transcript SUGGESTS a strong visual moment you \
cannot judge from words alone — reactions ([laughter], [screaming], \
[cheering]), demonstrations ("look at this", "watch"), gestures, physical \
comedy, on-screen events the speakers react to — set "needs_visual": true \
instead of guessing or disqualifying. The engine will fetch frames and a \
vision pass will finish the judgment. Use it only when visuals could \
genuinely change the verdict, not for ordinary talking.

Also write: hook_text (first line verbatim from the transcript), a \
suggested_title (max 90 chars, curiosity-driven), a caption (1-2 sentences + \
CTA), hashtags (5-8), and rationale (1-2 lines).

Respond with ONLY strict JSON:
{"subscores": {"hook":0,"self_containment":0,"payoff":0,"emotion":0,\
"quotability":0,"density":0,"duration_fit":0}, "disqualified": false, \
"disqualify_reason": "", "needs_visual": false, "hook_text": "", \
"suggested_title": "", "caption": "", "hashtags": [], "rationale": ""}"""


# ---------- candidate generation ----------
def _targets_ms() -> list:
    """Target clip lengths, clamped into the configured band and deduped."""
    lo, hi = config.MIN_CLIP_SECONDS * 1000, config.MAX_CLIP_SECONDS * 1000
    return sorted({min(max(t * 1000, lo), hi) for t in config.CANDIDATE_TARGETS_S})


SENTENCE_END = (".", "?", "!")


def starts_sentence(segs: list, i: int) -> bool:
    """Can a clip open at segment i without landing mid-sentence?

    YouTube auto-caption segments break on TIMING, not syntax, so a segment
    boundary is not a sentence boundary — that is what produced openings like
    "much to elaborate on." and "[__] your homies and". A start is clean when
    the previous segment finished its sentence, or when this one opens a new
    speaker turn (">>"), which is a good cold open regardless.
    """
    if i == 0:
        return True
    if segs[i]["text"].lstrip().startswith(">>"):
        return True
    return segs[i - 1]["text"].rstrip().endswith(SENTENCE_END)


def ends_sentence(segs: list, j: int) -> bool:
    """Can a clip close at segment j — i.e. does it finish its sentence?"""
    return segs[j]["text"].rstrip().endswith(SENTENCE_END)


def _windows(tm: dict, strict: bool) -> list:
    """Window generation; `strict` enforces sentence-aligned boundaries."""
    segs = tm["segments"]
    lo, hi = config.MIN_CLIP_SECONDS * 1000, config.MAX_CLIP_SECONDS * 1000
    targets = _targets_ms()
    out, seen = [], set()

    def emit(start, j, dur, i):
        key = (start, segs[j]["end_ms"])
        if dur >= lo and key not in seen:
            seen.add(key)
            out.append({"start_ms": start, "end_ms": segs[j]["end_ms"],
                        "seg_range": (i, j), "duration_s": round(dur / 1000, 1)})

    for i in range(len(segs)):
        if strict and not starts_sentence(segs, i):
            continue
        start = segs[i]["start_ms"]
        ti = 0
        last = None                    # longest window still inside the band
        for j in range(i, len(segs)):
            dur = segs[j]["end_ms"] - start
            if dur > hi:
                break
            # A window may only close on a finished sentence; skipping j
            # without consuming a target lets the next one carry the length.
            if strict and not ends_sentence(segs, j):
                continue
            last = (j, dur)
            while ti < len(targets) and dur >= targets[ti]:
                ti += 1
                emit(start, j, dur, i)
            if ti >= len(targets):
                break
        # Segment boundaries rarely land exactly on a target, so a start can
        # run out of runway (dur jumps past hi) with long targets unemitted —
        # that starved the 180s end of the range almost entirely. Always offer
        # the longest window that DID fit.
        if last and ti < len(targets):
            emit(start, last[0], last[1], i)
    return out


def candidate_windows(tm: dict) -> list:
    """For each starting segment, one window per target length.

    Boundaries snap to SENTENCE ends, not merely to segment ends — a clip
    never starts or ends mid-sentence. Emitting several lengths per start is
    what lets a 30s and a 3-minute treatment of the same moment compete.

    Some transcripts carry no punctuation at all (whisper on a noisy source,
    or captions stripped of it); those would yield nothing under the sentence
    rule, so fall back to raw segment boundaries rather than return empty.

    Deliberately does NOT build the transcript text: with a 180s ceiling the
    raw window count runs to six figures on a long video, and joining text for
    all of them would burn memory for candidates that get thinned away
    immediately. Text is attached after thinning (see attach_text).
    """
    out = _windows(tm, strict=True)
    if not out:
        log("Transcript has no sentence punctuation — falling back to raw "
            "segment boundaries (clips may open or close mid-sentence).")
        out = _windows(tm, strict=False)
    return out


def thin_candidates(cands: list, max_n: int = None) -> list:
    """Cap the count while preserving BOTH kinds of coverage: positions spread
    across the whole video, and the length variants at each kept position."""
    max_n = max_n or config.CANDIDATE_LIMIT
    if len(cands) <= max_n:
        return cands
    by_start = {}
    for c in cands:
        by_start.setdefault(c["start_ms"], []).append(c)
    starts = sorted(by_start)
    variants = max(1, len(_targets_ms()))
    keep_starts = max(1, max_n // variants)
    step = max(1, len(starts) / keep_starts)
    kept = []
    for k in range(keep_starts):
        idx = int(k * step)
        if idx >= len(starts):
            break
        kept.extend(by_start[starts[idx]])
    return kept[:max_n]


def attach_text(cands: list, tm: dict) -> list:
    """Fill in transcript text + stable ids for the survivors of thinning.

    candidate_id is derived from the window itself, not its position in the
    list, so it stays stable if generation order ever changes — segment files
    and visual frames are cached under it (see pipeline.stage_download)."""
    segs = tm["segments"]
    for c in cands:
        i, j = c.pop("seg_range", (None, None))
        if i is not None:
            c["text"] = " ".join(s["text"] for s in segs[i:j + 1])
        c["candidate_id"] = f"cand_{c['start_ms']}_{c['end_ms']}"
    return cands


def weighted_score(subscores: dict) -> float:
    w = config.RUBRIC_WEIGHTS
    total_w = sum(w.values())
    return round(sum(subscores.get(k, 0) * w[k] for k in w) / total_w, 2)


def nms(clips: list) -> list:
    """Non-max suppression: keep best, drop overlaps >50% of the shorter."""
    clips = sorted(clips, key=lambda c: -c["score"])
    kept = []
    for c in clips:
        for k in kept:
            inter = min(c["end_ms"], k["end_ms"]) - max(c["start_ms"], k["start_ms"])
            shorter = min(c["end_ms"] - c["start_ms"], k["end_ms"] - k["start_ms"])
            if shorter > 0 and inter > 0.5 * shorter:
                break
        else:
            kept.append(c)
    return kept


def finalize(scored: list) -> list:
    """Filter, suppress overlaps, cap, order chronologically.

    Clips flagged needs_visual and not yet visually reviewed get a grace
    window below the bar — the vision pass will confirm or reject them."""
    def clears(c):
        bar = config.MIN_SCORE
        if c.get("needs_visual") and not c.get("visual_reviewed"):
            bar -= config.VISUAL_GRACE
        return c["score"] >= bar
    good = [c for c in scored if not c.get("disqualified") and clears(c)]
    good = nms(good)[: config.MAX_CLIPS]
    good.sort(key=lambda c: c["start_ms"])
    for i, c in enumerate(good, 1):
        c["clip_id"] = f"clip_{i:02d}"
    return good


# ---------- intelligence layers ----------
def select_moments(tm: dict, project_dir: Path) -> list:
    """Return final clips [{clip_id,start_ms,end_ms,score,subscores,...}].
    Cached in moments.json; operator mode pauses with a task file."""
    out = project_dir / "moments.json"
    if out.exists():
        clips = json.loads(out.read_text(encoding="utf-8-sig"))
        # re-finalize so a hand-edited file still gets NMS/caps/ordering
        for c in clips:
            c.setdefault("score", weighted_score(c.get("subscores", {})))
        return verify_titles(write_hooks(finalize(clips)))

    cands = attach_text(thin_candidates(candidate_windows(tm)), tm)
    if not cands:
        raise RuntimeError(
            f"No candidate windows fit the {config.MIN_CLIP_SECONDS}-"
            f"{config.MAX_CLIP_SECONDS}s duration band. The video may be "
            "shorter than CLIP_MIN_SECONDS, or its transcript may be empty.")

    if config.OPERATOR_MODE or not config.LLM_ENABLED:
        task = project_dir / "select_task.json"
        task.write_text(json.dumps({
            "instructions": (
                "OPERATOR TASK — score these candidate windows against the "
                "clip-scoring rubric (subscores 0-10 each: " + ", ".join(SUBSCORE_KEYS) +
                "; the engine applies weights). For each candidate you keep, "
                "emit {candidate_id, start_ms, end_ms, subscores{}, hook_text, "
                "suggested_title, caption, hashtags, rationale}. Discard weak "
                "ones and hard-disqualified ones (mid-sentence cut, not "
                "self-contained, filler open). If a candidate hints at a "
                "strong VISUAL moment you can't judge from the transcript "
                "([laughter]/[screaming], 'look at this', physical comedy, "
                "on-screen events), keep it with needs_visual: true instead "
                "of guessing — the engine will fetch frames for a vision "
                "review. Write the kept list as a JSON array to moments.json "
                "next to this file, then rerun clipinn."),
            "candidates": cands,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        raise OperatorTask(
            f"Selection needs the operator: score {len(cands)} candidates in\n"
            f"  {task}\nand write the kept clips to {out}, then rerun.")

    scored = _llm_score(cands)
    if not scored:
        raise RuntimeError(
            f"Every one of the {len(cands)} scoring calls to "
            f"{config.LLM_MODEL} failed — nothing was scored. Check "
            "OPENROUTER_API_KEY, the model name, and your credit balance. "
            "Nothing was downloaded, so rerunning costs only the retry.")
    out.write_text(json.dumps(scored, ensure_ascii=False, indent=1), encoding="utf-8")
    return verify_titles(write_hooks(finalize(scored)))


class OperatorTask(RuntimeError):
    """Raised when the pipeline pauses for Claude Code to do the thinking."""


def _parse_json_obj(text: str) -> dict:
    # A reasoning model (deepseek-v4-flash and friends) can spend the entire max_tokens
    # budget on reasoning tokens and return content=None. That surfaced as a baffling
    # "'NoneType' object has no attribute 'strip'" on 3 of 12 verifications; say what
    # actually happened instead, for every caller of this parser.
    if not text:
        raise ValueError(
            "model returned empty content - a reasoning model can consume the whole "
            "max_tokens budget before writing an answer; raise max_tokens")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        raise ValueError(f"no JSON object in: {text[:200]}")
    raw = text[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


VERIFY_PROMPT = """You are fact-checking a short-video title against the transcript it \
was made from.

TRANSCRIPT:
{text}

TITLE: {title}

Does the title assert any fact, event, or consequence the transcript does not support? \
Paraphrase, compression and hype are fine. Inventing people, events, or outcomes is not.
Answer ONLY JSON: {"supported": true|false, "problem": "<short reason or empty>"}"""


HOOK_PROMPT = """You are writing the on-screen hook for a short vertical video.
It sits over the first seconds and is the ONLY thing deciding whether someone stops
scrolling.

TRANSCRIPT OF THE CLIP:
{text}

Write ONE line that makes a stranger want to watch THIS clip.

Rules:
- Under 60 characters. It is burned onto the video; long lines shrink to nothing.
- Say what is interesting ABOUT the clip. Never transcribe its first sentence.
- Ground it in what actually happens here. No invented people, numbers or outcomes.
- Write like a person talking, not a headline. No "you won't believe", no "this is
  why", no colon-splices, no emoji, no hashtags, no quotation marks.
- Create a gap: name the interesting thing, withhold the resolution. If the clip
  answers a question, ask it. If it lands a surprise, point at it without spoiling.

Answer ONLY JSON: {"hook": "<the line>"}"""


HOOK_MAX_TOKENS = int(os.getenv("HOOK_MAX_TOKENS", "2400"))


def write_hooks(clips: list) -> list:
    """Write a real hook for each kept clip, instead of quoting its first line.

    The scoring pass asks for hook_text "verbatim from the transcript", which makes the
    on-screen caption whatever the speaker happened to say first — usually the least
    interesting sentence in the clip. That is a quote, not a hook.

    This runs only on the clips that survived selection, so it is a handful of calls
    rather than one per candidate, and it can afford a prompt that does one job well.

    Grounding is enforced, not requested: a hook is burned into the video and cannot be
    reviewed in a list later, so an unsupported one FALLS BACK to the verbatim line.
    Titles are only flagged (see verify_titles) because a human still sees those.
    """
    if not clips or not config.LLM_ENABLED:
        return clips
    todo = [c for c in clips if c.get("text") and not c.get("hook_written")]
    if not todo:
        return clips

    from concurrent.futures import ThreadPoolExecutor
    from openai import OpenAI
    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)

    def ask(prompt, temperature):
        # A reasoning model spends this budget THINKING before it writes anything, so
        # a fifteen-word answer still needs a large cap: at 200 it returned empty 3
        # times in 4, and at 900 it still lost one clip in four. The output is tiny
        # either way — only the reasoning that precedes it is not.
        resp = client.chat.completions.create(
            model=config.LLM_MODEL, max_tokens=HOOK_MAX_TOKENS,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}])
        return _parse_json_obj(resp.choices[0].message.content)

    def one(c: dict) -> None:
        quote = (c.get("hook_text") or "").strip()
        c["hook_quote"] = quote          # keep what it used to say
        text = (c.get("text") or "")[:6000]
        try:
            hook = str(ask(HOOK_PROMPT.replace("{text}", text), 0.8)
                       .get("hook", "")).strip().strip('"')
        except Exception as e:
            log(f"  {c.get('clip_id','?')} hook generation failed: {str(e)[:120]}")
            return                        # keeps the verbatim line, which is not wrong
        if not hook or len(hook) > 90:
            return
        # One retry with the objection fed back. The first attempt reaches for a
        # comparison or a cause the clip never makes; told exactly what it invented,
        # it usually writes a grounded line instead of a blander one.
        for attempt in (1, 2):
            try:
                verdict = ask(VERIFY_PROMPT.replace("{text}", text)
                                           .replace("{title}", hook), 0)
            except Exception:
                return                  # unverified means unused, never "probably fine"
            if verdict.get("supported", False):
                c["hook_text"] = hook
                c["hook_written"] = True
                return
            if attempt == 2:
                break
            try:
                retry = (HOOK_PROMPT.replace("{text}", text) +
                         f"\n\nA previous attempt was rejected:\n  {hook}\n"
                         f"Reason: {str(verdict.get('problem', ''))[:200]}\n"
                         "Write a different line that stays strictly inside what the "
                         "transcript actually says.")
                hook = str(ask(retry, 0.7).get("hook", "")).strip().strip('"')
            except Exception:
                return
            if not hook or len(hook) > 90:
                return
        log(f"  {c.get('clip_id','?')} hook not supported, keeping the quote: {hook}")

    with ThreadPoolExecutor(max_workers=config.LLM_CONCURRENCY) as pool:
        list(pool.map(one, todo))
    written = sum(1 for c in clips if c.get("hook_written"))
    log(f"Hooks: wrote {written}/{len(clips)}"
        + (f", {len(clips) - written} kept their transcript line" if written < len(clips)
           else ""))
    return clips


def verify_titles(clips: list) -> list:
    """Flag titles that assert things the clip's own transcript never says.

    Selection is extractive — the model ranks spans that already exist — but titling is
    generative, and a cheap model will reach for a familiar clickbait shape and fill it
    with facts that were never in the source. Measured on a BeardMeatsFood run: 2 of 4
    titles invented an event ("banned from Denmark", "book signing"). Word-overlap
    scoring does NOT separate those from honest paraphrase ("leaves him speechless") —
    both look equally unsupported at the token level. Asking the model to judge
    entailment does: 4/4 on that sample, on the free model.

    Sets title_supported (True/False/None when unchecked) and title_problem. Never
    raises and never rewrites a title — this gate reports, a human decides.
    """
    if not clips or not getattr(config, "VERIFY_TITLES", True):
        return clips
    todo = [c for c in clips if c.get("suggested_title") and "title_supported" not in c]
    if not todo:
        return clips
    if not config.LLM_ENABLED:
        for c in todo:                      # explicitly unchecked, never silently "fine"
            c["title_supported"], c["title_problem"] = None, "no LLM available to verify"
        return clips

    from concurrent.futures import ThreadPoolExecutor
    from openai import OpenAI
    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)

    def check(c: dict) -> None:
        prompt = (VERIFY_PROMPT.replace("{text}", (c.get("text") or "")[:6000])
                               .replace("{title}", c["suggested_title"]))
        # The free model is not deterministic even at temperature 0: the same title
        # came back supported on one run and fabricated on the next. Vote, and let a
        # single "unsupported" decide — this gate only FLAGS for review, so a false
        # flag costs a glance while a miss ships an invented claim to a user.
        verdicts = []
        for _ in range(config.VERIFY_VOTES):
            try:
                resp = client.chat.completions.create(
                    model=config.LLM_MODEL, max_tokens=config.VERIFY_MAX_TOKENS, temperature=0,
                    messages=[{"role": "user", "content": prompt}])
                r = _parse_json_obj(resp.choices[0].message.content)
                verdicts.append((bool(r.get("supported")), str(r.get("problem", ""))[:300]))
            except Exception as e:
                # Free tiers rate-limit; a 429 is not a verdict. Retry once slowly
                # before recording "unchecked", or the gate reports noise as doubt.
                try:
                    time.sleep(5)
                    resp = client.chat.completions.create(
                        model=config.LLM_MODEL, max_tokens=config.VERIFY_MAX_TOKENS, temperature=0,
                        messages=[{"role": "user", "content": prompt}])
                    r = _parse_json_obj(resp.choices[0].message.content)
                    verdicts.append((bool(r.get("supported")), str(r.get("problem", ""))[:300]))
                except Exception:
                    verdicts.append((None, f"verification failed: {e}"[:300]))
        if any(v is False for v, _ in verdicts):
            c["title_supported"] = False
            c["title_problem"] = next(p for v, p in verdicts if v is False)
        elif all(v is True for v, _ in verdicts):
            c["title_supported"], c["title_problem"] = True, ""
        else:
            # A verifier that errored must not pass the title — unchecked is its own state.
            c["title_supported"] = None
            c["title_problem"] = next(p for v, p in verdicts if v is None)

    # ponytail: re-verifies on a cached rerun because the verdicts are not written back
    # into moments.json. It is <=MAX_CLIPS calls on a free model; persist them only if
    # that ever shows up in a bill.
    with ThreadPoolExecutor(max_workers=config.LLM_CONCURRENCY) as pool:
        list(pool.map(check, todo))
    bad = [c for c in clips if c.get("title_supported") is False]
    log(f"Title check: {len(clips) - len(bad)}/{len(clips)} supported by their transcript"
        + (f" — {len(bad)} flagged for review" if bad else ""))
    for c in bad:
        log(f"  {c.get('clip_id', '?')} unsupported title: {c['suggested_title']}")
        log(f"     {c['title_problem']}")
    return clips


def _llm_score(cands: list) -> list:
    """Score each candidate independently against the rubric (cold viewer).

    Candidates are scored concurrently — they're independent by design (each
    is judged with no context but its own window), and 120 sequential network
    round-trips would cost more time than the segment-download savings.
    """
    from concurrent.futures import ThreadPoolExecutor
    from openai import OpenAI

    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)
    # .replace, not .format — the prompt contains literal JSON braces
    prompt = (RUBRIC_PROMPT.replace("{lo}", str(config.MIN_CLIP_SECONDS))
                           .replace("{hi}", str(config.MAX_CLIP_SECONDS)))
    done = itertools.count(1)

    def score_one(c: dict) -> dict | None:
        user = f"duration: {c['duration_s']}s\ntranscript window:\n{c['text'][:4000]}"
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=config.LLM_MODEL, max_tokens=1000, temperature=0.2,
                    messages=[{"role": "system", "content": prompt},
                              {"role": "user", "content": user}])
                r = _parse_json_obj(resp.choices[0].message.content)
                n = next(done)
                if n % 20 == 0:
                    log(f"  ...{n}/{len(cands)} scored")
                return {**c, **r, "score": weighted_score(r.get("subscores", {}))}
            except Exception as e:
                if attempt == 2:
                    log(f"  {c['candidate_id']} gave up after 3 attempts: {e}")
                    next(done)
        return None

    log(f"Scoring {len(cands)} candidates against the rubric "
        f"({config.LLM_MODEL}, {config.LLM_CONCURRENCY} at a time)...")
    with ThreadPoolExecutor(max_workers=config.LLM_CONCURRENCY) as pool:
        results = list(pool.map(score_one, cands))
    return [r for r in results if r]
