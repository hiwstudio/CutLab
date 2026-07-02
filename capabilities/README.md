# capabilities/

Empty in Phase 0 by design.

Effects, transitions, caption styles, and export presets become **registry
entries** here in later phases: one directory per capability containing a
manifest (id, params schema, phase requirements) plus a handler. Core code
never changes to add one (A2 principle 6).

In Phase 0 the validator treats every capability id as unknown and emits
`W_UNKNOWN_CAP` (a warning, never an error), and the render pipeline skips
effect/transition references with a logged warning.
