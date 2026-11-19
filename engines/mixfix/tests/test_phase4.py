"""Phase 4 tests: QA gate rejects broken renders, SRT output, manifest shape."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mixfix import assemble, qa
from mixfix.state import State

CFG = {"render": {"width": 320, "height": 180, "fps": 10, "target_lufs": -16}}


def _render(path: Path, dur: float = 6.0, silent_from: float | None = None):
    """Tiny test render: animated video + pink-noise 'narration'."""
    af = "volume=0.15,loudnorm=I=-16:TP=-1.5"
    if silent_from is not None:
        af += f",volume=enable='gte(t,{silent_from})':volume=0"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=10:duration={dur}",
         "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={dur}",
         "-af", af, "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "aac", str(path)],
        check=True, capture_output=True)


def _tmap(dur_ms: int) -> dict:
    return {"source": {"duration_ms": dur_ms}, "segments": [
        {"id": "seg_001", "text": "hello there.", "start_ms": 0, "end_ms": dur_ms}]}


def test_qa_passes_good_render(tmp_path):
    v = tmp_path / "good.mp4"
    _render(v)
    report = qa.run_qa(v, _tmap(6000), CFG)
    assert report["passed"], report


def test_qa_rejects_silent_gap(tmp_path):
    v = tmp_path / "broken.mp4"
    _render(v, silent_from=2.0)  # 4s of silence
    report = qa.run_qa(v, _tmap(6000), CFG)
    assert not report["passed"]
    assert not report["checks"]["silence"]["passed"]


def test_qa_rejects_duration_mismatch(tmp_path):
    v = tmp_path / "short.mp4"
    _render(v, dur=4.0)
    report = qa.run_qa(v, _tmap(6000), CFG)
    assert not report["checks"]["duration"]["passed"]


def test_write_srt(tmp_path):
    out = assemble.write_srt(_tmap(6000), tmp_path / "c.srt")
    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:06,000" in text
    assert "hello there." in text


def test_manifest_counts_and_provenance(tmp_path):
    state = State(tmp_path / "t.db")
    state.add_asset("abc", "r1", "research_extract", "clip", "x.mp4",
                    {"source_url": "https://yt/w?v=1", "channel": "chan",
                     "clip_start_ms": 0, "clip_end_ms": 5000})
    tl = {"project": "p", "total_ms": 10000, "scenes": [
        {"id": "s1", "start_ms": 0, "end_ms": 5000,
         "visual": {"asset_id": "abc", "kind": "clip", "path": "x.mp4",
                    "confidence": 90}},
        {"id": "s2", "start_ms": 5000, "end_ms": 10000, "visual": None},
    ]}
    m = assemble.build_manifest(tl, state)
    assert len(m["visuals"]) == 1
    v = m["visuals"][0]
    assert v["source_url"] == "https://yt/w?v=1"
    assert v["channel"] == "chan"
    assert (v["clip_start_ms"], v["clip_end_ms"]) == (0, 5000)


def test_mix_render_transitions_preserve_duration(tmp_path):
    """Crossfaded MIX render must stay sample-accurate to the Timing Map."""
    proj = tmp_path / "proj"
    (proj / "voiceover").mkdir(parents=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anoisesrc=color=pink:duration=9", "-af", "volume=0.1",
         "-c:a", "libmp3lame", str(proj / "voiceover" / "voice.mp3")],
        check=True, capture_output=True)
    clips = []
    for i, src in enumerate(["testsrc2", "smptebars", "testsrc"]):
        c = tmp_path / f"clip{i}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"{src}=size=320x180:rate=10:duration=2.5",
             "-c:v", "libx264", "-preset", "ultrafast", str(c)],
            check=True, capture_output=True)
        clips.append(c)
    tl = {"project": "p", "total_ms": 9000, "scenes": [
        {"id": f"s{i}", "start_ms": i * 3000, "end_ms": i * 3000 + 2500,
         "visual": {"kind": "clip", "path": str(clips[i]), "asset_id": str(i),
                    "trim_in_ms": 0, "trim_out_ms": 2000}}
        for i in range(3)]}
    tmap = {"source": {"duration_ms": 9000},
            "segments": [{"id": "seg_001", "text": "x.",
                          "start_ms": 0, "end_ms": 9000}]}
    cfg = {"render": {"width": 320, "height": 180, "fps": 10,
                      "transition_s": 0.5}}
    out = assemble.render(proj, tl, tmap, cfg)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True)
    assert abs(float(probe.stdout) * 1000 - 9000) <= 300


def test_engine_does_not_render_with_the_imagemagick_ffmpeg():
    """The first ffmpeg on PATH here is ImageMagick's 4.2.3 (2020), and it
    resolves concat entries against the CWD while a current build resolves them
    against the concat file — so renders passed or failed depending on the
    process's working directory, invisibly. Pin the binary.

    Also: no module may call bare "ffmpeg"/"ffprobe" again, or it silently
    reintroduces the 2020 build for that one call.
    """
    import subprocess
    from pathlib import Path

    from mixfix.tools import FFMPEG, FFPROBE

    for exe in (FFMPEG, FFPROBE):
        ver = subprocess.run([exe, "-version"], capture_output=True,
                             text=True).stdout.split()[2]
        major = int(ver.split(".")[0])
        assert major >= 5, f"{exe} is {ver}; concat resolution differs before 5.x"

    root = Path(__file__).resolve().parents[1]
    for pkg in ("mixfix", "split"):
        for f in (root / pkg).rglob("*.py"):
            if f.name == "tools.py":
                continue
            src = f.read_text(encoding="utf-8")
            for bare in ('["ffmpeg"', '["ffprobe"'):
                assert bare not in src, f"{f.name} calls {bare} directly"


def test_usable_rejects_and_removes_a_truncated_segment(tmp_path):
    """A render killed mid-write leaves a truncated mp4 at the FINAL path.

    The segment cache used to skip anything that merely existed, so that file
    was reused forever and every later run died on `moov atom not found`. The
    real case was 7.8 MB — not empty — so a size check does not catch it.
    """
    from mixfix.assemble import _usable

    truncated = tmp_path / "base_000_deadbeef.mp4"
    truncated.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\xff" * 4096)
    assert _usable(truncated) is False
    assert not truncated.exists(), "a bad segment must be removed, not just skipped"

    assert _usable(tmp_path / "never_written.mp4") is False
    empty = tmp_path / "empty.mp4"
    empty.touch()
    assert _usable(empty) is False
