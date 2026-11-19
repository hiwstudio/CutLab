"""Research layer — YouTube search, transcripts, and clip extraction.

Two sources behind one interface:
  YtDlpSource   — real YouTube via yt-dlp (search, auto-subs, archive + cut)
  FixtureSource — local fixtures for offline/sandbox testing (same shapes)

Clips ARE range-fetched. Only the requested window plus a pad is downloaded
(`fetch_segment`), cached by video id + window, and the exact window is cut out
of that locally (`cut_section`). If a 10s window is wanted, ~26s is fetched, not
a 300 MB upload.

This engine previously downloaded whole uploads because range-fetching appeared
unusable — a window that never arrived in 1500s while the full file pulled at
850 KiB/s. That diagnosis blamed the mechanism; the actual cause was the FORMAT.
yt-dlp's default sort picks AV1, and AV1 does not honour a `--download-sections`
seek: it streams from the start of the file, so a deep window downloads the
whole video anyway and never finishes. Forcing H.264 (`vcodec^=avc1`) makes the
same fetch range-correct — measured on this machine at 85s / 3 MiB for a 35s
window 26 minutes deep. `ext=mp4` does NOT discriminate; AV1 ships in mp4 too,
so the codec filter is required. See `_section_format`.

All network access goes through the politeness layer: SQLite cache (never fetch
the same thing twice) + minimum interval between calls + bounded retries.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import tempfile
import subprocess
import time
from pathlib import Path

# Both engines load the shared source-range validation implementation.
_engines_root = str(Path(__file__).resolve().parents[2])
if _engines_root not in sys.path:
    sys.path.insert(0, _engines_root)
import segment_core

from .tools import FFMPEG, FFPROBE
from .library import MIN_SOURCE_HEIGHT
from .state import State, now


class ResearchError(RuntimeError):
    pass


class SourceAccessError(ResearchError):
    """Authentication/configuration failure that repeating a chunk cannot fix."""
    pass


# Connectivity failure (DNS down, no route) vs. "this candidate is unusable".
# The candidate was never actually evaluated, so callers must NOT burn it.
# NOTE: a *timeout* is deliberately NOT here. Timing out means we reached the
# network and the transfer stalled — that candidate is bad, so the caller must
# advance. Only true "we have no network" signals belong in this list.
_OFFLINE_SIGNS = ("getaddrinfo failed", "failed to resolve",
                  "temporary failure in name resolution",
                  "network is unreachable", "no route to host")


def is_offline_error(err: object) -> bool:
    msg = str(err).lower()
    return any(s in msg for s in _OFFLINE_SIGNS)


def explain_ytdlp_error(stderr: str, browser: str | None) -> str | None:
    """Turn yt-dlp's stderr into something the operator can act on.

    These four account for essentially every non-transient failure seen on this
    machine, and each has a different fix — a raw CalledProcessError traceback
    sent past investigations down the wrong path for hours.
    """
    msg = (stderr or "").lower()
    b = browser or "firefox"
    if "page needs to be reloaded" in msg:
        return (f"YouTube rejected the {b} session (its cookies are stale).\n"
                f"  Fix: open youtube.com in {b}, signed in, load any video, "
                f"then rerun.\n"
                f"  If browser cookies cannot be read, an exported cookies.txt "
                f"can be used by clearing research.cookies_from_browser.\n"
                f"  (Anonymous access is not an option: metadata works but the "
                f"media CDN answers 403.)")
    if "could not copy" in msg and "cookie database" in msg:
        return (f"Cannot read {b}'s cookie database while {b} is running "
                f"(yt-dlp #7271).\n  Fix: close {b} and rerun, set "
                f"research.cookies_from_browser to firefox, or drop a "
                f"cookies.txt next to config.yaml.")
    if "dpapi" in msg:
        return (f"Windows refused to decrypt {b}'s cookies (yt-dlp #10927).\n"
                f"  Fix: use firefox, or drop a cookies.txt next to config.yaml.")
    if any(k in msg for k in ("sign in to confirm", "403: forbidden",
                              "403 forbidden", "http error 403",
                              "not a bot")):
        return ("YouTube demanded sign-in for the media download.\n"
                f"  Fix: make sure {b} is signed in to YouTube, then rerun.")
    return None


_VIDEO_ID = re.compile(r"(?:v=|be/|shorts/|embed/)([\w-]{11})")


def video_id_from(url: str) -> str:
    """The 11-char YouTube id, which is what an archive is cached under.

    Falls back to a hash so a non-YouTube URL still gets a stable filename
    instead of blowing up the run.
    """
    m = _VIDEO_ID.search(url or "")
    if m:
        return m.group(1)
    return "url_" + hashlib.sha1((url or "").encode()).hexdigest()[:11]


def cut_section(src: Path, out_path: Path, start_ms: int, end_ms: int) -> Path:
    """Cut [start,end] out of a local file. Frame-accurate, so the window the
    reviewer picked is the window they get.

    -ss before -i seeks by keyframe (fast) and the re-encode makes the result
    exact; -c copy here would snap to the nearest keyframe and silently shift
    every hand-picked window.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-ss", f"{start_ms / 1000:.3f}",
         "-to", f"{end_ms / 1000:.3f}", "-i", str(src),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", str(out_path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode != 0 or not out_path.exists():
        raise ResearchError(
            f"local cut failed for {out_path.name}: {(proc.stderr or '')[-300:]}")
    return out_path


