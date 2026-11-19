"""Local, free embeddings via fastembed (onnxruntime backend, no torch).

Two spaces are used by the engine:
  - a text model (bge-small) for dialogue <-> narration similarity, and
  - CLIP (vision + text) for a joint image <-> text space, so narration can be
    matched to the most visually-relevant scene even with little/no dialogue.

Models are loaded lazily and cached as module singletons; the first call
downloads the ONNX weights via huggingface_hub. Every function returns a
float32 numpy array shaped (n, dim). These functions are deliberately small so
tests can monkeypatch them without any model download.
"""
import os

import numpy as np

import config
from engine.utils import die, log

# Windows without Developer Mode can't symlink the HF cache; the fallback works
# fine, so silence the noisy warning rather than alarm the user.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Force the classic LFS download path: the newer Xet/hf_transfer backends route
# through a CDN host that does not resolve on some networks and the download
# hangs. The standard resolve URL downloads fine.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
# Be patient on slow links so a large onnx file doesn't trip the default 10s
# read timeout and churn through retries (models are a one-time download).
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

_text_model = None
_clip_img_model = None
_clip_txt_model = None


def _require_fastembed():
    try:
        import fastembed  # noqa: F401
    except ImportError:
        die("fastembed is required for embeddings/vision (local, onnxruntime).\n"
            "  Run:  pip install fastembed")


def text_embed(texts: list) -> np.ndarray:
    """Embed text for dialogue<->narration similarity (bge-small space)."""
    global _text_model
    _require_fastembed()
    if _text_model is None:
        from fastembed import TextEmbedding
        log(f"[embed] loading text model {config.EMBED_TEXT_MODEL} ...")
        _text_model = TextEmbedding(config.EMBED_TEXT_MODEL,
                                    cache_dir=config.MODEL_CACHE_DIR)
    return np.asarray(list(_text_model.embed(list(texts))), dtype="float32")


def clip_image_embed(paths: list) -> np.ndarray:
    """Embed keyframe images into the CLIP joint space."""
    global _clip_img_model
    _require_fastembed()
    if _clip_img_model is None:
        from fastembed import ImageEmbedding
        log(f"[embed] loading CLIP vision model {config.CLIP_VISION_MODEL} ...")
        _clip_img_model = ImageEmbedding(config.CLIP_VISION_MODEL,
                                         cache_dir=config.MODEL_CACHE_DIR)
    return np.asarray(list(_clip_img_model.embed([str(p) for p in paths])),
                      dtype="float32")


def clip_text_embed(texts: list) -> np.ndarray:
    """Embed text into the CLIP joint space (same space as clip_image_embed)."""
    global _clip_txt_model
    _require_fastembed()
    if _clip_txt_model is None:
        from fastembed import TextEmbedding
        log(f"[embed] loading CLIP text model {config.CLIP_TEXT_MODEL} ...")
        _clip_txt_model = TextEmbedding(config.CLIP_TEXT_MODEL,
                                        cache_dir=config.MODEL_CACHE_DIR)
    return np.asarray(list(_clip_txt_model.embed(list(texts))), dtype="float32")


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity between every row of a and every row of b ->
    shape (len(a), len(b)). Safe against zero vectors."""
    a = np.atleast_2d(np.asarray(a, dtype="float32"))
    b = np.atleast_2d(np.asarray(b, dtype="float32"))
    an = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    bn = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return an @ bn.T
