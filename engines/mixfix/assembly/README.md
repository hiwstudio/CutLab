# Assembly MixFix — select a section of a long episode, then FIX it

Turns one podcast episode into a single 15–25 minute video built around one
promise: several windows of the episode cut out and joined, opening on a hook
lifted from inside that section, with a handful of cutaways over the body. Not a
highlight reel, not the episode with gaps in it.

```
python -m assembly run --project <name>
```

`input/source.txt` — the episode URL.
`input/theme.txt` — optional. The thread to build around; leave it out and the
plan stage picks the strongest one in the episode.

## Shape

The back half of this mode **is FIX**, reused unmodified. `render_fix` already
plays a video and replaces the picture for planned windows while stream-copying
the original audio — exactly this format. What FIX cannot do is *choose* a
section: `fix_intake` ingests a whole upload, so a 3-hour podcast would cost 3
hours of download and transcription. The front half is that missing step.

```
assembly_intake → assembly_plan → assembly_extract → assembly_cut
      NEW              NEW              NEW              NEW
→ timing_map → fix_shots → insert_plan → research_extract → generate_visuals
     core        core          NEW             core              core
→ timeline → assemble (render_fix) → render_qa → export
    core            core              core        core
```

**assembly_intake** fetches auto-captions and nothing else. A 111-minute episode
costs a few KB here; no video is downloaded until windows have been chosen.

**assembly_plan** is the first operator task — the windows and the hook:

```json
{"title": "The Cops Offered To Tase Us After The Show",
 "hook": {"segment_ids": ["seg_2104"], "why": "names a stake, needs no setup"},
 "windows": [{"id": "win_001", "segment_ids": ["seg_1808", "..."],
              "why": "what this window contributes to the promise"}]}
```

Windows are caption segment ids, never raw timestamps — a hand-typed millisecond
opens mid-sentence, and a window that opens mid-sentence reads as a broken upload
however good the moment inside it is. The schema rejects non-consecutive ids,
overlapping windows, windows under `min_window_s`, and any plan whose runtime
falls outside the band — all **before** anything is downloaded.

**assembly_extract** range-fetches only the chosen windows, cutting each to exact
bounds locally.

**assembly_cut** joins them behind the hook and writes `input/source.mp4`. From
that point the run is an ordinary FIX run over a video file.

**insert_plan** is the second operator task — the cutaways.

## The hook

A moment lifted from inside the selected section and prepended, so it plays
twice: once cold, once in its natural place. It is the whole reason a stranger
watches past two seconds.

Selection is not taste. Measured on 1,065 Shorts and held on 9 of 9 sampled
videos: openings that work are a **complete spoken sentence carrying a number or
a named danger**; openings that fail are a plan or a pleasantry. The schema
enforces the mechanical half — consecutive segments, 8–35s, inside a selected
window, at least `hook_min_depth_s` into the body so the replay is not a stutter.

It must sit inside a window that survived. A teaser promising something the video
does not contain is punished at the exact moment the viewer notices.

## The cutaways are sparse on purpose

4–10 per video, roughly 3–7% of runtime. The picture changes for a few seconds
while the speaker keeps talking; the audio is stream-copied and never touched.
The viewer came for the conversation — the cutaways exist so it does not feel
like a flat unedited lift, not to turn it into a fast-cut edit.

Each is `visual_type` **video** (sourced footage), **image** (one still), or
**generate** (a timed generated sequence, which needs a `style_lock` so the shots
do not drift apart visually). The core visual_plan contract already modelled all
three; FIX never used them because `replace_plan` hardcodes `"video"`. That is
the main reason this mode has its own plan stage rather than reusing FIX's.

No cutaway may start inside the hook — the cold open plays raw.

## Sourcing cutaways: illustrative, not exact

`insert_plan` marks every sourced cutaway `sourcing: "illustrative"` in the visual
plan. That flag changes what the ranker will accept.

The default (`"exact"`, what MIX and SPLIT use) requires a candidate's TRANSCRIPT
to match the scene — right when the shot must show the event being described,
because the transcript is how that gets confirmed. An illustrative cutaway has a
different job: the speaker named Sixth Street, and any decent shot of Sixth Street
does it.