# archives/<video_id>_<padded_start_ms>-<padded_end_ms>_<height>.mp4
# Greedy vid group: ids from video_id_from() may themselves contain "_".
_SEGMENT_NAME = re.compile(
    r"^(?P<vid>.+)_(?P<a>\d+)-(?P<b>\d+)_(?P<h>\d+)\.mp4$")
# A window that comes back audio-only is transient CDN fragment loss, so it is
# worth re-asking — but not forever, or one bad window eats the stage's budget.
SECTION_ATTEMPTS = 3
# A chunk of a long window gets its own retries. Throttling here is intermittent,
# not sticky: the same request that times out often lands minutes later, so the
# cheap fix is patience per chunk rather than failing a window that is already
# half paid for. Completed chunks are kept on disk, so a retry never re-fetches
# what already arrived.
CHUNK_ATTEMPTS = 4
CHUNK_BACKOFF_S = 45.0


class NetworkTimeout(ResearchError):
    """A transfer stalled. Distinct from other ResearchErrors so a caller with
    no alternative candidate can retry it in place."""


def _tile_at(t_s: float, duration_s: float, counts: list[int]) -> tuple[int, int]:
    """Map a timestamp to (sheet index, cell index within that sheet).

    `counts` is the tile count of each sprite sheet in order; the last is often
    a partial grid, so the total is their sum rather than sheets*full_grid, and
    the index is clamped into range so a window at the very end never points at
    a tile that does not exist."""
    total = sum(counts)
    idx = max(0, min(total - 1, int(t_s / duration_s * total)))
    s = 0
    while idx >= counts[s]:
        idx -= counts[s]
        s += 1
    return s, idx


def _storyboard_sheets(mhtml: bytes) -> list[bytes]:
    """The sprite sheets embedded in a yt-dlp storyboard mhtml, in order."""
    import email
    msg = email.message_from_bytes(mhtml)
    out = []
    for part in msg.walk():
        if part.get_content_type().startswith("image/"):
            data = part.get_payload(decode=True)
            if data:
                out.append(data)
    return out


def _has_video(path: Path) -> bool:
    """True if the file actually carries a video stream.

    Not paranoia: when the CDN drops video fragments mid-section, yt-dlp merges
    what it got and exits 0, leaving an audio-only mp4 that looks like success.
    Cheap ffprobe check — the expensive full-decode check (`_playable`) still
    runs later on the cut clip.
    """
    return segment_core.has_video(path, FFPROBE, min_bytes=100_000)


def media_covers(path: Path, required_ms: int, *, require_audio: bool = False) -> bool:
    """Reject a section that ends early or loses audio despite yt-dlp exit 0.

    The cache filename records the requested range, not what the CDN delivered.
    Probe stream durations before trusting that filename on later runs. Video-only
    reference footage is valid; assembly calls this with require_audio=True.
    """
    return segment_core.media_covers(path, required_ms, FFPROBE,
                                     require_audio=require_audio,
                                     min_bytes=100_000)


def _wait_with_progress(proc, limit: float, progress_glob: str | None,
                        stall_s: float, grace_s: float | None = None) -> None:
    """Wait for yt-dlp, failing early if it stops making progress.

    The elapsed-time budget alone cannot tell "stuck" from "slow", and it must
    stay generous or it kills healthy long fetches (see
    test_section_timeout_scales_with_the_window_it_asks_for). So the real signal
    is BYTES ARRIVING: a live transfer keeps growing its .part file however
    slowly, a dead one does not grow at all.

    This covers the whole invocation, which `-rw_timeout` on the ffmpeg reader
    cannot: a throttled extraction stalls BEFORE any ffmpeg exists, and that is
    the failure that sat at zero bytes for 31 minutes. `stall_s` doubles as the
    grace period for extraction, so it must comfortably exceed a healthy
    metadata fetch.
    """
    if not progress_glob:
        proc.wait(timeout=limit)
        return
    from pathlib import Path as _P
    pat = _P(progress_glob)
    # Match on the STEM, not the full name. yt-dlp writes its in-progress parts
    # as "<stem>.f<itag>.mp4.part" — the format id goes BEFORE the extension —
    # so globbing "<stem>.mp4*" matches nothing and a perfectly healthy download
    # reads as zero progress. That killed a 32MiB fetch at 246s that was moving
    # at 90 KiB/s the whole time.
    started = time.time()
    best, last_change = -1, started
    while True:
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
        now = time.time()
        if now - started > limit:
            raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=limit)
        size = 0
        try:
            for f in pat.parent.glob(pat.stem + "*"):
                size = max(size, f.stat().st_size)
        except OSError:
            pass                      # mid-rename; treat as no reading
        if size > best:
            best, last_change = size, now
        elif now - last_change > (stall_s if best > 0 else (grace_s or stall_s)):
            raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=now - started)


