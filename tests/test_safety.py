import numpy as np
import pytest

from crowdshield.geometry import GroundCalibration
from crowdshield.safety import (_box_sum, crowd_pressure, density_level, density_per_m2,
                                zone_density)

# Straight-down camera where 1 pixel = 1 cm, so an 8 x 8 cell covers 0.0064 m².
TOP_DOWN = GroundCalibration([(0, 0), (100, 0), (100, 100), (0, 100)],
                             [(0, 0), (1, 0), (1, 1), (0, 1)])


def test_density_levels_follow_the_cited_thresholds():
    assert density_level(1.0) == "Normal"
    assert density_level(3.0) == "Crowded"
    assert density_level(5.5) == "Dangerous"
    assert density_level(8.0) == "Crush risk"


def test_box_sum_matches_a_plain_loop():
    a = np.arange(30, dtype=float).reshape(5, 6)
    padded = np.pad(a, 1)
    expected = np.array([[padded[r:r + 3, c:c + 3].sum() for c in range(6)] for r in range(5)])
    assert np.allclose(_box_sum(a, 3), expected)


def test_uniform_crowd_reads_its_true_density():
    density = np.full((40, 40), 2 * 0.0064)  # 2 people per m² in every cell
    per_m2 = density_per_m2(density, TOP_DOWN, (320, 320))
    assert np.allclose(per_m2[5:-5, 5:-5], 2.0)


def test_zone_density_counts_people_inside_the_drawn_zone():
    density = np.zeros((40, 40))
    density[2:10, 2:10] = 3 / 64  # 3 people spread over the first metre (cells 0 to 12)
    zone = zone_density(density, TOP_DOWN, [(0, 0), (100, 0), (100, 100), (0, 100)])
    assert zone["people"] == pytest.approx(3.0)
    assert zone["area_m2"] == pytest.approx(1.0)
    assert zone["per_m2"] == pytest.approx(3.0)
    assert zone["level"] == "Crowded"


def test_crowd_pressure_is_density_times_velocity_variance():
    assert crowd_pressure(4.0, [(1.0, 0.0)] * 10) == pytest.approx(0.0)  # all moving together
    jostling = [(0.5, 0.0), (-0.5, 0.0)] * 5  # variance 0.25 m²/s²
    assert crowd_pressure(4.0, jostling) == pytest.approx(1.0)
