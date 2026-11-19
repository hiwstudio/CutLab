"""Curated, machine-local music and sound effects available inside CutLab."""
from __future__ import annotations

from pathlib import Path

from . import config


SOUNDS = (
    ("music-forward-motion", "Forward Motion", "music", "upbeat", "music/upbeat/forward-motion-514d073f6718.mp3"),
    ("music-stakes-emerge", "The Stakes Emerge", "music", "tense", "music/tense/the-stakes-emerge-837c07aecb63.mp3"),
    ("music-controlled-pressure", "Controlled Pressure", "music", "tense", "music/tense/controlled-pressure-76c5df85565b.mp3"),
    ("music-competitive-drive", "Competitive Drive", "music", "tense", "music/tense/competitive-drive-fd6e682fa70c.mp3"),
    ("music-precision-garage", "Precision Garage", "music", "neutral", "music/neutral/precision-garage-84eef44d1ade.mp3"),
    ("music-way-forward", "A Way Forward", "music", "hopeful", "music/hopeful/a-way-forward-3c956eadbccb.mp3"),
    ("music-quiet-weight", "Quiet Weight", "music", "emotional", "music/emotional/quiet-weight-ee894d4ef435.mp3"),
    ("music-human-oddity", "Human Oddity", "music", "curious", "music/curious/human-oddity-841129043df7.mp3"),
    ("music-hidden-thread", "Hidden Thread", "music", "curious", "music/curious/hidden-thread-16450dd954f3.mp3"),
    ("music-curious-mechanism", "Curious Mechanism", "music", "curious", "music/curious/curious-mechanism-6566e43e5314.mp3"),
    ("sfx-whoosh", "Whoosh", "sfx", "transition", "sfx/whoosh/whoosh-01.mp3"),
    ("sfx-impact", "Impact", "sfx", "emphasis", "sfx/impact/impact-01.mp3"),
    ("sfx-riser", "Riser", "sfx", "transition", "sfx/riser/riser-01.mp3"),
    ("sfx-pop", "Pop", "sfx", "emphasis", "sfx/pop/pop-01.mp3"),
    ("sfx-click", "UI Click", "sfx", "interface", "sfx/ui/ui-click-01.mp3"),
    ("sfx-camera", "Camera", "sfx", "camera", "sfx/camera/camera-01.mp3"),
    ("sfx-success", "Success", "sfx", "interface", "sfx/success/success-01.mp3"),
)


def catalog() -> list[dict[str, str]]:
    return [
        {"id": sound_id, "title": title, "kind": kind, "category": category,
         "filename": path_for(sound_id).name}
        for sound_id, title, kind, category, _ in SOUNDS if path_for(sound_id).is_file()
    ]


def path_for(sound_id: str) -> Path:
    row = next((row for row in SOUNDS if row[0] == sound_id), None)
    if row is None:
        raise KeyError(sound_id)
    return config.SOUND_LIBRARY_ROOT / Path(row[4])
