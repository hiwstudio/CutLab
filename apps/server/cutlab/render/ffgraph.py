"""FFmpeg graph compiler (A8 stages 2-4).

Pure: (plan, project_dir, work_dir) -> full ffmpeg command lists. Timeline is
rendered in <=60s chunks (each chunk one ffmpeg invocation compiling video +
audio together), then concat-demuxed into the final mp4. Deterministic: same
plan + paths -> identical commands.
"""
from __future__ import annotations

from pathlib import Path

from . import audio as audio_filters
from .planner import AudioPiece, Plan, VideoPiece


def _sec(ms: int) -> str:
    return f"{ms / 1000:.3f}"


def _fps_str(fps: float) -> str:
    return f"{fps:.6g}"


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def chunk_path(work_dir: Path, index: int) -> Path:
    return work_dir / f"chunk_{index:04d}.mp4"


def _crop_geometry(piece: VideoPiece, canvas_w: int, canvas_h: int) -> tuple[str | None, int, int]:
    """Returns (crop filter or None, effective source w, effective source h)."""
    w, h = piece.asset_w, piece.asset_h
    if piece.crop_mode == "manual" and piece.crop_rect:
        x, y, cw, ch = piece.crop_rect
        cw, ch = min(cw, w - x), min(ch, h - y)
        return f"crop={cw}:{ch}:{x}:{y}", cw, ch
    if piece.crop_mode == "center":
        target_ar = canvas_w / canvas_h
        if w / h > target_ar:
            cw, ch = _even(h * target_ar), h
        else:
            cw, ch = w, _even(w / target_ar)
        cw, ch = min(cw, w), min(ch, h)
        return f"crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2", cw, ch
    return None, w, h


def _piece_video_chain(
    piece: VideoPiece, input_index: int, label: str,
    canvas_w: int, canvas_h: int, fps: float, offset_ms: int,
) -> tuple[str, int, int]:
    """Filter chain for one visible video piece; returns (chain, x, y)."""
    crop, w1, h1 = _crop_geometry(piece, canvas_w, canvas_h)
    fit = min(canvas_w / w1, canvas_h / h1) * piece.scale
    w2, h2 = _even(w1 * fit), _even(h1 * fit)
    x = (canvas_w - w2) // 2 + piece.offset_x
    y = (canvas_h - h2) // 2 + piece.offset_y

    steps = []
    if piece.speed != 1.0 and not piece.is_image:
        steps.append(f"setpts=(PTS-STARTPTS)/{piece.speed:.6g}")
    else:
        steps.append("setpts=PTS-STARTPTS")
    steps.append(f"fps={_fps_str(fps)}")
    if crop:
        steps.append(crop)
    steps.append(f"scale={w2}:{h2}")
    steps.append("setsar=1")
    steps.append("format=yuv420p")
    if offset_ms > 0:
        steps.append(f"setpts=PTS+{_sec(offset_ms)}/TB")
    return f"[{input_index}:v]" + ",".join(steps) + f"[{label}]", x, y


def compile_chunk(plan: Plan, index: int, project_dir: Path, work_dir: Path) -> list[str]:
    """Full ffmpeg args (without the binary) for one timeline chunk."""
    t0, t1 = plan.chunks[index]
    dur_ms = t1 - t0
    dur_s = _sec(dur_ms)
    fps = _fps_str(plan.fps)

    inputs: list[str] = []
    filters: list[str] = []
    n_inputs = 0

    filters.append(
        f"color=c=black:s={plan.width}x{plan.height}:r={fps}:d={dur_s}[b]"
    )
    current = "b"
    n_label = 0

    for pieces in plan.video_tracks:  # bottom-up
        for piece in pieces:
            vis0, vis1 = max(piece.start_ms, t0), min(piece.end_ms, t1)
            if vis0 >= vis1:
                continue
            src = str(project_dir / piece.src)
            if piece.is_image:
                inputs += ["-loop", "1", "-t", _sec(vis1 - vis0), "-i", src]
            else:
                src_start = piece.in_ms + round((vis0 - piece.start_ms) * piece.speed)
                src_dur = round((vis1 - vis0) * piece.speed)
                inputs += ["-ss", _sec(src_start), "-t", _sec(src_dur), "-i", src]
            label = f"p{n_label}"
            chain, x, y = _piece_video_chain(
                piece, n_inputs, label, plan.width, plan.height, plan.fps, vis0 - t0,
            )
            filters.append(chain)
            out_label = f"v{n_label}"
            filters.append(
                f"[{current}][{label}]overlay={x}:{y}"
                f":enable='between(t,{_sec(vis0 - t0)},{_sec(vis1 - t0)})'"
                f":eof_action=pass[{out_label}]"
            )
            current = out_label
            n_label += 1
            n_inputs += 1

    audio_labels: list[str] = []
    for piece in plan.audio:
        vis0, vis1 = max(piece.start_ms, t0), min(piece.end_ms, t1)
        if vis0 >= vis1:
            continue
        src_start = piece.in_ms + round((vis0 - piece.start_ms) * piece.speed)
        src_dur = round((vis1 - vis0) * piece.speed)
        inputs += ["-ss", _sec(src_start), "-t", _sec(src_dur), "-i",
                   str(project_dir / piece.src)]
        label = f"a{len(audio_labels)}"
        filters.append(audio_filters.piece_filter(piece, n_inputs, vis0 - t0, label))
        audio_labels.append(label)
        n_inputs += 1

    filters.append(audio_filters.mix_filter(audio_labels, dur_s))

    return [
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{current}]", "-map", "[aout]",
        # preview (L1 segment) trades quality for turnaround; final is archival.
        *(["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]
          if plan.quality == "preview"
          else ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]),
        "-c:a", "aac", "-b:a", "128k" if plan.quality == "preview" else "192k",
        "-ar", "48000",
        "-r", fps,
        "-t", dur_s,
        str(chunk_path(work_dir, index)),
    ]


def concat_list_content(chunk_files: list[Path]) -> str:
    """concat demuxer list; single quotes escaped, forward slashes for safety."""
    lines = []
    for p in chunk_files:
        posix = str(p).replace("\\", "/").replace("'", r"'\''")
        lines.append(f"file '{posix}'")
    return "\n".join(lines) + "\n"


def compile_mux(list_file: Path, out_file: Path) -> list[str]:
    return [
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart",
        str(out_file),
    ]


def compile_all(plan: Plan, project_dir: Path, work_dir: Path, out_file: Path) -> dict:
    """Every command for this render, for deterministic logging."""
    return {
        "chunks": [compile_chunk(plan, i, project_dir, work_dir)
                   for i in range(len(plan.chunks))],
        "mux": compile_mux(work_dir / "concat.txt", out_file),
    }