def _kill_tree(pid: int) -> None:
    """Kill a process AND its children (yt-dlp spawns ffmpeg; orphans hang us)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


# ---------- politeness / cache ----------
class Cache:
    def __init__(self, state: State):
        self.state = state
        state.conn.executescript(
            "CREATE TABLE IF NOT EXISTS yt_cache ("
            " key TEXT PRIMARY KEY, json TEXT NOT NULL, created_at REAL NOT NULL);")
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        row = self.state.conn.execute(
            "SELECT json FROM yt_cache WHERE key=?", (key,)).fetchone()
        if row:
            self.hits += 1
            return json.loads(row["json"])
        self.misses += 1
        return None

    def put(self, key: str, value) -> None:
        with self.state.conn:
            self.state.conn.execute(
                "INSERT OR REPLACE INTO yt_cache (key, json, created_at) VALUES (?,?,?)",
                (key, json.dumps(value), now()))


class Politeness:
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
                if attempt == self.retries - 1:
                    raise ResearchError(
                        f"network call failed after {self.retries} attempts: "
                        f"{(e.stderr or '')[:300]}") from e
                time.sleep(delay)
                delay *= 3
            except subprocess.TimeoutExpired as e:
                # Not retried HERE: candidate search always has another candidate,
                # and retrying in place burned 15 min per candidate. Fail fast so
                # the caller moves on.
                #
                # The previous note justified this by claiming a stall "almost
                # always stalls again with the same args (usually a deep offset in
                # a long video)". Measured false: the same window stalled on one
                # attempt and pulled 4.46MB in 60s on the next, and window length
                # did not predict which. Stalls are transient — so a caller with no
                # alternative candidate (fetch_segment: the window IS the window)
                # catches NetworkTimeout and retries instead of failing the run.
                raise NetworkTimeout(
                    f"network call timed out after {e.timeout:.0f}s") from e


# ---------- sources ----------
class YtDlpSource:
    """Real YouTube. Requires yt-dlp installed; runs on the user's machine."""

    def __init__(self, cache: Cache, politeness: Politeness,
                 cookies_from_browser: str | None = None,
                 meta_timeout_s: float = 90.0, download_timeout_s: float = 300.0,
                 max_height: int = 720, archive_dir: Path | None = None,
                 section_pad_s: float = 8.0,
                 download_timeout_per_s: float = 3.0,
                 stall_s: float = 240.0,
                 first_byte_grace_s: float = 240.0,
                 chunk_s: float = 200.0,
                 ytdlp_ffmpeg_dir: str | None = None):
        self.cache = cache
        self.polite = politeness
        # Where fetched SEGMENTS live — never whole uploads. Keyed by video id +
        # padded window, shared across scenes AND runs, so two scenes wanting
        # nearby windows of the same source cost one fetch.
        self.archive_dir = Path(archive_dir or "archives")
        # Slack fetched either side of the requested window. This is what makes a
        # reviewer's nudge free: a window moved inside the pad is a local re-cut,
        # not a round trip. It also absorbs keyframe imprecision at the section
        # edges, which is why --force-keyframes-at-cuts is not needed.
        self.section_pad_s = section_pad_s
        self.meta_timeout_s = meta_timeout_s        # search / transcript calls
        # Source resolution cap. Lower = far fewer bytes over a slow link; b-roll
        # is scaled into the frame at assembly anyway, so dropping to 480p is a
        # reasonable trade when the connection cannot sustain 720p.
        self.max_height = max_height
        # A STALL guard. It is a FLOOR, not the whole budget: a fixed ceiling
        # tuned for b-roll (seconds of video, single-digit MB) rejects a
        # legitimately healthy fetch as soon as a mode asks for minutes of video.
        # Measured on this link: 3.85 MiB / 45s for a 77s window at 86 KiB/s, so
        # download time scales with the window and the ceiling has to as well.
        # The real budget is max(floor, window_seconds * download_timeout_per_s),
        # which keeps "stuck, not slow" meaningful at every window length.
        # Deliberately NOT capped: a ceiling low enough to catch a stall quickly
        # also kills a legitimately slow long fetch, which is what
        # test_section_timeout_scales_with_the_window_it_asks_for guards. A stall
        # is caught by -rw_timeout on the ffmpeg reader instead — by absence of
        # progress, not by elapsed time — so the two concerns stop competing.
        self.download_timeout_s = download_timeout_s          # floor per fetch
        self.download_timeout_per_s = download_timeout_per_s  # per second of video
        # No-progress budget. Doubles as the grace period for extraction, so it
        # must clear a healthy metadata fetch (seconds) with room to spare while
        # still catching a stall in minutes rather than half an hour.
        self.stall_s = stall_s
        # Extraction happens before any file exists and is the phase throttling
        # hits hardest, so it gets its own, much longer budget.
        self.first_byte_grace_s = first_byte_grace_s
        # A window longer than this is fetched in chunks and stitched. YouTube
        # throttles by REQUEST SIZE, not just bandwidth: measured here, a 3-min
        # section pulls clean at ~49 KiB/s while an 8-min window of the SAME
        # video stalls to zero for 20+ minutes. b-roll (seconds) never chunks;
        # only assembly/FIX windows (minutes) do.
        self.chunk_s = chunk_s
        # yt-dlp shells out to ffmpeg for --download-sections. Its compatible
        # build can differ from the modern render binary pinned at the front of
        # PATH by config.load_config, so override PATH only for yt-dlp children.
        # Never pass --ffmpeg-location: that breaks googlevideo DNS on this PC.
        self.ytdlp_ffmpeg_dir = str(ytdlp_ffmpeg_dir) if ytdlp_ffmpeg_dir else None
        if self.ytdlp_ffmpeg_dir and not Path(self.ytdlp_ffmpeg_dir).is_dir():
            raise ValueError(
                f"research.ytdlp_ffmpeg_dir is not a directory: {self.ytdlp_ffmpeg_dir}")
        # YouTube's CDN 403s anonymous downloads ("confirm you're not a bot"),
        # so cookies are mandatory, not an optimisation. Prefer the configured
        # live browser over a saved cookies.txt: the Tyson segment fetched with
        # Firefox while the two-day-old export received a video-stream 403.
        # The file remains an explicit fallback when no browser is configured.
        self.browser = cookies_from_browser
        cookiefile = self.archive_dir.parent / "cookies.txt"
        self.cookie_args = segment_core.cookie_args(cookies_from_browser, cookiefile)

    def _ytdlp(self, args: list[str], timeout: float | None = None,
               progress_glob: str | None = None) -> str:
        """Run yt-dlp with a timeout that actually works.

        NOT subprocess.run(capture_output=True): yt-dlp spawns ffmpeg for muxing,
        ffmpeg inherits the stdout/stderr PIPES, and killing yt-dlp on timeout
        leaves ffmpeg holding them open — communicate() then blocks forever and
        the timeout silently does nothing. Writing to temp files means no pipes,
        no reader threads, and a timeout that really fires; on expiry we kill the
        whole process tree so no orphan survives.
        """
        limit = timeout or self.meta_timeout_s
        # Retries are what make a lossy link finish: without them a single
        # dropped fragment fails the whole transfer and the wall clock kills it.
        # Keep the socket timeout generous — it is a stall guard, and 30s aborts
        # transfers that are merely slow.
        cmd = ["python", "-m", "yt_dlp", "--no-warnings", *self.cookie_args,
               "--socket-timeout", "60",
               "--retries", "10", "--fragment-retries", "10",
               "--extractor-retries", "3", *args]
        with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as out, \
             tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as err:
            env = None
            if self.ytdlp_ffmpeg_dir:
                env = os.environ.copy()
                # Put the section-download build first while preserving the
                # normal PATH after it (including MixFix's render-only build).
                compatible = os.path.normcase(os.path.normpath(self.ytdlp_ffmpeg_dir))
                entries = [p for p in env.get("PATH", "").split(os.pathsep)
                           if p and os.path.normcase(os.path.normpath(p)) != compatible]
                env["PATH"] = os.pathsep.join([self.ytdlp_ffmpeg_dir, *entries])
            proc = subprocess.Popen(cmd, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, env=env)
            try:
                _wait_with_progress(proc, limit, progress_glob,
                                    self.stall_s, self.first_byte_grace_s)
            except subprocess.TimeoutExpired:
                _kill_tree(proc.pid)
                proc.wait(timeout=15)
                # Keep what the child managed to say. Discarding it on timeout
                # makes a throttle, a stalled CDN, a bad cookie session and a
                # genuinely slow link all present as the same bare "timed out",
                # which is several hours of guessing per incident.
                try:
                    out.seek(0), err.seek(0)
                    self._last_stdout, self._last_stderr = out.read(), err.read()
                except (OSError, ValueError):
                    self._last_stdout = self._last_stderr = ""
                raise
            out.seek(0), err.seek(0)
            stdout, stderr = out.read(), err.read()
        self._last_stderr = stderr
        if proc.returncode != 0:
            hint = explain_ytdlp_error(stderr, getattr(self, "browser", None))
            if hint:
                # Not retryable: spacing and patience cannot fix a bad session,
                # so fail now with the fix rather than after three attempts.
                raise SourceAccessError(hint)
            raise subprocess.CalledProcessError(proc.returncode, cmd, stdout, stderr)
        return stdout

    def search(self, query: str, n: int = 5) -> list[dict]:
        key = f"search:{n}:{query}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        out = self.polite.call(
            self._ytdlp, [f"ytsearch{n}:{query}", "--flat-playlist", "--dump-json"])
        results = []
        for line in out.strip().splitlines():
            d = json.loads(line)
            results.append({
                "video_id": d["id"],
                "url": d.get("url") or f"https://www.youtube.com/watch?v={d['id']}",
                "title": d.get("title", ""),
                "channel": d.get("channel") or d.get("uploader", ""),
                "duration_s": d.get("duration") or 0,
            })
        self.cache.put(key, results)
        return results

    def transcript(self, video_id: str, url: str) -> list[dict]:
        """Auto-captions as [{text,start_ms,end_ms}]. Empty list if none exist."""
        key = f"transcript:{video_id}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            try:
                self.polite.call(self._ytdlp, [
                    url, "--skip-download", "--write-auto-subs", "--write-subs",
                    "--sub-langs", "en.*", "--sub-format", "json3",
                    "-o", f"{td}/sub"])
            except ResearchError:
                self.cache.put(key, [])
                return []
            segs = []
            for f in Path(td).glob("*.json3"):
                data = json.loads(f.read_text(encoding="utf-8"))
                for ev in data.get("events", []):
                    text = "".join(s.get("utf8", "") for s in ev.get("segs", [])).strip()
                    if text and "tStartMs" in ev:
                        segs.append({
                            "text": text,
                            "start_ms": int(ev["tStartMs"]),
                            "end_ms": int(ev["tStartMs"]) + int(ev.get("dDurationMs", 2000)),
                        })
                break
        self.cache.put(key, segs)
        return segs

    def extract_section(self, url: str, start_ms: int, end_ms: int,
                        out_path: Path) -> Path:
        """A window of a source video — range-fetched, never the whole upload.

        find reference -> pick window -> fetch ONLY that window (+pad) -> cut the
        exact window out of it locally. The padded segment is what the archive
        keeps, so a window moved inside the pad never touches the network again.
        """
        seg, base_ms = self.fetch_segment(url, start_ms, end_ms)
        return cut_section(seg, out_path, start_ms - base_ms, end_ms - base_ms)

    def _section_format(self) -> str:
        """Format selector for a RANGE fetch. `vcodec^=avc1` is load-bearing.

        yt-dlp's default sort picks AV1, and AV1 does not honour a
        `--download-sections` seek — it streams from the start of the file, so a
        deep window quietly downloads the entire upload and never finishes. That
        is the failure this engine once recorded as "range-fetching does not
        work". Measured on this machine: a 35s window 26 minutes in pulled tens
        of MB and never completed as AV1, and finished in 85s / 3 MiB as H.264.
        `ext=mp4` does not discriminate — AV1 ships in mp4 too.

        Every branch keeps a height cap so the selector can never fall through to
        an audio-only format, which yt-dlp would merge and exit 0 on. The
        MIN_SOURCE_HEIGHT floor sits on the preferred branch only: a low-res
        source is better judged by the quality gate than lost at selection with
        no file to look at.
        """
        h, lo = self.max_height, MIN_SOURCE_HEIGHT
        return (f"bv*[height<={h}][height>={lo}][vcodec^=avc1]+ba[ext=m4a]/"
                f"bv*[height<={h}][vcodec^=avc1]+ba/"
                f"bv*[height<={h}]+ba/b[height<={h}]")

    def _link_healthy(self, url: str, probe_s: float = 45.0) -> bool:
        """Is this link fine, or is the client being throttled?

        A metadata-only fetch is a few KB and is the FIRST thing to slow down
        when YouTube throttles: measured at 98-124s while throttled against 5-8s
        healthy. That gap is wide enough to decide on, and it is far cheaper than
        discovering the answer by re-asking for 60MB.
        """
        try:
            t0 = time.time()
            self._ytdlp([url, "--no-playlist", "--skip-download",
                         "--print", "id"], timeout=probe_s)
        except Exception:
            return False           # cannot even read metadata; do not push harder
        return (time.time() - t0) < probe_s * 0.6

    def _covering_segment(self, video_id: str, start_ms: int,
                          end_ms: int) -> tuple[Path | None, int]:
        """An already-fetched segment that fully contains [start,end].

        This is the payoff of the pad: the reviewer nudging a window, or a second
        scene wanting a nearby moment of the same source, is served from disk.
        """
        for p in sorted(self.archive_dir.glob(
                f"*_*-*_{self.max_height}.mp4")):
            m = _SEGMENT_NAME.match(p.name)
            if not m or m.group("vid") != video_id:
                continue
            a, b = int(m.group("a")), int(m.group("b"))
            if a <= start_ms and end_ms <= b and media_covers(p, end_ms - a):
                return p, a
        return None, 0

    def storyboard_tiles(self, url: str, video_id: str, start_ms: int,
                         end_ms: int, duration_s: float | None,
                         out_dir: Path, n: int = 3) -> list[Path]:
        """Preview frames spanning a window WITHOUT downloading the video.

        YouTube ships a storyboard — the low-res tiles the scrubber shows on
        hover — as one small mhtml (whole video, ~200KB, ~3s) instead of the
        tens of MB and multi-minute range-fetch a real window costs on this
        link. That is enough to reject a title card, a talking head or a
        watermarked reupload before anything is downloaded; the human does final
        visual QA on the deep-linked moment. Returns [] when the video has no
        storyboard or no duration to place tiles against — the caller then falls
        back to the real download-and-frame path.
        """
        if not duration_s or duration_s <= 0:
            return []
        cached = sorted(out_dir.glob("sb_*.jpg"))
        if cached:
            return cached
        board = self.archive_dir / "storyboards" / f"{video_id}.mhtml"
        if not board.exists():
            board.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._ytdlp([url, "--no-playlist", "-f", "sb0",
                             "-o", str(board.with_suffix(".%(ext)s"))],
                            timeout=self.meta_timeout_s)
            except Exception:
                return []
            if not board.exists():
                return []
        try:
            sheets = _storyboard_sheets(board.read_bytes())
        except Exception:
            return []
        if not sheets:
            return []
        try:
            from PIL import Image
        except ImportError:
            return []
        import io as _io
        imgs = [Image.open(_io.BytesIO(s)).convert("RGB") for s in sheets]
        tw, th = 160, 90                       # sb0 tile size (yt-dlp reports this)
        grids = [(max(1, im.width // tw), max(1, im.height // th)) for im in imgs]
        counts = [c * r for c, r in grids]
        total = sum(counts)
        if total <= 0:
            return []
        out_dir.mkdir(parents=True, exist_ok=True)
        out = []
        for k in range(n):
            frac = (k + 0.5) / n               # evenly across the window
            t = (start_ms + frac * (end_ms - start_ms)) / 1000.0
            s, cell = _tile_at(t, duration_s, counts)
            cols = grids[s][0]
            r, c = divmod(cell, cols)
            tile = imgs[s].crop((c * tw, r * th, c * tw + tw, r * th + th))
            dest = out_dir / f"sb_{k + 1:02d}.jpg"
            tile.save(dest, "JPEG", quality=90)
            out.append(dest)
        return out

    def _fetch_chunked(self, url: str, video_id: str, start_ms: int,
                       end_ms: int) -> tuple[Path, int]:
        """Fetch a long window as several short sections and stitch them.

        Each chunk goes through the ordinary single-fetch path (recursion), so
        all its tested retry/health/stall handling applies per chunk. Chunks are
        cut to their EXACT bounds (cut_section re-encodes, so no keyframe overlap
        survives) and concatenated, giving a clean [start,end] segment. Returned
        base is start_ms — the file IS the exact window, so the caller's own cut
        is a no-op slice from zero.
        """
        dest = (self.archive_dir /
                f"{video_id}_{start_ms}-{end_ms}_{self.max_height}.mp4")
        if dest.exists() and media_covers(dest, end_ms - start_ms):
            return dest, start_ms
        n = math.ceil((end_ms - start_ms) / (self.chunk_s * 1000))
        step = (end_ms - start_ms) / n
        tmp = self.archive_dir / f"_chunk_{video_id}_{start_ms}_{end_ms}"
        tmp.mkdir(parents=True, exist_ok=True)
        pieces = []
        for i in range(n):
            ca = start_ms + int(round(i * step))
            cb = end_ms if i == n - 1 else start_ms + int(round((i + 1) * step))
            exact = tmp / f"{i:03d}.mp4"
            if exact.exists() and media_covers(exact, cb - ca):
                pieces.append(exact)      # resume: this chunk already landed
                continue
            # A throttled link fails INTERMITTENTLY: the identical request that
            # times out now succeeds minutes later (measured — same argv, same
            # window, one 300s timeout and one 61s success). So a chunk timeout
            # is not a verdict on the chunk, and failing the whole window over it
            # throws away every chunk already paid for. Retry this chunk with a
            # widening pause; only give up when it will not land at all.
            last = None
            for attempt in range(CHUNK_ATTEMPTS):
                try:
                    seg, seg_base = self.fetch_segment(url, ca, cb)
                    cut_section(seg, exact, ca - seg_base, cb - seg_base)
                    if not media_covers(exact, cb - ca):
                        exact.unlink(missing_ok=True)
                        raise ResearchError(f"chunk {i + 1}/{n} ended early or lost audio")
                    break
                except (SourceAccessError, NetworkTimeout):
                    # A bad session needs human refresh. A timeout already got
                    # the single-fetch link-health probe and its one live-edge
                    # retry; keep completed chunks for a later resumed run.
                    raise
                except ResearchError as e:
                    last = e
                    if attempt == CHUNK_ATTEMPTS - 1:
                        raise ResearchError(
                            f"chunk {i + 1}/{n} of {video_id} "
                            f"[{ca}-{cb}ms] failed {CHUNK_ATTEMPTS}x: {e}") from e
                    time.sleep(CHUNK_BACKOFF_S * (attempt + 1))
            pieces.append(exact)
        listing = tmp / "concat.txt"
        listing.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in pieces), encoding="utf-8")
        proc = subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listing), "-c", "copy", "-movflags", "+faststart",
             str(dest)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if proc.returncode != 0 or not media_covers(dest, end_ms - start_ms):
            dest.unlink(missing_ok=True)
            raise ResearchError(
                f"chunk concat failed for {dest.name}: {(proc.stderr or '')[-300:]}")
        for p in pieces:
            p.unlink(missing_ok=True)
        listing.unlink(missing_ok=True)
        try:
            tmp.rmdir()
        except OSError:
            pass
        return dest, start_ms

    def fetch_segment(self, url: str, start_ms: int, end_ms: int,
                      _attempt: int = 1) -> tuple[Path, int]:
        """Download ONLY [start,end] plus `section_pad_s` either side.

        Returns (path, segment_start_ms) — the caller cuts its exact window at
        an offset from the segment start, because the file begins at the pad,
        not at the requested moment.
        """
        video_id = video_id_from(url)
        hit, base = self._covering_segment(video_id, start_ms, end_ms)
        if hit:
            return hit, base

        # Lasting bypass for operator-ingested full sources when CDN 403s;
        # archives/full/<video_id>.mp4 is the contract (seed via seed_local_full.py).
        # Prefer a local ffmpeg cut over network yt-dlp whenever the full file
        # exists and carries video. Network path remains the fallback when
        # full/ is missing — FixtureSource is untouched.
        full = self.archive_dir / "full" / f"{video_id}.mp4"
        if full.exists() and _has_video(full):
            pad = int(self.section_pad_s * 1000)
            a, b = max(0, start_ms - pad), end_ms + pad
            dest = self.archive_dir / f"{video_id}_{a}-{b}_{self.max_height}.mp4"
            if dest.exists() and media_covers(dest, end_ms - a):
                return dest, a
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Stream-copy first (pad absorbs keyframe snap); re-encode via
            # cut_section if copy fails or lands without video — same quality
            # practice as the rest of research.py.
            proc = subprocess.run(
                [FFMPEG, "-v", "error", "-y",
                 "-ss", f"{a / 1000:.3f}", "-to", f"{b / 1000:.3f}",
                 "-i", str(full), "-c", "copy", "-avoid_negative_ts", "make_zero",
                 str(dest)],
                capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if proc.returncode != 0 or not media_covers(dest, end_ms - a):
                dest.unlink(missing_ok=True)
                cut_section(full, dest, a, b)
            if not media_covers(dest, end_ms - a):
                dest.unlink(missing_ok=True)
                raise ResearchError(
                    f"local full cut failed for {video_id} [{a}-{b}ms] from {full}")
            return dest, a

        # A window longer than chunk_s trips YouTube's large-request throttle
        # (a 3-min section flies, an 8-min one stalls to zero). Fetch it in
        # chunks — each through this same tested single-fetch path — and stitch.
        if _attempt == 1 and (end_ms - start_ms) > self.chunk_s * 1000:
            return self._fetch_chunked(url, video_id, start_ms, end_ms)

        pad = int(self.section_pad_s * 1000)
        a, b = max(0, start_ms - pad), end_ms + pad
        # The height cap is part of the identity, not just the request: a segment
        # fetched at 480p must not silently satisfy a run configured for 720p.
        dest = self.archive_dir / f"{video_id}_{a}-{b}_{self.max_height}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        # An earlier yt-dlp exit 0 can leave a short .mp4. Do not let yt-dlp
        # mistake that existing final filename for a completed download.
        if dest.exists() and not media_covers(dest, end_ms - a):
            dest.unlink(missing_ok=True)
        # A killed run leaves .part/.ytdl behind; yt-dlp would resume a stale
        # partial from a different format and produce a corrupt file at exit 0.
        for junk in dest.parent.glob(dest.stem + "*"):
            if ".part" not in junk.name and junk.suffix != ".ytdl":
                continue
            try:
                junk.unlink()
            except PermissionError:
                # Windows locks a file that is still open, meaning another fetch
                # of THIS window is in flight. Killing the pipeline over it loses
                # every other scene's work — fail this candidate, move on.
                raise ResearchError(
                    f"{junk.name} is locked by another download of this window; "
                    "wait for it to finish (or kill the stray yt-dlp) and "
                    "rerun") from None
            except OSError:
                pass                       # already gone; nothing to clean

        try:
            self.polite.call(self._ytdlp, [
                url, "--no-playlist",
                "--download-sections", f"*{a / 1000:.2f}-{b / 1000:.2f}",
                "-f", self._section_format(),
                "--merge-output-format", "mp4", "--no-continue",
                "--concurrent-fragments", "5",
                # Deliberately NOT --force-keyframes-at-cuts: it re-encodes the
                # whole section (measured: >300s timeout -> 39s without it). We cut
                # the exact window locally afterwards and the pad absorbs the
                # keyframe slack, so section edges need not be frame-exact.
                #
                # ffmpeg's HTTP reader gives up mid-stream on a lossy link while
                # yt-dlp still exits 0 over a 262-byte stub; reconnecting resumes
                # it (measured here: 262 bytes -> 3.0 MB on the same clip).
                #
                # -rw_timeout (microseconds) is the STALL detector. Without it a
                # read that hangs forever hangs the whole attempt, and the only
                # backstop is the elapsed-time budget — which cannot be tightened
                # without also killing healthy long fetches. Bounding the READ
                # instead separates "stuck" from "slow": a live transfer keeps
                # resetting the clock however slowly it moves, a dead one trips it
                # in 60s and reconnect/retry takes over. Measured stalls sat at
                # ~0 bytes for 30+ minutes before this.
                "--downloader-args",
                "ffmpeg:-nostdin -rw_timeout 60000000 -reconnect 1 "
                "-reconnect_streamed 1 -reconnect_delay_max 10",
                "-o", str(dest)],
                timeout=max(self.download_timeout_s,
                            (b - a) / 1000 * self.download_timeout_per_s),
                progress_glob=str(dest))
        except NetworkTimeout:
            dest.unlink(missing_ok=True)
            # Retried ONCE, and only when a probe says the link is healthy.
            #
            # Blind retries were tried and were worse: during a rate limit they
            # turned a 31-minute failure into a 95-minute one, the mistake
            # lessons/time-a-metadata-call-before-theorising-about-a-stall.md
            # records. But never retrying is wrong for the other failure, which
            # is just as real and was measured repeatedly here: on a healthy link
            # one window stalls at zero bytes while the SAME window, re-asked
            # immediately with fresh URLs, downloads at full speed. That is a CDN
            # edge going dark, not a throttle, and failing the run over it wastes
            # everything already fetched.
            #
            # The probe is what tells the two apart, so it runs BEFORE the retry
            # instead of after the postmortem — which is what that lesson
            # actually asks for.
            if _attempt >= 2 or not self._link_healthy(url):
                raise
            return self.fetch_segment(url, start_ms, end_ms, _attempt + 1)

        if not media_covers(dest, end_ms - a):
            # A stub, early end, or dropped audio at exit 0 is transient CDN
            # fragment loss. Never admit it to the covering-segment cache.
            size = dest.stat().st_size if dest.exists() else 0
            dest.unlink(missing_ok=True)
            if _attempt >= SECTION_ATTEMPTS:
                raise ResearchError(
                    f"section {a}-{b}ms of {url} came back incomplete after "
                    f"{_attempt} attempts (last size {size}B) — the CDN keeps "
                    "dropping video fragments for this window")
            return self.fetch_segment(url, start_ms, end_ms, _attempt + 1)
        return dest, a


class FixtureSource:
    """Offline source for tests/sandbox. Fixture dir layout:
        search.json                — {"<query>": [candidate, ...]}
        transcripts/<video_id>.json — {"segments": [{text,start_ms,end_ms}]}
        videos/<video_id>.mp4       — local media
    """

    def __init__(self, fixture_dir: Path, cache: Cache | None = None):
        self.dir = Path(fixture_dir)
        self.calls: list[str] = []

    def search(self, query: str, n: int = 5) -> list[dict]:
        self.calls.append(f"search:{query}")
        index = json.loads((self.dir / "search.json").read_text(encoding="utf-8"))
        # exact key, else token-overlap best match (fixtures are small)
        if query in index:
            return index[query][:n]
        qtok = set(query.lower().split())
        best, best_score = [], 0
        for k, v in index.items():
            score = len(qtok & set(k.lower().split()))
            if score > best_score:
                best, best_score = v, score
        return best[:n]

    def transcript(self, video_id: str, url: str) -> list[dict]:
        self.calls.append(f"transcript:{video_id}")
        p = self.dir / "transcripts" / f"{video_id}.json"
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8"))["segments"]

    def fetch_segment(self, url: str, start_ms: int, end_ms: int,
                      _attempt: int = 1) -> tuple[Path, int]:
        """Offline twin of YtDlpSource.fetch_segment.

        Returns the whole fixture file with a base of 0, so the caller's
        `cut_section(path, out, start - base, end - base)` cuts the real window.
        Without this, any mode that range-fetches (rather than searching for a
        candidate) simply cannot run offline — which left ASSEMBLY untestable
        without a healthy network, the one condition a test must not depend on.
        """
        src = self.dir / "videos" / f"{video_id_from(url)}.mp4"
        if not src.exists():
            raise ResearchError(f"fixture video missing: {src}")
        self.calls.append(f"fetch_segment:{start_ms}-{end_ms}")
        return src, 0

    def storyboard_tiles(self, url: str, video_id: str, start_ms: int,
                         end_ms: int, duration_s: float | None,
                         out_dir: Path, n: int = 3) -> list[Path]:
        """Offline fixtures carry no storyboards, so this always falls through to
        the real extract_section path — which keeps the sourcing tests exercising
        the download-and-frame flow exactly as before."""
        return []

    def extract_section(self, url: str, start_ms: int, end_ms: int,
                        out_path: Path) -> Path:
        video_id = url.rsplit("=", 1)[-1]
        src = self.dir / "videos" / f"{video_id}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-ss", f"{start_ms / 1000:.3f}",
             "-to", f"{end_ms / 1000:.3f}", "-i", str(src),
             "-c:v", "libx264", "-preset", "ultrafast", "-an", str(out_path)],
            check=True, capture_output=True, text=True)
        return out_path


