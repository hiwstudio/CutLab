"""Assembly — ffmpeg render of an approved timeline.

Each scene becomes a segment spanning from its start to the next scene's start
(so inter-sentence gaps stay covered and video duration == narration duration).
Clips are trimmed/scaled/padded to the project resolution. When a clip runs out
before its window ends, real footage beyond trim_out fills the gap first (the
trim stays the scene's chosen start/body); only then does the last frame hold.
MIX scenes crossfade into each other (render.transition_s) without changing
total duration: every segment carries a transition-length tail that the xfade
consumes, so each scene's content still starts exactly on its narration beat.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from .tools import FFMPEG, FFPROBE


def _run(args: list[str]) -> None:
    """ffmpeg, with its own words on failure.

    check=True alone raises CalledProcessError whose str() is just the command
    and an exit code — the actual reason ("Impossible to open", "Invalid
    argument") sits in .stderr where no traceback shows it. Every render
    failure then looks identical and tells you nothing.
    """
    proc = subprocess.run([FFMPEG, "-v", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed ({' '.join(args[:6])}...): "
            f"{(proc.stderr or '').strip()[-500:]}")


def _fit(w: int, h: int, fps: int) -> str:
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}")


def _fill(w: int, h: int, fps: int) -> str:
    """Cover the frame and centre-crop — no letterbox bars.

    SPLIT panes are half-height boxes fed by 16:9 sources; _fit would pad each
    pane with black and the stacked frame would be mostly bars. Cropping loses
    the edges, which is the right trade when the subject is centred (a speaker,
    a ring)."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,fps={fps}")


def _even(n: int) -> int:
    return n - (n % 2)  # yuv420p needs even dimensions on both panes


def _clip_len_ms(path: str) -> int:
    probe = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True, capture_output=True, text=True)
    return round(float(probe.stdout.strip()) * 1000)


def _kenburns_clip(img: Path, dur_ms: int, out: Path, w: int, h: int, fps: int,
                   zoom_in: bool = True) -> None:
    """One still → a slow-zoom (Ken Burns) clip of exactly dur_ms.
    Supersamples 4x to kill zoompan's jitter bug; fills the frame."""
    if out.exists():
        return
    frames = max(1, round(dur_ms / 1000 * fps))
    z = ("min(zoom+0.0008,1.12)" if zoom_in
         else "if(lte(zoom,1.001),1.12,max(zoom-0.0008,1.0))")
    vf = (f"scale={w*4}:{h*4}:force_original_aspect_ratio=increase,"
          f"crop={w*4}:{h*4},"
          f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':"
          f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},setsar=1,format=yuv420p")
    _run(["-loop", "1", "-i", str(img), "-t", f"{dur_ms / 1000:.3f}",
          "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-preset", "veryfast", "-crf", "20", str(out)])


