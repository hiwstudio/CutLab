"""Local vision degradation — OpenCLIP frame–text scoring (no API, CPU).

Used only when no brain is available to fulfill verify_clip tasks and the
config degradation policy is 'local' (default policy is 'pause').
Requires: pip install open_clip_torch torch --extra-index-url (CPU wheels).
"""
from __future__ import annotations

from pathlib import Path


class LocalVisionUnavailable(RuntimeError):
    pass


_MODEL = None  # lazy singleton (model load is expensive)


def _load():
    global _MODEL
    if _MODEL is None:
        try:
            import open_clip  # type: ignore
            import torch  # type: ignore
        except ModuleNotFoundError as e:
            raise LocalVisionUnavailable(
                "open_clip_torch not installed — install it or set "
                "degradation policy to 'pause'") from e
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu")
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        _MODEL = (model, preprocess, tokenizer, torch)
    return _MODEL


def verify_frames(frames: list[Path], scene_text: str,
                  visual_intent: str) -> dict:
    """Score frames against the scene's visual intent. Returns a verify_clip
    result: {confidence: int 0-100, reason: str}."""
    model, preprocess, tokenizer, torch = _load()
    from PIL import Image  # type: ignore

    text = tokenizer([f"{visual_intent}. {scene_text}"[:300]])
    with torch.no_grad():
        tfeat = model.encode_text(text)
        tfeat /= tfeat.norm(dim=-1, keepdim=True)
        sims = []
        for f in frames:
            img = preprocess(Image.open(f)).unsqueeze(0)
            ifeat = model.encode_image(img)
            ifeat /= ifeat.norm(dim=-1, keepdim=True)
            sims.append(float((ifeat @ tfeat.T).item()))
    if not sims:
        return {"confidence": 0, "reason": "no frames to score"}
    # CLIP cosine similarities land roughly in [0.1, 0.4]; map to 0-100.
    peak = max(sims)
    confidence = max(0, min(100, int(round((peak - 0.10) / 0.25 * 100))))
    return {"confidence": confidence,
            "reason": f"OpenCLIP peak similarity {peak:.3f} over "
                      f"{len(sims)} frames (local degradation mode)"}
