"""Font registry + picker for captions/subtitles.

Drop .ttf/.otf files into the project's fonts/ folder and they become available
to pick at run time. Custom fonts are loaded via ffmpeg's ass `fontsdir`, so
they render even if they are not installed system-wide.
"""
import shutil
import struct
from pathlib import Path

import config
from engine.utils import log

# Built-in fonts assumed present on Windows (no file needed).
BUILTIN_FONTS = ["Arial", "Impact", "Verdana", "Georgia"]


def _read_font_family(path: Path) -> str | None:
    """Parse the OpenType 'name' table to get the font's family name.
    Returns None if it can't be read. Pure-python, no dependencies."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 12:
        return None
    tag = data[:4]
    if tag == b"ttcf":  # font collection - use first font's table dir
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
        ttag = data[rec:rec + 4]
        toff, tlen = struct.unpack(">II", data[rec + 8:rec + 16])
        if ttag == b"name":
            name_off, name_len = toff, tlen
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
        if name_id not in (1, 16):  # 1=family, 16=typographic family
            continue
        s = data[strings_base + offset: strings_base + offset + length]
        try:
            if platform == 3 or (platform == 0):
                text = s.decode("utf-16-be", "ignore")
            else:
                text = s.decode("latin-1", "ignore")
        except Exception:
            continue
        text = text.strip()
        if text:
            best[name_id] = text
    return best.get(16) or best.get(1)


def list_fonts() -> list:
    """Return available fonts: [{'name','family','file'}]. Built-ins first,
    then everything found in the fonts/ folder."""
    fonts = [{"name": f, "family": f, "file": None} for f in BUILTIN_FONTS]
    seen = {f["family"].lower() for f in fonts}
    fonts_dir = config.FONTS_DIR
    if fonts_dir.exists():
        for fp in sorted(fonts_dir.iterdir()):
            if fp.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            family = _read_font_family(fp) or fp.stem
            key = family.lower()
            entry = {"name": family, "family": family, "file": fp}
            if key in seen:
                # a folder font overrides a same-named builtin so the file is used
                fonts = [e for e in fonts if e["family"].lower() != key]
            fonts.append(entry)
            seen.add(key)
    return fonts


def choose_font(cli_font: str | None) -> dict:
    """Pick a font: honor --font if it matches, else show an interactive menu."""
    fonts = list_fonts()
    if cli_font:
        want = cli_font.strip().lower()
        for f in fonts:
            if f["family"].lower() == want or f["name"].lower() == want:
                return f
        log(f'Font "{cli_font}" not found; you will be asked to pick one.')

    print()
    print("  Which font for the captions/subtitles?")
    for i, f in enumerate(fonts, 1):
        src = "  (from fonts/ folder)" if f["file"] else ""
        print(f"    {i}. {f['name']}{src}")
    print()
    print("  Tip: drop a .ttf/.otf into the 'fonts' folder to add more")
    print("       (e.g. Wargod.ttf), then run again.")
    print()
    while True:
        choice = input(f"  Pick 1-{len(fonts)} (Enter for 1): ").strip()
        if choice == "":
            return fonts[0]
        if choice.isdigit() and 1 <= int(choice) <= len(fonts):
            return fonts[int(choice) - 1]
        print(f"  Please type a number 1-{len(fonts)}.")


def apply_font(entry: dict) -> None:
    """Make the chosen font active for this run."""
    config.SUB_FONT = entry["family"]
    config.ACTIVE_FONT_FILE = entry["file"]
    log(f'Using font: {entry["name"]}')


def install_into(render_dir: Path) -> bool:
    """Copy the active font file into render_dir (next to the .ass) so ffmpeg
    can load it via fontsdir=. Returns True if a custom font is in use."""
    fp = config.ACTIVE_FONT_FILE
    if not fp:
        return False
    dest = render_dir / Path(fp).name
    if not dest.exists():
        try:
            shutil.copy(str(fp), str(dest))
        except OSError as e:
            log(f"Could not copy font into render dir: {e}")
            return False
    return True


def remove_from(render_dir: Path) -> None:
    """Delete the font copy made by install_into once rendering is done,
    so it doesn't ship alongside the output files."""
    fp = config.ACTIVE_FONT_FILE
    if fp:
        (render_dir / Path(fp).name).unlink(missing_ok=True)


def fontsdir_suffix() -> str:
    """ASS filter suffix that tells libass to load fonts from the current dir."""
    return ":fontsdir=." if config.ACTIVE_FONT_FILE else ""
