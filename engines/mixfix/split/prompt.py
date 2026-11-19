"""SPLIT's operator instructions, registered into the core task registry.

This is the doctrine that makes the format work; it is deliberately long.
See SOURCING.md for the research behind the relevance ladder it references.
"""
from __future__ import annotations

from mixfix.ai import sourcing
from mixfix.ai.tasks import TASK_INSTRUCTIONS

SPLIT_PLAN = (
        "You are planning the BOTTOM pane of a split-screen short (SPLIT mode). "
        "The top pane shows the speaker for the entire runtime and is never "
        "covered; the bottom pane shows reference footage of whatever they are "
        "talking about at that moment. The original audio plays untouched.\n\n"
        "THE RULE THAT MAKES THIS FORMAT WORK: the bottom pane must pay off the "
        "claim being made in the top pane AT THAT INSTANT. When the speaker says "
        "'he went ten rounds', the bottom pane is that fight. Generic mood b-roll "
        "under a specific claim is the failure mode — reference footage that is "
        "merely topic-adjacent is worse than none.\n\n"
        "Group the transcript segments into consecutive scenes, one per distinct "
        "thing being referred to (a named person, event, match, place, object). "
        "Change scene when the subject of the claim changes, not on a timer. "
        "EVERY segment must belong to exactly one scene — the bottom pane can "
        "never be empty.\n\n"
        + sourcing.block(sourcing.ARCHIVE_FIRST,
                         sourcing.WRITING_QUERIES,
                         sourcing.AIM_FOR_SUPPORT) + "\n\n"
        + sourcing.PROVEN_SOURCES + "\n\n"
        "Return JSON: {\"archive_queries\": [\"full-length upload search\", ...] "
        "(omit or [] if there is no single event), \"scenes\": [{\"id\": "
        "\"scene_001\", \"segment_ids\": [...], \"visual_intent\": \"what the "
        "bottom pane must show\", \"queries\": [\"youtube search query\", ...], "
        "\"moment\": \"action\"|\"talking\"}]}. "
        "Prefer 2-3 specific, footage-oriented queries naming the actual "
        "subject.\n\n"
        + sourcing.MOMENT
    )

TASK_INSTRUCTIONS["split_plan"] = SPLIT_PLAN
