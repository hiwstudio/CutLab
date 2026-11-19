"""Visual treatments for the `movierecap` profile — break up the picture.

WHY THIS EXISTS. A recap assembled the default way shows the film and nothing
else: every second of the picture track is source footage, and a beat's run can
hold one unbroken lift for over a minute. That is repetitive to watch, and it is
the shape that gets a video blocked. This pass keeps the finished audio exactly
as it is and rebuilds parts of the PICTURE.

Five treatments, cycled so no one device repeats:

    insert      2-5s of silent footage from ELSEWHERE IN THE SAME SCENE
    crop        the same moment, punched in tight on the subject
    still       a frozen frame, held, with an optional slow push
    motion      a still with a real Ken Burns move across it
    typography  a line of text over the picture

AUDIO IS NEVER TOUCHED. Every treatment is a video overlay on the finished
recap and the final mux copies the audio stream, so narration, ducked source
audio and their timing come through bit-identical.

TWO STAGES, because the middle one needs judgement:

    plan(project)      -> treatments.json   (proposed, editable)
    apply(project)     -> recap_treated.mp4 (renders whatever the file says)

The planner picks slots and candidate footage mechanically. It CANNOT know
whether a cutaway reads as the same moment or whether a line of text earns its
place, so `typography` slots ship with an empty `text` and are skipped until an
operator writes one. Edit treatments.json freely between the two stages; the
renderer treats it as the source of truth.

Definition of "the same scene": the insert is drawn from a dialogue-free scene
card inside TREAT_SCENE_WINDOW seconds of the footage the beat is already
showing, and never from material that beat already used. Detected scenes are
camera shots, not dramatic scenes, so proximity in time is the honest proxy for
"same place, same moment" - and the window is deliberately tight, because a
cutaway from another location is a continuity error, not a treatment.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import config
from engine.utils import die, log, run_ffmpeg


# ---------- timeline ----------
def _timeline(plan: list) -> list:
    """Where each beat lands in the FINISHED recap.

    Beats are concatenated in order, so a beat's output position is the sum of
    the durations before it. A voiced beat runs for its narration; a dialogue
    beat carries the film's own audio and stores `seconds` instead.
    """
    out, t = [], 0.0
    for b in plan:
        dur = float(b.get("audio_seconds") or b.get("seconds") or 0.0)
        if dur <= 0:
            continue
        scenes = b.get("scenes") or []
        if scenes:
            out.append({
                "order": b.get("order"),
                "out_start": t,
                "out_end": t + dur,
                "src_start": float(scenes[0]["start"]),
                "src_end": float(scenes[-1]["end"]),
                "narration": b.get("narration", ""),
            })
        t += dur
    return out


def _beat_at(timeline: list, t: float) -> dict | None:
    for b in timeline:
        if b["out_start"] <= t < b["out_end"]:
            return b
    return None


# ---------- candidate footage ----------
def _silent_candidates(cards: list, beat: dict) -> list:
    """Dialogue-free shots near this beat's footage, NEAREST first.

    Excludes anything overlapping what the beat already shows - the point of an
    insert is that the viewer has not just seen it.

    Ranked by distance from the beat's own footage, not by length. Ranking by
    length looked sensible and was wrong: on the first real plan it answered a
    beat at 95-149s with a shot from 35s, which is a different scene of the film
    entirely. The whole premise of the treatment is that the cutaway belongs to
    the moment on screen, so proximity is the only ordering that serves it; a
    shot merely needs to clear TREAT_MIN_SECONDS to be long enough.
    """
    win = config.TREAT_SCENE_WINDOW
    lo, hi = beat["src_start"] - win, beat["src_end"] + win
    out = []
    for c in cards:
        if c.get("has_dialogue"):
            continue
        s, e = float(c["start"]), float(c["end"])
        if e < lo or s > hi:
            continue
        if s < beat["src_end"] and e > beat["src_start"]:
            continue                      # already on screen in this beat
        if e - s < config.TREAT_MIN_SECONDS:
            continue
        out.append((s, e))

    def _gap(p: tuple) -> float:
        """Seconds between this shot and the footage the beat is showing."""
        return max(beat["src_start"] - p[1], p[0] - beat["src_end"], 0.0)

    out.sort(key=_gap)
    return [p for p in out if _gap(p) <= config.TREAT_MAX_GAP]


# ---------- planning ----------
def plan(project: Path) -> Path:
    """Propose one treatment every TREAT_EVERY_SECONDS. Writes treatments.json."""
    recap = json.loads((project / "recap.json").read_text(encoding="utf-8"))
    cards = json.loads((project / "scene_cards.json").read_text(encoding="utf-8"))
    timeline = _timeline(recap["plan"])
    if not timeline:
        die("treatments.plan: recap.json has no beats with durations.")

    total = float(recap.get("duration") or timeline[-1]["out_end"])
    cycle = [k.strip() for k in config.TREAT_CYCLE.split(",") if k.strip()]
    used: list[tuple[float, float]] = []
    items, i = [], 0

    t = config.TREAT_EVERY_SECONDS
    while t < total - config.TREAT_MAX_SECONDS:
        beat = _beat_at(timeline, t)
        if not beat:
            t += config.TREAT_EVERY_SECONDS
            continue
        kind = cycle[i % len(cycle)]
        i += 1
        # Never start a treatment in the last second of a beat: it would run
        # past the cut and land on footage from somewhere else entirely.
        at = min(t, beat["out_end"] - config.TREAT_MIN_SECONDS - 0.1)
        if at <= beat["out_start"]:
            t += config.TREAT_EVERY_SECONDS
            continue

        item = {"at": round(at, 3), "kind": kind, "beat": beat["order"]}

        if kind in ("insert", "still", "motion"):
            cands = [c for c in _silent_candidates(cards, beat)
                     if not any(c[0] < u[1] and c[1] > u[0] for u in used)]
            if not cands:
                t += config.TREAT_EVERY_SECONDS
                continue
            s, e = cands[0]
            used.append((s, e))
            # Take the END OF THE SHOT THAT TOUCHES THE BEAT, not always its
            # head. A shot can run 50s and still qualify on proximity because
            # its tail sits next to the beat - taking the head then lands the
            # cutaway a minute away in a different scene, which is exactly the
            # error the proximity ranking was meant to prevent.
            before = e <= beat["src_start"]
            if kind == "insert":
                dur = min(config.TREAT_MAX_SECONDS, e - s)
                src = (e - dur - 0.1) if before else (s + 0.2)
                item |= {"src": round(max(s, src), 3), "seconds": round(dur, 3)}
            else:                                  # a still is one frame from it
                item |= {"src": round(e - 0.5 if before else s + 0.5, 3),
                         "seconds": round(config.TREAT_MIN_SECONDS + 0.5, 3)}
        elif kind == "crop":
            # The same moment the viewer is already watching, punched in. Source
            # time is derived from how far into the beat we are.
            frac = (at - beat["out_start"]) / max(0.1, beat["out_end"] - beat["out_start"])
            src = beat["src_start"] + frac * (beat["src_end"] - beat["src_start"])
            item |= {"src": round(src, 3),
                     "seconds": round(config.TREAT_MAX_SECONDS - 1, 3),
                     "zoom": config.TREAT_CROP_ZOOM}
        elif kind == "typography":
            # Left for the operator: the engine cannot tell which words deserve
            # the screen. Empty text = skipped at render.
            item |= {"seconds": round(config.TREAT_MIN_SECONDS, 3), "text": "",
                     "hint": beat["narration"][:120]}
        else:
            die(f"treatments.plan: unknown kind {kind!r} in TREAT_CYCLE")

        items.append(item)
        t += config.TREAT_EVERY_SECONDS

    out = project / "treatments.json"
    out.write_text(json.dumps(
        {"recap": recap["output"], "duration": total, "profile": "movierecap",
         "items": items}, indent=1), encoding="utf-8")
    kinds = {k: sum(1 for x in items if x["kind"] == k) for k in cycle}
    log(f"planned {len(items)} treatments over {total / 60:.1f} min: {kinds}")
    log(f"  -> {out}   (edit it, then run --treat-apply; typography needs text)")
    return out


# ---------- rendering ----------
def _clip(video: Path, item: dict, out: Path, W: int, H: int, FPS: int) -> None:
    """Render one treatment to a silent WxH clip."""
    kind, dur = item["kind"], float(item["seconds"])
    if kind == "crop":
        z = float(item.get("zoom", config.TREAT_CROP_ZOOM))
        # Scale UP then centre-crop back to frame: a punch-in, not a letterbox.
        vf = (f"scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1,fps={FPS}")
        run_ffmpeg(["-ss", f"{item['src']:.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                    "-an", "-vf", vf, "-c:v", "libx264", "-preset",
                    config.VIDEO_INTERMEDIATE_PRESET, "-crf",
                    str(config.VIDEO_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
                    str(out)], desc=f"treat {kind}")
        return

    if kind == "insert":
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}")
        run_ffmpeg(["-ss", f"{item['src']:.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                    "-an", "-vf", vf, "-c:v", "libx264", "-preset",
                    config.VIDEO_INTERMEDIATE_PRESET, "-crf",
                    str(config.VIDEO_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
                    str(out)], desc=f"treat {kind}")
        return

    if kind in ("still", "motion"):
        frames = max(1, int(round(dur * FPS)))
        push = config.TREAT_STILL_PUSH if kind == "still" else max(
            0.18, config.TREAT_STILL_PUSH * 2)
        # zoompan works on the scaled-up frame so the push has pixels to eat.
        big = f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2}"
        zp = (f"zoompan=z='1+{push}*on/{frames}':d={frames}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
        run_ffmpeg(["-ss", f"{item['src']:.3f}", "-i", str(video), "-frames:v", "1",
                    "-an", "-vf", f"{big},{zp},setsar=1", "-c:v", "libx264",
                    "-preset", config.VIDEO_INTERMEDIATE_PRESET, "-crf",
                    str(config.VIDEO_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
                    str(out)], desc=f"treat {kind}")
        return

    die(f"treatments._clip: cannot render kind {kind!r}")


def _write_text(work: Path, n: int, text: str) -> str:
    """Put typography in a sidecar file and return the filename to reference.

    Never inline the string into the filtergraph. ffmpeg's filter syntax cannot
    express an apostrophe inside a quoted value at all - backslash-escaping it
    is not a fix, the quote simply ends - so `text='It\\'s 3\\:00'` failed the
    whole graph with "Error initializing complex filters". `textfile=` sidesteps
    every escaping rule, and per this project's CLAUDE.md the call runs with
    cwd set to the file's folder so a bare filename avoids Windows drive-colon
    escaping too.
    """
    f = work / f"txt_{n:03d}.txt"
    f.write_text(text, encoding="utf-8")
    return f.name


def apply(project: Path, video: Path) -> Path:
    """Render treatments.json onto the finished recap. Audio is stream-copied."""
    spec = json.loads((project / "treatments.json").read_text(encoding="utf-8"))
    recap = Path(spec["recap"])
    if not recap.exists():
        die(f"treatments.apply: {recap} is missing — assemble first.")
    W, H, FPS = config.OUT_WIDTH, config.OUT_HEIGHT, config.OUT_FPS

    overlays = [i for i in spec["items"] if i["kind"] != "typography"]
    texts = [i for i in spec["items"] if i["kind"] == "typography" and i.get("text")]
    skipped = sum(1 for i in spec["items"]
                  if i["kind"] == "typography" and not i.get("text"))
    if skipped:
        log(f"{skipped} typography slots have no text — skipping them.")
    if not overlays and not texts:
        die("treatments.apply: nothing to render (empty or unedited treatments.json).")

    work = project / "treat"
    work.mkdir(exist_ok=True)
    clips = []
    for n, item in enumerate(overlays):
        c = work / f"t{n:03d}.mp4"
        if not c.exists():                      # cached: a rerun resumes
            _clip(video, item, c, W, H, FPS)
        clips.append((c, item))

    # ONE pass: chain an overlay per clip, each shifted to its moment and
    # enabled only across its window, then draw any text on top.
    inputs, chain, cur = ["-i", str(recap)], [], "[0:v]"
    for n, (c, item) in enumerate(clips):
        inputs += ["-i", str(c)]
        at, dur = float(item["at"]), float(item["seconds"])
        chain.append(f"[{n + 1}:v]setpts=PTS-STARTPTS+{at}/TB[t{n}]")
        chain.append(f"{cur}[t{n}]overlay=0:0:enable='between(t,{at},{at + dur})'[v{n}]")
        cur = f"[v{n}]"
    for n, item in enumerate(texts):
        at, dur = float(item["at"]), float(item["seconds"])
        font = (f"fontfile='{Path(config.TREAT_FONT).name}':"
                if config.TREAT_FONT else "")
        chain.append(
            f"{cur}drawtext={font}textfile={_write_text(work, n, item['text'])}:"
            f"fontsize={config.TREAT_FONT_SIZE}:fontcolor=white:borderw=6:"
            f"bordercolor=black@0.9:x=(w-text_w)/2:y=h*0.78:"
            f"enable='between(t,{at},{at + dur})'[x{n}]")
        cur = f"[x{n}]"
    if texts and config.TREAT_FONT:
        # The graph names the font by filename, so it has to sit beside the text.
        f = Path(config.TREAT_FONT)
        if f.is_file() and not (work / f.name).exists():
            (work / f.name).write_bytes(f.read_bytes())

    out = recap.with_name(recap.stem + "_treated.mp4")
    run_ffmpeg(inputs + ["-filter_complex", ";".join(chain), "-map", cur,
                         "-map", "0:a?", "-c:a", "copy"] + _v_args() +
               ["-movflags", "+faststart", str(out)], desc="apply treatments",
               cwd=work)
    log(f"treated recap -> {out}  ({len(clips)} overlays, {len(texts)} text)")
    return out


def _v_args() -> list:
    return ["-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p"]


# ---------- self-check ----------
def selftest() -> None:
    """No source video, no network. Proves the planning logic, not the pixels."""
    beats = [{"order": 0, "audio_seconds": 40.0,
              "scenes": [{"start": 100.0, "end": 130.0}], "narration": "a"},
             {"order": 1, "audio_seconds": 40.0,
              "scenes": [{"start": 200.0, "end": 240.0}], "narration": "b"}]
    tl = _timeline(beats)
    assert [b["out_start"] for b in tl] == [0.0, 40.0], tl
    assert _beat_at(tl, 45.0)["order"] == 1
    assert _beat_at(tl, 1000.0) is None

    cards = [
        {"start": 90.0, "end": 96.0, "has_dialogue": False},    # near, silent
        {"start": 110.0, "end": 118.0, "has_dialogue": False},  # OVERLAPS beat 0
        {"start": 140.0, "end": 146.0, "has_dialogue": True},   # talking
        {"start": 133.0, "end": 139.0, "has_dialogue": False},  # near, silent
        {"start": 900.0, "end": 910.0, "has_dialogue": False},  # far away
    ]
    got = _silent_candidates(cards, tl[0])
    assert (110.0, 118.0) not in got, "an insert must not repeat on-screen footage"
    assert (140.0, 146.0) not in got, "an insert must be dialogue-free"
    assert (900.0, 910.0) not in got, "an insert must stay inside the scene window"
    assert set(got) == {(90.0, 96.0), (133.0, 139.0)}, got
    # Nearest first, not longest first: beat 0 shows 100-130, so the shot ending
    # at 96 (4s away) must outrank the one starting at 133 (3s away)... which is
    # in fact nearer, and that is the point - ordering follows the gap.
    assert got[0] == (133.0, 139.0), f"candidates must be ranked by proximity: {got}"
    far = [{"start": 300.0, "end": 320.0, "has_dialogue": False}]   # 170s away
    assert _silent_candidates(far, tl[0]) == [], "a far cutaway must be dropped, not used"

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        name = _write_text(Path(d), 0, "It's 3:00")
        assert (Path(d) / name).read_text(encoding="utf-8") == "It's 3:00"
    print("treatments selftest ok")


if __name__ == "__main__":
    selftest()
