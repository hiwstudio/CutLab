# Split MixFix

The split-screen engine: the speaker holds the **top** pane for the whole
runtime and is never covered; sourced reference footage fills the **bottom**
pane, scene by scene; one all-caps word sits on the seam, driven by the Timing
Map's word timings. The original audio is stream-copied, never touched.

```
python -m split run --project <name>          # portrait by default
python -m split run --project <name> --landscape
python -m split preview --project <name>      # review board on :8765
python -m split status
```

Input is the same as FIX: `projects/<name>/input/source.mp4`, or a YouTube URL
in `input/source.txt`. **The top video must be a real locked-off interview** —
one speaker, one camera, no cutaways. That is the format; a video that cuts
around fights the bottom pane for attention.

## What lives here vs. in MixFix

This is a separate engine, not a fork. It shares MixFix's core so every fix to
intake, timing, research, the timeline, the review board, QA and export lands
here for free.

| file | owns |
|---|---|
| `pipeline.py` | `SplitPipeline`, the `split_plan` stage, `SPLIT_STAGES` |
| `render.py` | the vstack renderer, pane geometry, seam captions |
| `schema.py` | the `split_plan` result contract |
| `prompt.py` | the operator doctrine for planning the bottom pane |
| `defaults.py` | the `split:` config block and the project template |
| `tests/` | schema, caption timing, and an end-to-end render |

Importing `split` registers all of it with the core (`mixfix/modes.py`), which
is why `mixfix/` contains no split-specific code and `python -m mixfix.cli`
offers only `mix` and `fix`.

## Stages

`fix_intake → timing_map → split_plan → research_extract → timeline → assemble
→ render_qa → export`

No `fix_shots`: the speaker holds the top pane throughout, so shot boundaries
and face presence — which exist to decide when covering the speaker is safe —
have nothing to decide.

## The rule that makes the format work

The bottom pane must pay off the claim in the top pane **at that instant**.
Topic-adjacent b-roll is the failure mode. Full doctrine, the relevance ladder
and the research behind it: `../SOURCING.md`.

## Config

Under `split:` in `config.yaml` — `top_fraction` (default 0.5),
`word_captions`, `caption_style` (`size`, `colour` as ASS `&HAABBGGRR`,
`outline`). Caption size defaults to 5% of frame height.
