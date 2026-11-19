"""best_start_ms/best_end_ms must actually cut the clip.

The schemas ask for an optional tighter sub-range and used to validate it and
then drop it, so a verdict like "start after the burned-in title card" changed
nothing and the title card shipped in the finished film.
"""
import subprocess

from mixfix.pipeline import _apply_subrange


def _say(report, msg):
    report.append(msg)


def _fake_clip(path, seconds=20):
    from mixfix.tools import FFMPEG
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-f", "lavfi",
         "-i", f"testsrc=size=320x180:rate=15:duration={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True)
    return path


SCENE = {"start_ms": 0, "end_ms": 8000}          # an 8s slot


def test_subrange_is_applied(tmp_path):
    src = _fake_clip(tmp_path / "clip.mp4")
    report = []
    out = _apply_subrange({"best_start_ms": 10600, "best_end_ms": 19600},
                          src, SCENE, report, _say, "scene_017")
    assert out != src, "sub-range was ignored — the clip was not re-cut"
    assert out.exists() and out.stat().st_size > 0
    assert any("sub-range" in r for r in report)


def test_subrange_shorter_than_slot_is_refused(tmp_path):
    """A 3s sub-range cannot fill an 8s slot; cutting it would leave a gap."""
    src = _fake_clip(tmp_path / "clip2.mp4")
    report = []
    out = _apply_subrange({"best_start_ms": 1000, "best_end_ms": 4000},
                          src, SCENE, report, _say, "scene_017")
    assert out == src
    assert any("ignored" in r for r in report)


def test_absent_subrange_is_a_no_op(tmp_path):
    src = _fake_clip(tmp_path / "clip3.mp4")
    report = []
    assert _apply_subrange({"best_start_ms": None, "best_end_ms": None},
                           src, SCENE, report, _say, "s") == src
    assert _apply_subrange({}, src, SCENE, report, _say, "s") == src
    assert report == []
