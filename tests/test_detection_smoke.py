"""Runs the real detectors on a sample photo. Skipped where Ultralytics isn't installed."""

import pytest

pytest.importorskip("ultralytics")
cv2 = pytest.importorskip("cv2")

from ultralytics.utils import ASSETS  # noqa: E402

from crowdshield.detection import analyse_image_bytes, detect_people  # noqa: E402

BUS = ASSETS / "bus.jpg"  # four people standing by a bus


def test_coco_model_counts_the_people_by_the_bus():
    det = detect_people(cv2.imread(str(BUS)), "yolov8l", use_faces=False,
                        allow_fallback=False)
    assert det["detector"] == "yolov8l"
    assert det["count"] >= 3


def test_drone_model_loads_and_runs():
    det = detect_people(cv2.imread(str(BUS)), "crowd_yolo", allow_fallback=False)
    assert det["detector"] == "crowd_yolo"
    assert det["count"] == det["body_count"] + det["head_count"]


def test_app_result_has_an_overlay_of_the_same_size():
    result = analyse_image_bytes(BUS.read_bytes(), "yolov8l")
    assert result["overlay"].shape == cv2.imread(str(BUS)).shape
    assert result["counter"] == "points"  # PET counts; YOLO is only the last fallback


@pytest.mark.skipif(hasattr(cv2, "CascadeClassifier"), reason="OpenCV 4 still has the cascades")
def test_face_add_on_explains_why_it_is_unavailable_on_opencv_5():
    with pytest.raises(RuntimeError, match="OpenCV 5"):
        detect_people(cv2.imread(str(BUS)), "yolov8l", use_faces=True, allow_fallback=False)
