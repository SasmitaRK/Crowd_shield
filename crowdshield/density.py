"""Density-map crowd counting with DM-Count (Wang et al., NeurIPS 2020, MIT licence).

Instead of drawing a box around each person, the model predicts a density map:
every pixel holds a fraction of a person, and the whole map sums to the head
count. That keeps working when bodies overlap, which is where detectors fail.
The network mirrors DM-Count's models.py so its trained weights load as-is.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import REPO_ROOT

DEFAULT_WEIGHTS = REPO_ROOT / "models" / "dmcount.pth"

# VGG19 convolution layers ("M" = 2x2 max-pool), configuration E without batch norm.
_VGG19 = [64, 64, "M", 128, 128, "M", 256, 256, 256, 256, "M",
          512, 512, 512, 512, "M", 512, 512, 512, 512]
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def build_model():
    """DM-Count's network: VGG19 features, 2x upsampling, then a small regression head."""
    import torch.nn as nn
    import torch.nn.functional as F

    class DMCount(nn.Module):
        def __init__(self):
            super().__init__()
            layers, channels = [], 3
            for v in _VGG19:
                if v == "M":
                    layers.append(nn.MaxPool2d(kernel_size=2, stride=2))
                else:
                    layers += [nn.Conv2d(channels, v, kernel_size=3, padding=1),
                               nn.ReLU(inplace=True)]
                    channels = v
            self.features = nn.Sequential(*layers)
            self.reg_layer = nn.Sequential(
                nn.Conv2d(512, 256, kernel_size=3, padding=1), nn.ReLU(inplace=True),
                nn.Conv2d(256, 128, kernel_size=3, padding=1), nn.ReLU(inplace=True),
            )
            self.density_layer = nn.Sequential(nn.Conv2d(128, 1, 1), nn.ReLU())

        def forward(self, x):
            x = F.interpolate(self.features(x), scale_factor=2, mode="bilinear",
                              align_corners=True)
            return self.density_layer(self.reg_layer(x))

    return DMCount()


@lru_cache(maxsize=2)
def load_density_model(weights: str = str(DEFAULT_WEIGHTS)):
    """Load trained weights onto the GPU if there is one, else the CPU."""
    import torch

    path = Path(weights)
    if not path.exists():
        raise FileNotFoundError(f"Density model weights not found: {path}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model()
    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    return model.to(device).eval(), device


def density_from_model(model, device: str, img_bgr: np.ndarray) -> np.ndarray:
    """Run the network on a BGR image; returns the density map at 1/8 resolution."""
    import torch

    rgb = img_bgr[:, :, ::-1].astype(np.float32) / 255.0
    x = torch.from_numpy(((rgb - _MEAN) / _STD).transpose(2, 0, 1).copy())
    with torch.no_grad():
        return model(x.unsqueeze(0).to(device))[0, 0].cpu().numpy()


def estimate_density(img_bgr: np.ndarray, weights: str | None = None) -> dict:
    """Count people in a BGR photo; the density map sums to the count."""
    model, device = load_density_model(str(weights or DEFAULT_WEIGHTS))
    density = density_from_model(model, device, img_bgr)
    return {"count": float(density.sum()), "density": density}
