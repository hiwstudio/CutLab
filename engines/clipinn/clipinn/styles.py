"""Output layout styles — the one place that knows how a 9:16 frame is built.
Ported from VCE (stable): blur / center / split / face.

A Render tells the caller everything ffmpeg needs:
  inputs   extra ffmpeg input args (main video is always input 0)
  fc       filter_complex string ending in [v]
  hook_box px height of the top band a caption may use (None = default)
  out_args extra output args   temp  files to delete after the render
"""
from collections import namedtuple
from pathlib import Path

from . import config, fonts
from .utils import log, probe_size, run_ffmpeg

Render = namedtuple("Render", "inputs fc hook_box out_args temp")


def _render(fc, inputs=(), hook_box=None, out_args=(), temp=()):
    return Render(list(inputs), fc, hook_box, list(out_args), list(temp))


def build(video: Path, ass_name: str, *, start: float = 0.0, end: float = None,
          workdir: Path = None, split_image: Path = None) -> Render:
    name = config.STYLE.strip().lower()
    style = STYLES.get(name)
    if style is None:
        raise ValueError(f"Unknown style '{name}'. Available: {', '.join(STYLES)}")
    kwargs = {"custom_image": split_image} if name == "split" and split_image else {}
    return style(video, ass_name, start, end, workdir, **kwargs)


def describe() -> list:
    return [(n, f.__doc__.splitlines()[0]) for n, f in STYLES.items()]


def _blur_geometry(video):
    """(top_band, fg_filter) for the blur layout.

    Landscape sources fill a centered band of BLUR_VIDEO_PCT of the frame
    height (25/50/25 by default), cover-cropped left/right to gain the height.
    Portrait/square sources are fitted to width instead - cropping them to a
    half-height band would throw away half the picture."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    try:
        sw, sh = probe_size(video)
    except Exception:
        sw, sh = 16, 9  # safe default for landscape

    if sw > sh:
        band_h = min(h, int(round(h * config.BLUR_VIDEO_PCT / 2) * 2))
        return ((h - band_h) // 2,
                f"[fg]scale={w}:{band_h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{band_h}[fgs];")
    fg_h = int(round(sh * (w / sw) / 2) * 2)
    return max(0, (h - fg_h) // 2), f"[fg]scale={w}:-2[fgs];"


def _blur(video, ass_name, start, end, workdir):
    """Blurred background: video centered over a blurred zoomed copy."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    top_band, fg = _blur_geometry(video)
    log(f"Blur layout: video band {h - 2 * top_band}px "
        f"({100 * (h - 2 * top_band) / h:.0f}% of height), "
        f"blurred {top_band}px top & bottom.")
    fc = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur=24:4[bgb];"
        f"{fg}"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc, hook_box=top_band)


def _original(video, ass_name, start, end, workdir):
    """Original format: keep the source frame, no vertical reframe."""
    # The ASS canvas comes from config.OUT_WIDTH/HEIGHT, so without this the subtitle
    # positions would be computed against a 1080x1920 frame and land off-picture on a
    # 16:9 clip. styles.build() runs before build_ass(), so setting it here is read
    # back in time. Callers that reuse this module across runs must restore these.
    w, h = probe_size(video)
    if w and h:
        config.OUT_WIDTH, config.OUT_HEIGHT = w, h
    log(f"Original format: keeping source {config.OUT_WIDTH}x{config.OUT_HEIGHT}.")
    return _render(f"[0:v]ass={ass_name}{fonts.fontsdir_suffix()}[v]")


