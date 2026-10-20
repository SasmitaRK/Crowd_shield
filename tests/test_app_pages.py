"""Render every Streamlit page headlessly, with no browser and no detector, to catch breakage.

Skipped where Streamlit isn't installed; GitHub Actions runs it in the "app" job.
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("streamlit")
pytest.importorskip("cv2")
pytest.importorskip("matplotlib")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGES = {path.stem.split("_")[-1]: path for path in (ROOT / "pages").glob("*.py")}


def render(path: Path, **session_state) -> AppTest:
    app = AppTest.from_file(str(path), default_timeout=60)
    for key, value in session_state.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def zone_result(count: int) -> dict:
    """What process_segment returns for a zone with one photo."""
    photo = {"count": count, "body_count": count, "head_count": 0,
             "overlay": np.zeros((60, 80, 3), dtype=np.uint8), "model_key": "yolov8l"}
    return {"count": count, "body_count": count, "head_count": 0, "image_count": 1,
            "per_image": [photo], "model_key": "yolov8l", "per_img_sources": ["ground"],
            "combine": "sum"}


def test_home_page():
    render(ROOT / "main.py")


def test_agents_page():
    render(PAGES["Agents"])


def test_upload_page_asks_how_each_zones_photos_overlap():
    app = render(PAGES["Upload"])
    assert len(app.radio) == 5  # one choice per zone, A to E
    assert all(radio.value == "sum" for radio in app.radio)


def test_analysis_page_plans_a_relocation():
    # Default limits are 30 / 60 / 90: A is Critical, B is Safe, C is Moderate.
    crowd = {"A": zone_result(95), "B": zone_result(10), "C": zone_result(45)}
    app = render(PAGES["Analysis"], crowd_data=crowd)
    text = " ".join(block.value for block in app.markdown)
    assert "Relocate <b>~36</b> people to Segment <b>B</b>" in text


def test_settings_page():
    render(PAGES["Settings"])


def test_video_page_waits_for_a_clip():
    app = render(PAGES["Video"])
    assert any("Upload a clip" in block.value for block in app.info)
