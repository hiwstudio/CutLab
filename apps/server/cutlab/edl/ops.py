"""Operation vocabulary (A5) and application semantics.

Ops are pydantic models discriminated on the `op` field. Each op mutates a
working EDL model in place and returns a one-line human summary. Failures
raise OpError with a stable Issue code; the engine rejects the whole plan.

Pure module: no I/O, no DB. Id generation is injected so tests can pin ids.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, Callable, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ..util import ids
from .schema import (
    Canvas,
    CaptionClip,
    Crop,
    EDL,
    EffectRef,
    MediaClip,
    Track,
    TrackKindT,
    Transform,
    TransitionOut,
    timeline_len_ms,
)

if TYPE_CHECKING:
    from ..understanding.schema import Understanding


class OpError(Exception):
    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


@dataclass
class OpContext:
    """Read-only side data an op may need beyond the EDL. Populated by the
    engine before apply (it loads referenced understanding artifacts). Smart
    ops (remove_silence, caption_from_transcript) read `understanding`; primitive
    ops ignore it. Keeps op.apply a pure function of (edl, ctx)."""

    understanding: dict[str, "Understanding"] = field(default_factory=dict)

    def require_understanding(self, asset_id: str) -> "Understanding":
        u = self.understanding.get(asset_id)
        if u is None:
            raise OpError(
                "E_NO_UNDERSTANDING", "asset",
                f"asset {asset_id} has no understanding; analyze it first",
            )
        return u


# -- helpers -----------------------------------------------------------------


def _track(edl: EDL, track_id: str) -> Track:
    t = edl.find_track(track_id)
    if t is None:
        raise OpError("E_REF", "track", f"track {track_id} not found")
    return t


def _clip(edl: EDL, clip_id: str) -> tuple[Track, MediaClip | CaptionClip]:
    found = edl.find_clip(clip_id)
    if found is None:
        raise OpError("E_REF", "clip", f"clip {clip_id} not found")
    return found


def _media_clip(edl: EDL, clip_id: str) -> tuple[Track, MediaClip]:
    track, clip = _clip(edl, clip_id)
    if not isinstance(clip, MediaClip):
        raise OpError("E_KIND", "clip", f"clip {clip_id} is not a media clip")
    return track, clip


def _clip_span(clip: MediaClip | CaptionClip) -> tuple[int, int]:
    if isinstance(clip, MediaClip):
        return clip.start_ms, clip.end_ms()
    return clip.start_ms, clip.end_ms


def _sort_and_check(track: Track, context: str) -> None:
    """Re-sort clips by start_ms and reject overlaps within the track."""
    track.clips.sort(key=lambda c: (c.start_ms, c.id))
    prev_end = -1
    prev_id = ""
    for c in track.clips:
        s, e = _clip_span(c)
        if s < prev_end:
            raise OpError(
                "E_OVERLAP", context,
                f"clip {c.id} at {s}ms overlaps {prev_id} (ends {prev_end}ms) on track {track.id}",
            )
        prev_end, prev_id = e, c.id


def _src_len_for_timeline(target_tl_ms: int, speed: float) -> int:
    """Source ms that occupy at most `target_tl_ms` timeline ms at `speed`.

    floor guarantees round(src/speed) <= target, so trims/splits never create
    1ms overlaps from rounding.
    """
    return int(math.floor(target_tl_ms * speed))


def _ripple(track: Track, at_ms: int, delta_ms: int, exclude: set[str] = frozenset()) -> None:
    """Shift every clip starting at or after at_ms by delta_ms."""
    for c in track.clips:
        if c.id in exclude or c.start_ms < at_ms:
            continue
        c.start_ms += delta_ms
        if isinstance(c, CaptionClip):
            c.end_ms += delta_ms


def _degenerate(clip: MediaClip | CaptionClip) -> bool:
    """True when trimming left the clip with no content (empty source range
    or empty time window)."""
    if isinstance(clip, MediaClip):
        return clip.out_ms <= clip.in_ms
    return clip.end_ms <= clip.start_ms


def _asset_kind_ok(edl: EDL, asset_id: str, track: Track, path: str) -> None:
    asset = edl.assets.get(asset_id)
    if asset is None:
        raise OpError("E_REF", path, f"asset {asset_id} not found")
    allowed = {"video": {"video", "image"}, "audio": {"audio", "video"}}.get(track.kind, set())
    if asset.kind not in allowed:
        raise OpError("E_KIND", path, f"asset kind '{asset.kind}' not allowed on '{track.kind}' track")


class _OpBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- structural ops ----------------------------------------------------------


class AddTrack(_OpBase):
    op: Literal["add_track"]
    kind: TrackKindT
    index: int | None = None
    id: str | None = Field(default=None, pattern=r"^trk_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track_id = self.id or ids.new_track_id()
        if edl.find_track(track_id):
            raise OpError("E_DUP", "id", f"track {track_id} already exists")
        track = Track(id=track_id, kind=self.kind, clips=[])
        idx = len(edl.tracks) if self.index is None else max(0, min(self.index, len(edl.tracks)))
        edl.tracks.insert(idx, track)
        return f"add {self.kind} track {track_id}"


class RemoveTrack(_OpBase):
    op: Literal["remove_track"]
    track: str

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        t = _track(edl, self.track)
        edl.tracks.remove(t)
        return f"remove track {t.id} ({len(t.clips)} clips)"


class AddClip(_OpBase):
    op: Literal["add_clip"]
    track: str
    asset: str
    in_ms: int = Field(ge=0)
    out_ms: int = Field(gt=0)
    start_ms: int = Field(ge=0)
    speed: float = Field(default=1.0, ge=0.1, le=10.0)
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    transform: Transform | None = None
    crop: Crop | None = None
    effects: list[EffectRef] = Field(default_factory=list)
    transition_out: TransitionOut | None = None
    id: str | None = Field(default=None, pattern=r"^clp_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track = _track(edl, self.track)
        if track.kind not in ("video", "audio"):
            raise OpError("E_KIND", "track", f"add_clip targets media tracks, not '{track.kind}'")
        _asset_kind_ok(edl, self.asset, track, "asset")
        clip_id = self.id or ids.new_clip_id()
        if edl.find_clip(clip_id):
            raise OpError("E_DUP", "id", f"clip {clip_id} already exists")
        clip = MediaClip(
            id=clip_id, asset=self.asset, in_ms=self.in_ms, out_ms=self.out_ms,
            start_ms=self.start_ms, speed=self.speed, gain_db=self.gain_db,
            transform=self.transform, crop=self.crop, effects=self.effects,
            transition_out=self.transition_out,
        )
        track.clips.append(clip)
        _sort_and_check(track, "add_clip")
        return f"add clip {clip_id} ({self.asset}) to {track.id} @{self.start_ms}ms"


class RemoveClip(_OpBase):
    op: Literal["remove_clip"]
    clip: str
    ripple: bool = False

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _clip(edl, self.clip)
        start, end = _clip_span(clip)
        track.clips.remove(clip)
        if self.ripple:
            _ripple(track, end, -(end - start))
            _sort_and_check(track, "remove_clip")
        return f"remove clip {clip.id} from {track.id}" + (" (ripple)" if self.ripple else "")


class Trim(_OpBase):
    op: Literal["trim"]
    clip: str
    new_in_ms: int | None = Field(default=None, ge=0)
    new_out_ms: int | None = Field(default=None, gt=0)
    edge_mode: Literal["hold_start", "hold_end"] = "hold_start"

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        if self.new_in_ms is None and self.new_out_ms is None:
            raise OpError("E_SCHEMA", "trim", "trim requires new_in_ms and/or new_out_ms")
        track, clip = _media_clip(edl, self.clip)
        old_end = clip.end_ms()
        new_in = clip.in_ms if self.new_in_ms is None else self.new_in_ms
        new_out = clip.out_ms if self.new_out_ms is None else self.new_out_ms
        if new_in >= new_out:
            raise OpError("E_RANGE", "trim", f"in_ms {new_in} must be < out_ms {new_out}")
        clip.in_ms, clip.out_ms = new_in, new_out
        if self.edge_mode == "hold_end":
            clip.start_ms = old_end - clip.timeline_len_ms()
            if clip.start_ms < 0:
                raise OpError("E_RANGE", "trim", "hold_end trim pushes start_ms below 0")
        _sort_and_check(track, "trim")
        return f"trim {clip.id} to [{new_in},{new_out}]ms ({self.edge_mode})"


class Split(_OpBase):
    op: Literal["split"]
    clip: str
    at_ms: int = Field(ge=0)  # timeline coords
    new_id: str | None = Field(default=None, pattern=r"^clp_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _clip(edl, self.clip)
        start, end = _clip_span(clip)
        if not (start < self.at_ms < end):
            raise OpError("E_RANGE", "at_ms",
                          f"split point {self.at_ms}ms not strictly inside clip [{start},{end})")
        new_id = self.new_id or ids.new_clip_id()
        if edl.find_clip(new_id):
            raise OpError("E_DUP", "new_id", f"clip {new_id} already exists")

        if isinstance(clip, MediaClip):
            # Partition the source range respecting speed. floor keeps the left
            # piece's timeline length <= (at_ms - start): no rounding overlap.
            src_off = _src_len_for_timeline(self.at_ms - start, clip.speed)
            if not (0 < src_off < clip.out_ms - clip.in_ms):
                raise OpError("E_RANGE", "at_ms", "split lands outside divisible source range")
            right = clip.model_copy(deep=True)
            right.id = new_id
            right.in_ms = clip.in_ms + src_off
            clip.out_ms = clip.in_ms + src_off
            # Right piece starts where the left piece now ends (continuity).
            right.start_ms = clip.end_ms()
            # Only the right piece keeps the outgoing transition.
            clip.transition_out = None
        else:
            right = clip.model_copy(deep=True)
            right.id = new_id
            right.start_ms = self.at_ms
            clip.end_ms = self.at_ms
        track.clips.append(right)
        _sort_and_check(track, "split")
        return f"split {clip.id} at {self.at_ms}ms -> {clip.id} + {new_id}"


class Move(_OpBase):
    op: Literal["move"]
    clip: str
    to_start_ms: int = Field(ge=0)
    to_track: str | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _clip(edl, self.clip)
        dest = track if self.to_track is None else _track(edl, self.to_track)
        if dest is not track:
            if isinstance(clip, MediaClip):
                if dest.kind not in ("video", "audio"):
                    raise OpError("E_KIND", "to_track", f"media clip cannot move to '{dest.kind}' track")
                _asset_kind_ok(edl, clip.asset, dest, "to_track")
            else:
                if dest.kind not in ("caption", "text"):
                    raise OpError("E_KIND", "to_track", f"caption clip cannot move to '{dest.kind}' track")
            track.clips.remove(clip)
            dest.clips.append(clip)
        delta = self.to_start_ms - clip.start_ms
        clip.start_ms = self.to_start_ms
        if isinstance(clip, CaptionClip):
            clip.end_ms += delta
        _sort_and_check(dest, "move")
        where = f" to {dest.id}" if dest is not track else ""
        return f"move {clip.id}{where} @{self.to_start_ms}ms"


class DeleteRange(_OpBase):
    op: Literal["delete_range"]
    tracks: list[str] | Literal["all"]
    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)
    ripple: bool = True

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        if self.from_ms >= self.to_ms:
            raise OpError("E_RANGE", "delete_range", "from_ms must be < to_ms")
        targets = edl.tracks if self.tracks == "all" else [_track(edl, t) for t in self.tracks]
        length = self.to_ms - self.from_ms
        removed = 0
        for track in targets:
            removed += self._apply_track(track, length)
            _sort_and_check(track, "delete_range")
        scope = "all tracks" if self.tracks == "all" else ",".join(t.id for t in targets)
        return (f"delete range [{self.from_ms},{self.to_ms}]ms on {scope}"
                f" ({removed} clips removed{', ripple' if self.ripple else ''})")

    def _apply_track(self, track: Track, length: int) -> int:
        kept: list = []
        removed = 0
        for clip in list(track.clips):
            s, e = _clip_span(clip)
            if e <= self.from_ms:
                kept.append(clip)
            elif s >= self.to_ms:
                kept.append(clip)  # ripple below
            elif s >= self.from_ms and e <= self.to_ms:
                removed += 1  # fully inside -> dropped
            elif s < self.from_ms and e > self.to_ms:
                # Spans the whole range: split into left + right. Rounding can
                # make a remnant degenerate (zero source length) — drop those.
                pieces = self._split_spanning(clip)
                removed += 2 - len(pieces)
                kept.extend(pieces)
            elif s < self.from_ms:
                self._trim_end_to(clip, self.from_ms)
                if _degenerate(clip):
                    removed += 1
                else:
                    kept.append(clip)
            else:
                self._trim_start_to(clip, self.to_ms)
                if _degenerate(clip):
                    removed += 1
                else:
                    kept.append(clip)
        track.clips = kept
        if self.ripple:
            _ripple(track, self.to_ms, -length)
        return removed

    def _trim_end_to(self, clip, at_ms: int) -> None:
        if isinstance(clip, MediaClip):
            clip.out_ms = clip.in_ms + _src_len_for_timeline(at_ms - clip.start_ms, clip.speed)
        else:
            clip.end_ms = at_ms

    def _trim_start_to(self, clip, at_ms: int) -> None:
        if isinstance(clip, MediaClip):
            clip.in_ms += _src_len_for_timeline(at_ms - clip.start_ms, clip.speed)
        else:
            pass  # caption keeps its text; only the window moves
        old_start = clip.start_ms
        clip.start_ms = at_ms
        if isinstance(clip, CaptionClip):
            clip.end_ms = max(clip.end_ms, at_ms + 1)

    def _split_spanning(self, clip) -> list:
        if isinstance(clip, MediaClip):
            right = clip.model_copy(deep=True)
            right.id = ids.new_clip_id()
            self._trim_end_to(clip, self.from_ms)
            head_src = _src_len_for_timeline(self.to_ms - right.start_ms, right.speed)
            right.in_ms += head_src
            right.start_ms = self.to_ms
        else:
            right = clip.model_copy(deep=True)
            right.id = ids.new_clip_id()
            clip.end_ms = self.from_ms
            right.start_ms = self.to_ms
        return [p for p in (clip, right) if not _degenerate(p)]


class SetSpeed(_OpBase):
    op: Literal["set_speed"]
    clip: str
    speed: float = Field(ge=0.1, le=10.0)
    ripple: bool = False

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        old_len = clip.timeline_len_ms()
        clip.speed = self.speed
        delta = clip.timeline_len_ms() - old_len
        if self.ripple and delta != 0:
            _ripple(track, clip.start_ms + 1, delta, exclude={clip.id})
        _sort_and_check(track, "set_speed")
        return f"set speed of {clip.id} to {self.speed}x"


class SetGain(_OpBase):
    op: Literal["set_gain"]
    clip: str
    gain_db: float = Field(ge=-60.0, le=12.0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        clip.gain_db = self.gain_db
        return f"set gain of {clip.id} to {self.gain_db}dB"


class SetTransform(_OpBase):
    op: Literal["set_transform"]
    clip: str
    transform: dict[str, Any]  # partial; merge semantics

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        current = clip.transform.model_dump() if clip.transform else {}
        current.update(self.transform)
        try:
            clip.transform = Transform(**current)
        except Exception as e:
            raise OpError("E_SCHEMA", "transform", f"invalid transform: {e}") from e
        return f"set transform of {clip.id}"


class SetCrop(_OpBase):
    op: Literal["set_crop"]
    clip: str
    crop: Crop

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        clip.crop = self.crop
        return f"set crop of {clip.id} ({self.crop.mode})"


class SetCanvas(_OpBase):
    op: Literal["set_canvas"]
    width: int
    height: int
    fps: float

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        try:
            edl.project.canvas = Canvas(width=self.width, height=self.height, fps=self.fps)
        except Exception as e:
            raise OpError("E_RANGE", "canvas", f"illegal canvas: {e}") from e
        return f"set canvas {self.width}x{self.height}@{self.fps}"


class AddCaption(_OpBase):
    op: Literal["add_caption"]
    track: str
    text: str = Field(min_length=1, max_length=500)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    cap_style: str | None = None
    id: str | None = Field(default=None, pattern=r"^clp_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track = _track(edl, self.track)
        if track.kind not in ("caption", "text"):
            raise OpError("E_KIND", "track", "add_caption targets caption/text tracks only")
        if self.start_ms >= self.end_ms:
            raise OpError("E_RANGE", "end_ms", "start_ms must be < end_ms")
        clip_id = self.id or ids.new_clip_id()
        if edl.find_clip(clip_id):
            raise OpError("E_DUP", "id", f"clip {clip_id} already exists")
        track.clips.append(CaptionClip(
            id=clip_id, start_ms=self.start_ms, end_ms=self.end_ms,
            text=self.text, cap_style=self.cap_style,
        ))
        _sort_and_check(track, "add_caption")
        return f"add caption '{self.text[:32]}' @{self.start_ms}ms"


class SetProject(_OpBase):
    op: Literal["set_project"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    profile: str | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        changes = []
        if self.name is not None:
            edl.project.name = self.name
            changes.append(f"name='{self.name}'")
        if self.profile is not None:
            edl.project.profile = self.profile
            changes.append(f"profile='{self.profile}'")
        return "set project " + (", ".join(changes) or "(no changes)")


class AddAsset(_OpBase):
    """Server-internal op: ingest completion registers the asset in the EDL.

    Not in the A5 table; added because assets must enter the EDL through the
    op path (principle A2.2) and no other op does it. See DECISIONS.md.
    """

    op: Literal["add_asset"]
    asset_id: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    kind: Literal["video", "audio", "image"]
    src: str
    proxy: str | None = None
    duration_ms: int | None = Field(default=None, gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .schema import Asset

        if self.asset_id in edl.assets:
            raise OpError("E_DUP", "asset_id", f"asset {self.asset_id} already exists")
        edl.assets[self.asset_id] = Asset(
            kind=self.kind, src=self.src, proxy=self.proxy,
            duration_ms=self.duration_ms, width=self.width, height=self.height,
        )
        return f"register asset {self.asset_id} ({self.kind}: {self.src})"


class SetUnderstanding(_OpBase):
    """Phase 1 op: point an asset at its understanding artifact.

    Like add_asset, this is a server-internal registration op (the understanding
    job applies it on completion) so the `understanding` field enters the EDL via
    the op path (A2.2), never by a direct snapshot write.
    """

    op: Literal["set_understanding"]
    asset: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    understanding: str = Field(min_length=1)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        asset = edl.assets.get(self.asset)
        if asset is None:
            raise OpError("E_REF", "asset", f"asset {self.asset} not found")
        if asset.understanding == self.understanding:
            raise OpError("E_NOOP", "understanding", "already set to this path")
        asset.understanding = self.understanding
        return f"set understanding for {self.asset}"


# -- smart ops (P2 first tier): consume understanding via OpContext -----------


def _apply_primitive_ops(edl: EDL, op_dicts: list[dict[str, Any]], ctx: OpContext | None) -> int:
    """Apply a planner's primitive-op dicts to the working EDL in sequence.
    Used by smart ops that expand into primitives. Any primitive failure raises
    OpError, which the engine turns into a whole-plan rejection (transactional)."""
    for d in op_dicts:
        sub = parse_ops([d])[0]
        sub.apply(edl, ctx)
    return len(op_dicts)


class RemoveSilence(_OpBase):
    op: Literal["remove_silence"]
    asset: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    tracks: list[str] | None = None       # None = all tracks
    min_ms: int = Field(default=300, ge=0)  # ignore silences shorter than this
    ripple: bool = True

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .smartops import plan_remove_silence

        if ctx is None:
            raise OpError("E_NO_UNDERSTANDING", "asset", "no op context available")
        u = ctx.require_understanding(self.asset)
        plan = plan_remove_silence(edl, u, self.asset, self.tracks, self.min_ms, self.ripple)
        _apply_primitive_ops(edl, plan, ctx)
        return f"remove silence from {self.asset}: {len(plan)} cut(s)"


class CaptionFromTranscript(_OpBase):
    op: Literal["caption_from_transcript"]
    asset: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    track: str                             # target caption/text track
    max_words: int = Field(default=6, ge=1, le=20)
    max_gap_ms: int = Field(default=700, ge=0)
    cap_style: str | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .smartops import plan_caption_from_transcript

        if ctx is None:
            raise OpError("E_NO_UNDERSTANDING", "asset", "no op context available")
        track = _track(edl, self.track)
        if track.kind not in ("caption", "text"):
            raise OpError("E_KIND", "track", "caption_from_transcript targets caption/text tracks")
        u = ctx.require_understanding(self.asset)
        plan = plan_caption_from_transcript(
            edl, u, self.asset, self.track, self.max_words, self.max_gap_ms, self.cap_style,
        )
        _apply_primitive_ops(edl, plan, ctx)
        return f"caption {self.asset} -> {len(plan)} caption(s) on {self.track}"


class Reframe(_OpBase):
    """Basic center reframe: change the canvas and center-crop affected video
    clips. The Phase-0 render already center-crops to the canvas aspect.
    (`reframe_auto` — subject tracking — stays later-phase; needs vision.)"""

    op: Literal["reframe"]
    width: int
    height: int
    fps: float | None = None
    tracks: list[str] | None = None        # None = all video tracks

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        fps = self.fps if self.fps is not None else edl.project.canvas.fps
        primitives: list[dict[str, Any]] = [
            {"op": "set_canvas", "width": self.width, "height": self.height, "fps": fps},
        ]
        target = edl.tracks if self.tracks is None else [
            t for t in edl.tracks if t.id in set(self.tracks)
        ]
        count = 0
        for t in target:
            if t.kind != "video":
                continue
            for c in t.clips:
                if isinstance(c, MediaClip):
                    primitives.append({"op": "set_crop", "clip": c.id, "crop": {"mode": "center"}})
                    count += 1
        _apply_primitive_ops(edl, primitives, ctx)
        return f"reframe to {self.width}x{self.height} (center-crop {count} clip(s))"


class AddEmphasis(_OpBase):
    """P3: punch-in emphasis — split out [at, at+duration) and scale it up.
    at_ms omitted -> the saliency peak inside the clip (needs understanding)."""

    op: Literal["add_emphasis"]
    clip: str
    at_ms: int | None = Field(default=None, ge=0)
    duration_ms: int = Field(default=1000, ge=50, le=30_000)
    scale: float = Field(default=1.15, gt=1.0, le=3.0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .smartops import plan_add_emphasis

        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video":
            raise OpError("E_KIND", "clip", "add_emphasis targets video clips")
        u = None
        if self.at_ms is None:
            if ctx is None:
                raise OpError("E_NO_UNDERSTANDING", "clip", "no op context available")
            u = ctx.require_understanding(clip.asset)
        plan = plan_add_emphasis(
            edl, clip, u, self.at_ms, self.duration_ms, self.scale,
            new_ids=(ids.new_clip_id(), ids.new_clip_id()),
        )
        if not plan:
            raise OpError("E_RANGE", "at_ms", "no emphasis point found in clip")
        _apply_primitive_ops(edl, plan, ctx)
        return f"emphasize {self.clip} ({self.scale}x for {self.duration_ms}ms)"


# -- later-phase ops: enum defined now, E_NOT_IMPLEMENTED on apply ------------

LATER_PHASE_OPS = (
    "duck", "denoise", "fade", "apply_effect", "add_transition",
    "find", "compact", "apply_style", "reorder",
)


class LaterPhaseOp(_OpBase):
    model_config = ConfigDict(extra="allow")
    op: Literal[LATER_PHASE_OPS]  # type: ignore[valid-type]

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        raise OpError("E_NOT_IMPLEMENTED", "op", f"op '{self.op}' is a later phase")


Op = Annotated[
    Union[
        AddTrack, RemoveTrack, AddClip, RemoveClip, Trim, Split, Move,
        DeleteRange, SetSpeed, SetGain, SetTransform, SetCrop, SetCanvas,
        AddCaption, SetProject, AddAsset, SetUnderstanding,
        RemoveSilence, CaptionFromTranscript, Reframe, AddEmphasis, LaterPhaseOp,
    ],
    Field(discriminator="op"),
]

_ops_adapter: TypeAdapter[list[Op]] = TypeAdapter(list[Op])


def parse_ops(raw_ops: list[dict[str, Any]]) -> list[Op]:
    """Parse raw op dicts; raises OpError(E_SCHEMA) on malformed plans."""
    from pydantic import ValidationError

    try:
        return _ops_adapter.validate_python(raw_ops)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        raise OpError("E_SCHEMA", loc, first["msg"]) from exc
