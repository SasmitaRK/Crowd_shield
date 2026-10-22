"""Crowd counting with head points: PET, fine-tuned on ShanghaiTech A + B.

PET (Liu et al., ICCV 2023) puts one point on each head it finds, so it gives
both the count and where every person is. On the ShanghaiTech test photos it
was the most accurate counter we tried (see results/shanghaitech).

The raw count is passed through one correction, true ≈ 1.375 × raw^0.942,
fitted on the 70 held-out training photos (never on test photos). It trims
PET's overcounting in packed crowds and its undercounting on streets.
"""

from __future__ import annotations

import os
from argparse import Namespace
from functools import lru_cache

import numpy as np

from .config import REPO_ROOT, default_max_side, fit_max_side
from .weights import RELEASES, fetch

WEIGHTS = REPO_ROOT / "models" / "pet_shab.pth"
WEIGHTS_URL = f"{RELEASES}/pet-shab-v1/pet_shab.pth"
WEIGHTS_SHA256 = "5a7c6590e61938e42c6b3a2bbde5fbec34ee7eb8b2c9cae0fdba2a45d8437595"
CORRECTION = (1.375, 0.942)  # true ≈ a * raw ** b, fitted on held-out training photos
MAX_SIDE = default_max_side()  # 2048, or less on a small server (see config.py)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# The settings PET was trained with (its train.sh).
_ARGS = dict(backbone="vgg16_bn", position_embedding="sine", dec_layers=2,
             dim_feedforward=512, hidden_dim=256, dropout=0.0, nheads=8,
             set_cost_class=1.0, set_cost_point=0.05, ce_loss_coef=1.0,
             point_loss_coef=5.0, eos_coef=0.5)


def corrected_count(raw: float) -> float:
    a, b = CORRECTION
    return float(a * raw ** b) if raw > 0 else 0.0


def build_model(device: str = "cpu"):
    from .pet.models import build_pet

    model, _ = build_pet(Namespace(**_ARGS, device=device))
    return model


@lru_cache(maxsize=1)
def load_point_model():
    """The trained PET model on the GPU if there is one, else the CPU."""
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    path = fetch(WEIGHTS, WEIGHTS_URL, WEIGHTS_SHA256)
    model = build_model(device)
    state = torch.load(path, map_location="cpu", weights_only=False)["model"]
    model.load_state_dict(state)
    return model.to(device).eval(), device


def points_from_model(model, device: str, img_bgr: np.ndarray) -> np.ndarray:
    """Head points (N x 2, row then column, in the given image's pixels)."""
    import torch

    from .pet.util.misc import nested_tensor_from_tensor_list

    rgb = img_bgr[:, :, ::-1].astype(np.float32) / 255.0
    x = torch.from_numpy(((rgb - _MEAN) / _STD).transpose(2, 0, 1).copy())
    with torch.no_grad():
        samples = nested_tensor_from_tensor_list([x]).to(device)
        out = model(samples, test=True)
    h, w = samples.tensors.shape[-2:]
    pts = out["pred_points"][0].cpu().numpy().reshape(-1, 2)
    return pts * np.array([h, w], dtype=float)


def count_points(img_bgr: np.ndarray) -> dict:
    """Count people in a BGR photo: corrected count, raw count and head points."""
    import cv2

    model, device = load_point_model()
    scale = min(1.0, fit_max_side(ceiling=MAX_SIDE) / max(img_bgr.shape[:2]))
    small = img_bgr if scale == 1.0 else cv2.resize(img_bgr, None, fx=scale, fy=scale,
                                                    interpolation=cv2.INTER_AREA)
    pts = points_from_model(model, device, small) / scale
    return {"count": corrected_count(len(pts)), "raw_count": len(pts), "points": pts}


def point_grid(frame_bgr: np.ndarray) -> np.ndarray:
    """Counter for the video monitor: a 1/8-size grid of head points, scaled to the corrected count."""
    from .monitor import points_to_grid

    out = count_points(frame_bgr)
    grid = points_to_grid(out["points"], frame_bgr.shape)
    if out["raw_count"]:
        grid *= out["count"] / out["raw_count"]
    return grid
