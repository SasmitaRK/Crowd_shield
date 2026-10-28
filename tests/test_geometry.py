import numpy as np
import pytest

from crowdshield.geometry import GroundCalibration, homography

# A typical CCTV view of a 10 m x 20 m rectangle: the far edge looks narrower.
CORNERS = [(220, 100), (420, 100), (600, 460), (40, 460)]


def test_homography_recovers_a_known_mapping():
    true = np.array([[0.8, 0.1, 5.0], [0.05, 1.2, -3.0], [0.0005, 0.001, 1.0]])
    src = np.array([[0, 0], [100, 0], [100, 80], [0, 80], [50, 40]], float)
    dst_h = np.c_[src, np.ones(len(src))] @ true.T
    dst = dst_h[:, :2] / dst_h[:, 2:]
    assert np.allclose(homography(src, dst), true / true[2, 2], atol=1e-8)


def test_calibration_points_land_exactly_on_the_rectangle():
    cal = GroundCalibration.from_rectangle(CORNERS, width_m=10, length_m=20)
    assert np.allclose(cal.to_ground(CORNERS), [(0, 0), (10, 0), (10, 20), (0, 20)], atol=1e-6)


def test_the_clicked_rectangle_measures_its_true_area():
    cal = GroundCalibration.from_rectangle(CORNERS, width_m=10, length_m=20)
    assert cal.polygon_area(CORNERS) == pytest.approx(200.0)


def test_far_pixels_cover_more_ground_than_near_ones():
    cal = GroundCalibration.from_rectangle(CORNERS, width_m=10, length_m=20)
    area = cal.pixel_area((480, 640))
    assert area[110, 320] > 3 * area[450, 320]  # top of the rectangle vs bottom


def test_pixel_areas_add_up_to_the_rectangle():
    cal = GroundCalibration.from_rectangle(CORNERS, width_m=10, length_m=20)
    area = cal.pixel_area((480, 640))
    v, u = np.mgrid[0:480, 0:640]
    # inside test for the trapezoid: between the two slanted sides, rows 100 to 460
    left = 220 + (v - 100) * (40 - 220) / 360
    right = 420 + (v - 100) * (600 - 420) / 360
    inside = (v >= 100) & (v < 460) & (u >= left) & (u < right)
    assert np.nansum(area[inside]) == pytest.approx(200.0, rel=0.02)


def test_points_above_the_horizon_have_no_ground_area():
    # A low camera: the rectangle's sides meet at row ~157, so the horizon is in view.
    cal = GroundCalibration.from_rectangle([(280, 200), (360, 200), (600, 460), (40, 460)],
                                           width_m=10, length_m=20)
    area = cal.pixel_area((480, 640))
    assert np.isnan(area[100, 320])  # sky: not on the ground
    assert np.isfinite(area[300, 320])


def test_flow_becomes_metres_per_second():
    # Straight-down camera: 1 pixel = 1 cm everywhere.
    cal = GroundCalibration([(0, 0), (100, 0), (100, 100), (0, 100)],
                            [(0, 0), (1, 0), (1, 1), (0, 1)])
    v = cal.ground_velocity([(50, 50)], [(2, 0)], fps=25)
    assert v[0] == pytest.approx([0.5, 0.0])


def test_degenerate_points_are_rejected():
    with pytest.raises(ValueError):
        homography([(0, 0), (1, 1), (2, 2), (3, 3)], [(0, 0), (1, 0), (1, 1), (0, 1)])
