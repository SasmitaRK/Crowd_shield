"""The Live feed page, rendered headlessly (kept apart from test_app_pages.py so PRs don't collide)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("cv2")
pytest.importorskip("matplotlib")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LIVE = next((ROOT / "pages").glob("*_Live.py"))


def render() -> AppTest:
    app = AppTest.from_file(str(LIVE), default_timeout=60)
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def test_live_page_demo_feed_counts_and_charts(monkeypatch):
    """The demo feed runs end to end with a stand-in counter (the real model is not installed here)."""
    from crowdshield import counting
    from crowdshield.monitor import points_to_grid

    monkeypatch.setattr(counting, "make_counter",
                        lambda: (lambda f: points_to_grid([(150.0, 500.0 + i) for i in range(35)], f.shape), "test counter"))
    app = render()
    toggle = next(t for t in app.toggle if t.label == "Monitoring")
    toggle.set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    text = " ".join(m.value for m in app.markdown)
    assert "Stairs" in text
    assert any("High Risk" in m.value or "Safe" in m.value or "Moderate" in m.value for m in app.markdown)


def test_live_page_refuses_a_private_stream_address():
    app = render()
    app.radio[0].set_value("Stream URL").run()
    app.text_input[0].set_value("http://127.0.0.1:8080/stream").run()
    assert any("private network" in e.value for e in app.error)
