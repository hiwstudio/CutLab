# MixFix agent notes

- Read README.md and CUTLAB.md before operating the engine.
- Use the operator brain by default. Do not enable automatic LLM calls unless
  the user asks for that mode.
- Treat a review gate as the user's decision. Do not approve or reject it for
  them.
- Keep the engine's cache and provenance intact. Resume the same project after
  a pause instead of recreating its state.
- MIX and FIX projects can be imported into CutLab. SPLIT remains a
  standalone workflow.
