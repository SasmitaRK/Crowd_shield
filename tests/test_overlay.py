import numpy as np
import pytest

pytest.importorskip("cv2")  # the minimal "core" CI job has no OpenCV; the "app" job runs these

from crowdshield.detection import render_overlay  # noqa: E402


def test_head_dots_are_big_and_see_through():
    img = np.full((600, 800, 3), 100, np.uint8)
    out = render_overlay(img, [], [], None, [(300, 400)])
    radius = max(5, round(600 / 110))
    ring = out[300, 400 + radius].astype(int)
    assert ring.min() > 200                    # a white ring marks the dot's edge, 5 px out
    centre = out[300, 400].astype(int)
    assert centre[1] > centre[0] and centre.tolist() != [0, 255, 0]   # green, but blended, not solid


def test_no_points_means_no_dots():
    img = np.full((60, 80, 3), 100, np.uint8)
    out = render_overlay(img, [], [], None, [])
    assert out.shape == img.shape
