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
            "combine": "sum", "counter": "points"}


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
    assert "Relocate <b>~36</b> people to Zone <b>B</b>" in text
    assert any("Counted by the PET point model" in c.value for c in app.caption)


def test_settings_page():
    render(PAGES["Settings"])


def test_video_page_waits_for_a_clip():
    app = render(PAGES["Video"])
    assert any("Upload a clip" in block.value for block in app.info)


def test_map_page_shows_the_kumbh_demo_with_an_evacuation_plan():
    pytest.importorskip("streamlit_folium")
    app = render(PAGES["Map"])
    text = " ".join(block.value for block in app.markdown)
    assert "Sangam Nose bathing area" in text
    assert "CRITICAL" in text and "A → B → D" in text


def test_dashboard_shows_the_headline_results():
    app = render(PAGES["Dashboard"])
    text = " ".join(block.value for block in app.markdown)
    assert "92.7%" in text and "86.5%" in text


def test_upload_page_says_which_model_counts():
    app = render(PAGES["Upload"])
    assert any("PET point model" in block.value for block in app.markdown)


def test_benchmark_page_reports_the_india_pilot():
    app = render(PAGES["Benchmark"])
    text = " ".join(block.value for block in app.markdown)
    assert "Known failure" in text


def test_video_page_opens_the_sample_clip_as_a_fixed_camera():
    app = render(PAGES["Video"])
    app.radio[0].set_value("Sample: Paris Saint-Lazare station").run()
    assert not app.exception, [e.message for e in app.exception]
    assert any("450 frames" in block.value for block in app.caption)
    assert not app.warning  # no moving-camera warning: the station camera is fixed
    assert [box.value for box in app.text_input] == ["Stairs", "Concourse"]


def test_photo_page_offers_instant_sample_photos():
    app = render(PAGES["Upload"])
    app.button(key="sample_show").click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert any(m.label == "Counted by hand" for m in app.metric)


def test_map_page_compares_the_simple_rule_with_the_optimised_plan():
    pytest.importorskip("streamlit_folium")
    app = render(PAGES["Map"])
    names = [box.label for box in app.selectbox]
    assert "Evacuation planner" in names
    box = next(b for b in app.selectbox if b.label == "Evacuation planner")
    box.set_value("Simple rule").run()
    assert not app.exception, [e.message for e in app.exception]
