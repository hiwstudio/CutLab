"""Understanding artifact schema (Phase 1).

One JSON per analyzed asset: `understanding/{asset}.understanding.json`, referenced
from `asset.understanding` in the EDL. It is *derived data* about an asset — the
inputs a later-phase director/compaction engine reasons over. Unlike a render
(A2.7), it is not byte-stable; it records the tools/params used, for provenance.

All times are integer milliseconds, consistent with the EDL (A2.5). The analyzers
work in float seconds internally (ffmpeg/whisper native units) and convert at the
boundary.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UNDERSTANDING_VERSION = "1.0"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Word(Strict):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    word: str


class TranscriptSegment(Strict):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str
    words: list[Word] = Field(default_factory=list)
    # Whisper confidence signals — how clear the speech is (used by saliency).
    avg_logprob: float = 0.0
    no_speech_prob: float = Field(default=0.0, ge=0.0, le=1.0)


class Transcript(Strict):
    language: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)

    def word_count(self) -> int:
        return sum(len(s.words) for s in self.segments)


class Scene(Strict):
    index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class SilenceSpan(Strict):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class ActiveRange(Strict):
    """Complement of silence — the spoken/active spans (padded, merged)."""

    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class SaliencyWindow(Strict):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    score: float = Field(ge=0.0, le=1.0)


class Saliency(Strict):
    profile: str
    window_ms: int = Field(gt=0)
    windows: list[SaliencyWindow] = Field(default_factory=list)
    # The weights actually applied, for provenance/tuning.
    weights: dict[str, float] = Field(default_factory=dict)

    def peak(self) -> SaliencyWindow | None:
        return max(self.windows, key=lambda w: w.score, default=None)


class Provenance(Strict):
    """What produced each signal — tools, models, params."""

    transcribe: dict[str, str] | None = None
    scenes: dict[str, str] | None = None
    silence: dict[str, str] | None = None
    beats: dict[str, str] | None = None


class Understanding(Strict):
    version: Literal["1.0"]
    asset_id: str
    kind: Literal["video", "audio", "image"]
    duration_ms: int = Field(ge=0)
    transcript: Transcript | None = None
    scenes: list[Scene] = Field(default_factory=list)
    silence: list[SilenceSpan] = Field(default_factory=list)
    active_ranges: list[ActiveRange] = Field(default_factory=list)
    beats_ms: list[int] = Field(default_factory=list)
    tempo_bpm: float | None = None
    saliency: Saliency | None = None
    provenance: Provenance = Field(default_factory=Provenance)


def seconds_to_ms(s: float) -> int:
    return int(round(s * 1000))
