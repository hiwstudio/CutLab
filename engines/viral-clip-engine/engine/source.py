"""Resolve the input video: ask the user, accept a local path or a URL
(YouTube etc.), and download URLs with yt-dlp."""
from pathlib import Path

import config
from engine.utils import FFMPEG, die, log


_VIDEO_HOSTS = (
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com",
    "fb.watch", "twitter.com", "x.com", "vimeo.com", "dailymotion.com",
    "twitch.tv", "reddit.com", "streamable.com",
)


def _is_url(text: str) -> bool:
    t = text.strip().lower()
    if t.startswith(("http://", "https://", "www.")):
        return True
    if Path(text).exists():  # a real local file is never a URL
        return False
    return any(host in t for host in _VIDEO_HOSTS)


def _clean_path(text: str) -> str:
    # Windows drag-and-drop / "Copy as path" wraps paths in quotes
    return text.strip().strip('"').strip("'")


def download_video(url: str) -> Path:
    """Download a video with yt-dlp into downloads/. Returns the file path.

    Prefers efficient ~1080p separate streams (small files), like the original
    workflow. Keeps the portrait/TikTok fix and a fallback for the YouTube 403
    / sign-in blocks, and shows only a clean, minimal progress line.
    """
    try:
        import yt_dlp
    except ImportError:
        die("yt-dlp is not installed. Run:  pip install yt-dlp")

    downloads = config.ROOT / "downloads"
    downloads.mkdir(exist_ok=True)
    log(f"Downloading video from {url} ...")

    R = config.DL_MAX_RES

    # Minimal progress: print at most every ~20%, plus a done line.
    last = {"pct": -20}
    def _hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            if total:
                pct = int(done * 100 / total)
                if pct >= last["pct"] + 20:
                    last["pct"] = pct
                    mb = total / 1048576
                    log(f"  downloading... {pct}%  (~{mb:.0f} MB)")
        elif d.get("status") == "finished":
            log("  download complete, finishing up...")

    base_opts = {
        "format_sort": ["res:1080", "ext:mp4:m4a"],
        "merge_output_format": "mp4",
        # merge AV1 video + m4a audio with the same modern ffmpeg the engine uses
        "ffmpeg_location": str(Path(FFMPEG).parent),
        "outtmpl": str(downloads / "%(title).80s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,           # no verbose yt-dlp chatter
        "no_warnings": True,
        "noprogress": True,      # suppress the per-second progress bar
        "progress_hooks": [_hook],
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        # Use normal clients (not the "tv downgraded" one that 403s), and allow
        # formats that lack a PO token.
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "android", "ios", "web_safari", "mweb"],
                "formats": ["missing_pot"],
            }
        },
    }

    # Profile 1 = efficient, ~Rp-capped separate streams (small; portrait-safe via
    # the width clause). Profile 2 = combined fallback only if 403 forces it.
    format_profiles = [
        (f"bv*[height<={R}]+ba/bv*[width<={R}]+ba/"
         f"b[height<={R}]/b[width<={R}]/b"),
        "b/best",
    ]

    # Auth order: cookies.txt (if present) -> anonymous -> browser cookies.
    browsers = []
    for b in [config.YT_BROWSER.strip().lower(),
              "chrome", "edge", "firefox", "brave", "opera"]:
        if b and b not in browsers:
            browsers.append(b)
    cookie_attempts = [None] + browsers
    cookiefile = config.ROOT / "cookies.txt"
    if cookiefile.exists():
        log("Found cookies.txt - using it for YouTube authentication.")
        cookie_attempts = ["cookies.txt"] + cookie_attempts

    def _is_auth_wall(msg: str) -> bool:
        return any(k in msg for k in ("sign in", "not a bot", "cookies", "cookie"))

    def _is_403(msg: str) -> bool:
        return any(k in msg for k in ("403", "forbidden", "unable to download video data",
                                      "fragment", "sabr"))

    info = file = last_err = None
    for cookie in cookie_attempts:
        cookie_opts = {}
        if cookie == "cookies.txt":
            cookie_opts["cookiefile"] = str(cookiefile)
        elif cookie:
            log(f"YouTube wants a sign-in. Retrying with {cookie} cookies...")
            cookie_opts["cookiesfrombrowser"] = (cookie,)

        needs_cookies = False
        for fmt in format_profiles:
            opts = dict(base_opts, format=fmt, **cookie_opts)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
                break
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                if _is_auth_wall(msg):
                    needs_cookies = True
                    break                      # need different cookies
                if _is_403(msg):
                    log("  download blocked (403); trying a fallback format...")
                    needs_cookies = True       # 403 often clears with cookies too
                    continue                   # try next format profile first
                raise                          # unrelated error - surface it
        if info is not None:
            break
        if not needs_cookies:
            break

    if info is None:
        die(
            "Could not download the video.\n"
            "  If it is a YouTube 'sign in to confirm' block:\n"
            "    1. Be logged into YouTube in your browser, set YT_BROWSER in .env.\n"
            "    2. Or export cookies with the 'Get cookies.txt LOCALLY' extension\n"
            "       and save them as cookies.txt in the viral-clip-engine folder.\n"
            "  If it is an HTTP 403 / SABR block, update yt-dlp:\n"
            "    python -m pip install -U \"yt-dlp[default]\"\n"
            "  Or download the video manually and run:\n"
            "    python run.py path\\to\\downloaded-video.mp4\n"
            f"  Last error: {last_err}"
        )

    if not file.exists():
        # fallback: yt-dlp may keep the original extension
        candidates = sorted((p for p in downloads.iterdir() if info["id"] in p.name),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            die("Download finished but the file was not found in downloads/")
        file = candidates[0]

    size_mb = file.stat().st_size / 1048576
    log(f"Downloaded -> {file.name}  ({size_mb:.0f} MB)")
    return file


def resolve_input(arg: str | None) -> Path:
    """Turn a CLI arg or interactive prompt answer into a local video path."""
    if not arg:
        print()
        print("  Paste a YouTube link (or any video URL),")
        print("  or the path to a video file on your computer.")
        print("  Tip: drag the video file into this window to paste its path.")
        print()
        arg = input("  Video link or path: ")

    arg = _clean_path(arg)
    if not arg:
        die("No input given.")

    if _is_url(arg):
        url = arg if arg.startswith("http") else "https://" + arg
        return download_video(url)

    video = Path(arg).expanduser().resolve()
    if not video.exists():
        die(f"Video not found: {video}")
    return video
