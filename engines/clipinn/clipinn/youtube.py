"""YouTube access — metadata, auto-captions, and SEGMENT-ONLY downloads.

The core Clipinn idea: never download the full video. Selection runs on the
auto-caption transcript (a tiny fetch); only chosen windows are downloaded via
yt-dlp --download-sections.

ClipInn and MixFix share authentication choice and media-integrity checks in
../segment_core.py. Their download orchestration remains engine-specific.
The specifics below are load-bearing:

  * ONE cookie source (live Firefox first, saved cookies.txt only if the
    browser is unconfigured), never a retry ladder.
    Per lessons/ytdlp-cdn-403-2026-07.md: googlevideo.com 403s anonymous
    downloads ("Sign in to confirm you're not a bot"); Chrome/Edge cookie DBs
    can't be copied while those browsers run (yt-dlp #7271 / app-bound
    encryption + Windows DPAPI). Firefox works first try.
  * NO --extractor-args. Forcing player_client=android,ios and
    formats=missing_pot lets SABR/PO-token-less formats through, which
    intermittently yields audio-only or broken streams.
  * Format selector has NO bare `/b` fallback — `b` can resolve to an
    audio-only format when video fragments fail, and yt-dlp still exits 0.
  * Transient failures are handled by bounded retries with exponential
    backoff (MixFix's Politeness), not by trying different cookie sources.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import config
from .utils import MAX_AUDIO_GAP_S, audio_gap_s, has_video, media_covers, log, segment_core


class YouTubeError(RuntimeError):
    pass


# Prefer H.264 + AAC explicitly. YouTube also serves AV1 and VP9 at every
# resolution, and yt-dlp's default sort picks AV1 — which for a --download-
# sections seek deep into a video either fails the ffmpeg merge outright or
# streams from the start of the file instead of range-fetching the window
# (measured: a 35s clip 26min in pulled tens of MB and never finished; the
# same window as H.264 finished in 85s / 3 MiB). Note ext:mp4 does NOT
# discriminate — AV1 is served in mp4 too — so the codec filter is required.
# Fallbacks keep a height constraint so they can never resolve to audio-only.
_SECTION_FORMAT = ("bv*[height<={R}][vcodec^=avc1]+ba[ext=m4a]/"
                   "bv*[height<={R}][vcodec^=avc1]+ba/"
                   "bv*[height<={R}]+ba/"
                   "b[height<={R}]")


class Politeness:
    """Minimum interval between network calls + bounded retries with
    exponential backoff. Ported from MixFix."""

    def __init__(self, min_interval_s: float = 2.0, retries: int = 3):
        self.min_interval = min_interval_s
        self.retries = retries
        self._last_call = 0.0

    def call(self, fn, *args, **kwargs):
        delay = 1.0
        for attempt in range(self.retries):
            wait = self._last_call + self.min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                return fn(*args, **kwargs)
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or "")
                if attempt == self.retries - 1:
                    raise YouTubeError(_explain(stderr, self.retries)) from e
                log(f"    attempt {attempt + 1}/{self.retries} failed, "
                    f"retrying in {delay:.0f}s...")
                time.sleep(delay)
                delay *= 3


_polite = Politeness(min_interval_s=config.YT_MIN_INTERVAL_S)


def _explain(stderr: str, attempts: int) -> str:
    """Turn a yt-dlp stderr blob into an actionable message."""
    msg = stderr.lower()
    tail = stderr[-400:].strip()
    browser = config.YT_BROWSER or "firefox"
    if "tiktok" in msg:
        return ("TikTok blocked the download (challenge or webpage).\n"
                "  Retry once; do not change the YouTube downloader.\n"
                f"  Last error: {tail}")
    if any(k in msg for k in ("sign in", "not a bot", "403", "forbidden")):
        return ("YouTube demanded sign-in / blocked the CDN download.\n"
                f"  Open YouTube in {browser} while logged in (the session "
                "cookie may have expired), then rerun the same command.\n"
                f"  Last error: {tail}")
    if "dpapi" in msg or "could not copy" in msg or "cookie database" in msg:
        return (f"Could not read {browser}'s cookies.\n"
                f"  Close {browser} and rerun, or set YT_BROWSER in .env to a "
                "browser you're signed into YouTube with (firefox is the "
                "proven one on this machine).\n"
                f"  Last error: {tail}")
    if any(k in msg for k in ("failed to resolve hostname", "name does not "
                              "resolve", "connection reset", "timed out")):
        return ("Couldn't reach YouTube's video servers (googlevideo.com) — "
                f"a network/DNS blip, retried {attempts}x.\n"
                "  Check your connection and rerun; finished work is cached "
                "and won't repeat.\n"
                f"  Last error: {tail}")
    return f"yt-dlp failed after {attempts} attempts: {tail}"


def _cookie_args() -> list:
    """Use the same live-browser-first source choice as MixFix."""
    return segment_core.cookie_args(config.YT_BROWSER, config.ROOT / "cookies.txt")


def is_tiktok(url: str) -> bool:
    return "tiktok.com" in (url or "").lower()


def _auth_args(url: str) -> list:
    """YouTube keeps the MixFix cookie contract. TikTok does not.

    Measured 2026-09-21: TikTok's JS challenge fails without
    `--impersonate chrome`. Firefox YouTube cookies are the wrong jar and
    are not applied. Never add impersonate to a YouTube URL.
    """
    if is_tiktok(url):
        return ["--impersonate", "chrome"]
    return _cookie_args()


def _url_from_args(args: list) -> str:
    for a in args:
        if isinstance(a, str) and a.startswith(("http://", "https://")):
            return a
    return ""


def _ytdlp(args: list) -> str:
    """One yt-dlp invocation, exactly as MixFix builds it — unless the URL
    is TikTok, in which case impersonate replaces cookies."""
    proc = subprocess.run(
        ["python", "-m", "yt_dlp", "--no-warnings", *_auth_args(_url_from_args(args)),
         # NOTE: deliberately NOT passing --ffmpeg-location, matching MixFix.
         # yt-dlp must use whatever ffmpeg is on PATH. Pinning the modern
         # Gyan 8.1.2 build here breaks downloads on this machine: ffmpeg 8
         # fails to resolve googlevideo.com CDN hostnames ("The name does not
         # resolve for the supplied parameters", IPv6 connection), so the
         # video input errors while the audio input succeeds — and the merge
         # silently produces an AUDIO-ONLY file with yt-dlp exiting 0. The
         # older PATH ffmpeg resolves them fine. Clipinn's own render calls
         # still use utils.FFMPEG (the pinned modern build) — that pin is for
         # rendering only, where the filter graph needs a current ffmpeg.
         "--retries", "10", "--fragment-retries", "10",
         "--extractor-retries", "3",
         *args],
        capture_output=True, text=True, check=True)
    return proc.stdout


def video_info(url: str) -> dict:
    """Metadata without downloading: id, title, channel, duration_s."""
    out = _polite.call(_ytdlp, [url, "--skip-download", "--dump-json",
                                "--no-playlist"])
    d = json.loads(out.strip().splitlines()[0])
    return {"video_id": d["id"], "title": d.get("title", ""),
            "channel": d.get("channel") or d.get("uploader", ""),
            "duration_s": d.get("duration") or 0,
            "url": d.get("webpage_url") or url}


def fetch_auto_subs(url: str) -> list:
    """Auto/manual captions as [{text, start_ms, end_ms}]. [] if none."""
    with tempfile.TemporaryDirectory() as td:
        try:
            # "en.*" also matches every auto-TRANSLATED track (en-de-DE, en-fr-FR, ...).
            # Requesting dozens of them earns an HTTP 429 partway through. Ask only for
            # the English tracks that carry the real transcript.
            _polite.call(_ytdlp, [
                url, "--skip-download", "--write-auto-subs", "--write-subs",
                "--sub-langs", "en,en-orig,en-US,en-GB", "--sub-format", "json3",
                "-o", f"{td}/sub"])
        except YouTubeError:
            # A failed variant must NOT discard tracks already written to disk. Falling
            # back to whisper costs a full audio download plus minutes of CPU, when a
            # complete caption file is often already sitting in this temp dir.
            pass
        order = ["sub.en.json3", "sub.en-orig.json3", "sub.en-US.json3", "sub.en-GB.json3"]
        files = sorted(Path(td).glob("*.json3"),
                       key=lambda p: (order.index(p.name) if p.name in order else 99, p.name))
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            segs = []
            for ev in data.get("events", []):
                text = "".join(s.get("utf8", "") for s in ev.get("segs", [])).strip()
                if text and "tStartMs" in ev:
                    segs.append({
                        "text": text,
                        "start_ms": int(ev["tStartMs"]),
                        "end_ms": int(ev["tStartMs"]) + int(ev.get("dDurationMs", 2000))})
            if segs:
                return segs
        return []


def download_audio(url: str, out_path: Path) -> Path:
    """Audio-only download (small) — whisper fallback when no captions exist."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _polite.call(_ytdlp, [url, "-f", "ba/b", "-x", "--audio-format", "mp3",
                          "--no-playlist", "-o", str(out_path)])
    if not out_path.exists():
        raise YouTubeError(f"yt-dlp did not produce {out_path}")
    return out_path


