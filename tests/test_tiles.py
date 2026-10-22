import numpy as np
import pytest

from crowdshield import config, points

cv2 = pytest.importorskip("cv2")


def dotted_image(centres, h=700, w=900):
    img = np.zeros((h, w, 3), np.uint8)
    for y, x in centres:
        cv2.circle(img, (int(x), int(y)), 3, (255, 255, 255), -1)
    return img


def fake_model(monkeypatch):
    """A stand-in 'model' that finds the bright dots, so tiling can be checked without PyTorch."""
    def fake_points(model, device, img_bgr):
        gray = img_bgr[:, :, 0]
        n, _, _, centroids = cv2.connectedComponentsWithStats((gray > 128).astype(np.uint8))
        return np.array([(cy, cx) for cx, cy in centroids[1:]], float).reshape(-1, 2)
    monkeypatch.setattr(points, "load_point_model", lambda: (None, "cpu"))
    monkeypatch.setattr(points, "points_from_model", fake_points)


def test_tiles_cover_the_image_exactly_once():
    h, w = 700, 900
    cover = np.zeros((h, w), int)
    for y0, y1, x0, x1 in points.tile_layout(h, w, 300):
        cover[y0:y1, x0:x1] += 1
        assert (y1 - y0) + 2 * points.TILE_MARGIN <= 300 and (x1 - x0) + 2 * points.TILE_MARGIN <= 300
    assert (cover == 1).all()


def test_a_small_image_is_one_tile():
    assert len(points.tile_layout(200, 300, 704)) == 1


def test_heads_on_a_seam_are_counted_once_and_none_are_lost(monkeypatch):
    fake_model(monkeypatch)
    rng = np.random.default_rng(1)
    centres = [(float(y), float(x)) for y, x in zip(rng.integers(10, 690, 150), rng.integers(10, 890, 150))]
    # put heads exactly on the tile seams, where double counting would show up
    seams = [(y, x) for y0, y1, x0, x1 in points.tile_layout(700, 900, 300) for y, x in ((y1 - 1, x1 - 2), (y1, x1 + 1))]
    centres += [(float(min(y, 698)), float(min(x, 898))) for y, x in seams]
    img = dotted_image(centres)
    whole = points.points_from_model(None, "cpu", img)
    tiled = points.points_tiled(None, "cpu", img, 300)
    assert len(tiled) == len(whole)
    key = lambda p: sorted(map(tuple, np.round(p, 0)))
    assert key(tiled) == key(whole)


def test_count_uses_tiles_only_when_the_whole_photo_does_not_fit(monkeypatch):
    fake_model(monkeypatch)
    img = dotted_image([(100, 100), (300, 400), (600, 800)])
    calls = {"tiles": 0}
    real = points.points_tiled
    monkeypatch.setattr(points, "points_tiled", lambda *a, **k: (calls.__setitem__("tiles", calls["tiles"] + 1), real(*a, **k))[1])
    monkeypatch.setattr(points, "WORK_SIDE", 900)
    monkeypatch.setattr(points, "fit_max_side", lambda ceiling=None, **k: ceiling)       # plenty of memory
    assert points.count_points(img)["raw_count"] == 3 and calls["tiles"] == 0
    monkeypatch.setattr(points, "fit_max_side", lambda ceiling=None, **k: 320)           # a small server
    out = points.count_points(img)
    assert out["raw_count"] == 3 and calls["tiles"] == 1


def test_points_come_back_in_the_original_photos_pixels(monkeypatch):
    fake_model(monkeypatch)
    img = dotted_image([(500, 700)], h=1000, w=1400)
    monkeypatch.setattr(points, "WORK_SIDE", 700)                                         # shrunk to half size
    monkeypatch.setattr(points, "fit_max_side", lambda ceiling=None, **k: 320)
    out = points.count_points(img)
    assert out["raw_count"] == 1
    assert np.allclose(out["points"][0], (500, 700), atol=4)


def test_work_side_is_set_by_the_server_but_overridable(monkeypatch):
    monkeypatch.delenv("CROWDSHIELD_MAX_SIDE", raising=False)
    monkeypatch.setattr(config, "on_streamlit_cloud", lambda: True)
    assert config.default_work_side() == config.SMALL_SERVER_WORK_SIDE
    monkeypatch.setattr(config, "on_streamlit_cloud", lambda: False)
    monkeypatch.setattr(config, "memory_limit_bytes", lambda: 32 * 1024 ** 3)
    assert config.default_work_side() == config.FULL_MAX_SIDE
    monkeypatch.setenv("CROWDSHIELD_MAX_SIDE", "1280")
    assert config.default_work_side() == 1280
