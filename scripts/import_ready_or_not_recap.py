"""Import a Recap Engine output as an editable CutLab project.

The recap engine output is read-only.  This importer separates the final video
and narration mix, registers both through CutLab's durable ingest jobs, and
reconstructs each beat as a scene, linked clips, and a caption.
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/server"))

from cutlab.config import FFMPEG, FFPROBE

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--source",
    type=Path,
    required=True,
    help="Recap Engine output directory containing the rendered segments and edit metadata",
)
SOURCE = parser.parse_args().source.expanduser().resolve()
if not SOURCE.is_dir():
    raise FileNotFoundError(f"Recap Engine output directory was not found: {SOURCE}")
OUT = ROOT / "data" / f"demo-recap-{SOURCE.name}"
OUT.mkdir(parents=True, exist_ok=True)
CHECKPOINT = OUT / "import-state.json"
state = (
    json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if CHECKPOINT.exists()
    else {"assets": {}}
)


def save() -> None:
    CHECKPOINT.write_text(json.dumps(state, indent=2), encoding="utf-8")


def api(path: str, body: dict | None = None):
    request = Request(
        "http://127.0.0.1:8787/api/v1/" + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8")) from error


def prepare(name: str, args: list[str]) -> Path:
    destination = OUT / name
    if destination.exists():
        return destination
    partial = destination.with_name("partial-" + name)
    subprocess.run(
        [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *args, str(partial)],
        check=True,
    )
    partial.replace(destination)
    return destination


def duration_ms(path: Path) -> int:
    value = subprocess.check_output(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    ).strip()
    return round(float(value) * 1000)


def ingest(project_id: str, path: Path) -> str:
    key = path.name
    if key not in state["assets"]:
        state["assets"][key] = api(
            f"projects/{project_id}/assets", {"path": str(path)}
        )
        save()
    result = state["assets"][key]
    for _ in range(900):
        job = api("jobs/" + result["job_id"])
        if job["state"] == "done":
            return result["asset_id"]
        if job["state"] in ("failed", "cancelled"):
            raise RuntimeError(job)
        time.sleep(2)
    raise TimeoutError(f"Ingest still running: {key}")


for required in ("recap.mp4", "edit.json", "outline.json"):
    if not (SOURCE / required).is_file():
        raise FileNotFoundError(SOURCE / required)

edit = json.loads((SOURCE / "edit.json").read_text(encoding="utf-8"))
outline = json.loads((SOURCE / "outline.json").read_text(encoding="utf-8"))
beats = sorted(edit, key=lambda beat: beat["order"])
titles = {
    int(beat["order"]): beat["title"]
    for beat in outline["beats"]
}
if not beats or len(titles) != len(beats):
    raise RuntimeError("Recap edit and outline must contain matching story beats")

video_path = prepare(
    "recap-video.mp4",
    ["-i", str(SOURCE / "recap.mp4"), "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart"],
)
audio_path = prepare(
    "recap-narration-mix.m4a",
    ["-i", str(SOURCE / "recap.mp4"), "-map", "0:a:0", "-c:a", "copy", "-vn"],
)

segment_paths = sorted((SOURCE / "segments").glob("seg_*.mp4"))
if len(segment_paths) != len(beats):
    raise RuntimeError(f"Expected {len(beats)} rendered segments, found {len(segment_paths)}")

boundaries = [0]
for segment in segment_paths:
    boundaries.append(boundaries[-1] + duration_ms(segment))
boundaries[-1] = duration_ms(video_path)

if "project_id" not in state:
    project = api(
        "projects",
        {
            "name": f"{SOURCE.name} · Recap",
            "canvas": {"width": 1920, "height": 1080, "fps": 24},
        },
    )
    state["project_id"] = project["id"]
    save()
project_id = state["project_id"]
print(f"Project: {project_id}", flush=True)

if not state.get("assembled"):
    print("Ingesting the complete recap video…", flush=True)
    video_asset = ingest(project_id, video_path)
    print("Ingesting the narration mix…", flush=True)
    audio_asset = ingest(project_id, audio_path)

    # Container duration rounding can differ by 1 ms between the stream-copy
    # video and AAC audio assets. Use their shared editable range so the final
    # linked scene validates atomically on both tracks.
    asset_rows = {row["asset_id"]: row for row in api(f"projects/{project_id}/assets")}
    boundaries[-1] = min(
        int(asset_rows[video_asset]["duration_ms"]),
        int(asset_rows[audio_asset]["duration_ms"]),
    )

    operations = []
    for track_id, kind, name, role in (
        ("trk_footage", "video", "Recap footage", "footage"),
        ("trk_voice", "audio", "Narration mix", "voiceover"),
        ("trk_caps", "caption", "Beat captions", "captions"),
    ):
        operations.append({"op": "add_track", "id": track_id, "kind": kind})
        operations.append(
            {"op": "set_track", "track": track_id, "name": name, "role": role}
        )

    for index, beat in enumerate(beats):
        start, end = boundaries[index], boundaries[index + 1]
        operations.extend(
            [
                {
                    "op": "add_scene",
                    "id": f"scn_b{index:03d}",
                    "title": titles[index],
                    "start_ms": start,
                    "end_ms": end,
                },
                {
                    "op": "add_clip",
                    "id": f"clp_v{index:03d}",
                    "track": "trk_footage",
                    "asset": video_asset,
                    "in_ms": start,
                    "out_ms": end,
                    "start_ms": start,
                },
                {
                    "op": "add_clip",
                    "id": f"clp_a{index:03d}",
                    "track": "trk_voice",
                    "asset": audio_asset,
                    "in_ms": start,
                    "out_ms": end,
                    "start_ms": start,
                },
                {
                    "op": "add_caption",
                    "id": f"clp_c{index:03d}",
                    "track": "trk_caps",
                    "text": beat["narration"],
                    "start_ms": start,
                    "end_ms": end,
                    "cap_style": "recap-beat",
                },
            ]
        )

    head = api(f"projects/{project_id}")["head_rev"]
    result = api(
        f"projects/{project_id}/apply",
        {"base_rev": head, "ops": operations, "mode": "commit"},
    )
    state.update({"assembled": True, "revision": result["rev"]})
    save()

    (OUT / "IMPORT-NOTES.md").write_text(
        f"# {SOURCE.name} recap in CutLab\n\n"
        f"Source: Recap Engine output `{SOURCE.name}`. The source "
        "project and its review state were not modified.\n\n"
        "The complete 9:28 finished picture and narration mix are separated "
        f"into independent CutLab tracks, then split into {len(beats)} story "
        "beats. Scene names and narration come from the recap outline/edit.\n\n"
        "Known source-bound limitation: recap-engine stores exact final picture "
        "as one rendered segment per narration beat. Shot construction inside a "
        "beat is therefore baked into that beat. The source also has no word-level "
        "narration timing map, so captions are honest beat-level ranges rather "
        "than invented word timings.\n",
        encoding="utf-8",
    )

print(f"Open http://localhost:3000/p/{project_id}", flush=True)
