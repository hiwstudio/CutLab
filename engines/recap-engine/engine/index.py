"""Stage: footage understanding -> scene_cards.json (+ scene_embeddings.npz).

For every detected scene we build a "scene card" so later stages can match
narration to the right footage:
  - dialogue: the transcript text spoken during the scene's time window,
  - has_dialogue: whether the scene is talky or essentially visual,
  - keyframe: a representative frame extracted from the middle of the scene,
  - embeddings (stored separately in scene_embeddings.npz, aligned by index):
      * clip_image  - the keyframe in CLIP's joint image<->text space, so even a
                      silent/action scene is matchable to narration,
      * dialogue_text - the dialogue in the text-similarity space (zeros when the
                      scene has no usable dialogue).

All local + free (onnxruntime via engine.embed). Cached on disk; rerun resumes.
"""
import json
from pathlib import Path

import numpy as np

import config
from engine import embed
from engine.utils import log, run_ffmpeg


def build_scene_cards(scenes: list, transcript: dict, video: Path,
                      workdir: Path) -> list:
    """Build scene_cards.json + scene_embeddings.npz for all scenes."""
    cards_path = workdir / "scene_cards.json"
    emb_path = workdir / "scene_embeddings.npz"
    if cards_path.exists() and emb_path.exists():
        log("scene_cards.json already exists, skipping footage indexing")
        return json.loads(cards_path.read_text(encoding="utf-8"))

    frames_dir = workdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    segments = transcript.get("segments", [])

    cards, keyframes, dialogues = [], [], []
    for sc in scenes:
        text, wc = _dialogue_in_window(segments, sc["start"], sc["end"])
        jpg = frames_dir / f"scene_{sc['index']:04d}.jpg"
        if not jpg.exists():
            _extract_keyframe(video, (sc["start"] + sc["end"]) / 2.0, jpg)
        cards.append({
            "index": sc["index"],
            "start": sc["start"],
            "end": sc["end"],
            "dialogue": text,
            "word_count": wc,
            "has_dialogue": wc >= config.DIALOGUE_MIN_WORDS,
            "keyframe": str(jpg.relative_to(workdir)).replace("\\", "/"),
        })
        keyframes.append(jpg)
        dialogues.append(text)

    log(f"Footage index: embedding {len(cards)} keyframes (CLIP) "
        f"+ dialogue...")
    clip_image = embed.clip_image_embed(keyframes)
    dialogue_text = _embed_dialogue(dialogues)

    np.savez(emb_path,
             index=np.array([c["index"] for c in cards], dtype="int32"),
             clip_image=clip_image.astype("float32"),
             dialogue_text=dialogue_text.astype("float32"))
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    visual = sum(1 for c in cards if not c["has_dialogue"])
    log(f"Footage index: {len(cards)} scene cards "
        f"({visual} mostly-visual, {len(cards) - visual} with dialogue).")
    return cards


def load_embeddings(workdir: Path) -> dict:
    """Load scene_embeddings.npz as {'index','clip_image','dialogue_text'}."""
    data = np.load(workdir / "scene_embeddings.npz")
    return {k: data[k] for k in data.files}


def _dialogue_in_window(segments: list, start: float, end: float) -> tuple:
    """Concatenate transcript text that overlaps [start, end); return
    (text, word_count). A segment counts if it overlaps the window at all."""
    parts = []
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end:
            continue
        t = seg.get("text", "").strip()
        if t:
            parts.append(t)
    text = " ".join(parts).strip()
    return text, len(text.split())


def _embed_dialogue(dialogues: list) -> np.ndarray:
    """Embed non-empty dialogue in the text space; zero-vector for empty scenes
    (no dialogue signal) while keeping every row aligned by scene index."""
    nonempty_idx = [i for i, d in enumerate(dialogues) if d.strip()]
    if not nonempty_idx:
        # degenerate: embed a probe just to learn the dim, then zero everything
        dim = embed.text_embed([" "]).shape[1]
        return np.zeros((len(dialogues), dim), dtype="float32")

    vecs = embed.text_embed([dialogues[i] for i in nonempty_idx])
    out = np.zeros((len(dialogues), vecs.shape[1]), dtype="float32")
    for row, i in enumerate(nonempty_idx):
        out[i] = vecs[row]
    return out


def _extract_keyframe(video: Path, t: float, out_jpg: Path) -> None:
    """Grab a single frame at time t, downscaled for CLIP (fast -ss seek)."""
    run_ffmpeg(
        ["-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"scale={config.KEYFRAME_WIDTH}:-2", "-q:v", "3", str(out_jpg)],
        desc=f"keyframe @ {t:.1f}s",
    )