def make_source(cfg: dict, state: State):
    mode = cfg.get("research", {}).get("source", "yt-dlp")
    cache = Cache(state)
    if mode == "fixture":
        return FixtureSource(Path(cfg["root"]) / cfg["research"]["fixture_dir"], cache), cache
    polite = Politeness(
        min_interval_s=cfg.get("research", {}).get("min_interval_s", 2.0))
    r = cfg.get("research", {})
    return YtDlpSource(
        cache, polite,
        cookies_from_browser=r.get("cookies_from_browser"),
        max_height=int(r.get("max_height", 720)),
        archive_dir=Path(cfg["root"]) / r.get("archive_dir", "archives"),
        section_pad_s=float(r.get("section_pad_s", 8.0)),
        # A padded section is single-digit MB. Generous enough to survive a
        # throttled client being told to sleep by the site, tight enough that a
        # genuinely stuck window loses one candidate rather than the afternoon.
        download_timeout_s=float(r.get("download_timeout_s", 300.0)),
        stall_s=float(r.get("stall_s", 240.0)),
        first_byte_grace_s=float(r.get("first_byte_grace_s", 240.0)),
        download_timeout_per_s=float(r.get("download_timeout_per_s", 3.0)),
        chunk_s=float(r.get("chunk_s", 200.0)),
        ytdlp_ffmpeg_dir=r.get("ytdlp_ffmpeg_dir"),
    ), cache
