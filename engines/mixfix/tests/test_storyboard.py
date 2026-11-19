"""Storyboard tile mapping — the pure math behind the download-free visual gate."""
import pytest

from mixfix.research import _tile_at, _storyboard_sheets


def test_tile_at_walks_partial_last_sheet():
    # 5 full 5x5 sheets + a partial 3-tile sheet = 128 tiles (a real sb0 shape)
    counts = [25, 25, 25, 25, 25, 3]
    dur = 631.0
    # start of video -> first sheet, first cell
    assert _tile_at(0.0, dur, counts) == (0, 0)
    # a mid window (~257s of 631s) lands in sheet 2, as measured on the spy-cat clip
    assert _tile_at(257.0, dur, counts)[0] == 2
    # the very end clamps into the partial last sheet, never past it
    s, cell = _tile_at(dur, dur, counts)
    assert s == 5 and cell < counts[5]
    # every timestamp across the video resolves to a real cell
    for t in range(0, int(dur), 7):
        s, cell = _tile_at(float(t), dur, counts)
        assert 0 <= s < len(counts) and 0 <= cell < counts[s]


def test_storyboard_sheets_parses_mhtml_images():
    import email.mime.multipart, email.mime.image
    m = email.mime.multipart.MIMEMultipart("related")
    for payload in (b"\xff\xd8sheetA", b"\xff\xd8sheetB"):
        part = email.mime.image.MIMEImage(payload, _subtype="jpeg")
        m.attach(part)
    # a non-image part must be ignored
    from email.mime.text import MIMEText
    m.attach(MIMEText("<html>layout</html>", "html"))
    sheets = _storyboard_sheets(m.as_bytes())
    assert len(sheets) == 2
    assert all(s.startswith(b"\xff\xd8") for s in sheets)


def test_a_chunk_retries_and_keeps_what_already_landed(tmp_path, monkeypatch):
    """Throttling is intermittent: the same request that times out often lands
    minutes later. So one bad chunk must not discard a window that is already
    half fetched — completed chunks stay on disk and only the failing one is
    retried."""
    import pathlib, tempfile
    from mixfix.research import (Cache, Politeness, YtDlpSource, ResearchError,
                                 CHUNK_ATTEMPTS)
    from mixfix.state import State
    src = YtDlpSource(Cache(State(pathlib.Path(tempfile.mkdtemp()) / "t.db")),
                      Politeness(min_interval_s=0.0),
                      archive_dir=tmp_path / "arch",
                      section_pad_s=0.0, chunk_s=45.0)
    monkeypatch.setattr("mixfix.research.CHUNK_BACKOFF_S", 0.0)
    calls = []

    def flaky(url, a, b, _attempt=1):
        calls.append((a, b))
        raise ResearchError("network call timed out after 300s")

    monkeypatch.setattr(src, "fetch_segment", flaky)
    with pytest.raises(ResearchError, match="failed"):
        src._fetch_chunked("https://youtu.be/x", "x", 0, 90_000)
    # the first chunk was retried, not abandoned after one go
    assert len(calls) == CHUNK_ATTEMPTS, calls
    assert len({c for c in calls}) == 1, "retries must re-ask for the SAME chunk"


def test_chunked_fetch_does_not_retry_an_access_denial(tmp_path, monkeypatch):
    """A 403 from stale auth is not repaired by repeating every chunk four times."""
    from mixfix.research import (Politeness, SourceAccessError, YtDlpSource)

    src = YtDlpSource(cache=None, politeness=Politeness(min_interval_s=0.0),
                      archive_dir=tmp_path / "arch", section_pad_s=0.0,
                      chunk_s=45.0)
    calls = []

    def denied(url, a, b, _attempt=1):
        calls.append((a, b))
        raise SourceAccessError("403 Forbidden")

    monkeypatch.setattr(src, "fetch_segment", denied)
    with pytest.raises(SourceAccessError, match="403"):
        src._fetch_chunked("https://youtu.be/x", "x", 0, 90_000)
    assert len(calls) == 1
