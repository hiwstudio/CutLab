"""Scene-range editing over the existing EDL; no new persistence engine."""
from __future__ import annotations

import math

from .schema import EDL, CaptionClip, MediaClip


def end(clip):
    return clip.end_ms() if isinstance(clip, MediaClip) else clip.end_ms


def fingerprint(edl: EDL, scene):
    # Full contributing clips intentionally invalidate a scene if shared media changes.
    contents = []
    solos = [t.id for t in edl.tracks if t.solo and t.kind in ("video", "audio")]
    for t in edl.tracks:
        clips = [c for c in t.clips if c.start_ms < scene.end_ms and end(c) > scene.start_ms]
        if clips:
            contents.append((t.id, t.kind, t.muted, t.solo, t.gain_db,
                             [(c.model_dump(), edl.assets[c.asset].model_dump()
                               if isinstance(c, MediaClip) else None) for c in clips]))
    return (scene.start_ms, scene.end_ms, scene.title,
            edl.project.canvas.model_dump(), solos, contents)


def guard_and_review(before: EDL, after: EDL, op_name: str):
    """Called after each op in the transactional engine, including smart operations."""
    from .ops import OpError

    for old in before.tracks:
        if not old.locked:
            continue
        new = after.find_track(old.id)
        a = old.model_dump(exclude={"locked"})
        b = new.model_dump(exclude={"locked"}) if new else None
        if a != b:
            raise OpError("E_LOCKED", "track", f"Unlock {old.name or old.id} before editing it")
    originals = {s.id: s for s in before.scenes}
    for scene in after.scenes:
        old = originals.get(scene.id)
        if old and fingerprint(before, old) != fingerprint(after, scene):
            scene.approved = False


def delete_scene_range(edl: EDL, start: int, stop: int):
    """Map explicit scene markers through an all-track ripple delete."""
    def position(p):
        return p if p <= start else max(start, p - (stop - start))
    kept = []
    for s in edl.scenes:
        s.start_ms, s.end_ms = position(s.start_ms), position(s.end_ms)
        if s.start_ms < s.end_ms:
            kept.append(s)
    edl.scenes = kept


def move_scene(edl: EDL, scene_id: str, to_index: int):
    """Reorder contiguous story ranges, moving bounded layers together.

    Crossing clips are partitioned using the same source/time conversion as
    split/delete_range. Tracks explicitly marked music retain absolute placement.
    """
    from .ops import OpError, _sort_and_check
    from ..util.ids import new_clip_id

    ordered = sorted(edl.scenes, key=lambda s: s.start_ms)
    source = next((s for s in ordered if s.id == scene_id), None)
    if source is None:
        raise OpError("E_REF", "scene", "Scene not found")
    if not 0 <= to_index < len(ordered):
        raise OpError("E_RANGE", "to_index", "Scene position is outside the story")
    if ordered.index(source) == to_index:
        return
    if any(a.end_ms != b.start_ms for a, b in zip(ordered, ordered[1:])):
        raise OpError("E_RANGE", "scenes", "Close the gaps between scene ranges before reordering")
    rearranged = [s for s in ordered if s.id != source.id]
    rearranged.insert(to_index, source)
    cursor = ordered[0].start_ms
    shifts = {}
    for s in rearranged:
        shifts[s.id] = cursor - s.start_ms
        cursor += s.end_ms - s.start_ms
    bounds = sorted({p for s in ordered for p in (s.start_ms, s.end_ms)})
    for track in edl.tracks:
        if track.role == "music":
            continue
        result = []
        for clip in track.clips:
            cuts = [clip.start_ms, *[b for b in bounds if clip.start_ms < b < end(clip)], end(clip)]
            for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
                piece = clip.model_copy(deep=True)
                if i:
                    piece.id = new_clip_id()
                scope = next((s for s in ordered if s.start_ms <= a < s.end_ms), None)
                delta = shifts[scope.id] if scope else 0
                piece.start_ms = a + delta
                if isinstance(piece, MediaClip):
                    piece.in_ms = clip.in_ms + math.floor((a - clip.start_ms) * clip.speed)
                    piece.out_ms = (clip.out_ms if b == end(clip) else
                                    clip.in_ms + math.floor((b - clip.start_ms) * clip.speed))
                    if piece.out_ms <= piece.in_ms:
                        continue
                    if b != end(clip):
                        piece.transition_out = None
                else:
                    piece.end_ms = b + delta
                result.append(piece)
        track.clips = result
        _sort_and_check(track, "move_scene")
    for s in ordered:
        delta = shifts[s.id]
        s.start_ms += delta
        s.end_ms += delta
    edl.scenes = rearranged
