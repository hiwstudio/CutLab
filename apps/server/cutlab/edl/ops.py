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
    Scene,
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
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["footage", "overlay", "voiceover", "music", "sfx", "captions", "other"] | None = None
    id: str | None = Field(default=None, pattern=r"^trk_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track_id = self.id or ids.new_track_id()
        if edl.find_track(track_id):
            raise OpError("E_DUP", "id", f"track {track_id} already exists")
        track = Track(id=track_id, kind=self.kind, clips=[],
                      name=self.name or "", role=self.role or "other")
        idx = len(edl.tracks) if self.index is None else max(0, min(self.index, len(edl.tracks)))
        edl.tracks.insert(idx, track)
        return f"add {self.role or self.kind} track {track_id}"


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
    fade_in_ms: int = Field(default=0, ge=0, le=60_000)
    fade_out_ms: int = Field(default=0, ge=0, le=60_000)
    audio_denoise: bool = False
    audio_low_cut_hz: int = Field(default=0, ge=0, le=1000)
    audio_high_cut_hz: int = Field(default=0, ge=0, le=20_000)
    audio_effect: Literal["none", "voice-enhance", "telephone", "echo"] = "none"
    reversed: bool = False
    freeze_frame_at_ms: int | None = Field(default=None, ge=0)
    video_fade_in_ms: int = Field(default=0, ge=0, le=10_000)
    video_fade_out_ms: int = Field(default=0, ge=0, le=10_000)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
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
            fade_in_ms=self.fade_in_ms, fade_out_ms=self.fade_out_ms,
            audio_denoise=self.audio_denoise,
            audio_low_cut_hz=self.audio_low_cut_hz,
            audio_high_cut_hz=self.audio_high_cut_hz,
            audio_effect=self.audio_effect,
            reversed=self.reversed, freeze_frame_at_ms=self.freeze_frame_at_ms,
            video_fade_in_ms=self.video_fade_in_ms,
            video_fade_out_ms=self.video_fade_out_ms, opacity=self.opacity,
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
        if self.ripple and {t.id for t in targets} == {t.id for t in edl.tracks}:
            from .scenes import delete_scene_range
            delete_scene_range(edl, self.from_ms, self.to_ms)
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


class Duck(_OpBase):
    """Lower a music track wherever voiceover clips are present.

    The operation writes ordinary splits and clip gains into the EDL, so the
    result stays visible, editable, undoable, and identical in preview/export.
    """

    op: Literal["duck"]
    music_track: str
    voice_track: str | None = None
    gain_db: float = Field(default=-14.0, ge=-60.0, le=0.0)
    padding_ms: int = Field(default=150, ge=0, le=5000)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        music = _track(edl, self.music_track)
        if music.kind not in ("audio", "video"):
            raise OpError("E_KIND", "music_track", "ducking requires an audio-capable music track")

        if self.voice_track is not None:
            voice_tracks = [_track(edl, self.voice_track)]
            if voice_tracks[0].id == music.id:
                raise OpError("E_RANGE", "voice_track", "voice and music tracks must be different")
            if voice_tracks[0].kind not in ("audio", "video"):
                raise OpError("E_KIND", "voice_track", "ducking requires an audio-capable voice track")
        else:
            voice_tracks = [
                track for track in edl.tracks
                if track.id != music.id and track.kind in ("audio", "video")
                and track.role == "voiceover" and not track.muted
            ]

        intervals = sorted(
            (max(0, clip.start_ms - self.padding_ms), clip.end_ms() + self.padding_ms)
            for track in voice_tracks if not track.muted
            for clip in track.clips if isinstance(clip, MediaClip)
        )
        if not intervals:
            raise OpError("E_RANGE", "voice_track", "no voiceover clips are available to drive ducking")
        merged: list[list[int]] = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        changed = 0
        originals = [clip for clip in list(music.clips) if isinstance(clip, MediaClip)]
        for original in originals:
            original_start, original_end = _clip_span(original)
            boundaries = sorted({
                point for start, end in merged for point in (start, end)
                if original_start < point < original_end
            })
            piece_ids = {original.id}
            original_fade_in, original_fade_out = original.fade_in_ms, original.fade_out_ms
            for boundary in boundaries:
                piece = next(
                    clip for clip in music.clips
                    if isinstance(clip, MediaClip) and clip.id in piece_ids
                    and clip.start_ms < boundary < clip.end_ms()
                )
                new_id = ids.new_clip_id()
                Split(op="split", clip=piece.id, at_ms=boundary, new_id=new_id).apply(edl, ctx)
                piece_ids.add(new_id)
            for piece_id in piece_ids:
                piece = next(c for c in music.clips if c.id == piece_id)
                piece.fade_in_ms = original_fade_in if piece.start_ms == original_start else 0
                piece.fade_out_ms = original_fade_out if piece.end_ms() == original_end else 0
                if any(piece.start_ms < end and piece.end_ms() > start for start, end in merged):
                    piece.gain_db = self.gain_db
                    changed += 1

        if not changed:
            raise OpError("E_RANGE", "music_track", "voiceover does not overlap any music clips")
        _sort_and_check(music, "duck")
        return f"duck {music.id} to {self.gain_db}dB under voiceover ({changed} regions)"


class SetAudioFades(_OpBase):
    op: Literal["set_audio_fades"]
    clip: str
    fade_in_ms: int = Field(ge=0, le=60_000)
    fade_out_ms: int = Field(ge=0, le=60_000)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        if self.fade_in_ms + self.fade_out_ms > clip.timeline_len_ms():
            raise OpError("E_RANGE", "fade", "audio fades cannot exceed the clip duration")
        clip.fade_in_ms, clip.fade_out_ms = self.fade_in_ms, self.fade_out_ms
        return f"set audio fades of {clip.id} to {self.fade_in_ms}/{self.fade_out_ms}ms"


class SetAudioCleanup(_OpBase):
    op: Literal["set_audio_cleanup"]
    clip: str
    denoise: bool = False
    low_cut_hz: int = Field(default=0, ge=0, le=1000)
    high_cut_hz: int = Field(default=0, ge=0, le=20_000)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        if self.low_cut_hz and self.high_cut_hz and self.low_cut_hz >= self.high_cut_hz:
            raise OpError("E_RANGE", "audio_cleanup", "low cut must be below high cut")
        clip.audio_denoise = self.denoise
        clip.audio_low_cut_hz = self.low_cut_hz
        clip.audio_high_cut_hz = self.high_cut_hz
        return (f"set audio cleanup of {clip.id}: denoise={self.denoise}, "
                f"low={self.low_cut_hz}Hz, high={self.high_cut_hz}Hz")


class SetAudioEffect(_OpBase):
    op: Literal["set_audio_effect"]
    clip: str
    effect: Literal["none", "voice-enhance", "telephone", "echo"]

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        clip.audio_effect = self.effect
        return f"set audio effect of {clip.id} to {self.effect}"


class SetVideoAnimation(_OpBase):
    """Simple, deterministic enter/exit animation for any visual clip."""

    op: Literal["set_video_animation"]
    clip: str
    fade_in_ms: int = Field(ge=0, le=10_000)
    fade_out_ms: int = Field(ge=0, le=10_000)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video":
            raise OpError("E_KIND", "clip", "visual animation targets video clips")
        if self.fade_in_ms + self.fade_out_ms > clip.timeline_len_ms():
            raise OpError("E_RANGE", "animation", "video fades cannot exceed the clip duration")
        clip.video_fade_in_ms, clip.video_fade_out_ms = self.fade_in_ms, self.fade_out_ms
        return f"set visual animation of {clip.id} to {self.fade_in_ms}/{self.fade_out_ms}ms"


class SetTransitionOut(_OpBase):
    op: Literal["set_transition_out"]
    clip: str
    transition_out: TransitionOut | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video":
            raise OpError("E_KIND", "clip", "transitions can only be applied to video clips")
        if self.transition_out is not None:
            from .. import capabilities
            if capabilities.get(self.transition_out.cap, "transition") is None:
                raise OpError("E_REF", "transition_out", f"unknown transition {self.transition_out.cap}")
        clip.transition_out = self.transition_out
        return (f"set {self.transition_out.cap} transition on {clip.id}"
                if self.transition_out else f"remove transition from {clip.id}")


class SetReverse(_OpBase):
    op: Literal["set_reverse"]
    clip: str
    reversed: bool

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        if edl.assets[clip.asset].kind == "image":
            raise OpError("E_KIND", "clip", "still images cannot be reversed")
        clip.reversed = self.reversed
        return f"{'reverse' if self.reversed else 'restore forward'} {clip.id}"


class SetFreezeFrame(_OpBase):
    op: Literal["set_freeze_frame"]
    clip: str
    at_ms: int | None = Field(default=None, ge=0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video" or edl.assets[clip.asset].kind != "video":
            raise OpError("E_KIND", "clip", "freeze frame targets video clips")
        if self.at_ms is not None and not clip.in_ms <= self.at_ms < clip.out_ms:
            raise OpError("E_RANGE", "at_ms", "freeze frame must be inside the clip source range")
        clip.freeze_frame_at_ms = self.at_ms
        return (f"freeze {clip.id} at {self.at_ms}ms" if self.at_ms is not None
                else f"remove freeze frame from {clip.id}")


class SnapToBeat(_OpBase):
    """Move a clip's timeline start onto the nearest beat of an analyzed music clip."""

    op: Literal["snap_to_beat"]
    clip: str
    beat_clip: str

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        target_track, target = _media_clip(edl, self.clip)
        _, reference = _media_clip(edl, self.beat_clip)
        if ctx is None:
            raise OpError("E_NO_UNDERSTANDING", "beat_clip", "no op context available")
        understanding = ctx.require_understanding(reference.asset)
        candidates = [
            reference.start_ms + round((beat - reference.in_ms) / reference.speed)
            for beat in understanding.beats_ms
            if reference.in_ms <= beat < reference.out_ms
        ]
        if not candidates:
            raise OpError("E_NO_BEATS", "beat_clip", "no detected beats fall inside the reference clip")
        snapped = min(candidates, key=lambda beat: (abs(beat - target.start_ms), beat))
        target.start_ms = snapped
        _sort_and_check(target_track, "snap_to_beat")
        return f"snap {target.id} to beat at {snapped}ms"


class SetOpacity(_OpBase):
    op: Literal["set_opacity"]
    clip: str
    opacity: float = Field(ge=0.0, le=1.0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        _, clip = _media_clip(edl, self.clip)
        clip.opacity = self.opacity
        return f"set opacity of {clip.id} to {self.opacity:.2f}"


class SetEffect(_OpBase):
    """Add or update one named render effect on a video clip.

    Effect references are intentionally keyed by capability id.  Reapplying an
    adjustment updates it rather than silently stacking another copy of the
    same filter on the clip.
    """

    op: Literal["set_effect"]
    clip: str
    cap: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video":
            raise OpError("E_KIND", "clip", "effects can only be applied to video clips")
        from .. import capabilities
        if capabilities.get(self.cap, "effect") is None:
            raise OpError("E_REF", "cap", f"unknown effect capability {self.cap}")
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               for value in self.params.values()):
            raise OpError("E_SCHEMA", "params", "effect parameters must be numbers")
        effect = EffectRef(cap=self.cap, params=self.params)
        for index, existing in enumerate(clip.effects):
            if existing.cap == self.cap:
                clip.effects[index] = effect
                return f"update {self.cap} effect on {clip.id}"
        clip.effects.append(effect)
        return f"apply {self.cap} effect to {clip.id}"


class RemoveEffect(_OpBase):
    op: Literal["remove_effect"]
    clip: str
    cap: str = Field(min_length=1)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        if track.kind != "video":
            raise OpError("E_KIND", "clip", "effects can only be removed from video clips")
        before = len(clip.effects)
        clip.effects = [effect for effect in clip.effects if effect.cap != self.cap]
        if len(clip.effects) == before:
            raise OpError("E_REF", "cap", f"effect {self.cap} is not applied to this clip")
        return f"remove {self.cap} effect from {clip.id}"


class ReplaceClip(_OpBase):
    """Swap a clip's source while retaining its edit decisions and timing."""

    op: Literal["replace_clip"]
    clip: str
    asset: str
    in_ms: int | None = Field(default=None, ge=0)
    out_ms: int | None = Field(default=None, gt=0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _media_clip(edl, self.clip)
        replacement = edl.assets.get(self.asset)
        if replacement is None:
            raise OpError("E_REF", "asset", f"asset {self.asset} not found")
        _asset_kind_ok(edl, self.asset, track, "asset")
        original = edl.assets[clip.asset]
        if replacement.kind != original.kind and not (
            track.kind == "video" and {replacement.kind, original.kind} <= {"video", "image"}
            and self.in_ms is not None and self.out_ms is not None
        ):
            raise OpError("E_KIND", "asset", "replacement must be the same media kind as the original")
        tin = clip.in_ms if self.in_ms is None else self.in_ms
        tout = clip.out_ms if self.out_ms is None else self.out_ms
        if tout <= tin:
            raise OpError("E_RANGE", "out_ms", "source end must follow source start")
        if replacement.kind != "image" and replacement.duration_ms is not None and tout > replacement.duration_ms:
            raise OpError("E_RANGE", "asset", "replacement is shorter than this clip's source range")
        clip.asset = self.asset
        clip.in_ms, clip.out_ms = tin, tout
        return f"replace source of {clip.id} with {self.asset}"


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
            edl.project.canvas = Canvas(width=self.width, height=self.height, fps=self.fps,
                                        background_color=edl.project.canvas.background_color)
        except Exception as e:
            raise OpError("E_RANGE", "canvas", f"illegal canvas: {e}") from e
        return f"set canvas {self.width}x{self.height}@{self.fps}"


class SetBackground(_OpBase):
    op: Literal["set_background"]
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        edl.project.canvas.background_color = self.color
        return f"set background {self.color}"


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
    engine_source: dict[str, str] | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        changes = []
        if self.name is not None:
            edl.project.name = self.name
            changes.append(f"name='{self.name}'")
        if self.profile is not None:
            edl.project.profile = self.profile
            changes.append(f"profile='{self.profile}'")
        if self.engine_source is not None:
            edl.project.engine_source = self.engine_source
            changes.append("engine source")
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


class AutoLyrics(_OpBase):
    """Create a dedicated, short-phrase lyric track from analyzed audio."""

    op: Literal["auto_lyrics"]
    asset: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    track: str | None = None
    max_words: int = Field(default=4, ge=1, le=8)
    cap_style: Literal["karaoke", "bold-pop", "boxed", "default"] = "karaoke"

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .smartops import plan_caption_from_transcript

        if ctx is None:
            raise OpError("E_NO_UNDERSTANDING", "asset", "no op context available")
        u = ctx.require_understanding(self.asset)
        created = self.track is None
        track_id = self.track or ids.new_track_id()
        if created:
            edl.tracks.append(Track(
                id=track_id, kind="caption", role="captions", name="Auto lyrics",
            ))
        else:
            track = _track(edl, track_id)
            if track.kind not in ("caption", "text"):
                raise OpError("E_KIND", "track", "auto_lyrics targets caption/text tracks")
        plan = plan_caption_from_transcript(
            edl, u, self.asset, track_id, self.max_words, 350, self.cap_style,
        )
        if not plan:
            if created:
                edl.tracks = [track for track in edl.tracks if track.id != track_id]
            raise OpError("E_RANGE", "asset", "no timed lyric words overlap this asset on the timeline")
        _apply_primitive_ops(edl, plan, ctx)
        return f"auto lyrics for {self.asset}: {len(plan)} phrase(s) on {track_id}"


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


class Compact(_OpBase):
    """P4: saliency-driven compaction — keep the best-scoring spans of an
    asset until the timeline fits the target duration; delete the rest."""

    op: Literal["compact"]
    asset: str = Field(pattern=r"^ast_[a-z0-9]{2,12}$")
    target_ms: int = Field(gt=0)
    band_ms: tuple[int, int] | None = None    # candidate duration band
    sweet_ms: tuple[int, int] | None = None   # scoring sweet spot

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from ..engines import compaction

        if ctx is None:
            raise OpError("E_NO_UNDERSTANDING", "asset", "no op context available")
        u = ctx.require_understanding(self.asset)
        # Explicit params > profile's compaction block > engine defaults.
        from ..profiles import load_profile

        prof = load_profile(edl.project.profile).get("compaction", {})
        band = tuple(self.band_ms or prof.get("band_ms") or compaction.DEFAULT_BAND)
        sweet = tuple(self.sweet_ms or prof.get("sweet_ms") or compaction.DEFAULT_SWEET)
        # Small target -> shrink the band so candidates can fit the budget.
        band = (min(band[0], max(2000, self.target_ms // 3)), min(band[1], self.target_ms))
        sweet = (min(sweet[0], band[1]), min(sweet[1], band[1]))
        cands = compaction.score(compaction.candidates(u, band), u, sweet)
        keep = compaction.select(cands, self.target_ms)
        if not keep:
            raise OpError("E_RANGE", "target_ms", "no viable segments for this target")
        plan = compaction.plan_compact(edl, self.asset, keep)
        _apply_primitive_ops(edl, plan, ctx)
        kept_ms = sum(c.duration_ms for c in keep)
        return (f"compact {self.asset} to ~{kept_ms}ms "
                f"({len(keep)} segment(s), target {self.target_ms}ms)")


class SetClipTiming(_OpBase):
    """Move and trim together, validating the final placement atomically."""
    op: Literal["set_clip_timing"]
    clip: str
    start_ms: int = Field(ge=0)
    in_ms: int = Field(ge=0)
    out_ms: int = Field(gt=0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _clip(edl, self.clip)
        if not isinstance(clip, MediaClip):
            raise OpError("E_KIND", "clip", "Timing requires a media clip")
        if self.out_ms <= self.in_ms:
            raise OpError("E_RANGE", "out_ms", "Source out must follow source in")
        clip.start_ms, clip.in_ms, clip.out_ms = self.start_ms, self.in_ms, self.out_ms
        _sort_and_check(track, "set_clip_timing")
        return f"set timing {self.clip}"


class SetCaption(_OpBase):
    op: Literal["set_caption"]
    clip: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)
    cap_style: str | None = Field(default=None, min_length=1)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track, clip = _clip(edl, self.clip)
        if not isinstance(clip, CaptionClip):
            raise OpError("E_KIND", "clip", "Select a caption or text clip")
        if self.end_ms <= self.start_ms:
            raise OpError("E_RANGE", "end_ms", "Caption end must follow start")
        clip.start_ms, clip.end_ms, clip.text = self.start_ms, self.end_ms, self.text
        if self.cap_style is not None:
            clip.cap_style = self.cap_style
        _sort_and_check(track, "set_caption")
        return f"set caption {self.clip}"


class SetTrack(_OpBase):
    op: Literal["set_track"]
    track: str
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["footage", "overlay", "voiceover", "music", "sfx", "captions", "other"] | None = None
    muted: bool | None = None
    solo: bool | None = None
    locked: bool | None = None
    gain_db: float | None = Field(default=None, ge=-60, le=12)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        track = _track(edl, self.track)
        values = self.model_dump(exclude_none=True, exclude={"op", "track"})
        if track.kind not in ("video", "audio") and ("gain_db" in values or values.get("solo")):
            raise OpError("E_KIND", "track", "Gain and solo require a media track")
        for key, value in values.items():
            setattr(track, key, value)
        return f"set track {track.name or track.id}: {', '.join(values)}"


class AddScene(_OpBase):
    op: Literal["add_scene"]
    title: str = Field(min_length=1, max_length=120)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    id: str | None = Field(default=None, pattern=r"^scn_[a-z0-9]{2,12}$")

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        if self.end_ms <= self.start_ms:
            raise OpError("E_RANGE", "scene", "Scene end must be after start")
        scene = Scene(id=self.id or ids.new_clip_id().replace("clp_", "scn_"),
                      title=self.title, start_ms=self.start_ms, end_ms=self.end_ms)
        if any(s.id == scene.id for s in edl.scenes):
            raise OpError("E_DUP", "scene", "Scene id already exists")
        edl.scenes.append(scene)
        edl.scenes.sort(key=lambda s: s.start_ms)
        return f"add scene {scene.title}"


class SetScene(_OpBase):
    op: Literal["set_scene"]
    scene: str
    title: str | None = Field(default=None, min_length=1, max_length=120)
    approved: bool | None = None

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        scene = next((s for s in edl.scenes if s.id == self.scene), None)
        if scene is None:
            raise OpError("E_REF", "scene", "Scene not found")
        if self.title is not None:
            scene.title = self.title
        if self.approved is not None:
            scene.approved = self.approved
        return f"{'approve' if self.approved else 'update'} scene {scene.title}"


class MoveScene(_OpBase):
    op: Literal["move_scene"]
    scene: str
    to_index: int = Field(ge=0)

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        from .scenes import move_scene
        move_scene(edl, self.scene, self.to_index)
        return f"move scene {self.scene} to position {self.to_index + 1}"


# -- later-phase ops: enum defined now, E_NOT_IMPLEMENTED on apply ------------

LATER_PHASE_OPS = (
    "denoise", "fade", "apply_effect", "add_transition",
    "find", "apply_style", "reorder",
)


class LaterPhaseOp(_OpBase):
    model_config = ConfigDict(extra="allow")
    op: Literal[LATER_PHASE_OPS]  # type: ignore[valid-type]

    def apply(self, edl: EDL, ctx: OpContext | None = None) -> str:
        raise OpError("E_NOT_IMPLEMENTED", "op", f"op '{self.op}' is a later phase")


Op = Annotated[
    Union[
        AddTrack, RemoveTrack, AddClip, RemoveClip, Trim, Split, Move,
        DeleteRange, SetSpeed, SetGain, Duck, SetAudioFades, SetAudioCleanup, SetAudioEffect, SetVideoAnimation, SetTransitionOut, SetReverse, SetFreezeFrame, SnapToBeat, SetOpacity, SetEffect, RemoveEffect, ReplaceClip, SetTransform, SetCrop, SetCanvas, SetBackground,
        AddCaption, SetProject, AddAsset, SetUnderstanding,
        RemoveSilence, CaptionFromTranscript, AutoLyrics, Reframe, AddEmphasis, Compact,
        SetTrack, AddScene, SetScene, MoveScene, SetClipTiming, SetCaption,
        LaterPhaseOp,
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
