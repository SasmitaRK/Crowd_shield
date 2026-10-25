import numpy as np
import pytest

from crowdshield import crosscheck, density

cv2 = pytest.importorskip("cv2")


@pytest.fixture
def dm(monkeypatch):
    """DM-Count stand-in that finds `found` people, so the check runs without PyTorch."""
    state = {"found": 100.0, "seen": None}

    def fake_density(model, device, img):
        state["seen"] = img.shape
        return np.full((4, 4), state["found"] / 16)

    monkeypatch.setattr(density, "load_density_model", lambda: (None, "cpu"))
    monkeypatch.setattr(density, "density_from_model", fake_density)
    monkeypatch.setattr(crosscheck, "has_headroom", lambda: True)
    monkeypatch.delenv("CROWDSHIELD_SECOND_OPINION", raising=False)
    return state


def test_agreeing_models_raise_nothing(dm):
    out = crosscheck.second_opinion(np.zeros((768, 1024, 3), np.uint8), 180)
    assert out == {"dm_count": 100, "ratio": 1.8, "disagree": False}


def test_point_model_far_above_the_density_model_asks_for_a_second_look(dm):
    dm["found"] = 415
    out = crosscheck.second_opinion(np.zeros((768, 1024, 3), np.uint8), 1282)  # the Mumbai railway photo
    assert out["disagree"] and out["ratio"] == 3.09


def test_the_photo_is_shrunk_for_the_second_model(dm):
    crosscheck.second_opinion(np.zeros((1536, 2048, 3), np.uint8), 500)
    assert max(dm["seen"][:2]) == crosscheck.SIDE


def test_small_counts_low_memory_and_switched_off_are_skipped(dm, monkeypatch):
    img = np.zeros((300, 400, 3), np.uint8)
    assert crosscheck.second_opinion(img, 20) is None
    monkeypatch.setenv("CROWDSHIELD_SECOND_OPINION", "0")
    assert crosscheck.second_opinion(img, 500) is None
    monkeypatch.delenv("CROWDSHIELD_SECOND_OPINION")
    monkeypatch.setattr(crosscheck, "has_headroom", lambda: False)
    assert crosscheck.second_opinion(img, 500) is None


def test_headroom_needs_free_memory_on_a_small_server():
    gb = 1024 ** 3
    assert crosscheck.has_headroom(limit=3.2 * gb, used=1.9 * gb)
    assert not crosscheck.has_headroom(limit=3.2 * gb, used=2.9 * gb)
    assert crosscheck.has_headroom(limit=128 * gb, used=127 * gb)  # no real limit: a big machine


def test_a_failing_second_model_never_breaks_counting(monkeypatch):
    monkeypatch.setattr(crosscheck, "has_headroom", lambda: True)
    monkeypatch.setattr(density, "load_density_model", lambda: (_ for _ in ()).throw(RuntimeError("no weights")))
    assert crosscheck.second_opinion(np.zeros((300, 400, 3), np.uint8), 500) is None
