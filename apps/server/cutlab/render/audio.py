"""Audio filter chain builders (A8 stage 3)."""
from __future__ import annotations

from .planner import AudioPiece


def atempo_chain(speed: float) -> list[str]:
    """Decompose a speed factor into atempo stages within [0.5, 2.0]."""
    if speed == 1.0:
        return []
    stages: list[str] = []
    f = speed
    while f > 2.0:
        stages.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        stages.append("atempo=0.5")
        f /= 0.5
    stages.append(f"atempo={f:.6g}")
    return stages


def piece_filter(piece: AudioPiece, input_index: int, delay_ms: int, label: str) -> str:
    """Filter chain for one audio piece, already source-trimmed by input seek."""
    steps = ["asetpts=PTS-STARTPTS"]
    steps += atempo_chain(piece.speed)
    if piece.gain_db:
        steps.append(f"volume={piece.gain_db:.6g}dB")
    steps.append("aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")
    if delay_ms > 0:
        steps.append(f"adelay={delay_ms}:all=1")
    return f"[{input_index}:a]" + ",".join(steps) + f"[{label}]"


def mix_filter(labels: list[str], dur_s: str, out_label: str = "aout") -> str:
    """amix all piece labels (or silence when none), padded/trimmed to dur_s."""
    if not labels:
        return f"anullsrc=r=48000:cl=stereo,atrim=0:{dur_s}[{out_label}]"
    ins = "".join(f"[{l}]" for l in labels)
    mix = f"amix=inputs={len(labels)}:duration=longest:normalize=0" if len(labels) > 1 \
        else "anull"
    return (f"{ins}{mix},apad=whole_dur={dur_s},atrim=0:{dur_s},"
            f"asetpts=PTS-STARTPTS[{out_label}]")
