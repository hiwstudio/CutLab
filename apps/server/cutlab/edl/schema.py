"""EDL v1.0 pydantic models (A4).

These models enforce *shape* (types, patterns, numeric ranges, enums).
Cross-document rules (id uniqueness, reference resolution, overlaps,
duration recomputation, file existence) live in validate.py.

All times are integer milliseconds. No frames, no floats in the EDL.
"""
from __future__ import annotations

import math
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EDL_VERSION = "1.0"
LEGAL_FPS = (24, 25, 30, 50, 60)

TrackKindT = Literal["video", "audio", "caption", "text"]

PROJECT_ID_RE = r"^proj_[a-z0-9]{4,12}$"
ASSET_ID_RE = r"^ast_[a-z0-9]{2,12}$"
TRACK_ID_RE = r"^trk_[a-z0-9]{2,12}$"
CLIP_ID_RE = r"^clp_[a-z0-9]{2,12}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Canvas(Strict):
    width: int = Field(ge=16, le=7680)
    height: int = Field(ge=16, le=7680)
    fps: float
    background_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("width", "height")
    @classmethod
    def _even(cls, v: int) -> int:
        if v % 2 != 0:
            raise ValueError("canvas dimensions must be even")
        return v

    @field_validator("fps")
    @classmethod
    def _legal_fps(cls, v: float) -> float:
        if v not in LEGAL_FPS:
            raise ValueError(f"fps must be one of {LEGAL_FPS}")
        return v


class Project(Strict):
    id: str = Field(pattern=PROJECT_ID_RE)
    name: str = Field(min_length=1, max_length=120)
    profile: str = "default"
    engine_source: dict[str, str] | None = None
    canvas: Canvas
    duration_ms: int = Field(default=0, ge=0)  # derived; recomputed server-side


class Asset(Strict):
    kind: Literal["video", "audio", "image"]
    src: str = Field(min_length=1)
    proxy: str | None = None
    duration_ms: int | None = Field(default=None, gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    understanding: str | None = None

    @model_validator(mode="after")
    def _kind_requirements(self) -> "Asset":
        if self.kind in ("video", "audio") and self.duration_ms is None:
            raise ValueError(f"{self.kind} asset requires duration_ms")
        if self.kind in ("video", "image") and (self.width is None or self.height is None):
            raise ValueError(f"{self.kind} asset requires width and height")
        return self


class Transform(Strict):
    scale: float = Field(default=1.0, ge=0.1, le=10.0)
    x: int = 0
    y: int = 0
    rotate: float = Field(default=0.0, ge=-360.0, le=360.0)


class CropRect(Strict):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class Crop(Strict):
    # `reframe_auto` is a later-phase mode; excluding it from the enum
    # rejects it in v1.0 validation as the spec requires.
    mode: Literal["none", "center", "manual"]
    rect: CropRect | None = None

    @model_validator(mode="after")
    def _manual_needs_rect(self) -> "Crop":
        if self.mode == "manual" and self.rect is None:
            raise ValueError("crop mode 'manual' requires rect")
        return self


class EffectRef(Strict):
    cap: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class TransitionOut(Strict):
    cap: str = Field(min_length=1)
    duration_ms: int = Field(ge=50, le=2000)


class MediaClip(Strict):
    """Clip on a video or audio track."""

    id: str = Field(pattern=CLIP_ID_RE)
    asset: str = Field(pattern=ASSET_ID_RE)
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

    @model_validator(mode="after")
    def _in_before_out(self) -> "MediaClip":
        if self.in_ms >= self.out_ms:
            raise ValueError("in_ms must be < out_ms")
        if self.fade_in_ms + self.fade_out_ms > self.timeline_len_ms():
            raise ValueError("audio fades cannot exceed the clip duration")
        if (self.audio_low_cut_hz and self.audio_high_cut_hz
                and self.audio_low_cut_hz >= self.audio_high_cut_hz):
            raise ValueError("audio low cut must be below high cut")
        if self.freeze_frame_at_ms is not None and not self.in_ms <= self.freeze_frame_at_ms < self.out_ms:
            raise ValueError("freeze frame must be inside the clip source range")
        if self.video_fade_in_ms + self.video_fade_out_ms > self.timeline_len_ms():
            raise ValueError("video fades cannot exceed the clip duration")
        return self

    def timeline_len_ms(self) -> int:
        return timeline_len_ms(self.in_ms, self.out_ms, self.speed)

    def end_ms(self) -> int:
        return self.start_ms + self.timeline_len_ms()


class CaptionSource(Strict):
    kind: Literal["transcript"]
    asset: str = Field(pattern=ASSET_ID_RE)
    words: list[int]


class CaptionClip(Strict):
    """Clip on a caption or text track."""

    id: str = Field(pattern=CLIP_ID_RE)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)
    cap_style: str | None = None
    source: CaptionSource | None = None

    @model_validator(mode="after")
    def _start_before_end(self) -> "CaptionClip":
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be < end_ms")
        return self

    def timeline_len_ms(self) -> int:
        return self.end_ms - self.start_ms


