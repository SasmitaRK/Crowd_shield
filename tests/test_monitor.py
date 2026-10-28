import numpy as np
import pytest

from crowdshield.forecast import seconds_until, theil_sen_slope
from crowdshield.geometry import GroundCalibration
from crowdshield.monitor import CELL, VideoMonitor, Zone, points_to_grid


def test_rising_density_gives_time_to_danger():
    t = np.arange(0, 30, 1.0)
    per_m2 = 2.0 + 0.05 * t  # reaches 5 at t = 60, i.e. 31 s after the last reading
    assert seconds_until(t, per_m2) == pytest.approx(31, abs=1)


def test_steady_or_falling_density_gives_no_warning():
    t = np.arange(20.0)
    assert seconds_until(t, np.full(20, 3.0)) is None
    assert seconds_until(t, 4.0 - 0.05 * t) is None


def test_already_dangerous_is_zero_and_one_bad_count_cannot_swing_the_trend():
    t = np.arange(10.0)
    assert seconds_until(t, np.full(10, 6.0)) == 0.0
    values = 1.0 + 0.1 * t
    values[4] = 50.0  # a single wild reading
    assert theil_sen_slope(t, values) == pytest.approx(0.1, rel=0.05)


def test_points_become_a_count_grid():
    grid = points_to_grid([(5, 5), (6, 7), (100, 200)], (240, 320))
    assert grid.shape == (30, 40)
    assert grid.sum() == 3 and grid[0, 0] == 2


def _moving_texture(n_frames, shift_px, shape=(240, 320)):
    rng = np.random.default_rng(0)
    texture = rng.integers(0, 255, (shape[0], shape[1] + n_frames * shift_px), dtype=np.uint8)
    import cv2
    texture = cv2.GaussianBlur(texture, (7, 7), 2)
    for i in range(n_frames):
        gray = texture[:, i * shift_px:i * shift_px + shape[1]]
        yield np.dstack([gray] * 3)


def test_monitor_reads_density_speed_and_pressure_per_zone():
    pytest.importorskip("cv2")
    h, w = 240, 320
    # Straight-down camera: the whole frame is a 32 m x 24 m floor, 0.1 m per pixel.
    calib = GroundCalibration.from_rectangle([(0, 0), (w, 0), (w, h), (0, h)], 32.0, 24.0)
    left = Zone("left", [(0, 0), (160, 0), (160, 240), (0, 240)])    # 16 m x 24 m = 384 m²
    right = Zone("right", [(160, 0), (320, 0), (320, 240), (160, 240)])

    def counter(frame):  # 768 people spread evenly over the left half only
        grid = np.zeros((h // CELL, w // CELL))
        grid[:, : (160 // CELL)] = 768 / grid[:, : (160 // CELL)].size
        return grid

    monitor = VideoMonitor(counter, fps=10, zones=[left, right], calib=calib,
                           count_every_s=1.0, flow_scale=1.0)
    rows, events = monitor.run(_moving_texture(21, shift_px=2))
    last = {r["zone"]: r for r in rows if r["t"] == 2.0}

    assert last["left"]["area_m2"] == pytest.approx(384, rel=1e-6)
    assert last["left"]["per_m2"] == pytest.approx(2.0, rel=1e-6)
    assert last["left"]["level"] == "Normal"
    assert last["right"]["people"] == 0
    # 2 px per frame x 0.1 m per px x 10 fps = 2 m/s, all in the same direction.
    assert last["left"]["speed"] == pytest.approx(2.0, rel=0.15)
    assert last["left"]["pressure"] < 0.2  # uniform motion: almost no velocity variance
    assert events == []  # steady motion is not a panic


def test_pressure_counts_neighbours_pushing_apart_not_calm_opposite_streams():
    from crowdshield.monitor import VideoMonitor

    rng = np.random.default_rng(0)
    # Two calm streams in different cells walking opposite ways: no local variance.
    calm = [(np.array([[0, 0]] * 50), np.tile([1.0, 0.0], (50, 1))),
            (np.array([[5, 0]] * 50), np.tile([-1.0, 0.0], (50, 1)))]
    # One cell where neighbours are shoved in random directions.
    shoved = [(np.array([[0, 0]] * 100), rng.normal(0, 1.0, (100, 2)))]
    assert VideoMonitor._local_pressure(4.0, calm) == pytest.approx(0.0, abs=1e-9)
    assert VideoMonitor._local_pressure(4.0, shoved) == pytest.approx(4.0 * 2.0, rel=0.3)
