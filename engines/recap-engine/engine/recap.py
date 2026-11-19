"""Stage: final assembly -> recap.mp4 (+ recap.json).

For each matched, voiced beat we build one self-contained segment:
  1. concat the beat's matched source scene(s), scaled+padded to 16:9,
  2. fit the footage to the narration length:
       - footage >= narration  -> trim to the narration length,
       - footage <  narration   -> hold the last frame for the remainder
         (the matcher already gathers enough footage, so this is the rare tail),
  3. lay the narration on top, with the original scene audio ducked under it
     (config.DUCK_ORIGINAL_DB).
Then all segments are concatenated into the final recap and a recap.json plan +
metadata is written. Per-beat footage and segments are cached on disk.
"""
import json
import math
import subprocess
from pathlib import Path

import config
from engine.utils import die, log, probe_duration, run_ffmpeg


# Scene-start -> order of first appearance in this assemble. Flip is keyed off
# that, so a locked 20s shot does not ping-pong left/right every 3s keep, and
# returning to the same scene later keeps the same orientation.
_SCENE_FLIP_ORDER: dict = {}


def reset_scene_flips() -> None:
    _SCENE_FLIP_ORDER.clear()


def _scene_key(start: float) -> float:
    return round(float(start), 3)


def _scene_should_flip(scene_start: float) -> bool:
    """One hflip orientation per source scene, stable for the whole recap.

    Consecutive *scenes* still alternate (~half the picture mirrored). Pieces
    cut from the same scene all share that scene's orientation.
    """
    key = _scene_key(scene_start)
    if key not in _SCENE_FLIP_ORDER:
        _SCENE_FLIP_ORDER[key] = len(_SCENE_FLIP_ORDER)
    return _SCENE_FLIP_ORDER[key] % 2 == 1


def _piece_scene_start(t: float, scenes: list) -> float:
    """The SOURCE start of the scene that contains t (for a stable flip)."""
    for s in scenes:
        a, b = float(s["start"]), float(s["end"])
        if a - 1e-3 <= float(t) < b + 1e-3:
            return float(s.get("orig_start", a))
    if not scenes:
        return float(t)
    return float(scenes[0].get("orig_start", scenes[0]["start"]))


