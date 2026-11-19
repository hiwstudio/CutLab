"""Step 3: find viral moments in the transcript using an LLM via OpenRouter.

Two-stage funnel for high recall + high precision:
  1. SCAN  (generous): surface EVERY moment with viral potential. Recall first.
  2. JUDGE (strict):    re-score each as a standalone clip, keep only the great
                        ones, rewrite hooks/titles. Precision second.

The number of clips is DYNAMIC: every moment that clears the quality bar is
kept (up to MAX_CLIPS). Strong videos yield more clips, weak videos fewer.

Produces moments.json: a list of
{ "start","end","score","hook","title","caption","hashtags","reason" }
"""
import json
import re
from pathlib import Path

import config
from engine.utils import log, fmt_ts

# --- Pass 1: SCAN. Be generous - this is the recall stage. ---
SCAN_PROMPT = """You are a world-class short-form video editor finding clips for \
TikTok, Reels and Shorts. This is the SCANNING stage. Your only job right now is \
RECALL: surface EVERY moment in this transcript that could possibly work as a \
viral short. A separate strict reviewer will cut the weak ones later, so when in \
doubt, INCLUDE it. Do NOT be picky here.

Surface a moment if it has ANY of these: a strong opening line, a story with a \
payoff, a hot take or controversial opinion, a surprising fact or number, genuine \
emotion (funny, shocking, inspiring, sad, angry), a useful tip or insight, a \
memorable quote, a question that creates curiosity, tension or conflict, a \
"wait what?" moment, or a satisfying conclusion.

Scan the ENTIRE transcript - beginning, middle AND end. Do not stop early. \
Spread your picks across the whole video; great moments are often in the middle.

HARD RULE — every clip must open and close on a complete thought:
- START only at a natural beginning: the first full sentence of an idea, a clear \
question, or the start of a new speaker turn. NEVER start mid-sentence, mid-clause, \
or mid-conversation ("and then...", "because...", "so anyway...", trailing \
continuations). Use the timestamp at the START of that transcript line.
- END only after the speaker finishes the idea: full sentence, punchline, or \
payoff. NEVER end mid-thought or mid-sentence. Use the timestamp at the END of \
that transcript line.
- The clip must stand alone: a stranger who never saw the full video must \
understand it from beginning to end with no abrupt cut-in or cut-off.
- Prefer a clean open/close over hitting an exact duration. Target {min_s}-{max_s} \
seconds, but extend or shorten by a few seconds (or merge adjacent sentences of \
the same story) whenever that yields a more natural beginning or ending. \
Completeness beats the duration band.

Respond with ONLY a strict JSON array (no markdown, no commentary, no trailing \
commas). Find as many as genuinely deserve it - typically 8 to 20 for a normal \
video. Each item:
{
  "start": <seconds, number>,
  "end": <seconds, number>,
  "score": <0-100 your rough guess of viral potential; be generous here>,
  "hook": "<overlay text, max 8 words, creates curiosity, may use ONE emoji>",
  "title": "<Shorts/TikTok title, max 90 chars, curiosity-driven>",
  "caption": "<post caption, 1-2 sentences + a question or CTA>",
  "hashtags": ["<5-8 hashtags: 1-2 broad, 3-5 niche>"],
  "reason": "<one sentence: the hook + the payoff>"
}
Never invent timestamps - only use ranges present in the transcript."""


# --- Pass 2: JUDGE. Be brutal - this is the precision stage. ---
JUDGE_PROMPT = """You are a brutally selective short-form content reviewer. You \
decide what actually gets posted. You will receive candidate clips (transcript \
excerpts + metadata) pulled from one long video. Judge each as a STANDALONE clip \
shown to someone who never saw the full video and is ready to swipe away in 1 \
second.

For EACH candidate ask:
1. Does the FIRST sentence stop the scroll? If the opening is weak, it fails.
2. Is it a complete, self-contained story (hook -> build -> payoff) that makes \
sense alone, with a satisfying ending?
3. Would a real person watch to the end and want to share, comment, or rewatch?
4. BOUNDARY CHECK (mandatory): read opening_line, closing_line, and the \
context_before / context_after fields.
   - If opening_line starts mid-thought or needs context_before to make sense, \
either move start earlier to a natural beginning OR reject.
   - If closing_line is incomplete / cut off, or context_after finishes the \
payoff, either move end later to complete the thought OR reject.
   - Prefer a slightly longer or shorter clip with a clean open and close over a \
perfect duration with abrupt cuts. Completeness always wins over target length.

Then SCORE it 0-100 with a harsh standard:
- 90-100: exceptional, would very likely go viral
- 80-89: strong, definitely worth posting
- 72-79: good, postable
- below 72: not good enough - REJECT it

Keep only what is genuinely worth posting. It is correct to reject half or more. \
When you keep a clip, adjust start/end whenever needed for a natural beginning \
and ending (use transcript line start/end times). Rewrite the hook/title/caption \
to be as catchy and specific as possible.

Respond with ONLY a strict JSON array. For EACH candidate return:
{"id": <same id>, "verdict": "keep" or "reject", "score": <0-100>,
 "start": <optional adjusted seconds>, "end": <optional adjusted seconds>,
 "hook": "<improved>", "title": "<improved>", "caption": "<improved>",
 "reason": "<one sentence: the hook + payoff, or why rejected>"}"""


