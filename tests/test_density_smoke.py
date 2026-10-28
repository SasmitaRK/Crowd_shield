"""Checks the density network's shape maths. Skipped where PyTorch isn't installed."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from crowdshield.density import build_model, density_from_model  # noqa: E402


def test_density_map_is_one_eighth_size_and_never_negative():
    model = build_model().eval()
    img = np.random.default_rng(0).integers(0, 255, (256, 320, 3), dtype=np.uint8)
    density = density_from_model(model, "cpu", img)
    assert density.shape == (32, 40)
    assert (density >= 0).all()


def test_weights_from_dm_count_load_without_renaming():
    # DM-Count saves state_dict keys under features.*, reg_layer.* and density_layer.*
    keys = build_model().state_dict().keys()
    assert {k.split(".")[0] for k in keys} == {"features", "reg_layer", "density_layer"}
    assert "features.34.weight" in keys  # last VGG19 convolution


def test_trained_weights_download_and_count_a_frame():
    # Fetches the release weights (checksum-verified) the first time it runs.
    from crowdshield.density import density_grid, estimate_density

    frame = np.random.default_rng(1).integers(0, 255, (250, 333, 3), dtype=np.uint8)
    out = estimate_density(frame)
    assert np.isfinite(out["count"]) and out["count"] >= 0
    big = np.zeros((2600, 1300, 3), dtype=np.uint8)  # shrunk to 2048 px inside, then mapped back
    grid = density_grid(big)
    assert grid.shape == (2600 // 8, 1300 // 8)