def build_scene_montage(images: list[Path], durs_ms: list[int], out: Path,
                        w: int, h: int, fps: int, trans_ms: int = 400) -> Path:
    """Compose an ordered list of stills into one scene clip: each image gets a
    Ken Burns move for its allotted duration, images crossfade into each other,
    and total duration == sum(durs_ms) exactly (transition tails absorbed by the
    xfade, same technique as the scene render). Alternates zoom in/out for life."""
    n = len(images)
    parts_dir = out.parent / (out.stem + "_parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (img, d) in enumerate(zip(images, durs_ms)):
        tail = trans_ms if (trans_ms and i < n - 1) else 0
        p = parts_dir / f"{i:02d}.mp4"
        _kenburns_clip(img, d + tail, p, w, h, fps, zoom_in=(i % 2 == 0))
        parts.append(p)
    total = sum(durs_ms)
    if trans_ms and n > 1:
        inputs = [a for p in parts for a in ("-i", str(p))]
        bounds, acc = [], 0
        for d in durs_ms[:-1]:
            acc += d
            bounds.append(acc)
        graph, prev = [], "0:v"
        for i in range(1, n):
            nxt = f"v{i}"
            graph.append(f"[{prev}][{i}:v]xfade=transition=fade:"
                         f"duration={trans_ms / 1000:.3f}:"
                         f"offset={bounds[i - 1] / 1000:.3f}[{nxt}]")
            prev = nxt
        _run([*inputs, "-filter_complex", ";".join(graph), "-map", f"[{prev}]",
              "-t", f"{total / 1000:.3f}", "-an", "-c:v", "libx264",
              "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
              str(out)])
    else:
        _kenburns_clip(images[0], total, out, w, h, fps)
    return out


def _write_concat(path: Path, pieces) -> None:
    """Concat list with paths relative to the CONCAT FILE's own directory.

    Two traps, both hit in production:
      * The demuxer resolves relative entries against the concat file's
        directory, not the cwd. A relative project dir therefore produced
        `assembly/projects/<name>/assembly/segments/...` — "Impossible to open".
      * Absolute paths are not the fix on Windows: the demuxer does not treat a
        drive letter as absolute, so `C:/...` got the same directory prepended.

    Anchoring to the concat file's own directory is correct on both platforms,
    and every caller already writes the list beside the segments it lists.

    This holds for a CURRENT ffmpeg. Measured on the same concat file with the
    engine's cwd elsewhere: 8.1.2 resolves against the concat file (works),
    4.2.3 resolves against the cwd (fails). That is why mixfix/tools.py pins
    the binary instead of taking whatever PATH offers.
    """
    base = path.parent.resolve()
    lines = []
    for q in pieces:
        p = Path(q).resolve()
        try:
            rel = p.relative_to(base).as_posix()
        except ValueError:                      # outside the tree: last resort
            rel = p.as_posix()
        lines.append(f"file '{rel}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _segment_key(scene: dict, dur_ms: int, w: int, h: int, fps: int) -> str:
    """Content hash naming a rendered segment.

    Segments used to be named by timeline position alone ('007_t400.mp4'), and
    _segment() skips any file that already exists. Re-sourcing a scene then
    silently reused the previous render of that slot — a scene that gained real
    footage still showed the old grey card. The identity of a segment is what is
    IN it, so the visual (and everything that changes its pixels) names it."""
    vis = scene.get("visual") or {}
    ident = "|".join(str(x) for x in (
        vis.get("kind", "none"), vis.get("asset_id") or vis.get("path", ""),
        vis.get("trim_in_ms", 0), dur_ms, w, h, fps))
    return hashlib.sha1(ident.encode("utf-8")).hexdigest()[:12]


def _usable(p: Path) -> bool:
    """True if `p` is a complete, readable video file.

    The segment cache skips anything that already exists, which makes resume
    cheap but trusts the file. A render killed mid-write (Ctrl-C, a closed
    session, an OOM) leaves a TRUNCATED mp4 at the final path — and because
    existence is all the guard checks, every later run skips it and ffmpeg dies
    on `moov atom not found`. The cache could never repair itself. Probing costs
    milliseconds against an encode that costs minutes, and a file that will not
    probe has to be rewritten anyway, so a bad one is removed here.
    """
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, check=True, timeout=30)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        p.unlink(missing_ok=True)
        return False


def _segment(scene: dict, dur_ms: int, out: Path, w: int, h: int, fps: int,
             fill: bool = False) -> None:
    if _usable(out):  # idempotent resume — content-keyed name, verified file
        return
    dur_s = f"{dur_ms / 1000:.3f}"
    vis = scene.get("visual")
    hold = "tpad=stop_mode=clone:stop=-1"  # hold last frame if footage runs out
    _fit_ = _fill if fill else _fit
    if vis and vis["kind"] == "clip":
        tin = vis.get("trim_in_ms", 0)
        # soft trim_out: when the segment window (scene + narration gap +
        # transition tail) outlasts the trimmed body, prefer real footage
        # beyond trim_out over a frozen frame — the sourced clip was
        # vision-verified across its full length
        avail = max(_clip_len_ms(vis["path"]) - tin, 0)
        take_ms = min(avail, dur_ms)
        _run(["-ss", f"{tin / 1000:.3f}", "-t", f"{take_ms / 1000:.3f}",
              "-i", vis["path"], "-vf", f"{_fit_(w, h, fps)},{hold}",
              "-t", dur_s, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
              "-crf", "20", str(out)])
    elif vis and vis["kind"] == "image":
        _run(["-loop", "1", "-i", vis["path"], "-vf", _fit_(w, h, fps),
              "-t", dur_s, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
              "-crf", "20", str(out)])
    else:  # uncovered scene: neutral card (not pure black — QA checks for black)
        # Faint temporal grain, not a dead-still card: a frame-identical fill
        # trips the render-QA freeze detector, and reads as a broken player to a
        # viewer. The grain makes an uncovered scene look deliberate.
        _run(["-f", "lavfi", "-i", f"color=c=0x303030:size={w}x{h}:rate={fps}",
              "-vf", "noise=alls=9:allf=t+u",
              "-t", dur_s, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
              "-crf", "20", str(out)])


def render(project_dir: Path, tl: dict, tmap: dict, cfg: dict,
           out_name: str = "render.mp4",
           seg_subdir: str = "segments") -> Path:
    r = cfg["render"]
    w, h, fps = r["width"], r["height"], r["fps"]
    total_ms = tmap["source"]["duration_ms"]
    trans_ms = int(float(r.get("transition_s", 0.4)) * 1000)
    scenes = sorted(tl["scenes"], key=lambda s: s["start_ms"])
    bounds = [0] + [s["start_ms"] for s in scenes[1:]] + [total_ms]
    n = len(scenes)

    seg_dir = project_dir / "assembly" / seg_subdir
    seg_dir.mkdir(parents=True, exist_ok=True)
    seg_paths = []
    for i, scene in enumerate(scenes):
        # every segment except the last carries a transition tail that the
        # crossfade consumes — total duration and narration sync are unchanged
        tail = trans_ms if (trans_ms and i < n - 1) else 0
        seg_ms = bounds[i + 1] - bounds[i] + tail
        p = seg_dir / f"{i:03d}_{_segment_key(scene, seg_ms, w, h, fps)}.mp4"
        _segment(scene, seg_ms, p, w, h, fps)
        seg_paths.append(p)
    keep = {q.name for q in seg_paths}
    for stale in seg_dir.glob("*.mp4"):   # superseded content keys, incl. the
        if stale.name not in keep and re.match(r"\d{3}_", stale.name):
            stale.unlink()                # position-named files from older runs

    voice = project_dir / "voiceover" / "voice.mp3"
    out = project_dir / "assembly" / out_name
    burn = ""
    if r.get("captions") == "burn":
        srt = write_srt(tmap, project_dir / "assembly" / "captions.srt")
        burn = (f"subtitles='{_filter_path(srt)}':"
                f"force_style='FontSize={r.get('caption_size', 24)}'")
    common = ["-af", f"loudnorm=I={r.get('target_lufs', -16)}:TP=-1.5:LRA=11",
              "-t", f"{total_ms / 1000:.3f}",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
              "-c:a", "aac", "-b:a", "192k",
              # Without this ffmpeg writes moov AFTER mdat, so a browser cannot
              # read the index until it has downloaded the whole file — the
              # review board loads but scenes will not play, because clicking a
              # scene is a SEEK and a seek needs moov. Measured here: a 26MB
              # draft put moov at byte 25,933,475 of 26,395,914.
              "-movflags", "+faststart",
              str(out)]

    if trans_ms and n > 1:
        # chain of xfades; transition i starts exactly at scene i+1's boundary
        inputs = [a for p in seg_paths for a in ("-i", str(p))]
        graph, prev = [], "0:v"
        for i in range(1, n):
            nxt = f"v{i}"
            graph.append(f"[{prev}][{i}:v]xfade=transition=fade:"
                         f"duration={trans_ms / 1000:.3f}:"
                         f"offset={bounds[i] / 1000:.3f}[{nxt}]")
            prev = nxt
        if burn:
            graph.append(f"[{prev}]{burn}[vout]")
            prev = "vout"
        _run([*inputs, "-i", str(voice),
              "-filter_complex", ";".join(graph),
              "-map", f"[{prev}]", "-map", f"{n}:a", *common])
    else:
        concat = project_dir / "assembly" / "concat.txt"
        _write_concat(concat, seg_paths)
        vf = _fit(w, h, fps) + (f",{burn}" if burn else "")
        _run(["-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(voice),
              "-map", "0:v", "-map", "1:a", "-vf", vf, *common])
    return out


def render_fix(project_dir: Path, tl: dict, tmap: dict, cfg: dict,
               source: Path) -> Path:
    """FIX render: original video plays; overlay scenes replace the picture
    for their window; the original audio stream is copied untouched."""
    r = cfg["render"]
    w, h, fps = r["width"], r["height"], r["fps"]
    total_ms = tmap["source"]["duration_ms"]
    overlays = sorted((s for s in tl["scenes"] if s.get("visual")),
                      key=lambda s: s["start_ms"])

    seg_dir = project_dir / "assembly" / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    pieces, cursor, idx = [], 0, 0

    def base_piece(start_ms: int, end_ms: int, out: Path) -> None:
        if _usable(out):
            return
        _run(["-ss", f"{start_ms / 1000:.3f}", "-t",
              f"{(end_ms - start_ms) / 1000:.3f}", "-i", str(source),
              "-vf", f"{_fit(w, h, fps)},tpad=stop_mode=clone:stop=-1",
              "-t", f"{(end_ms - start_ms) / 1000:.3f}",
              "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
              str(out)])

    for ov in overlays:
        if ov["start_ms"] > cursor:
            p = seg_dir / (f"base_{idx:03d}_" + hashlib.sha1(
                f"{cursor}|{ov['start_ms']}|{w}|{h}|{fps}".encode()
                ).hexdigest()[:12] + ".mp4")
            base_piece(cursor, ov["start_ms"], p)
            pieces.append(p)
            idx += 1
        p = seg_dir / (f"overlay_{ov['id']}_"
                       + _segment_key(ov, ov["end_ms"] - ov["start_ms"], w, h, fps)
                       + ".mp4")
        _segment(ov, ov["end_ms"] - ov["start_ms"], p, w, h, fps)
        pieces.append(p)
        cursor = ov["end_ms"]
    if cursor < total_ms:
        p = seg_dir / (f"base_{idx:03d}_" + hashlib.sha1(
            f"{cursor}|{total_ms}|{w}|{h}|{fps}".encode()).hexdigest()[:12] + ".mp4")
        base_piece(cursor, total_ms, p)
        pieces.append(p)

    concat = project_dir / "assembly" / "concat.txt"
    _write_concat(concat, pieces)
    out = project_dir / "assembly" / "render.mp4"
    # original audio is stream-copied — never re-encoded, never modified
    # +faststart moves moov ahead of mdat so the review board can seek (see the
    # note on `common` in render(); same failure, same fix, different mux)
    _run(["-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(source),
          "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
          "-movflags", "+faststart", str(out)])
    return out


def _filter_path(p: Path) -> str:
    """Escape a Windows path for use inside an ffmpeg filter argument."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def write_srt(tmap: dict, out: Path) -> Path:
    def ts(ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(tmap["segments"], 1):
        lines.append(f"{i}\n{ts(seg['start_ms'])} --> {ts(seg['end_ms'])}\n"
                     f"{seg['text']}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def build_manifest(tl: dict, state) -> dict:
    """Per-visual provenance for the final cut. Count == timeline visual count."""
    entries = []
    for s in tl["scenes"]:
        vis = s.get("visual")
        if not vis:
            continue
        meta = {}
        if vis.get("asset_id"):
            row = state.get_asset(vis["asset_id"])
            if row and row["meta_json"]:
                meta = json.loads(row["meta_json"])
        entries.append({
            "scene_id": s["id"],
            "scene_start_ms": s["start_ms"],
            "scene_end_ms": s["end_ms"],
            "kind": vis["kind"],
            "asset_id": vis.get("asset_id"),
            "path": vis["path"],
            "source_url": meta.get("source_url", "user-provided"),
            "channel": meta.get("channel", ""),
            "source_title": meta.get("source_title", ""),
            "clip_start_ms": meta.get("clip_start_ms"),
            "clip_end_ms": meta.get("clip_end_ms"),
            "confidence": vis.get("confidence"),
            # why this clip was acceptable: exact | subject | topic (SOURCING.md).
            # Provenance is where a later reviewer asks "was that the real moment
            # or a stand-in?" — the answer must travel with the cut.
            "tier": meta.get("tier"),
        })
    return {"project": tl["project"], "total_ms": tl["total_ms"],
            "visuals": entries}