def _transcript_lines(segments: list) -> list:
    return [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments]


def _chunk_segments(segments: list, max_chars: int = 24000,
                    overlap_segments: int = 6) -> list:
    """Split transcript into overlapping chunks so a moment that straddles a
    boundary is still seen whole in at least one chunk."""
    chunks, current, size = [], [], 0
    for seg in segments:
        line_len = len(seg["text"]) + 16
        if current and size + line_len > max_chars:
            chunks.append(current)
            # start next chunk with the tail of this one (overlap)
            current = current[-overlap_segments:] if overlap_segments else []
            size = sum(len(s["text"]) + 16 for s in current)
        current.append(seg)
        size += line_len
    if current:
        chunks.append(current)
    return chunks


def _parse_json_array(text: str) -> list:
    """Extract a JSON array from an LLM response, tolerating fences/noise
    and common LLM JSON mistakes (trailing commas, comments)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in LLM response: {text[:300]}")
    raw = text[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r",\s*([}\]])", r"\1", raw)          # trailing commas
    fixed = re.sub(r"^\s*//.*$", "", fixed, flags=re.M)  # // comments
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    items = []  # salvage individual objects
    for match in re.finditer(r"\{[^{}]*\}", fixed, flags=re.S):
        try:
            items.append(json.loads(re.sub(r",\s*([}\]])", r"\1", match.group())))
        except json.JSONDecodeError:
            continue
    if items:
        return items
    raise ValueError(f"Unparseable JSON from LLM: {raw[:300]}")


def _seg_index_at(segments: list, t: float) -> int | None:
    """Index of the segment containing t, else the nearest segment."""
    if not segments:
        return None
    for i, s in enumerate(segments):
        if s["start"] <= t <= s["end"] + 0.05:
            return i
    # nearest by distance to segment span
    best_i, best_d = 0, float("inf")
    for i, s in enumerate(segments):
        if t < s["start"]:
            d = s["start"] - t
        else:
            d = t - s["end"]
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def _snap_start_to_utterance(start: float, segments: list) -> float:
    """Pull start back to the beginning of the utterance that contains it.

    Never leave a clip opening mid-sentence: if the proposed start is inside a
    transcript segment, open at that segment's start (or the next segment if we
    landed in the last ~15% of a line, which is usually dead air into the next).
    """
    i = _seg_index_at(segments, start)
    if i is None:
        return start
    s = segments[i]
    span = max(s["end"] - s["start"], 0.01)
    # Near the end of a line → prefer the next thought's true start
    if start >= s["start"] + 0.85 * span and i + 1 < len(segments):
        return float(segments[i + 1]["start"])
    # Mid-line or early in the line → open at the line start
    if start > s["start"] + 0.15:
        return float(s["start"])
    # Already at/near the start; clamp to segment start for word alignment
    return float(s["start"])


def _snap_end_to_utterance(end: float, segments: list) -> float:
    """Push end forward to the end of the utterance that contains it.

    Never leave a clip ending mid-sentence: finish the containing transcript line.
    """
    i = _seg_index_at(segments, end)
    if i is None:
        return end
    s = segments[i]
    span = max(s["end"] - s["start"], 0.01)
    # Very early in a line → prefer previous line's clean end (unless first)
    if end <= s["start"] + 0.15 * span and i > 0:
        return float(segments[i - 1]["end"])
    # Otherwise complete the current utterance
    return float(s["end"])


def _extend_end_by_segments(start: float, end: float, segments: list,
                            min_dur: float) -> float:
    """Grow end by whole segments until duration >= min_dur (or out of speech)."""
    if end - start >= min_dur:
        return end
    i = _seg_index_at(segments, end)
    if i is None:
        return end
    # If end is already on a segment end, start growing from the next one
    j = i
    if abs(segments[i]["end"] - end) < 0.08:
        j = i + 1
    while j < len(segments) and end - start < min_dur:
        end = float(segments[j]["end"])
        j += 1
    return end


def _trim_end_by_segments(start: float, end: float, segments: list,
                          max_dur: float) -> float:
    """Shrink end by dropping whole trailing segments until duration <= max_dur.

    Always lands on a segment end so we never amputate a sentence. If even the
    first included segment alone exceeds max_dur, keep that full segment
    (completeness over the hard cap).
    """
    if end - start <= max_dur:
        return end
    # Collect segments fully/partially inside [start, end]
    idxs = [i for i, s in enumerate(segments)
            if s["end"] > start + 0.05 and s["start"] < end - 0.05]
    if not idxs:
        return end
    # Drop from the tail until under max_dur, keep at least the first segment
    while len(idxs) > 1:
        trial_end = float(segments[idxs[-2]]["end"])
        if trial_end - start <= max_dur:
            return trial_end
        idxs.pop()
    # Single segment (or still over): end at last remaining segment end
    return float(segments[idxs[-1]]["end"])


def _snap_to_words(moment: dict, segments: list) -> dict | None:
    """Snap clip boundaries to clean utterance edges, then word timings.

    Priority order (user hard rule):
      1. Natural beginning (start of a thought / transcript line)
      2. Natural ending (end of a finished sentence / transcript line)
      3. Target duration band — soft; grace past MAX is allowed to finish a thought
    Never hard-cut at start+MAX mid-sentence.
    """
    try:
        start, end = float(moment["start"]), float(moment["end"])
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start:
        return None

    if segments:
        start = _snap_start_to_utterance(start, segments)
        end = _snap_end_to_utterance(end, segments)
        if end <= start:
            # Degenerate after snap: keep the full utterance at start
            i = _seg_index_at(segments, start)
            if i is None:
                return None
            start = float(segments[i]["start"])
            end = float(segments[i]["end"])

    words = [w for s in segments for w in s.get("words") or []]
    if words:
        # Fine-align to first/last spoken word strictly inside the utterance
        # window. Use start < end (not <=) so a word that begins exactly at the
        # next segment boundary is not pulled in and bloating the end.
        in_range = [w for w in words
                    if w["end"] > start and w["start"] < end]
        if in_range:
            start = float(in_range[0]["start"])
            end = float(in_range[-1]["end"])

    min_s = float(config.MIN_CLIP_SECONDS)
    max_s = float(config.MAX_CLIP_SECONDS)
    grace = float(getattr(config, "CLIP_DURATION_GRACE", 20))
    soft_max = max_s + grace

    # Grow first (whole utterances only), then shrink if still over soft max.
    if end - start < min_s and segments:
        end = _extend_end_by_segments(start, end, segments, min_s)
        if end - start < min_s * 0.6:
            return None  # not enough speech left to form a clip

    if end - start > soft_max and segments:
        end = _trim_end_by_segments(start, end, segments, soft_max)
    elif end - start > max_s and segments:
        # Within grace of MAX: prefer a complete segment end under MAX when
        # possible; otherwise keep the clean utterance end (completeness wins).
        trimmed = _trim_end_by_segments(start, end, segments, max_s)
        if min_s * 0.6 <= (trimmed - start) <= soft_max:
            end = trimmed

    if end <= start:
        return None
    moment["start"], moment["end"] = round(start, 2), round(end, 2)
    return moment


def _dedupe(moments: list) -> list:
    """Drop moments that heavily overlap a higher-scored one."""
    moments = sorted(moments, key=lambda m: -m.get("score", 0))
    kept = []
    for m in moments:
        overlap = False
        for k in kept:
            inter = min(m["end"], k["end"]) - max(m["start"], k["start"])
            shorter = min(m["end"] - m["start"], k["end"] - k["start"])
            if shorter > 0 and inter > 0.5 * shorter:
                overlap = True
                break
        if not overlap:
            kept.append(m)
    return kept


def _build_scan_prompt() -> str:
    return (SCAN_PROMPT
            .replace("{min_s}", str(config.MIN_CLIP_SECONDS))
            .replace("{max_s}", str(config.MAX_CLIP_SECONDS)))


def _call_llm(user_text: str, system_prompt: str, temperature: float = 0.4) -> str:
    from openai import OpenAI  # OpenRouter is OpenAI-API compatible

    if not config.LLM_ENABLED:
        raise RuntimeError(
            "LLM is disabled (no OPENROUTER_API_KEY, or LLM_MODEL starts with '~')."
        )
    client = OpenAI(base_url=config.OPENROUTER_BASE_URL,
                    api_key=config.OPENROUTER_API_KEY)
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=8000,  # scan can return 20 full JSON objects; 4k truncated
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return resp.choices[0].message.content


def _excerpt(segments: list, start: float, end: float, limit: int = 1500) -> str:
    text = " ".join(s["text"] for s in segments
                    if s["end"] > start and s["start"] < end)
    return text[:limit]


def _boundary_context(segments: list, start: float, end: float) -> dict:
    """First/last spoken lines plus neighbors so JUDGE can fix abrupt cuts."""
    inside = [s for s in segments if s["end"] > start and s["start"] < end]
    if not inside:
        return {
            "opening_line": "",
            "closing_line": "",
            "context_before": "",
            "context_after": "",
        }
    first, last = inside[0], inside[-1]
    i0 = segments.index(first) if first in segments else _seg_index_at(segments, start)
    i1 = segments.index(last) if last in segments else _seg_index_at(segments, end)
    before = segments[i0 - 1]["text"] if i0 is not None and i0 > 0 else ""
    after = (segments[i1 + 1]["text"]
             if i1 is not None and i1 + 1 < len(segments) else "")
    return {
        "opening_line": first["text"],
        "closing_line": last["text"],
        "context_before": before,
        "context_after": after,
    }


def _scan(segments: list) -> list:
    """Pass 1: generous, high-recall sweep over overlapping chunks."""
    chunks = _chunk_segments(segments)
    scan_prompt = _build_scan_prompt()
    log(f"Scan pass (high recall) over {len(chunks)} "
        f"chunk{'s' if len(chunks) != 1 else ''}...")
    candidates = []
    for i, chunk in enumerate(chunks, 1):
        text = "\n".join(_transcript_lines(chunk))
        items = None
        for attempt in range(1, 4):
            try:
                raw = _call_llm(text, scan_prompt, temperature=0.5)
                items = _parse_json_array(raw)
                break
            except Exception as e:
                log(f"  chunk {i}/{len(chunks)} attempt {attempt} failed: {e}")
        if items is None:
            log(f"  chunk {i}/{len(chunks)} gave up after 3 attempts")
            continue
        added = 0
        for item in items:
            snapped = _snap_to_words(item, segments)
            if snapped:  # NO score filter here - recall stage keeps everything
                candidates.append(snapped)
                added += 1
        log(f"  chunk {i}/{len(chunks)}: {added} candidates")
    return _dedupe(candidates)


def _judge(candidates: list, segments: list) -> list:
    """Pass 2: strict gatekeeper. Re-scores, rejects weak clips, improves copy.
    Returns only clips that clear config.MIN_SCORE."""
    if not candidates:
        return []
    payload = []
    for i, m in enumerate(candidates):
        item = {
            "id": i,
            "start": m["start"],
            "end": m["end"],
            "duration_seconds": round(m["end"] - m["start"], 1),
            "hook": m.get("hook", ""),
            "title": m.get("title", ""),
            "transcript": _excerpt(segments, m["start"], m["end"]),
        }
        item.update(_boundary_context(segments, m["start"], m["end"]))
        payload.append(item)

    log(f"Judge pass (strict) on {len(candidates)} candidates "
        f"(quality bar: {config.MIN_SCORE})...")
    reviews = None
    for attempt in range(1, 4):
        try:
            raw = _call_llm(json.dumps(payload, ensure_ascii=False),
                            JUDGE_PROMPT, temperature=0.3)
            reviews = {r["id"]: r for r in _parse_json_array(raw) if "id" in r}
            break
        except Exception as e:
            log(f"  judge attempt {attempt} failed: {e}")
    if reviews is None:
        log("  judge pass failed; falling back to scan scores")
        return [m for m in candidates if m.get("score", 0) >= config.MIN_SCORE]

    kept = []
    for i, m in enumerate(candidates):
        r = reviews.get(i)
        if r is None:
            continue  # not reviewed -> drop (strict)
        score = r.get("score", m.get("score", 0))
        if str(r.get("verdict", "keep")).lower() == "reject" or score < config.MIN_SCORE:
            log(f"  reject ({score}): {m.get('title','')[:48]}")
            continue
        # allow the judge to tighten boundaries
        if isinstance(r.get("start"), (int, float)) and isinstance(r.get("end"), (int, float)):
            tightened = _snap_to_words({**m, "start": r["start"], "end": r["end"]}, segments)
            if tightened:
                m = tightened
        m["score"] = score
        for k in ("hook", "title", "caption", "reason"):
            if r.get(k):
                m[k] = r[k]
        kept.append(m)
        log(f"  keep   ({score}): {m.get('title','')[:48]}")
    return kept


def find_moments(transcript: dict, workdir: Path) -> list:
    """Find viral moments; cache result in workdir/moments.json."""
    out = workdir / "moments.json"
    if out.exists():
        log("moments.json already exists, skipping analysis")
        moments = json.loads(out.read_text(encoding="utf-8-sig"))  # agents may write a BOM
        if len(moments) > config.MAX_CLIPS:  # --clips caps seeded/cached lists too
            moments.sort(key=lambda m: -(m.get("score") or 0))
            moments = moments[:config.MAX_CLIPS]
            moments.sort(key=lambda m: m["start"])
        return moments

    segments = transcript["segments"]
    if not segments:
        raise RuntimeError("Transcript is empty - nothing to analyze.")

    if not config.LLM_ENABLED:
        if config.OPERATOR_MODE:
            raise RuntimeError(
                "Operator mode: Claude Code is the intelligence layer, so the "
                "engine will not call the LLM API.\n"
                f"  Read {workdir / 'transcript.json'}, pick the strongest "
                f"moments, and write them to:\n    {out}\n"
                "  (a JSON array of {start,end,score,hook,title,caption,"
                "hashtags,reason}), then re-run to render."
            )
        raise RuntimeError(
            "LLM analysis is disabled (LLM_MODEL starts with '~' or no API key), "
            f"and no seeded {out} was found.\n"
            "  Either write moments.json into the project folder yourself "
            "(agent workflow), or enable the LLM in .env."
        )

    log(f"Analyzing transcript with {config.LLM_MODEL}")
    candidates = _scan(segments)                 # pass 1: recall
    log(f"Scan found {len(candidates)} unique candidate moments.")
    kept = _judge(candidates, segments)          # pass 2: precision

    # dynamic count: keep all that cleared the bar, best first, capped
    kept.sort(key=lambda m: -m.get("score", 0))
    moments = kept[: config.MAX_CLIPS]
    moments.sort(key=lambda m: m["start"])

    if not moments:
        raise RuntimeError(
            "No clips cleared the quality bar. Lower CLIP_QUALITY_BAR in .env "
            "(e.g. 65), or the video may simply lack strong standalone moments. "
            "A stronger LLM_MODEL also helps a lot."
        )

    out.write_text(json.dumps(moments, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Selected {len(moments)} clips (dynamic):")
    for m in moments:
        log(f"  {fmt_ts(m['start'])}-{fmt_ts(m['end'])}  "
            f"score={m.get('score')}  {m.get('title','')[:60]}")
    return moments


# --- Caption suggestion for reframe modes ---
CAPTION_PROMPT = """You write short, punchy on-screen captions for vertical \
social videos. Given a transcript, return ONE caption (max 8 words) that would \
work as a bold text overlay at the top of the video to hook viewers. No quotes, \
no hashtags, no emoji. Return ONLY the caption text on a single line."""


def suggest_caption(transcript_text: str) -> str:
    """Ask the LLM for a short top caption from the transcript. Raises on failure."""
    text = transcript_text.strip()
    if not text:
        raise ValueError("empty transcript")
    snippet = text[:4000]
    raw = _call_llm(snippet, CAPTION_PROMPT, temperature=0.6)
    cap = raw.strip().strip('"').splitlines()[0].strip()
    if not cap:
        raise ValueError("LLM returned empty caption")
    return cap[:80]


# --- Universal social-media caption for reframe modes ---
SOCIAL_PROMPT = """You write ONE social-media caption for a short vertical video \
that will be posted on TikTok, YouTube Shorts, Instagram Reels and Facebook \
Reels. Write 1-2 short, punchy sentences that hook viewers and end with a \
question or call-to-action, then put 5-8 relevant hashtags on a new line \
(mix 1-2 broad + niche). Keep it platform-neutral. Return ONLY the caption."""


def suggest_social_caption(transcript_text: str) -> str:
    """One ready-to-post caption (with hashtags) usable on any platform."""
    text = transcript_text.strip()
    if not text:
        raise ValueError("empty transcript")
    raw = _call_llm(text[:4000], SOCIAL_PROMPT, temperature=0.7)
    return raw.strip()