Clip = Union[MediaClip, CaptionClip]


class Track(Strict):
    id: str = Field(pattern=TRACK_ID_RE)
    kind: Literal["video", "audio", "caption", "text"]
    name: str = Field(default="", max_length=80)
    role: Literal["footage", "overlay", "voiceover", "music", "sfx", "captions", "other"] = "other"
    muted: bool = False
    solo: bool = False  # audio audition/export; does not hide other video layers
    locked: bool = False
    gain_db: float = Field(default=0, ge=-60, le=12)
    clips: list[Clip] = Field(default_factory=list)

    @model_validator(mode="after")
    def _clip_types_match_kind(self) -> "Track":
        want = MediaClip if self.kind in ("video", "audio") else CaptionClip
        for c in self.clips:
            if not isinstance(c, want):
                raise ValueError(
                    f"track kind '{self.kind}' requires {want.__name__} clips"
                )
        return self


class Scene(Strict):
    """Explicit story range. Layers intersecting this range are its contents."""

    id: str = Field(pattern=r"^scn_[a-z0-9]{2,12}$")
    title: str = Field(min_length=1, max_length=120)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    approved: bool = False

    @model_validator(mode="after")
    def _range(self) -> "Scene":
        if self.end_ms <= self.start_ms:
            raise ValueError("scene end must be after its start")
        return self


class EDL(Strict):
    edl_version: Literal["1.0"]
    project: Project
    assets: dict[str, Asset] = Field(default_factory=dict)
    tracks: list[Track] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)

    @field_validator("assets")
    @classmethod
    def _asset_keys(cls, v: dict[str, Asset]) -> dict[str, Asset]:
        import re

        for key in v:
            if not re.match(ASSET_ID_RE, key):
                raise ValueError(f"asset key '{key}' does not match {ASSET_ID_RE}")
        return v

    def find_track(self, track_id: str) -> Track | None:
        return next((t for t in self.tracks if t.id == track_id), None)

    def find_clip(self, clip_id: str) -> tuple[Track, Clip] | None:
        for t in self.tracks:
            for c in t.clips:
                if c.id == clip_id:
                    return t, c
        return None

    def computed_duration_ms(self) -> int:
        end = max((s.end_ms for s in self.scenes), default=0)
        for t in self.tracks:
            for c in t.clips:
                if isinstance(c, MediaClip):
                    end = max(end, c.end_ms())
                else:
                    end = max(end, c.end_ms)
        return end


def timeline_len_ms(in_ms: int, out_ms: int, speed: float) -> int:
    """Timeline length of a source range at a given speed, rounded to int ms.

    Uses round-half-up (not banker's rounding) so results are stable and
    order-independent across the codebase.
    """
    return int(math.floor((out_ms - in_ms) / speed + 0.5))


def empty_edl(project_id: str, name: str, canvas: dict[str, Any]) -> EDL:
    return EDL(
        edl_version=EDL_VERSION,
        project=Project(id=project_id, name=name, canvas=Canvas(**canvas)),
        assets={},
        tracks=[],
    )
