"""Output layout styles - the one place that knows how a 9:16 frame is built.

Every style is a function (ctx -> Render) registered in STYLES. To add a new
style: write one function, add one dict entry, done - it becomes selectable
in the menu and via --style across clip/reframe/cut-reframe.

  blur    video centered in a 50%-height band, blurred zoomed copy above/below
  center  crop the center of the frame to 9:16 (static)
  split   video on top, a still frame from the video on the bottom
  face    9:16 crop that smoothly follows the main face (needs opencv-python)

A Render tells the caller everything ffmpeg needs:
  inputs     extra ffmpeg input args (main video is always input 0)
  fc         filter_complex string ending in [v]
  hook_box   px height of the top band the caption may use (None = default)
  out_args   extra output args (e.g. -shortest for looped still inputs)
  temp       files to delete after the render
"""
from collections import namedtuple
from pathlib import Path

import config
from engine import fonts
from engine.utils import log, probe_size, run_ffmpeg

Render = namedtuple("Render", "inputs fc hook_box out_args temp")

# sensible defaults so most styles only fill in what they need
def _render(fc, inputs=(), hook_box=None, out_args=(), temp=()):
    return Render(list(inputs), fc, hook_box, list(out_args), list(temp))


def build(video: Path, ass_name: str, *, start: float = 0.0, end: float = None,
          boxed: bool = False, workdir: Path = None, split_image: Path = None,
          no_text: bool = False) -> Render:
    """Build the render recipe for the active style (config.STYLE).

    boxed=True (reframe modes) reserves a caption band in blur mode so the
    persistent caption never sits on the video. start/end are source-video
    seconds of the segment being rendered (whole video for reframe).
    no_text=True strips the subtitle/caption burn so Remotion can add text."""
    name = config.STYLE.strip().lower()
    style = STYLES.get(name)
    if style is None:
        raise ValueError(f"Unknown style '{name}'. Available: {', '.join(STYLES)}")
    kwargs = {"custom_image": split_image} if name == "split" and split_image else {}
    r = style(video, ass_name, start, end, boxed, workdir, **kwargs)
    if no_text:
        import re
        fc = re.sub(r",ass=[^\[]+\[v\]", "[v]", r.fc)
        r = r._replace(fc=fc)
    return r


def describe() -> list:
    """[(name, one-line description)] for menus/help."""
    return [(n, f.__doc__.splitlines()[0]) for n, f in STYLES.items()]


# --------------------------------------------------------------- blur ---

