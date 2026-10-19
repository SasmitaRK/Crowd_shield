"""Read crowd movement from video with dense optical flow.

Optical flow estimates how far every pixel moved between two frames. From it
we get how fast the crowd moves, whether people move together or in
conflicting directions, and how chaotic the movement is. A crowd that
suddenly moves much faster than its own normal pace is an early sign of
panic, before any zone is over its density limit.
"""

from __future__ import annotations

import numpy as np

# Pixels moving less than this per frame count as still (camera noise, shimmer).
MOVING_PX = 0.5


def optical_flow(prev_gray: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Farneback dense flow: an H x W x 2 array of (dx, dy) per pixel, in pixels per frame."""
    import cv2

    return cv2.calcOpticalFlowFarneback(prev_gray, gray, None, pyr_scale=0.5, levels=3,
                                        winsize=15, iterations=3, poly_n=5,
                                        poly_sigma=1.2, flags=0)


def flow_stats(flow: np.ndarray, mask: np.ndarray | None = None, grid: int = 8) -> dict:
    """Summarise one flow field.

    speed       mean speed of the moving pixels, in pixels per frame
    moving      share of pixels that move
    coherence   1 when everything moves the same way, near 0 when directions cancel out
    turbulence  velocity variance inside grid cells, averaged over cells with movement;
                multiplied by density, this is Helbing's "crowd pressure"
    """
    fx, fy = flow[..., 0], flow[..., 1]
    mag = np.hypot(fx, fy)
    valid = np.ones(mag.shape, dtype=bool) if mask is None else mask
    moving = valid & (mag > MOVING_PX)
    n_moving = int(moving.sum())
    if n_moving == 0:
        return {"speed": 0.0, "moving": 0.0, "coherence": 0.0, "turbulence": 0.0}

    ux, uy = fx[moving] / mag[moving], fy[moving] / mag[moving]
    h, w = mag.shape
    ch, cw = max(1, h // grid), max(1, w // grid)
    cell_var = []
    for y in range(0, h - ch + 1, ch):
        for x in range(0, w - cw + 1, cw):
            cell = moving[y:y + ch, x:x + cw]
            if cell.sum() >= 10:
                cell_var.append(fx[y:y + ch, x:x + cw][cell].var()
                                + fy[y:y + ch, x:x + cw][cell].var())
    return {
        "speed":      float(mag[moving].mean()),
        "moving":     n_moving / int(valid.sum()),
        "coherence":  float(np.hypot(ux.mean(), uy.mean())),
        "turbulence": float(np.mean(cell_var)) if cell_var else 0.0,
    }


class SpeedAlarm:
    """Raise an alarm when the crowd moves much faster than its own normal pace.

    The first `baseline_frames` frames set the normal pace (their median speed).
    After that, an alarm fires once speed stays above `ratio` x normal for
    `hold_frames` frames in a row, and re-arms after speed stays back below it
    for the same number of frames. At 30 fps the defaults mean "3 seconds to
    learn the scene, then twice the normal speed for half a second".
    """

    def __init__(self, baseline_frames: int = 90, ratio: float = 2.0, hold_frames: int = 15):
        self.baseline_frames = baseline_frames
        self.ratio = ratio
        self.hold_frames = hold_frames
        self._baseline: list[float] = []
        self.normal: float | None = None
        self._above = 0
        self._below = 0
        self.active = False

    def update(self, speed: float) -> bool:
        """Feed one frame's speed; returns True only on the frame an alarm starts."""
        if self.normal is None:
            self._baseline.append(speed)
            if len(self._baseline) >= self.baseline_frames:
                self.normal = max(float(np.median(self._baseline)), 1e-6)
            return False

        fast = speed > self.ratio * self.normal
        self._above = self._above + 1 if fast else 0
        self._below = 0 if fast else self._below + 1
        if not self.active and self._above >= self.hold_frames:
            self.active = True
            return True
        if self.active and self._below >= self.hold_frames:
            self.active = False
        return False
