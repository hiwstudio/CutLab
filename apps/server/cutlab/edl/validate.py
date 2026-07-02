"""EDL validation (A4 validation contract).

`validate(edl_data, base_dir=None) -> ValidationResult` with stable Issue
codes. Errors block apply; warnings don't.

Codes:
  E_SCHEMA   shape violation: wrong type, bad pattern, illegal enum value,
             missing required field, unknown field
  E_RANGE    numeric value out of range (includes clip ranges vs asset duration)
  E_REF      reference does not resolve (clip -> asset)
  E_KIND     kind incompatibility (asset kind vs track kind, clip vs track)
  E_DUP      duplicate id (tracks, clips project-wide)
  E_ORDER    clips within a track not sorted by start_ms
  E_OVERLAP  clips within a track overlap in timeline
  E_SRC      asset src file missing on disk (only checked when base_dir given)
  E_DURATION project.duration_ms present but does not match recomputed value
  W_UNKNOWN_CAP  effect/transition/caption capability id not registered
                 (Phase 0 has no registry, so every cap warns)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schema import EDL, CaptionClip, MediaClip, Track

# Capability registry arrives in a later phase; Phase 0 knows no capabilities.
KNOWN_CAPS: frozenset[str] = frozenset()

_PYDANTIC_RANGE_TYPES = {
    "greater_than",
    "greater_than_equal",
    "less_than",
    "less_than_equal",
    "string_too_short",
    "string_too_long",
}


@dataclass
class Issue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    edl: EDL | None = None  # parsed model when shape validation passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
        }


def _loc_to_path(loc: tuple) -> str:
    parts: list[str] = []
    for item in loc:
        # Skip pydantic union-branch tags, e.g. "MediaClip" or
        # "function-after[_in_before_out(), MediaClip]".
        if isinstance(item, str) and ("MediaClip" in item or "CaptionClip" in item):
            continue
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(("." if parts else "") + str(item))
    return "".join(parts) or "$"


def _schema_issues(exc: ValidationError) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for err in exc.errors():
        code = "E_RANGE" if err["type"] in _PYDANTIC_RANGE_TYPES else "E_SCHEMA"
        path = _loc_to_path(tuple(err["loc"]))
        key = (path, err["msg"])
        if key in seen:
            continue
        seen.add(key)
        issues.append(Issue(code=code, path=path, message=err["msg"]))
    return issues


def validate(edl_data: dict[str, Any] | EDL, base_dir: str | Path | None = None) -> ValidationResult:
    # 1. Shape.
    if isinstance(edl_data, EDL):
        edl = edl_data
    else:
        try:
            edl = EDL.model_validate(edl_data)
        except ValidationError as exc:
            issues = _schema_issues(exc)
            errors = [i for i in issues if i.code.startswith("E_")]
            return ValidationResult(valid=False, errors=errors)

    errors: list[Issue] = []
    warnings: list[Issue] = []

    # 2. Asset checks.
    for asset_id, asset in edl.assets.items():
        apath = f"assets.{asset_id}"
        if base_dir is not None:
            src = Path(base_dir) / asset.src
            if not src.exists():
                errors.append(Issue("E_SRC", f"{apath}.src", f"source file not found: {asset.src}"))

    # 3. Track / clip cross-checks.
    track_ids: set[str] = set()
    clip_ids: set[str] = set()
    for ti, track in enumerate(edl.tracks):
        tpath = f"tracks[{ti}]"
        if track.id in track_ids:
            errors.append(Issue("E_DUP", f"{tpath}.id", f"duplicate track id {track.id}"))
        track_ids.add(track.id)

        prev_start: int | None = None
        prev_end: int | None = None
        prev_id: str | None = None
        for ci, clip in enumerate(track.clips):
            cpath = f"{tpath}.clips[{ci}]"
            if clip.id in clip_ids:
                errors.append(Issue("E_DUP", f"{cpath}.id", f"duplicate clip id {clip.id}"))
            clip_ids.add(clip.id)

            if isinstance(clip, MediaClip):
                _check_media_clip(edl, track, clip, cpath, errors, warnings)
                clip_len = clip.timeline_len_ms()
            else:
                _check_caption_clip(clip, cpath, warnings)
                clip_len = clip.timeline_len_ms()

            start = clip.start_ms
            end = start + clip_len
            if prev_start is not None and start < prev_start:
                errors.append(
                    Issue("E_ORDER", f"{cpath}.start_ms",
                          f"clips not sorted by start_ms ({start} after {prev_start})")
                )
            if prev_end is not None and start < prev_end:
                errors.append(
                    Issue("E_OVERLAP", cpath,
                          f"clip {clip.id} (start {start}ms) overlaps previous clip "
                          f"{prev_id} (ends {prev_end}ms) on track {track.id}")
                )
            prev_start, prev_end, prev_id = start, max(end, prev_end or 0), clip.id

    # 4. Derived duration.
    computed = edl.computed_duration_ms()
    if edl.project.duration_ms not in (0, computed):
        errors.append(
            Issue("E_DURATION", "project.duration_ms",
                  f"duration_ms is {edl.project.duration_ms}, recomputed {computed}")
        )

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings, edl=edl)


_KIND_COMPAT = {
    # track kind -> allowed asset kinds
    "video": {"video", "image"},
    "audio": {"audio", "video"},  # video assets carry audio streams
}


def _check_media_clip(
    edl: EDL, track: Track, clip: MediaClip, cpath: str,
    errors: list[Issue], warnings: list[Issue],
) -> None:
    asset = edl.assets.get(clip.asset)
    if asset is None:
        errors.append(Issue("E_REF", f"{cpath}.asset", f"asset {clip.asset} not found"))
    else:
        allowed = _KIND_COMPAT.get(track.kind, set())
        if asset.kind not in allowed:
            errors.append(
                Issue("E_KIND", f"{cpath}.asset",
                      f"asset kind '{asset.kind}' not allowed on '{track.kind}' track")
            )
        if asset.kind == "image":
            if clip.in_ms != 0:
                errors.append(
                    Issue("E_RANGE", f"{cpath}.in_ms", "image clips must have in_ms = 0")
                )
        elif asset.duration_ms is not None and clip.out_ms > asset.duration_ms:
            errors.append(
                Issue("E_RANGE", f"{cpath}.out_ms",
                      f"out_ms {clip.out_ms} exceeds asset duration {asset.duration_ms}")
            )
    for ei, eff in enumerate(clip.effects):
        if eff.cap not in KNOWN_CAPS:
            warnings.append(
                Issue("W_UNKNOWN_CAP", f"{cpath}.effects[{ei}].cap", f"unknown capability '{eff.cap}'")
            )
    if clip.transition_out and clip.transition_out.cap not in KNOWN_CAPS:
        warnings.append(
            Issue("W_UNKNOWN_CAP", f"{cpath}.transition_out.cap",
                  f"unknown capability '{clip.transition_out.cap}'")
        )


def _check_caption_clip(clip: CaptionClip, cpath: str, warnings: list[Issue]) -> None:
    if clip.cap_style and clip.cap_style not in KNOWN_CAPS:
        warnings.append(
            Issue("W_UNKNOWN_CAP", f"{cpath}.cap_style", f"unknown capability '{clip.cap_style}'")
        )
