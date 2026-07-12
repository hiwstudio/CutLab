# Capabilities

Registry entries per A2.6: **manifest + handler, core code never changes to add
one.** Drop a `*.json` file here (one manifest or a list) and it is live on the
next server start — the validator accepts the id, the render pipeline applies it,
and profiles can reference it.

Kinds and their fields (see `apps/server/cutlab/capabilities.py` for built-ins):

- `effect` — `{"id","kind":"effect","name","filter","defaults"}`; `filter` is an
  ffmpeg video-filter template with `{param}` placeholders (numeric params only).
- `transition` — `{"id","kind":"transition","name","filter"}` with `{start_s}` /
  `{duration_s}` placeholders, applied to a clip's outgoing tail (`transition_out`).
- `caption_style` — ASS style overrides (`font`, `size_frac`, `primary`,
  `outline`, `align`, `margin_v_frac`, …) merged over the default style.
- `export_preset` — `{"video": [ffmpeg args], "audio": [ffmpeg args]}` for final
  renders; selected per project profile (`export_preset` in `profiles/*.json`).

Built-ins available out of the box: effects `grayscale`, `blur`, `vignette`,
`brightness`; transitions `fade`, `fade-white`; caption styles `default`,
`bold-pop`, `boxed`, `top-title`; export presets `h264-archive`, `h264-social`.

Example (`capabilities/sepia.json`):

```json
{"id": "sepia", "kind": "effect", "name": "Sepia",
 "filter": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
 "defaults": {}}
```
