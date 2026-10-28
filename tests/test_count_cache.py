"""A photo counted before comes back instantly, but never from another model, and never with old page parts."""

import pytest

pytest.importorskip("streamlit")

import detection  # noqa: E402
from crowdshield import points  # noqa: E402


@pytest.fixture
def counter(monkeypatch):
    calls = []

    def fake(image_bytes, model_key):
        calls.append(image_bytes)
        return {"count": len(calls)}

    monkeypatch.setattr(detection, "analyse_image_bytes", fake)
    detection._counted().clear()
    yield calls
    detection._counted().clear()


def test_a_repeated_photo_is_not_counted_again(counter):
    assert detection.process_image(b"photo")["count"] == 1
    assert detection.process_image(b"photo")["count"] == 1
    assert detection.process_image(b"other")["count"] == 2
    assert len(counter) == 2


def test_new_model_weights_count_the_photo_again(counter, monkeypatch):
    detection.process_image(b"photo")
    monkeypatch.setattr(points, "WEIGHTS_SHA256", "new-weights")
    assert detection.process_image(b"photo")["count"] == 2


def test_the_cache_stays_small(counter):
    for i in range(detection.CACHE_SIZE + 5):
        detection.process_image(bytes([i]))
    assert len(detection._counted()) == detection.CACHE_SIZE


def test_callers_cannot_change_the_stored_result(counter):
    detection.process_image(b"photo")["count"] = 99
    assert detection.process_image(b"photo")["count"] == 1
