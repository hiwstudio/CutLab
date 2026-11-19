"""Smoke tests for the pure-logic core (no network, no ffmpeg).
Run: python -m pytest tests/ -q   (or just: python tests/test_smoke.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clipinn import config, timing, visual
from clipinn.moments import (attach_text, candidate_windows, ends_sentence,
                             finalize, nms, starts_sentence, thin_candidates,
                             weighted_score)
from clipinn.subtitles import build_ass


def _tm(n=20, seg_s=5):
    segs = [{"id": f"seg_{i+1:04d}", "text": f"sentence {i} " * 5,
             "start_ms": i * seg_s * 1000, "end_ms": (i + 1) * seg_s * 1000}
            for i in range(n)]
    return {"version": "1.0",
            "source": {"duration_ms": n * seg_s * 1000},
            "segments": segs, "meta": {}}


def test_timing_validate():
    assert timing.validate(_tm()) == []
    bad = _tm()
    bad["segments"][0]["end_ms"] = 0
    assert timing.validate(bad)


def test_candidates_fit_band():
    # 240 segments x 5s = 20 min, enough to reach the 180s ceiling
    tm = _tm(n=240, seg_s=5)
    cands = candidate_windows(tm)
    assert cands, "should find candidate windows"
    for c in cands:
        assert config.MIN_CLIP_SECONDS <= c["duration_s"] <= config.MAX_CLIP_SECONDS
        assert c["start_ms"] % 5000 == 0 and c["end_ms"] % 5000 == 0  # snapped


def test_candidates_offer_multiple_lengths():
    """The same starting moment must be offered at several lengths, or the
    engine can never choose a long treatment over a short one."""
    tm = _tm(n=240, seg_s=5)
    cands = candidate_windows(tm)
    by_start = {}
    for c in cands:
        by_start.setdefault(c["start_ms"], []).append(c["duration_s"])
    first = by_start[0]
    assert len(first) >= 3, f"expected several lengths per start, got {first}"
    assert max(first) >= 120, f"long options missing: {first}"
    assert min(first) <= 45, f"short options missing: {first}"


def test_thinning_keeps_spread_and_lengths():
    tm = _tm(n=400, seg_s=5)
    cands = candidate_windows(tm)
    kept = thin_candidates(cands, max_n=60)
    assert len(kept) <= 60
    starts = sorted({c["start_ms"] for c in kept})
    assert len(starts) >= 5, "should keep several distinct positions"
    # spread across the video, not clustered at the beginning
    assert max(starts) > 0.5 * max(c["start_ms"] for c in cands)
    # text is only attached after thinning (memory guard)
    assert all("text" not in c for c in kept)
    attach_text(kept, tm)
    assert all(c.get("text") and c.get("candidate_id") for c in kept)


def test_candidate_id_stable_for_window():
    """Ids must derive from the window, not list position — segment files and
    visual frames are cached under them."""
    tm = _tm(n=240, seg_s=5)
    a = attach_text(thin_candidates(candidate_windows(tm), max_n=30), tm)
    b = attach_text(thin_candidates(candidate_windows(tm), max_n=30), tm)
    ids_a = {(c["start_ms"], c["end_ms"]): c["candidate_id"] for c in a}
    for c in b:
        assert ids_a[(c["start_ms"], c["end_ms"])] == c["candidate_id"]


def test_config_validate_catches_bad_ranges():
    lo, hi = config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS
    try:
        config.validate()          # current settings must be valid
        config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS = 120, 60
        raised = False
        try:
            config.validate()
        except ValueError:
            raised = True
        assert raised, "min > max must be rejected"
    finally:
        config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS = lo, hi


def test_scoring_and_nms():
    subs = {k: 8 for k in config.RUBRIC_WEIGHTS}
    assert weighted_score(subs) == 8.0
    a = {"start_ms": 0, "end_ms": 30000, "score": 9.0}
    b = {"start_ms": 5000, "end_ms": 30000, "score": 8.0}   # >50% overlap
    c = {"start_ms": 60000, "end_ms": 90000, "score": 7.0}
    kept = nms([a, b, c])
    assert a in kept and c in kept and b not in kept


def test_finalize_filters_and_orders():
    subs_hi = {k: 9 for k in config.RUBRIC_WEIGHTS}
    subs_lo = {k: 2 for k in config.RUBRIC_WEIGHTS}
    clips = [
        {"start_ms": 60000, "end_ms": 90000, "score": 9.0, "subscores": subs_hi},
        {"start_ms": 0, "end_ms": 30000, "score": 9.0, "subscores": subs_hi},
        {"start_ms": 120000, "end_ms": 150000, "score": 2.0, "subscores": subs_lo},
        {"start_ms": 200000, "end_ms": 230000, "score": 9.0,
         "subscores": subs_hi, "disqualified": True},
    ]
    out = finalize(clips)
    assert [c["start_ms"] for c in out] == [0, 60000]      # chronological, filtered
    assert out[0]["clip_id"] == "clip_01"


def test_prompts_build():
    """Prompts contain literal JSON braces — building them must not treat
    those as format fields (regression: RUBRIC_PROMPT.format KeyError)."""
    from clipinn.moments import RUBRIC_PROMPT
    from clipinn.visual import VISION_PROMPT
    built = (RUBRIC_PROMPT.replace("{lo}", str(config.MIN_CLIP_SECONDS))
                          .replace("{hi}", str(config.MAX_CLIP_SECONDS)))
    assert "{lo}" not in built and "{hi}" not in built
    assert '"subscores"' in built and '"subscores"' in VISION_PROMPT


def test_ytdlp_command_shape():
    """Guards the download contract that took a whole session to pin down.
    See lessons/ytdlp-download-port-2026-07.md before relaxing any of this."""
    import subprocess
    from clipinn import youtube

    captured = {}

    class FakeProc:
        stdout, returncode, stderr = "", 0, ""

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    real_run = subprocess.run
    subprocess.run = fake_run
    try:
        youtube._ytdlp(["https://example.com/x", "--dump-json"])
    finally:
        subprocess.run = real_run

    cmd = captured["cmd"]
    joined = " ".join(cmd)
    # ffmpeg 8 can't resolve googlevideo CDN hosts here -> audio-only + exit 0
    assert "--ffmpeg-location" not in cmd, "must not pin ffmpeg for yt-dlp"
    # android/ios clients + missing_pot admit SABR/broken streams
    assert "--extractor-args" not in cmd, "must not force player clients"
    # one cookie source, never a ladder
    assert joined.count("--cookies-from-browser") <= 1
    # a dropped fragment must be retried in place, not surface as audio-only
    assert "--fragment-retries" in cmd
    assert "--impersonate" not in cmd, "YouTube/generic URLs must not impersonate"

    captured.clear()
    subprocess.run = fake_run
    try:
        youtube._ytdlp(["https://www.tiktok.com/@x/video/1", "--dump-json"])
    finally:
        subprocess.run = real_run
    tt = captured["cmd"]
    assert "--impersonate" in tt and "chrome" in tt
    assert "--cookies-from-browser" not in tt and "--cookies" not in tt
    assert "--ffmpeg-location" not in tt and "--extractor-args" not in tt


def test_section_format_selector():
    """Every rung keeps a height constraint (so none can resolve to
    audio-only) and prefers H.264 (AV1 breaks deep --download-sections)."""
    from clipinn.youtube import _SECTION_FORMAT
    rungs = _SECTION_FORMAT.format(R=720).split("/")
    assert all("height<=720" in r for r in rungs), rungs
    assert "vcodec^=avc1" in rungs[0]
    assert not any(r.strip() == "b" for r in rungs), "bare /b can be audio-only"


def test_visual_grace():
    """Flagged-but-unreviewed clips survive slightly below the bar; once
    reviewed, the standard bar applies again."""
    subs = {k: 6 for k in config.RUBRIC_WEIGHTS}
    base = {"start_ms": 0, "end_ms": 30000, "subscores": subs,
            "score": config.MIN_SCORE - 0.5}
    assert finalize([dict(base)]) == []                          # below bar
    assert len(finalize([dict(base, needs_visual=True)])) == 1   # grace
    assert finalize([dict(base, needs_visual=True,
                          visual_reviewed=True)]) == []          # reviewed


def test_ass_placement_zones(tmp_path):
    config.CAPTION_POSITION, config.SUBTITLE_POSITION = "top", "bottom"
    tm = {"words": [{"text": "hello", "start_ms": 0, "end_ms": 400},
                    {"text": "world", "start_ms": 500, "end_ms": 900}]}
    out = build_ass(tm, "My hook", 10.0, tmp_path / "t.ass")
    text = out.read_text(encoding="utf-8")
    assert "My hook" in text and "hello" in text
    assert f",{int(config.OUT_HEIGHT * 0.83)})" in text     # subs in bottom zone
    config.CAPTION_POSITION = config.SUBTITLE_POSITION = None


def test_blur_geometry():
    """Landscape gets the 25/50/25 band; portrait stays fitted (not cropped)."""
    from clipinn import styles
    orig = styles.probe_size
    try:
        styles.probe_size = lambda p: (1920, 1080)          # landscape 16:9
        top, fg = styles._blur_geometry(Path("x"))
        assert top == 480 and config.OUT_HEIGHT - 2 * top == 960
        assert "force_original_aspect_ratio=increase" in fg and "crop=1080:960" in fg

        styles.probe_size = lambda p: (1080, 1920)          # portrait 9:16
        top, fg = styles._blur_geometry(Path("x"))
        assert fg == "[fg]scale=1080:-2[fgs];"              # fitted, never cropped
        assert top == 0

        styles.probe_size = lambda p: (_ for _ in ()).throw(RuntimeError())
        top, fg = styles._blur_geometry(Path("x"))          # unprobeable -> landscape
        assert top == 480
    finally:
        styles.probe_size = orig


def test_windows_never_cut_mid_sentence():
    """Auto-caption segments break on timing, not syntax — windows must still
    open and close on a finished sentence (or a '>>' speaker turn)."""
    texts = ["Hey, bro.", ">> Party is officially", "locked. It is locked.",
             "I don't know. There's a bit too", "much to elaborate on.",
             ">> What's the smoking fee?", "It was in the playoffs.",
             "I crossed over and went right", "down. That was it."]
    segs = [{"id": f"seg_{i+1:04d}", "text": t,
             "start_ms": i * 10000, "end_ms": (i + 1) * 10000}
            for i, t in enumerate(texts * 6)]
    tm = {"version": "1.0", "source": {"duration_ms": len(segs) * 10000},
          "segments": segs, "meta": {}}
    by_start = {s["start_ms"]: i for i, s in enumerate(segs)}
    by_end = {s["end_ms"]: i for i, s in enumerate(segs)}
    cands = candidate_windows(tm)
    assert cands, "sentence-aligned windows should still be found"
    for c in cands:
        assert starts_sentence(segs, by_start[c["start_ms"]]), \
            f"window opens mid-sentence at {c['start_ms']}"
        assert ends_sentence(segs, by_end[c["end_ms"]]), \
            f"window closes mid-sentence at {c['end_ms']}"
    # the fragment continuation "much to elaborate on." must never be an open
    bad = segs[by_start[40000]]
    assert not starts_sentence(segs, by_start[bad["start_ms"]])


def test_unpunctuated_transcript_falls_back():
    """Whisper on a noisy source can emit no punctuation at all; the strict
    rule would return nothing, so raw segment boundaries must take over."""
    tm = _tm(n=240, seg_s=5)                    # _tm text has no terminal '.'
    assert not any(ends_sentence(tm["segments"], j)
                   for j in range(len(tm["segments"])))
    assert candidate_windows(tm), "must fall back rather than return empty"


def test_visual_backfills_transcript_from_select_task(tmp_path):
    """A clip reloaded from an operator-written moments.json has no text; the
    review must not go out blind."""
    import json as _json
    (tmp_path / "select_task.json").write_text(_json.dumps({
        "candidates": [{"candidate_id": "cand_1_2", "text": "the transcript"}]}),
        encoding="utf-8")
    flagged = [{"clip_id": "clip_01", "candidate_id": "cand_1_2"}]
    visual._backfill_text(flagged, tmp_path)
    assert flagged[0]["text"] == "the transcript"


def test_audio_gap_detected(tmp_path):
    """A section whose sound stops early must be caught, a whole one must not.
    Needs ffmpeg (the one exception here): the check IS an ffprobe reading."""
    import subprocess
    from clipinn.utils import FFMPEG, MAX_AUDIO_GAP_S, audio_gap_s, media_covers

    def make(name, audio_s):
        out = tmp_path / name
        subprocess.run([FFMPEG, "-v", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=64x64:d=5",
                        "-f", "lavfi", "-i", f"sine=d={audio_s}",
                        "-c:v", "libx264", "-c:a", "aac", str(out)], check=True)
        return out

    whole = make("whole.mp4", 5)
    assert audio_gap_s(whole) <= MAX_AUDIO_GAP_S
    assert media_covers(whole, 4800, require_audio=True)
    assert not media_covers(whole, 7000, require_audio=True)
    assert audio_gap_s(make("cut.mp4", 2)) > MAX_AUDIO_GAP_S


def test_cookie_choice_prefers_live_browser(tmp_path, monkeypatch):
    from clipinn import config, youtube
    cookiefile = tmp_path / "cookies.txt"
    cookiefile.write_text("stale export", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "YT_BROWSER", "firefox")
    assert youtube._cookie_args() == ["--cookies-from-browser", "firefox"]
    monkeypatch.setattr(config, "YT_BROWSER", "")
    assert youtube._cookie_args() == ["--cookies", str(cookiefile)]


if __name__ == "__main__":
    import tempfile
    test_timing_validate()
    test_candidates_fit_band()
    test_candidates_offer_multiple_lengths()
    test_thinning_keeps_spread_and_lengths()
    test_candidate_id_stable_for_window()
    test_config_validate_catches_bad_ranges()
    test_scoring_and_nms()
    test_finalize_filters_and_orders()
    test_prompts_build()
    test_ytdlp_command_shape()
    test_section_format_selector()
    test_visual_grace()
    test_ass_placement_zones(Path(tempfile.mkdtemp()))
    test_blur_geometry()
    test_windows_never_cut_mid_sentence()
    test_unpunctuated_transcript_falls_back()
    test_visual_backfills_transcript_from_select_task(Path(tempfile.mkdtemp()))
    test_audio_gap_detected(Path(tempfile.mkdtemp()))
    print("all smoke tests passed")