def download_section(url: str, start_ms: int, end_ms: int, out_path: Path,
                     max_res: int = None, _attempt: int = 1) -> Path:
    """Download ONLY [start,end] (+pad) of the video. The heart of Clipinn.

    Even with the safe selector, a CDN hiccup can occasionally land a file
    with no video stream while yt-dlp still exits 0 — verify and redownload.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pad = config.SEGMENT_PAD_S
    a = max(0.0, start_ms / 1000 - pad)
    b = end_ms / 1000 + pad
    R = max_res or config.DL_MAX_RES
    _polite.call(_ytdlp, [
        url, "--download-sections", f"*{a:.2f}-{b:.2f}",
        "--force-keyframes-at-cuts", "--no-playlist",
        "-f", _SECTION_FORMAT.format(R=R),
        "--merge-output-format", "mp4", "-o", str(out_path)])
    if not out_path.exists():
        raise YouTubeError(f"yt-dlp did not produce {out_path}")
    # The same drop can hit the audio instead: exit 0, full video, sound that
    # stops partway. Intermittent — a fresh download of the section is whole.
    expected_ms = int(round((b - a) * 1000))
    if not media_covers(out_path, expected_ms, require_audio=True):
        gap = audio_gap_s(out_path) if has_video(out_path) else None
        out_path.unlink(missing_ok=True)
        problem = ("was missing video" if gap is None else
                   "was incomplete or missing audio" if gap <= MAX_AUDIO_GAP_S else
                   f"lost its audio {gap:.0f}s before the end")
        if _attempt >= 3:
            raise YouTubeError(
                f"{out_path.name} {problem} after {_attempt} attempts — the "
                "CDN keeps dropping fragments for this section. Rerun the "
                "command to retry.")
        log(f"  {out_path.name} {problem} (attempt {_attempt}); "
            "retrying download...")
        return download_section(url, start_ms, end_ms, out_path, max_res,
                                _attempt + 1)
    return out_path
