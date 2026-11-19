"""Sourcing doctrine shared by every mode that pulls footage off YouTube.

This text was written for SPLIT and proved out there, but nothing in it is
specific to a split screen — MIX sources clips through the same
`research_extract` stage, the same ranker and the same review board, so it
needs the same instructions. Keeping one copy here is what stops the two
prompts from drifting apart.

The engine already READS everything described below (`archive_candidates`
reads `archive_queries`, `order_candidates` takes `moment`). Before this
module, MIX simply was never asked to produce either, so the machinery sat
idle for half the engine's modes.

See SOURCING.md for the research behind the relevance ladder.
"""
from __future__ import annotations

ARCHIVE_FIRST = (
    "ARCHIVE FIRST — do this before writing per-scene queries. If the piece "
    "is about ONE event (a fight, a match, a speech, a launch, an incident), "
    "return `archive_queries`: 2-3 searches aimed at a single clean "
    "FULL-LENGTH upload of it — 'full fight', 'full match', 'full speech', "
    "'complete broadcast', the uploader names that post archives. The engine "
    "resolves those once and offers that upload to EVERY scene, so the whole "
    "piece is cut from one archive and each scene just takes its own window.\n"
    "Why this matters more than per-scene search: a popular event has a huge "
    "derivative ecosystem — reaction videos, phone recordings of a "
    "television, re-uploads, talk-show segments — sitting on top of very few "
    "clean archives. Searching per scene rediscovers that junk every time, "
    "while one archive serves every scene at once. It is also far cheaper: "
    "only each scene's own window is fetched from that upload (plus a small "
    "pad), and nearby windows reuse what is already on disk. Omit "
    "archive_queries only when the piece genuinely has no single event "
    "behind it."
)

WRITING_QUERIES = (
    "WRITING QUERIES — the trap that wastes the most candidates: clips are "
    "ranked by how well their TRANSCRIPT matches the narration, and the "
    "people who say those words are interviewers, not the event. Query "
    "'Ortiz headbutt Mayweather' and the top hits are press conferences "
    "ABOUT the headbutt; the footage itself is silent or buried under "
    "commentary, so it ranks below them. Name the FOOTAGE, not the topic: "
    "add 'full fight', 'highlights', 'round 4', 'slow motion replay', "
    "'ring walk', 'live broadcast', 'onboard camera', 'launch replay' — the "
    "words that appear on uploads of the thing itself. Reserve "
    "interview-shaped queries for scenes that genuinely want a talking head."
)

AIM_FOR_SUPPORT = (
    "AIM FOR SUPPORT, NOT RECREATION. The clip only has to make the viewer "
    "think 'yes, that is what this is about'. Write queries that would "
    "surface good footage of the SUBJECT — the person, the event, the place "
    "— not just the one instant described. A query that can only be "
    "satisfied by a single specific second will usually return nothing "
    "usable."
)

MOMENT = (
    "SET \"moment\" ON EVERY SOURCED SCENE. It decides which PART of a long "
    "upload the clip is cut from, and it is the most common way a correct "
    "source still yields a wrong clip. \"action\" = the thing happening (a "
    "punch, a knockdown, a launch, a demo, a build) — that lives in the BODY "
    "of a full-length upload. \"talking\" = someone discussing it (press "
    "conference, post-event interview, commentary) — that lives in the TAIL, "
    "after the event. Use \"any\" only when either would genuinely do. "
    "Without it, ranking sends action scenes to the post-event interview "
    "every time, because the tail is where those words are actually spoken."
)

PROVEN_SOURCES = (
    "The payload may include 'proven_sources': channels whose footage this "
    "engine has accepted before. They are a hint about what surfaces usable "
    "uploads for this kind of subject, not a whitelist."
)


def block(*parts: str) -> str:
    """Join doctrine sections into a prompt fragment."""
    return "\n\n".join(parts)