def _blur_geometry(video: Path, boxed: bool):
    """(box_w, box_h, top_band, cover) for the blur layout.

    Landscape sources get a fixed slice of the frame height (BLUR_VIDEO_PCT,
    25/50/25 by default) filled edge to edge -> cover=True, which crops the
    left/right edges to buy the extra height.
    Portrait/square sources are fitted instead (cover=False): cropping them to
    a half-height band would throw away half the picture."""
    W, H = config.OUT_WIDTH, config.OUT_HEIGHT
    try:
        sw, sh = probe_size(video)
    except Exception:
        sw, sh = 16, 9  # safe default for landscape

    if sw > sh:
        band_h = min(H, int(round(H * config.BLUR_VIDEO_PCT / 2) * 2))
        return W, band_h, (H - band_h) // 2, True

    reserve = max(0, min(config.CAPTION_BAND_MIN, (H - 200) // 2)) if boxed else 0
    box_h = H - 2 * reserve
    fg_h = int(round(sh * min(W / sw, box_h / sh) / 2) * 2)
    return W, box_h, max(0, (H - fg_h) // 2), False


def _blur(video, ass_name, start, end, boxed, workdir):
    """Blurred background: video centered over a blurred zoomed copy."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    box_w, box_h, top_band, cover = _blur_geometry(video, boxed)
    if cover:
        fg = (f"[fg]scale={box_w}:{box_h}:force_original_aspect_ratio=increase,"
              f"crop={box_w}:{box_h}[fgs];")
        log(f"Blur layout: video band {box_h}px "
            f"({100 * box_h / h:.0f}% of height), blurred {top_band}px top & bottom.")
    else:
        fg = (f"[fg]scale={box_w}:{box_h}:force_original_aspect_ratio=decrease,"
              f"scale=trunc(iw/2)*2:trunc(ih/2)*2[fgs];")
        log(f"Blur layout: portrait source fitted to width; "
            f"caption band {top_band}px.")
    fc = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur=24:4[bgb];"
        f"{fg}"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc, hook_box=top_band)


# ------------------------------------------------------------- center ---

def _center(video, ass_name, start, end, boxed, workdir):
    """Center crop: fill the whole 9:16 frame from the middle of the video."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    fc = (
        f"[0:v]crop=if(gte(iw/ih\\,9/16)\\,ih*9/16\\,iw):"
        f"if(gte(iw/ih\\,9/16)\\,ih\\,iw*16/9),"
        f"scale={w}:{h},ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc)


# -------------------------------------------------------------- split ---

def _split(video, ass_name, start, end, boxed, workdir, custom_image=None):
    """Split screen: video plays on top, a still from the video below."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    ratio = getattr(config, 'SPLIT_RATIO', 0.5)
    ratio = max(0.1, min(0.9, ratio))  # clamp to 10%-90%
    video_h = int(h * ratio)
    still_h = h - video_h
    if custom_image:
        shot = Path(custom_image)
    else:
        mid = (start + (end or start)) / 2  # still frame from the segment middle
        shot = (workdir or video.parent) / f"{Path(ass_name).stem}.shot.png"
        if not shot.exists():
            run_ffmpeg(["-ss", f"{mid:.2f}", "-i", str(video),
                        "-frames:v", "1", str(shot)], desc="split screenshot")
    fill_vid = f"scale={w}:{video_h}:force_original_aspect_ratio=increase,crop={w}:{video_h}"
    fill_still = f"scale={w}:{still_h}:force_original_aspect_ratio=increase,crop={w}:{still_h}"
    fc = (
        f"[0:v]{fill_vid}[top];"
        f"[1:v]{fill_still}[bot];"
        f"[top][bot]vstack=shortest=1,ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc, inputs=["-loop", "1", "-i", str(shot)],
                   out_args=["-shortest"], temp=[shot])


# --------------------------------------------------------------- face ---

FACE_SAMPLE_S = 0.5     # detect a face every N seconds
FACE_KEY_S = 1.0        # keep a camera keyframe every N seconds
# ffmpeg crop x='...' piecewise expressions fail above ~95 segments (~5.5KB)
# on modern Gyan builds. Cap keys so long face-tracks still render.
FACE_MAX_KEYS = 80
FACE_DEAD_ZONE = 0.05   # ignore face drift smaller than this (frac of width)
FACE_ALPHA = 0.25       # how fast the camera catches up (0..1, lower=calmer)


def _select_face(faces, small_w: float, prefer: str = "largest"):
    """Pick one face (x, y, w, h) from OpenCV detections.

    prefer:
      largest - biggest box (default)
      right   - only faces on the right half of the frame (viewer POV); largest
                among those. Returns None if none on that side (hold last track).
      left    - same for the left half.
    """
    if faces is None or len(faces) == 0:
        return None
    faces = list(faces)
    prefer = (prefer or "largest").strip().lower()
    if prefer == "right":
        # 0.48 threshold: slight bias into center so a slightly-off-center guest
        # still counts as "right" without stealing pure-center hosts.
        side = [f for f in faces if (f[0] + f[2] / 2.0) >= small_w * 0.48]
        if not side:
            return None
        return max(side, key=lambda f: f[2] * f[3])
    if prefer == "left":
        side = [f for f in faces if (f[0] + f[2] / 2.0) <= small_w * 0.52]
        if not side:
            return None
        return max(side, key=lambda f: f[2] * f[3])
    return max(faces, key=lambda f: f[2] * f[3])


def _detect_faces(video: Path, start: float, end: float,
                  prefer: str = None) -> tuple:
    """Sample frames and track one face. Returns (points, width)
    where points = [(t_since_start, face_center_x_px), ...].

    prefer: largest | left | right (default config.FACE_PREFER). When left/right,
    only detections on that side of the frame update the track so a two-person
    interview does not flip between speakers.
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError(
            "The 'face' style needs OpenCV. Run:  pip install opencv-python")
    prefer = (prefer or getattr(config, "FACE_PREFER", "largest") or "largest")
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
        # detect on a small copy for speed
        scale = 480.0 / frame.shape[1]
        small = cv2.resize(frame, (480, int(frame.shape[0] * scale)))
        faces = cascade.detectMultiScale(
            cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.2, 5, minSize=(36, 36))
        picked = _select_face(faces, small.shape[1], prefer)
        if picked is not None:
            x, y, fw, fh = picked
            last_cx = (x + fw / 2) / scale
        if last_cx is not None:
            pts.append((round(t - start, 2), last_cx))
        t += FACE_SAMPLE_S
    cap.release()
    return pts, width


def smooth_track(pts: list, width: float,
                 dead: float = FACE_DEAD_ZONE, alpha: float = FACE_ALPHA,
                 max_keys: int = FACE_MAX_KEYS) -> list:
    """Cinematic smoothing: the camera only moves when the face leaves a
    dead zone, and then eases toward it instead of jumping."""
    if not pts:
        return []
    cam = pts[0][1]
    out = []
    for t, cx in pts:
        if abs(cx - cam) > dead * width:
            cam += alpha * (cx - cam)
        out.append((t, cam))
    # thin to keyframes so the ffmpeg expression stays small
    duration = max(0.001, out[-1][0] - out[0][0])
    # stretch key spacing on long segments so we never exceed FACE_MAX_KEYS
    key_s = max(FACE_KEY_S, duration / max(1, max_keys - 1))
    kept, next_t = [], out[0][0]
    for t, x in out:
        if t >= next_t:
            kept.append((t, round(x, 1)))
            next_t = t + key_s
    if kept[-1] != (out[-1][0], round(out[-1][1], 1)):
        kept.append((out[-1][0], round(out[-1][1], 1)))
    # hard cap (keeps endpoints, evenly samples the middle)
    if len(kept) > max_keys:
        mid = kept[1:-1]
        need = max_keys - 2
        step = len(mid) / need
        kept = ([kept[0]]
                + [mid[int(i * step)] for i in range(need)]
                + [kept[-1]])
    return kept


def piecewise(pts: list) -> str:
    """ffmpeg expression that linearly interpolates x between keyframes."""
    if len(pts) == 1:
        return str(pts[0][1])
    terms = []
    for (t0, x0), (t1, x1) in zip(pts, pts[1:]):
        seg = f"({x0}+({x1}-{x0})*(t-{t0})/{t1 - t0})"
        terms.append(f"(gte(t,{t0})*lt(t,{t1}))*{seg}")
    terms.append(f"gte(t,{pts[-1][0]})*{pts[-1][1]}")
    return "+".join(terms)


def _face(video, ass_name, start, end, boxed, workdir):
    """Smart reframe: full-frame 9:16 crop that follows the main face."""
    w, h = config.OUT_WIDTH, config.OUT_HEIGHT
    sw, sh = probe_size(video)
    crop_w = min(sw, int(sh * 9 / 16 / 2) * 2)
    prefer = getattr(config, "FACE_PREFER", "largest") or "largest"
    log(f"Tracking faces (prefer={prefer}; samples the whole segment)...")
    pts, det_w = _detect_faces(video, start, end or start, prefer=prefer)
    if not pts:
        log("No face found - falling back to a static center crop.")
        return _center(video, ass_name, start, end, boxed, workdir)
    track = smooth_track(pts, det_w or sw)
    # face center -> crop left edge, clamped inside the frame
    lo, hi = 0, sw - crop_w
    xs = [(t, round(min(hi, max(lo, x - crop_w / 2)), 1)) for t, x in track]
    # piecewise() is 0 before the first key - pin t=0 so the open isn't a hard cut left
    if xs and xs[0][0] > 0:
        xs = [(0.0, xs[0][1])] + xs
    log(f"Face track: {len(pts)} samples -> {len(xs)} camera keyframes.")
    fc = (
        f"[0:v]crop={crop_w}:{sh}:x='{piecewise(xs)}':y=0,"
        f"scale={w}:{h},ass={ass_name}{fonts.fontsdir_suffix()}[v]"
    )
    return _render(fc)


STYLES = {
    "blur": _blur,
    "center": _center,
    "split": _split,
    "face": _face,
}