That distinction is load-bearing, because **most b-roll has no captions**. Before
the flag existed this mode found 0 usable candidates in 36 searches — the searches
returned four perfect Sixth Street walking tours and the transcript ranker dropped
every one of them for having no transcript to match. With it: 4 candidates per
scene, same queries.

Illustrative candidates are ranked on their title and given a window by POSITION —
skipping ~15% lead-in (titles, intros, sponsor cards) and ~10% tail — at a 0.6
weight, so a genuine transcript match still wins wherever one exists. A candidate
whose duration is unknown is skipped rather than guessed at.

## The review board

```
python -m assembly preview --project <name>
```

Same board MIX uses, and it reads the mode from the run, so the draft is rendered
by this mode's renderer rather than MIX's. What it shows per scene depends on what
the scene IS:

- **SOURCED FOOTAGE** — the queries that were run, then the ranked shortlist with
  each candidate's title, channel, score and window. "Use this" swaps the scene to
  that candidate (`swap_alternative`) and the next run fetches it; "watch ↗" opens
  the source.
- **GENERATED** / **STILL** — the exact prompts that were issued (style lock plus
  each shot delta) and the stills that were dropped back, rendered inline.

Only cutaways appear. The podcast underneath is not a scene, so there is nothing
to click on it — which is the point: the board lists precisely the decisions that
are yours.

Labels follow the mode. MIX writes its own narration, so "Narration" is accurate
there; here the transcript is what the speaker said, and the board says so.

## One engine, several channels

`assembly.channel_style` (free text) plus `fix.max_cover_s` and
`fix.min_return_gap_s` are the whole per-channel dial. A comedy channel wants
fast literal cutaways on references and punchlines; an informational channel
wants slower inserts on claims. Same code, different instruction — a profile,
not a fork.

## Known constraints

- **`research.max_height` matters more here than anywhere else.** It is tuned to
  480 for b-roll that gets scaled into a frame. In an assembly the source footage
  *is* the whole frame, so a 1080p render is upscaled 480p. Raise it for
  production, and pay the bandwidth.
- **The band assumes the episode has a sustained thread.** A banter-heavy episode
  may genuinely not contain 15 consecutive minutes on one promise. The plan stage
  is where that gets discovered — cheaply, before any download. That is a
  feature; do not widen the band to make a weak plan pass.
- **`timing_map` whispers the cut, not the episode** — ~18 minutes of CPU
  transcription rather than 3 hours. That is what buys word-level timings, which
  is what lets a cutaway land on the beat instead of a second late.
- **Two generations of x264.** `cut_section` encodes each window, then
  `assembly_cut` re-encodes on concat rather than stream-copying, because
  concat's copy path splices timestamps and a drifting audio PTS becomes visible
  lip desync twenty minutes in. Acceptable at crf 20; revisit if quality shows.
- Long windows need proportionally long download budgets — see
  `../lessons/section-timeout-must-scale-with-the-window.md`. If a fetch stalls,
  read `../lessons/time-a-metadata-call-before-theorising-about-a-stall.md`
  first: four mechanism hypotheses were investigated there and all four were
  wrong.

## Status

**Proven end to end 2026-08-26.** One real Theo Von episode (111 min, 2,844 caption
lines) produced `export/final.mp4`: 963.2s, 1920x1080, h264/aac, 6 planned
cutaways, QA all-pass.

Verified by frame, not just by log: the base podcast plays; the cutaway replaces
the picture at its planned second; and the frame 6.0s into the hook is identical
to the frame at 659.7s where that moment falls naturally — the cold open really
does play twice.

Two caveats on that sample run. Its three windows were seeded into `archives/`
by hand after direct yt-dlp fetches, so the mode's own fetch path is exercised
by tests but was not what pulled those sample bytes.
And the four sourced cutaways found no candidates (36 searches, 0 hits, also
throttling), so only the generated one carried an asset, using placeholder images.
