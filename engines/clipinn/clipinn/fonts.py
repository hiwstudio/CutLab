"""Font registry — drop .ttf/.otf into fonts/ and they become selectable.
Ported unchanged from VCE (stable); loaded via ffmpeg ass fontsdir.
"""
import shutil
import struct
from pathlib import Path

from . import config
from .utils import log

BUILTIN_FONTS = ["Arial", "Impact", "Verdana", "Georgia"]


def _read_font_family(path: Path) -> str | None:
    """Parse the OpenType 'name' table for the family name (pure python)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 12:
        return None
    if data[:4] == b"ttcf":
        try:
            off = struct.unpack(">I", data[12:16])[0]
        except struct.error:
            return None
    else:
        off = 0
    try:
        num_tables = struct.unpack(">H", data[off + 4:off + 6])[0]
    except struct.error:
        return None
    name_off = name_len = None
    rec = off + 12
    for _ in range(num_tables):
        if rec + 16 > len(data):
            break
        if data[rec:rec + 4] == b"name":
            name_off, name_len = struct.unpack(">II", data[rec + 8:rec + 16])
            break
        rec += 16
    if name_off is None or name_off + 6 > len(data):
        return None
    count, str_off = struct.unpack(">HH", data[name_off + 2:name_off + 6])
    strings_base = name_off + str_off
    best = {}
    for i in range(count):
        r = name_off + 6 + i * 12
        if r + 12 > len(data):
            break
        platform, enc, lang, name_id, length, offset = struct.unpack(
            ">HHHHHH", data[r:r + 12])
        if name_id not in (1, 16):
            continue
        s = data[strings_base + offset: strings_base + offset + length]
        try:
            text = s.decode("utf-16-be", "ignore") if platform in (0, 3) \
                else s.decode("latin-1", "ignore")
        except Exception:
            continue
        if text.strip():
            best[name_id] = text.strip()
    return best.get(16) or best.get(1)


def list_fonts() -> list:
    fonts = [{"name": f, "family": f, "file": None} for f in BUILTIN_FONTS]
    seen = {f["family"].lower() for f in fonts}
    if config.FONTS_DIR.exists():
        for fp in sorted(config.FONTS_DIR.iterdir()):
            if fp.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            family = _read_font_family(fp) or fp.stem
            key = family.lower()
            if key in seen:
                fonts = [e for e in fonts if e["family"].lower() != key]
            fonts.append({"name": family, "family": family, "file": fp})
            seen.add(key)
    return fonts


def apply_font(name: str | None) -> None:
    """Activate a font by name (case-insensitive); default = first builtin."""
    fonts = list_fonts()
    entry = fonts[0]
    if name:
        want = name.strip().lower()
        match = next((f for f in fonts
                      if f["family"].lower() == want or f["name"].lower() == want), None)
        if match:
            entry = match
        else:
            log(f'Font "{name}" not found; using {entry["name"]}. '
                f'Available: {", ".join(f["name"] for f in fonts)}')
    config.SUB_FONT = entry["family"]
    config.ACTIVE_FONT_FILE = entry["file"]


def find_font(name: str | None) -> dict | None:
    """The registry entry for a font name or family (case-insensitive), else None."""
    want = (name or "").strip().lower()
    if not want:
        return None
    return next((f for f in list_fonts()
                 if f["family"].lower() == want or f["name"].lower() == want), None)


def _render_font_files() -> list:
    """Every custom font file this render needs: the job-wide font, plus any font a
    text look sets for the caption or the subtitles. Without the extras, the second
    layer's fonts/ face is missing from the render dir and silently falls back."""
    files = [config.ACTIVE_FONT_FILE] if config.ACTIVE_FONT_FILE else []
    style = getattr(config, "TEXT_STYLE", None) or {}
    for layer in ("caption", "subtitles"):
        entry = find_font((style.get(layer) or {}).get("font"))
        if entry and entry["file"] and entry["file"] not in files:
            files.append(entry["file"])
    return files


def install_into(render_dir: Path) -> None:
    for fp in _render_font_files():
        dest = render_dir / Path(fp).name
        if not dest.exists():
            try:
                shutil.copy(str(fp), str(dest))
            except OSError as e:
                log(f"Could not copy font into render dir: {e}")


def remove_from(render_dir: Path) -> None:
    for fp in _render_font_files():
        (render_dir / Path(fp).name).unlink(missing_ok=True)


def fontsdir_suffix() -> str:
    return ":fontsdir=." if _render_font_files() else ""
