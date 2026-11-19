"""Local still-image subject cutout adapted from Mirage Studio's U2-Net engine."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def remove_background(source: Path, output: Path, model: Path, size: int = 320) -> None:
    import onnxruntime as ort

    if not model.is_file():
        raise FileNotFoundError(f"cutout model not found: {model}")
    bgr = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"could not read image: {source}")
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    peak = float(rgb.max())
    if peak > 0:
        rgb /= peak
    tensor = ((rgb - _MEAN) / _STD).transpose(2, 0, 1)[None].astype(np.float32)
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    pred = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    lo, hi = float(pred.min()), float(pred.max())
    alpha = cv2.resize(((pred - lo) / (hi - lo + 1e-8) * 255).astype(np.uint8),
                       (w, h), interpolation=cv2.INTER_LINEAR)
    alpha = np.where(alpha < 18, 0, alpha).astype(np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), np.dstack([bgr, alpha])):
        raise RuntimeError(f"could not write cutout: {output}")
