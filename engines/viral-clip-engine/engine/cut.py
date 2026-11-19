"""Step 4-5: cut each moment into a 9:16 clip with burned-in subtitles.

The frame layout comes from the active style (engine/styles.py, config.STYLE):
blur / center / split / face - picked via the menu or --style.
"""
from pathlib import Path

import config
from engine import fonts, styles
from engine.metadata import write_caption_file
from engine.subtitles import build_ass
from engine.utils import log, run_ffmpeg, safe_slug


def cut_clips(video: Path, transcript: dict, moments: list, workdir: Path,
               overlay_on: bool = True, split_image: Path = None,
               no_text: bool = False, subtitles_on: bool = True) -> list:
    """Render every moment to clips/NN-slug.mp4. Returns updated moments
    with a 'file' key. Skips clips that already exist (cache-friendly).
    no_text=True produces clean clips without any burned text (for Remotion)."""
    clips_dir = workdir / "clips"
    clips_dir.mkdir(exist_ok=True)
    segments = transcript["segments"]
    fonts.install_into(clips_dir)
    text_label = "none (Remotion)" if no_text else ("on" if overlay_on else "off")
    log(f"Rendering clips (style: {config.STYLE})  |  "
        f"Top caption: {text_label}")

    for i, m in enumerate(moments, 1):
        name = f"{i:02d}-{safe_slug(m.get('title', f'clip-{i}'))}"
        out_file = clips_dir / f"{name}.mp4"
        m["file"] = f"clips/{out_file.name}"
        if out_file.exists():
            log(f"  [{i}/{len(moments)}] exists, skipping: {out_file.name}")
            continue

        social = (m.get("caption", "").strip() + "\n\n" +
                  " ".join(m.get("hashtags", []))).strip()
        write_caption_file(clips_dir / f"{name}.txt", m.get("hook", ""),
                           social, overlay_on)

        if no_text:
            # Build render without subtitle burn; ASS file not needed
            ass_file = clips_dir / f"{name}.ass"
            r = styles.build(video, ass_file.name, start=m["start"], end=m["end"],
                             workdir=clips_dir, split_image=split_image,
                             no_text=True)
        else:
            ass_file = clips_dir / f"{name}.ass"
            r = styles.build(video, ass_file.name, start=m["start"], end=m["end"],
                             workdir=clips_dir, split_image=split_image)
            hook_text = m.get("hook", "") if overlay_on else ""
            build_ass(segments, m["start"], m["end"], hook_text, ass_file,
                      hook_persist=True, hook_box=r.hook_box,
                      subtitles_on=subtitles_on)

        log(f"  [{i}/{len(moments)}] rendering {out_file.name} "
            f"({m['end'] - m['start']:.0f}s)...")
        run_ffmpeg(
            [
                "-ss", str(m["start"]), "-to", str(m["end"]),
                "-i", str(video), *r.inputs,
                "-filter_complex", r.fc,
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
                "-crf", str(config.VIDEO_CRF),
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", *r.out_args,
                out_file.name,
            ],
            desc=out_file.name,
            cwd=clips_dir,  # cwd trick: avoids Windows path-escaping issues in ass=
        )
        ass_file.unlink(missing_ok=True)
        for tmp in r.temp:
            Path(tmp).unlink(missing_ok=True)

    fonts.remove_from(clips_dir)
    log(f"Rendered {len(moments)} clips -> {clips_dir}")
    return moments
