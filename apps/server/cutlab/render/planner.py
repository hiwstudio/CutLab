"""Render planning (A8 stage 1): normalize an EDL revision into a segment
plan. Pure: (edl, asset_audio) -> Plan. Path strings stay relative to the
project dir; the graph compiler receives the project dir separately.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import RENDER_CHUNK_MS
from ..edl.schema import EDL, CaptionClip, MediaClip

log = logging.getLogger("cutlab.render")


@dataclass
class VideoPiece:
    src: str                 # relative to project dir
    is_image: bool
    in_ms: int
    out_ms: int
    speed: float
    start_ms: int            # timeline
    end_ms: int              # timeline
    asset_w: int
    asset_h: int
    crop_mode: str = "none"  # none | center | manual
    crop_rect: tuple[int, int, int, int] | None = None  # x, y, w, h
    scale: float = 1.0
    offset_x: int = 0
    offset_y: int = 0


@dataclass
class AudioPiece:
    src: str
    in_ms: int
    out_ms: int
    speed: float
    start_ms: int
    end_ms: int
    gain_db: float


@dataclass
class CaptionPiece:
    start_ms: int
    end_ms: int
    text: str
    style: str | None = None  # caption-style capability id; None = default


@dataclass
class Plan:
    width: int
    height: int
    fps: float
    duration_ms: int
    video_tracks: list[list[VideoPiece]] = field(default_factory=list)  # bottom-up
    audio: list[AudioPiece] = field(default_factory=list)
    captions: list[CaptionPiece] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality: str = "final"  # final | preview (L1 segment renders: fast encode)

    @property
    def chunks(self) -> list[tuple[int, int]]:
        """Timeline chunk windows [t0, t1) of <= RENDER_CHUNK_MS each."""
        out = []
        t = 0
        while t < self.duration_ms:
            out.append((t, min(t + RENDER_CHUNK_MS, self.duration_ms)))
            t += RENDER_CHUNK_MS
        return out


def build_plan(edl: EDL, asset_audio: dict[str, bool]) -> Plan:
    """`asset_audio` maps asset id -> whether its file has an audio stream
    (probed by the runner; the EDL itself doesn't store it)."""
    duration = edl.computed_duration_ms()
    plan = Plan(
        width=edl.project.canvas.width,
        height=edl.project.canvas.height,
        fps=edl.project.canvas.fps,
        duration_ms=duration,
    )
    if duration == 0:
        return plan

    for track in edl.tracks:
        if track.kind in ("caption", "text"):
            for clip in track.clips:
                assert isinstance(clip, CaptionClip)
                plan.captions.append(CaptionPiece(
                    start_ms=clip.start_ms, end_ms=clip.end_ms,
                    text=clip.text, style=clip.cap_style,
                ))
            continue

        pieces: list[VideoPiece] = []
        for clip in track.clips:
            assert isinstance(clip, MediaClip)
            asset = edl.assets[clip.asset]
            if clip.effects:
                plan.warnings.append(f"clip {clip.id}: {len(clip.effects)} effect(s) skipped")
            if clip.transition_out:
                plan.warnings.append(f"clip {clip.id}: transition_out skipped")
            if clip.transform and clip.transform.rotate:
                plan.warnings.append(f"clip {clip.id}: rotate not rendered in Phase 0")

            if track.kind == "video":
                piece = VideoPiece(
                    src=asset.src,
                    is_image=asset.kind == "image",
                    in_ms=clip.in_ms, out_ms=clip.out_ms, speed=clip.speed,
                    start_ms=clip.start_ms, end_ms=clip.end_ms(),
                    asset_w=asset.width or 0, asset_h=asset.height or 0,
                )
                if clip.crop:
                    piece.crop_mode = clip.crop.mode
                    if clip.crop.rect:
                        r = clip.crop.rect
                        piece.crop_rect = (r.x, r.y, r.w, r.h)
                if clip.transform:
                    piece.scale = clip.transform.scale
                    piece.offset_x = clip.transform.x
                    piece.offset_y = clip.transform.y
                pieces.append(piece)

            # Audio: any clip whose asset carries an audio stream contributes.
            if asset.kind != "image" and asset_audio.get(clip.asset, False):
                plan.audio.append(AudioPiece(
                    src=asset.src,
                    in_ms=clip.in_ms, out_ms=clip.out_ms, speed=clip.speed,
                    start_ms=clip.start_ms, end_ms=clip.end_ms(),
                    gain_db=clip.gain_db,
                ))
        if track.kind == "video":
            plan.video_tracks.append(pieces)

    for w in plan.warnings:
        log.warning("%s", w)
    return plan


def window_plan(plan: Plan, from_ms: int, to_ms: int, quality: str = "preview") -> Plan:
    """Pure: restrict a plan to the timeline window [from_ms, to_ms), re-based
    to 0. Used for L1 segment previews. Source ranges are re-derived from the
    visible timeline span (respecting speed) so a windowed piece plays exactly
    what the full render would play in that window."""
    from_ms = max(0, from_ms)
    to_ms = min(plan.duration_ms, to_ms)
    if to_ms <= from_ms:
        raise ValueError("empty preview window")

    out = Plan(width=plan.width, height=plan.height, fps=plan.fps,
               duration_ms=to_ms - from_ms, warnings=list(plan.warnings),
               quality=quality)

    for pieces in plan.video_tracks:
        windowed: list[VideoPiece] = []
        for p in pieces:
            vis0, vis1 = max(p.start_ms, from_ms), min(p.end_ms, to_ms)
            if vis0 >= vis1:
                continue
            q = VideoPiece(**{**p.__dict__})
            if p.is_image:
                q.in_ms, q.out_ms = 0, vis1 - vis0
            else:
                q.in_ms = p.in_ms + round((vis0 - p.start_ms) * p.speed)
                q.out_ms = p.in_ms + round((vis1 - p.start_ms) * p.speed)
            q.start_ms, q.end_ms = vis0 - from_ms, vis1 - from_ms
            windowed.append(q)
        out.video_tracks.append(windowed)

    for a in plan.audio:
        vis0, vis1 = max(a.start_ms, from_ms), min(a.end_ms, to_ms)
        if vis0 >= vis1:
            continue
        out.audio.append(AudioPiece(
            src=a.src,
            in_ms=a.in_ms + round((vis0 - a.start_ms) * a.speed),
            out_ms=a.in_ms + round((vis1 - a.start_ms) * a.speed),
            speed=a.speed,
            start_ms=vis0 - from_ms, end_ms=vis1 - from_ms,
            gain_db=a.gain_db,
        ))

    for c in plan.captions:
        vis0, vis1 = max(c.start_ms, from_ms), min(c.end_ms, to_ms)
        if vis0 >= vis1:
            continue
        out.captions.append(CaptionPiece(
            start_ms=vis0 - from_ms, end_ms=vis1 - from_ms,
            text=c.text, style=c.style,
        ))
    return out
