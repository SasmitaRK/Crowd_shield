import json

import pytest

from crowdshield.session import BadSession, export_session, import_session


def state():
    return {
        "thresholds": {"A": {"moderate": 20, "high": 40, "critical": 60}},
        "seg_areas": {"A": 300},
        "agents": {"A": "a@example.com", "B": ""},
        "zone_names": {"A": "Gate"},
        "zone_adjacency": {"A": ["B"], "B": ["A"]},
        "crowd_data": {"A": {"count": 55, "image_count": 2, "counter": "points", "per_image": [object()]}},
    }


def test_a_session_round_trips():
    back = import_session(export_session(state()))
    assert back["thresholds"]["A"] == {"moderate": 20, "high": 40, "critical": 60}
    assert back["thresholds"]["B"] == {"moderate": 30, "high": 60, "critical": 90}  # untouched zones keep defaults
    assert back["agents"]["A"] == "a@example.com" and back["zone_names"] == {"A": "Gate"}
    assert back["crowd_data"]["A"]["count"] == 55 and back["crowd_data"]["A"]["per_image"] == []
    assert back["zone_adjacency"]["A"] == ["B"]


def test_photos_and_overlays_are_not_written_to_the_file():
    assert "per_image" not in export_session(state())


@pytest.mark.parametrize("text", ids=lambda t: t[:30] if t[:1] != "x" else "too-big", argvalues=[
    "not json", "[]", '{"hello": 1}', "x" * 1_000_001,
    json.dumps({"crowd_shield_session": 1, "thresholds": {"Z": {"moderate": 1, "high": 2, "critical": 3}}}),
    json.dumps({"crowd_shield_session": 1, "thresholds": {"A": {"moderate": 50, "high": 40, "critical": 60}}}),
    json.dumps({"crowd_shield_session": 1, "thresholds": {"A": {"moderate": 1}}}),
    json.dumps({"crowd_shield_session": 1, "agents": {"A": "not an email"}}),
    json.dumps({"crowd_shield_session": 1, "counts": {"A": {"count": -3}}}),
])
def test_bad_files_are_refused_with_a_reason(text):
    with pytest.raises(BadSession):
        import_session(text)