def assemble(video: Path, beats: list, workdir: Path) -> Path:
    """Build the final recap video from voiced, scene-matched beats."""
    reset_scene_flips()
    # A beat belongs in the cut if it has a length. Most have it because TTS
    # rendered narration; a DIALOGUE BEAT has it because the film plays its own
    # line and carries no `audio` at all - filtering on `audio` alone silently
    # dropped every one of them from the finished recap.
    voiced = [b for b in beats if b.get("audio_seconds")
              and (b.get("audio") or b.get("dialogue"))]
    if not voiced:
        die("recap.assemble: no beats have audio - run TTS first.")

    # Loud guard: silently shipping a shorter recap is the worst failure this
    # stage can have, and it has happened three separate ways while dialogue
    # beats were being added (filtered on `audio`; length lost through
    # edit.json; length left at 0). Any beat that has footage belongs in the
    # cut, so if one is about to be dropped, say so instead of rendering
    # without it.
    dropped = [b["order"] for b in beats
               if b.get("scenes") and b not in voiced]
    if dropped:
        die(f"recap.assemble: {len(dropped)} beat(s) have footage but no "
            f"length and would be dropped from the cut: {dropped}. "
            "Check TTS output / edit.json for those orders.")

    W, H, FPS = config.OUT_WIDTH, config.OUT_HEIGHT, config.OUT_FPS
    seg_dir = workdir / "segments"
    foot_dir = workdir / "footage"
    seg_dir.mkdir(parents=True, exist_ok=True)
    foot_dir.mkdir(parents=True, exist_ok=True)

    flags = []
    if config.MUTE_FILM_AUDIO:
        flags.append("mute")
    if config.DROP_ALTERNATE_SHOTS:
        flags.append(f"keep-every-other-{config.SHOT_SPLIT_SECONDS:g}s")
    if config.FLIP_ALTERNATE_SHOTS:
        flags.append("flip-alternate")
    if config.COPYRIGHT_ZOOM > 1.001:
        flags.append(f"zoom={config.COPYRIGHT_ZOOM:g}")
    if config.COPYRIGHT_GRADE:
        flags.append("grade")
    if flags:
        log("Copyright transform: " + ", ".join(flags) + ".")
    if config.MUTE_FILM_AUDIO and any(b.get("dialogue") for b in voiced):
        log("  MUTE_FILM_AUDIO is on: dialogue beats play silent picture "
            "(film audio would be a Content ID hit).")

    segments = []
    for b in voiced:
        seg = seg_dir / f"seg_{b['order']:03d}.mp4"
        if not seg.exists():
            need = float(b["audio_seconds"])
            footage = foot_dir / f"foot_{b['order']:03d}.mp4"
            if not footage.exists():
                # A dialogue beat plays the film's own line, so its footage must
                # be ONE continuous span - sub-cutting it into shots would chop
                # the sentence the beat exists to let you hear.
                _build_footage(video, b["scenes"], footage, W, H, FPS, need,
                               continuous=bool(b.get("dialogue")))
            if b.get("dialogue"):
                _dialogue_segment(footage, need, seg, FPS)
            else:
                narration = workdir / b["audio"]
                if not narration.exists():
                    die(f"recap.assemble: narration wav missing: {narration}")
                _voice_segment(footage, narration, need, seg, FPS)
        segments.append(seg)

    out = workdir / "recap.mp4"
    _concat(segments, out, seg_dir)

    duration = round(probe_duration(out), 2)
    recap = {
        "output": str(out),
        "width": W, "height": H, "fps": FPS,
        "beats": len(voiced),
        "duration": duration,
        "plan": voiced,
    }
    (workdir / "recap.json").write_text(
        json.dumps(recap, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Recap assembled: {out.name}  "
        f"({duration / 60:.1f} min, {len(voiced)} beats, {W}x{H}).")
    return out


def _final_v_args() -> list:
    """libx264 args for the size-determining (per-beat segment) encode: tuned CRF
    + preset, plus a peak-bitrate CAP (maxrate/bufsize) so busy footage can't
    balloon, and yuv420p for universal playback + concat-copy uniformity."""
    args = ["-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF)]
    if config.VIDEO_MAXRATE:
        args += ["-maxrate", config.VIDEO_MAXRATE,
                 "-bufsize", config.VIDEO_BUFSIZE or config.VIDEO_MAXRATE]
    args += ["-pix_fmt", "yuv420p"]
    return args


def _shot_list(scenes: list, need_seconds: float) -> list:
    """Cut a beat's scene run into SHOTS the way a recap editor would.

    MEASURED 2026-09-03 (scientist/projects/movie-recap-craft-2026): professional
    recaps hold a median shot of 1.5-2.4s and keep under 2% of shots past 8s.
    Playing each beat's scene run as one unbroken span gave us a 5.3s median with
    35% of shots past 8s - the picture sitting still while the narration walked
    through several events.

    So take a SHORT piece of each scene rather than all of it: skip the first
    SHOT_LEAD_SECONDS (a cut point is usually the least interesting frame of a
    shot) and keep at most SHOT_MAX_SECONDS.

    PIECES MUST NOT TOUCH. This is the whole correctness condition, and the
    first version of this function got it wrong. `_build_footage` keeps the
    chosen ranges with a `select` filter, and select can only KEEP frames in
    time order - it cannot reorder them. So two pieces that are adjacent in the
    source play back as one continuous shot, and the cut the piece list promised
    never appears. Measured on The Invisible Man beat 1: 10 pieces of <=2.4s,
    which merged into 3 visible runs of 8.7s, 2.4s and 12.0s. Sub-cutting looked
    like it worked and changed nothing on screen.

    The fix is to SPREAD the pieces: when a beat has more footage available than
    its narration needs, walk each scene in strides and drop the material in
    between, so every kept range is separated by a real gap and every boundary is
    a real cut. When there is barely enough footage the stride collapses to the
    piece length and the behaviour degrades to a continuous run - correct, since
    dropping material there would leave the narration with no picture.
    """
    lead, cap, floor = (config.SHOT_LEAD_SECONDS, config.SHOT_MAX_SECONDS,
                        config.SHOT_MIN_SECONDS)
    spans = []
    for s in scenes:
        start, end = float(s["start"]), float(s["end"])
        cur = start + lead if (end - start) > (lead + floor) else start
        if end - cur >= floor:
            spans.append((cur, end))
    if not spans:
        return [(float(s["start"]), float(s["end"])) for s in scenes]

    available = sum(e - s for s, e in spans)

    def _cut(stride: float) -> list:
        out = []
        for s, e in spans:
            t = s
            while t < e - 0.05:
                piece = (t, min(t + cap, e))
                if piece[1] - piece[0] >= min(floor, e - s):
                    out.append(piece)
                t += stride
        out.sort()
        return out

    # How far to advance between the START of one piece and the start of the
    # next. Sampling `cap` out of every `stride` seconds spends the material the
    # narration needs, spread across everything the beat has.
    #
    # Coverage is the constraint that decides the stride, because a beat whose
    # picture runs short gets its footage LOOPED (see _voice_segment) - and a
    # beat repeating itself is the exact defect this pacing work exists to fix.
    # So start from the ideal spacing and tighten until the beat is covered;
    # cap + 0.25s is the floor, below which pieces would touch and merge.
    ideal = cap * available / need_seconds if need_seconds > 0 else cap
    stride = max(cap + 0.25, ideal)
    pieces = _cut(stride)
    while (sum(b - a for a, b in pieces) < need_seconds
           and stride > cap + 0.25):
        stride = max(cap + 0.25, stride * 0.9)
        pieces = _cut(stride)

    # A beat can simply not have the footage: sampling 2.4s out of every 2.65s
    # spends ~91% of what it has, so a beat needs ~1.1x its narration before it
    # can be sub-cut at all. Below that, hand back the whole span and let the
    # beat play continuously. That is deliberately NOT the same as accepting the
    # shortfall - short footage gets LOOPED by _voice_segment, and a beat that
    # repeats itself is worse to watch than one that holds a longer shot.
    if sum(b - a for a, b in pieces) < need_seconds:
        return spans
    return pieces



def _video_codec(video: Path) -> str:
    """Return the primary video codec name (e.g. h264), or empty on failure."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0",
             str(video)],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or "").strip().lower()


def _annexb_span_input(video: Path, start: float, dur: float, tmp: Path,
                       fps: int) -> list:
    """Stream-copy a source span to annex-B; return ffmpeg input args for it.

    Ready or Not (2026-09-10) and similar feature mp4s carry non-monotonous
    video DTS. Decoding that container with input-seek makes ffmpeg emit one
    held frame for ~5.7s of every ~6s; fps= then freezes the recap. Copying
    the elementary bitstream and reading it at a forced framerate restores
    real motion — same class of fix as extract_audio's stream-copy sidecar
    for this file's audio DTS. Falls back to normal -ss/-t/-i for codecs
    without an mp4-to-annexb bitstream filter.
    """
    codec = _video_codec(video)
    if codec == "h264":
        bsf, fmt = "h264_mp4toannexb", "h264"
    elif codec in ("hevc", "h265"):
        bsf, fmt = "hevc_mp4toannexb", "hevc"
    else:
        return ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video)]
    run_ffmpeg(
        ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
         "-map", "0:v:0", "-c", "copy", "-bsf:v", bsf, "-an",
         "-f", fmt, str(tmp)],
        desc="beat span copy",
    )
    return ["-fflags", "+genpts", "-framerate", str(int(fps)), "-t",
            f"{dur:.3f}", "-i", str(tmp)]


def _copyright_shot_list(scenes: list) -> list:
    """His 3-second rule, then delete every second clip.

    Walk the beat's scenes in order, cut at SHOT_SPLIT_SECONDS (default 3),
    KEEP the first piece, DROP the second, KEEP the third, ... The keep/drop
    toggle carries across scene boundaries so a beat is one 3s grid, not a
    reset per scene (a reset would keep the head of every scene and leak
    continuous film).

    This is the copyright transform, not the pacing `_shot_list`. Do not fall
    back to a continuous span — that is the pattern he said gets flagged.
    """
    split = max(0.4, float(config.SHOT_SPLIT_SECONDS))
    keep_slot = True
    pieces = []
    for s in scenes:
        t, end = float(s["start"]), float(s["end"])
        while t < end - 0.05:
            nxt = min(t + split, end)
            if keep_slot and (nxt - t) >= 0.4:
                pieces.append((t, nxt))
            keep_slot = not keep_slot
            t = nxt
    if not pieces:
        die("recap.assemble: copyright 3s keep/drop produced no shots - "
            "the beat's scenes are too short.")
    return pieces


def _film_bed_volume() -> str:
    """ffmpeg `volume=` expression for the film's audio under the voice.

    Mute MUST be linear `0` (silence). `0dB` is unity gain — the 2026-09-09
    bug that played the film at full level while claiming to mute it.
    """
    if config.MUTE_FILM_AUDIO:
        return "0"
    return f"{int(config.DUCK_ORIGINAL_DB)}dB"


def _picture_vf(W: int, H: int, FPS: int) -> str:
    """Scale/pad (or fill-crop) plus the extra copyright picture layers."""
    if config.FILL_FRAME:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1,fps={FPS}")
    else:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}")
    z = float(config.COPYRIGHT_ZOOM)
    if z > 1.001:
        vf += f",scale=iw*{z:.4f}:ih*{z:.4f},crop={W}:{H}"
    if config.COPYRIGHT_GRADE:
        vf += ",eq=contrast=1.04:brightness=0.015:saturation=1.06"
    return vf


def _select_pieces(video: Path, scenes: list, pieces: list, out: Path,
                   vf: str, enc: list, afmt: str) -> None:
    """Keep `pieces` from the beat's span; one hflip orientation per scene.

    Uses trim+concat, not `select`. On the Invisible Man rebuild, `select` +
    `setpts=N/FRAME_RATE/TB` compacted the picture on the front of the file
    but left the container at the full source duration (audio timebase did
    not drop with the video), so ffmpeg froze the last frame to fill it.
    trim+concat emits only the kept shots; anullsrc is silent film audio.

    Flip is per SOURCE SCENE, not per 3s keep. A 20s locked shot of one person
    must not ping-pong left/right every clip; returning to that scene later
    keeps the same orientation. Consecutive scenes still alternate.
    """
    del afmt  # film audio is not used; silence is generated
    base = float(scenes[0]["start"])
    span = max(0.1, float(scenes[-1]["end"]) - base)
    kept = sum(float(b) - float(a) for a, b in pieces)
    n = len(pieces)
    # One [0:v] pad cannot feed many trims: the first trim consumes the
    # stream. Ready or Not 4K built 5.9s files from 65s spans (~9% keep)
    # and the recap looped. Split first, then trim each copy.
    chains = []
    if n == 1:
        srcs = ["[0:v]"]
    else:
        labels = "".join(f"[s{i}]" for i in range(n))
        chains.append(f"[0:v]split={n}{labels}")
        srcs = [f"[s{i}]" for i in range(n)]
    refs = []
    for i, (a, b) in enumerate(pieces):
        ra, rb = float(a) - base, float(b) - base
        flip = ""
        if config.FLIP_ALTERNATE_SHOTS and _scene_should_flip(
                _piece_scene_start(float(a), scenes)):
            flip = ",hflip"
        chains.append(
            f"{srcs[i]}trim=start={ra:.3f}:end={rb:.3f},setpts=PTS-STARTPTS"
            f"{flip}[v{i}]")
        refs.append(f"[v{i}]")
    chains.append("".join(refs) + f"concat=n={len(pieces)}:v=1:a=0[vc]")
    chains.append(f"[vc]{vf}[vout]")
    run_ffmpeg(
        ["-ss", f"{base:.3f}", "-t", f"{span:.3f}", "-i", str(video),
         "-f", "lavfi", "-t", f"{kept:.3f}",
         "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", ";".join(chains),
         "-map", "[vout]", "-map", "1:a", "-shortest"] + enc + [str(out)],
        desc="beat footage",
    )


def _build_footage(video: Path, scenes: list, out: Path, W: int, H: int,
                   FPS: int, need_seconds: float = 0.0,
                   continuous: bool = False) -> None:
    """Extract the beat's footage, scaled to WxH@FPS, audio 48k stereo.

    Three extract modes:
      - `continuous` (dialogue beats): one span, no 3s chopping (chopping
        would cut the line the beat exists to show). Mute still applies later.
      - DROP_ALTERNATE_SHOTS: his 3s keep/drop, then flip remaining.
      - SHOT_MAX_SECONDS > 0: pacing sub-cut (`_shot_list`).
      - else: one continuous span (shipping default for non-movie recaps).
    """
    if not scenes:
        die("recap.assemble: a beat has no matched scenes.")

    vf = _picture_vf(W, H, FPS)
    enc = ["-c:v", "libx264", "-preset", config.VIDEO_INTERMEDIATE_PRESET,
           "-crf", str(config.VIDEO_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-ar", "48000"]
    afmt = "aformat=sample_rates=48000:channel_layouts=stereo"

    def _span():
        start, dur = float(scenes[0]["start"]), max(
            0.1, float(scenes[-1]["end"]) - float(scenes[0]["start"]))
        use_vf = vf
        if config.FLIP_ALTERNATE_SHOTS and _scene_should_flip(start):
            use_vf = "hflip," + vf
        raw = out.with_suffix(".annexb")
        try:
            in_args = _annexb_span_input(video, start, dur, raw, FPS)
            if config.MUTE_FILM_AUDIO:
                run_ffmpeg(
                    in_args +
                    ["-f", "lavfi", "-t", f"{dur:.3f}",
                     "-i", "anullsrc=r=48000:cl=stereo",
                     "-vf", use_vf, "-map", "0:v", "-map", "1:a", "-shortest"]
                    + enc + [str(out)],
                    desc="beat footage")
            else:
                run_ffmpeg(
                    in_args + ["-vf", use_vf, "-af", afmt] + enc + [str(out)],
                    desc="beat footage")
        finally:
            try:
                raw.unlink()
            except OSError:
                pass

    if continuous:
        _span()
        return
    if config.DROP_ALTERNATE_SHOTS:
        pieces = _copyright_shot_list(scenes)
        # 4K sources cannot feed many trims off one [0:v] pad (Ready or Not
        # kept ~9% and the recap looped). Extract the beat span once to 1080p
        # so keep/drop runs on a file whose timestamps start at 0.
        origin = float(scenes[0]["start"])
        tmp = out.with_name(out.stem + "_span.mp4")
        span_vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}")
        dur = max(0.1, float(scenes[-1]["end"]) - origin)
        venc = ["-c:v", "libx264", "-preset", config.VIDEO_INTERMEDIATE_PRESET,
                "-crf", str(config.VIDEO_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p"]
        raw = out.with_name(out.stem + "_span.annexb")
        try:
            in_args = _annexb_span_input(video, origin, dur, raw, FPS)
            run_ffmpeg(
                in_args + ["-vf", span_vf, "-an"] + venc + [str(tmp)],
                desc="beat span")
            rel_scenes = [{"start": float(s["start"]) - origin,
                           "end": float(s["end"]) - origin,
                           "orig_start": float(s["start"])} for s in scenes]
            rel_pieces = [(float(a) - origin, float(b) - origin)
                          for a, b in pieces]
            _select_pieces(tmp, rel_scenes, rel_pieces, out, vf, enc, afmt)
        finally:
            for p in (raw, tmp):
                try:
                    p.unlink()
                except OSError:
                    pass
        return
    if config.SHOT_MAX_SECONDS <= 0:
        _span()
        return

    _select_pieces(video, scenes, _shot_list(scenes, need_seconds),
                   out, vf, enc, afmt)


def _voice_segment(footage: Path, narration: Path, audio_seconds: float,
                   out: Path, FPS: int) -> None:
    """Fit footage to the narration length and lay the voiceover on top with the
    original audio ducked underneath.

    If the matched footage is shorter than the narration, prefer SLOWING it
    (his rule #5: fit by speed, never freeze or repeat). Looping is only the
    safety net for non-movie recaps; DROP_ALTERNATE_SHOTS never loops, because
    a repeated clip is a repeated fingerprint.
    """
    vol = _film_bed_volume()
    afilt = (f"[0:a]volume={vol},apad[da];"
             f"[da][1:a]amix=inputs=2:duration=longest:dropout_transition=0[mx];"
             f"[mx]volume=2.0[aout]")

    vf_args, loops = _fit_to_narration(footage, audio_seconds)

    # -stream_loop repeats the footage input enough times to cover the narration;
    # it must precede the input it applies to.
    in_args = (["-stream_loop", str(loops)] if loops > 0 else []) + \
              ["-i", str(footage)]

    run_ffmpeg(
        in_args + ["-i", str(narration),
                   "-filter_complex", afilt] +
        (vf_args if vf_args else []) +
        ["-map", "0:v", "-map", "[aout]",
         "-t", f"{audio_seconds:.3f}", "-r", str(FPS)]
        + _final_v_args()
        + ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(out)],
        desc="voice segment",
    )


def _fit_to_narration(footage: Path, audio_seconds: float) -> tuple:
    """Return (vf_args, loops) to make footage last exactly audio_seconds.

    Long footage is trimmed later with -t. Short footage is slowed (setpts)
    when mute is on so the (silent) bed cannot desync. DROP_ALTERNATE_SHOTS
    always slows rather than looping, even above FIT_BY_SPEED_MAX_SLOW.
    """
    fdur = probe_duration(footage)
    if fdur <= 0 or audio_seconds <= fdur + 0.01:
        return [], 0
    stretch = audio_seconds / fdur
    can_retime = config.MUTE_FILM_AUDIO and (
        config.FIT_BY_SPEED or config.DROP_ALTERNATE_SHOTS)
    max_slow = config.FIT_BY_SPEED_MAX_SLOW
    if config.DROP_ALTERNATE_SHOTS:
        max_slow = max(max_slow, 2.0)
    if can_retime and (config.DROP_ALTERNATE_SHOTS or stretch <= max_slow):
        return ["-vf", f"setpts={stretch:.4f}*PTS"], 0
    loops = max(0, math.ceil(audio_seconds / fdur) - 1)
    return [], loops


def _dialogue_segment(footage: Path, seconds: float, out: Path, FPS: int) -> None:
    """A DIALOGUE BEAT: no narrator, the film plays its own line at full level.

    MrRecapFromYouTube (6.1M views, the largest channel measured 2026-09-03) does
    this continuously - the narration sets a moment up, then the film delivers
    the line itself, then narration resumes. It is the single most "movie-like"
    technique in the format, and it is also what gives a recap's mix somewhere to
    breathe (their loudness range is 2.9-3.2 LU against our old 1.3).

    The footage for these beats is the exact dialogue span, so it is used
    straight: no ducking, no voiceover, no looping. MUTE_FILM_AUDIO still
    wins — shipping the film's own line is a Content ID hit.
    """
    vol = _film_bed_volume() if config.MUTE_FILM_AUDIO else (
        f"{int(config.DIALOGUE_BEAT_DB)}dB")
    run_ffmpeg(
        ["-i", str(footage),
         "-af", f"volume={vol},"
                "aformat=sample_rates=48000:channel_layouts=stereo",
         "-t", f"{seconds:.3f}", "-r", str(FPS)]
        + _final_v_args()
        + ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(out)],
        desc="dialogue segment",
    )


def _concat(segments: list, out: Path, seg_dir: Path) -> None:
    """Concatenate beat segments into the final recap. Uses the concat demuxer
    with a cwd + relative-filename list (Windows-safe).

    Segments are all produced by `_voice_segment` with IDENTICAL codec params
    (same WxH, fps, yuv420p, libx264 profile, 48k-stereo AAC), so we STREAM-COPY
    (`-c copy`) instead of re-encoding. That removes a whole redundant encode
    generation (faster, and no extra quality loss), so the final recap's size is
    just the sum of the already-capped segments. `+faststart` moves the moov atom
    to the front for instant web playback; `+genpts` keeps timestamps clean."""
    listfile = seg_dir / "segments.txt"
    listfile.write_text(
        "".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")

    # out must be absolute: cwd is seg_dir, so a relative workdir/recap.mp4
    # would be created under segments/ and fail with 'No such file'.
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-fflags", "+genpts",
         "-i", listfile.name, "-c", "copy",
         "-movflags", "+faststart", str(Path(out).resolve())],
        desc="concat recap",
        cwd=seg_dir,
    )
