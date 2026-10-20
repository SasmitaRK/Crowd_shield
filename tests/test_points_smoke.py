"""Checks the point model (PET). The model test is skipped where PyTorch isn't installed."""

import numpy as np
import pytest

from crowdshield.points import CORRECTION, corrected_count


def test_correction_trims_big_counts_and_lifts_small_ones():
    assert corrected_count(0) == 0.0
    assert corrected_count(20) > 20      # streets: PET undercounted a little
    assert corrected_count(1000) < 1000  # packed crowds: PET overcounted
    a, b = CORRECTION
    assert corrected_count(100) == pytest.approx(a * 100 ** b)


def test_trained_point_model_finds_heads_in_a_frame():
    pytest.importorskip("torch")
    from crowdshield.points import count_points, point_grid

    frame = np.random.default_rng(2).integers(0, 255, (300, 400, 3), dtype=np.uint8)
    out = count_points(frame)  # downloads the release weights the first time
    assert out["points"].shape == (out["raw_count"], 2)
    assert np.isfinite(out["count"]) and out["count"] >= 0
    grid = point_grid(frame)
    assert grid.shape == (300 // 8, 400 // 8)
    assert grid.sum() == pytest.approx(out["count"], abs=1e-6)
