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


def test_video_page_shows_the_analysed_example_straight_away():
    app = render(PAGES["Video"])
    assert [t.label for t in app.tabs] == ["Example: a busy Paris station", "Analyse your own clip"]
    text = " ".join(m.value for m in app.markdown)
    assert "Stairs" in text and "Concourse" in text and "people at most" in text
    assert any("No surge" in s.value for s in app.success)


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


def test_settings_work_out_limits_from_areas_fills_the_table():
    app = render(PAGES["Settings"])
    app.number_input(key="area_A").set_value(100).run()
    next(b for b in app.button if b.label == "Work out and apply").click().run()
    assert not app.exception, [e.message for e in app.exception]
    # Standard preset (1 / 2 / 3.5 per m²) on 100 m² seen at 75%: 75 / 150 / 262.
    assert app.session_state.thresholds["A"] == {"moderate": 75, "high": 150, "critical": 262}
    assert app.number_input(key="lim_critical_A").value == 262


def test_analysis_page_sends_one_telegram_message_for_the_team(monkeypatch):
    from crowdshield import notify

    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(notify, "send_telegram", lambda text, image=None: sent.append(text) or (True, "Sent."))
    crowd = {"A": zone_result(95), "B": zone_result(10)}
    app = render(PAGES["Analysis"], crowd_data=crowd)
    next(b for b in app.button if b.label == "Send alerts").click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert len(sent) == 1 and "Zone A: CRITICAL, 95 people. Move ~" in sent[0]


def test_analysis_page_points_to_settings_when_no_alert_channel_is_set_up(monkeypatch):
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GMAIL_USER", "GMAIL_APP_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    app = render(PAGES["Analysis"], crowd_data={"A": zone_result(95), "B": zone_result(10)})
    assert any("No alert channel is set up" in w.value for w in app.warning)


def test_settings_saves_and_loads_a_session():
    from crowdshield.session import export_session, import_session

    app = render(PAGES["Settings"], crowd_data={"A": zone_result(55)},
                 agents={"A": "a@example.com", "B": "", "C": "", "D": "", "E": ""})
    saved = export_session(app.session_state)
    assert '"count": 55' in saved and "a@example.com" in saved
    assert import_session(saved)["crowd_data"]["A"]["count"] == 55


def test_photo_results_tell_the_user_to_check_where_the_dots_sit():
    app = render(PAGES["Upload"], crowd_data={"A": zone_result(40)})
    assert any("Look at where the dots sit" in c.value for c in app.caption)


def test_map_labels_demo_zones_as_illustrative():
    pytest.importorskip("streamlit_folium")
    text = " ".join(b.value for b in render(PAGES["Map"]).markdown)
    assert "Illustrative zones, not the official layout" in text


def test_photo_and_alert_pages_warn_when_the_two_models_disagree():
    zone = zone_result(1282)
    zone["per_image"][0]["check"] = {"dm_count": 415, "ratio": 3.09, "disagree": True}
    up = render(PAGES["Upload"], crowd_data={"A": zone})
    assert any("Check this count" in w.value and "415" in w.value for w in up.warning)
    alerts = render(PAGES["Analysis"], crowd_data={"A": zone})
    assert any("Check this count" in w.value for w in alerts.warning)