def _center(video, ass_name, start, end, workdir):
    """Center crop: fill the whole 9:16 frame from the middle of the video."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    fc = (
        f"[0:v]crop=if(gte(iw/ih\\,9/16)\\,ih*9/16\\,iw):"
        f"if(gte(iw/ih\\,9/16)\\,ih\\,iw*16/9),"
        f"scale={w}:{h},ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc)


def _split(video, ass_name, start, end, workdir, custom_image=None):
    """Split screen: video plays on top, a still from the video below."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    ratio = max(0.1, min(0.9, config.SPLIT_RATIO))
    video_h = int(h * ratio)
    still_h = h - video_h
    if custom_image:
        shot = Path(custom_image)
    else:
        mid = (start + (end or start)) / 2
        shot = (workdir or video.parent) / f"{Path(ass_name).stem}.shot.png"
        if not shot.exists():
            run_ffmpeg(["-ss", f"{mid:.2f}", "-i", str(video),
                        "-frames:v", "1", str(shot)], desc="split screenshot")
    fc = (
        f"[0:v]scale={w}:{video_h}:force_original_aspect_ratio=increase,crop={w}:{video_h}[top];"
        f"[1:v]scale={w}:{still_h}:force_original_aspect_ratio=increase,crop={w}:{still_h}[bot];"
        f"[top][bot]vstack=shortest=1,ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc, inputs=["-loop", "1", "-i", str(shot)],
                   out_args=["-shortest"], temp=[shot] if not custom_image else [])


FACE_SAMPLE_S = 0.5
FACE_KEY_S = 1.0
FACE_DEAD_ZONE = 0.05
FACE_ALPHA = 0.25


def _detect_faces(video: Path, start: float, end: float) -> tuple:
    try:
        import cv2
    except ImportError:
        raise RuntimeError("The 'face' style needs OpenCV: pip install opencv-python")
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(video))
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    pts, last_cx, t = [], None, start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        scale = 480.0 / frame.shape[1]
        small = cv2.resize(frame, (480, int(frame.shape[0] * scale)))
        faces = cascade.detectMultiScale(
            cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.2, 5, minSize=(36, 36))
        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            last_cx = (x + fw / 2) / scale
        if last_cx is not None:
            pts.append((round(t - start, 2), last_cx))
        t += FACE_SAMPLE_S
    cap.release()
    return pts, width


def smooth_track(pts: list, width: float,
                 dead: float = FACE_DEAD_ZONE, alpha: float = FACE_ALPHA) -> list:
    if not pts:
        return []
    cam = pts[0][1]
    out = []
    for t, cx in pts:
        if abs(cx - cam) > dead * width:
            cam += alpha * (cx - cam)
        out.append((t, cam))
    kept, next_t = [], 0.0
    for t, x in out:
        if t >= next_t:
            kept.append((t, round(x, 1)))
            next_t = t + FACE_KEY_S
    if kept[-1] != out[-1]:
        kept.append((out[-1][0], round(out[-1][1], 1)))
    return kept


def piecewise(pts: list) -> str:
    if len(pts) == 1:
        return str(pts[0][1])
    terms = []
    for (t0, x0), (t1, x1) in zip(pts, pts[1:]):
        seg = f"({x0}+({x1}-{x0})*(t-{t0})/{t1 - t0})"
        terms.append(f"(gte(t,{t0})*lt(t,{t1}))*{seg}")
    terms.append(f"gte(t,{pts[-1][0]})*{pts[-1][1]}")
    return "+".join(terms)


def _face(video, ass_name, start, end, workdir):
    """Smart reframe: full-frame 9:16 crop that follows the main face."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    sw, sh = probe_size(video)
    crop_w = min(sw, int(sh * 9 / 16 / 2) * 2)
    log("Tracking faces (samples the whole clip)...")
    pts, det_w = _detect_faces(video, start, end or start)
    if not pts:
        log("No face found — falling back to a static center crop.")
        return _center(video, ass_name, start, end, workdir)
    track = smooth_track(pts, det_w or sw)
    lo, hi = 0, sw - crop_w
    xs = [(t, round(min(hi, max(lo, x - crop_w / 2)), 1)) for t, x in track]
    fc = (
        f"[0:v]crop={crop_w}:{sh}:x='{piecewise(xs)}':y=0,"
        f"scale={w}:{h},ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc)


STYLES = {"blur": _blur, "center": _center, "split": _split, "face": _face,
          "original": _original}
