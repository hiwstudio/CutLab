"""ASSEMBLY's operator instructions, registered into the core task registry.

Two doctrines. `assembly_plan` is what separates an assembly from a re-upload:
one promise, and only the windows that pay it off. `insert_plan` is what keeps
the cutaways from turning a conversation into a slideshow.
"""
from __future__ import annotations

from mixfix.ai.tasks import TASK_INSTRUCTIONS

ASSEMBLY_PLAN = (
    "You are building a themed ASSEMBLY from ONE podcast episode: several "
    "windows of the episode, cut out and joined into a single 15-25 minute "
    "video that pays off one promise. This is not a highlight reel and it is "
    "not the whole episode — most of the episode is left out.\n\n"

    "THE RULE THAT MAKES THIS FORMAT WORK: the title states a promise, and "
    "every window earns its place by paying that promise off. A viewer who "
    "clicked \"Teddy Roosevelt: The Wildest President Ever\" wants Roosevelt. "
    "A funny tangent about the host's dog is a good bit and it does not belong "
    "in this video. The failure mode is a channel-hopping grab-bag of strong "
    "moments with no through-line — that is a re-upload with gaps in it.\n\n"

    "PICK THE PROMISE FIRST, THEN THE WINDOWS. Read the transcript, find the "
    "richest single thread in the episode, and name it as a title a stranger "
    "would click without knowing the podcast. Subject first. Do not name the "
    "podcast or the hosts in the title — that is added downstream.\n\n"

    "CHOOSING WINDOWS:\n"
    "- Open on a complete spoken sentence that lands a claim, a name, a number "
    "or a stated stake. Never open on a pleasantry, an ad read, an audio drop "
    "or someone agreeing with a point the viewer did not hear.\n"
    "- Each window is ONE continuous stretch. Its segment_ids must be "
    "consecutive — you are choosing where to start and stop, not splicing.\n"
    "- A window should be able to stand alone. If it only makes sense because "
    "of something said twenty minutes earlier that you did not include, either "
    "widen it to carry the setup or drop it.\n"
    "- Order is the episode's own order. Windows are joined in the sequence "
    "they occur, so the piece must still make sense read top to bottom.\n"
    "- Prefer fewer, longer windows over many short ones. Four to eight "
    "windows is typical. A dozen 40-second snippets is a montage, and the "
    "audio will feel chopped.\n"
    "- Cut sponsor reads, intros, outros, housekeeping and plugs every time.\n\n"

    "THE HOOK. Also choose ONE moment from inside your selected windows to be "
    "lifted to the very front of the video. It plays cold, before anything "
    "else, and then the video starts from its real beginning — so the hook "
    "plays twice. It is the whole reason a stranger keeps watching past two "
    "seconds.\n"
    "- Measured rule, held on 9 of 9 sampled videos: openings that work are a "
    "COMPLETE SPOKEN SENTENCE carrying a number or a named danger. Openings "
    "that fail are a plan or a pleasantry. \"He pulled a knife on me in the "
    "parking lot\" works. \"So anyway, we were talking about the thing\" does "
    "not.\n"
    "- It must land with ZERO setup. If it only hits once you already know who "
    "is speaking or what came before, it is not a hook.\n"
    "- Pull it from deeper in, not from the opening minute — it replays in its "
    "natural place, and too close together reads as a stutter.\n"
    "- It must sit entirely inside a window you selected. Never promise "
    "something the video does not contain.\n\n"

    "Return JSON: {\"title\": \"the promise, subject first\", \"hook\": "
    "{\"segment_ids\": [...], \"why\": \"what makes this stop a scroll\"}, "
    "\"windows\": [{\"id\": \"win_001\", \"segment_ids\": [...], \"why\": "
    "\"what this window contributes to the promise\"}]}. "
    "Windows and the hook are identified by transcript segment ids only — "
    "never write raw timestamps. Boundaries come from the segments so the cut "
    "lands between sentences instead of through one."
)

INSERT_PLAN = (
    "You are placing cutaways over a finished long-form podcast cut. The "
    "speaker's audio plays untouched from start to end; a cutaway replaces only "
    "the PICTURE for a few seconds while they keep talking.\n\n"

    "HOW MANY. The context gives you `min_inserts` and `max_inserts`, already "
    "scaled to this cut's runtime. Land inside that range. This is still not a "
    "fast-cut edit — the viewer came for the conversation and most of the "
    "runtime keeps the original picture — but a long cut carrying only a "
    "handful of cutaways reads as an unedited lift, which is exactly what this "
    "range exists to prevent. Spread them across the WHOLE runtime instead of "
    "clustering them early: many minutes with no picture change is where a "
    "viewer leaves.\n\n"

    "WHAT EARNS ONE. The speaker names something specific and concrete that "
    "the viewer would benefit from SEEING — a person, a place, an object, an "
    "event, a number worth putting on screen — and the cutaway pays off that "
    "reference at the instant it is made. A cutaway that is merely "
    "topic-adjacent, generic mood footage under a specific claim, is worse "
    "than leaving the picture alone.\n\n"

    "SOURCED CLIPS ARE RATIONED — the most important constraint here. The "
    "context gives `max_sourced` (typically 4): at most that many cutaways may "
    "be visual_type \"video\". Every sourced clip costs a YouTube search plus a "
    "range-fetch, the slow and failure-prone half of production, and a plan full "
    "of them does not finish. Spend those few slots ONLY where real footage is "
    "irreplaceable — a real place, a real event, a real person the viewer must "
    "actually see. In exchange for being few they are LONGER: aim for 10-20 "
    "seconds each rather than 4-second flashes.\n\n"

    "EVERYTHING ELSE IS GENERATED, and that is the default, not a fallback. Use "
    "\"generate\" for a described scene, a historical moment, an object or an "
    "idea being explained — a short timed sequence of generated shots. Use "
    "a single-segment \"generate\" when one strong still says it. Generated "
    "visuals cost no "
    "bandwidth and never stall, so lean on them; they are how this format stays "
    "productive. A generated cutaway that puts the thing being discussed on "
    "screen beats a sourced clip that never arrives.\n\n"

    "CHOOSE THE ASSET TYPE PER CUTAWAY:\n"
    "- \"video\": real footage exists and is findable — the event itself, the "
    "person, the clip being described. Give 2-3 specific search queries naming "
    "the actual subject, and a \"moment\" of \"action\" or \"talking\" so the "
    "right part of a long upload is used.\n"
    "- \"generate\": everything else — a described scene, a historical moment, "
    "an object, an abstraction, or a single strong still. Give timed segments, "
    "each with a start_ms and a delta describing that specific shot, and a "
    "style_lock at the top level so the generated shots do not drift apart "
    "visually. ONE segment is a still; several make a timed sequence.\n"
    "There is no \"image\" type in this mode — it is MIX legacy and renders "
    "nothing here.\n\n"

    "Never place a cutaway inside the opening hook — the cold open plays raw.\n"
    "Match the channel_style you are given: it says what this particular "
    "channel's cutaways are for.\n\n"

    "Return JSON: {\"scenes\": [{\"id\": \"ins_001\", \"segment_ids\": [...], "
    "\"visual_intent\": \"what appears on screen\", \"visual_type\": "
    "\"video\"|\"generate\", plus the keys that type needs}], "
    "\"archive_queries\": [...] (optional), \"style_lock\": \"...\" (required "
    "if any scene is generate)}."
)

TASK_INSTRUCTIONS["assembly_plan"] = ASSEMBLY_PLAN
TASK_INSTRUCTIONS["insert_plan"] = INSERT_PLAN
