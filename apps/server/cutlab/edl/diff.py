"""Human-readable plan summaries."""
from __future__ import annotations

from .schema import EDL

MAX_SUMMARY = 300


def summarize(op_summaries: list[str], before: EDL, after: EDL) -> str:
    parts = list(op_summaries)
    delta = after.project.duration_ms - before.project.duration_ms
    if delta:
        sign = "+" if delta > 0 else ""
        parts.append(f"duration {sign}{delta}ms -> {after.project.duration_ms}ms")
    text = "; ".join(parts) if parts else "(no-op)"
    if len(text) > MAX_SUMMARY:
        text = text[: MAX_SUMMARY - 1] + "…"
    return text
