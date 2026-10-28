import pytest

from crowdshield.config import FRUIN_PRESETS
from crowdshield.risk import (combine_counts, plan_relocations, risk_level, route,
                              thresholds_from_area)

T = {"moderate": 30, "high": 60, "critical": 90}


def zone(count, thresholds=T):
    return {"count": count, "risk": risk_level(count, thresholds), "thresholds": thresholds}


def test_risk_level_boundaries():
    assert risk_level(29, T) == "Safe"
    assert risk_level(30, T) == "Moderate"
    assert risk_level(59, T) == "Moderate"
    assert risk_level(60, T) == "High Risk"
    assert risk_level(89, T) == "High Risk"
    assert risk_level(90, T) == "Critical"


def test_thresholds_from_area_matches_the_settings_page_example():
    # 200 m², standard venue, cameras covering 75% of the zone
    t = thresholds_from_area(200, FRUIN_PRESETS["Standard (mixed venues)"], 0.75)
    assert t == {"moderate": 150, "high": 300, "critical": 525}


def test_thresholds_stay_strictly_increasing_for_tiny_zones():
    t = thresholds_from_area(1, FRUIN_PRESETS["Enclosed corridors / gates"], 0.5)
    assert t["moderate"] < t["high"] < t["critical"]


def test_thresholds_reject_empty_zones():
    with pytest.raises(ValueError):
        thresholds_from_area(0, FRUIN_PRESETS["Standard (mixed venues)"])


def test_combine_counts():
    assert combine_counts([40, 35], "sum") == 75
    assert combine_counts([40, 35], "max") == 40
    assert combine_counts([], "max") == 0
    with pytest.raises(ValueError):
        combine_counts([1], "mean")


def test_relocation_sends_the_excess_to_the_emptiest_safe_zone():
    [plan] = plan_relocations({"A": zone(95), "B": zone(10), "C": zone(20)})
    assert plan["target"] == "B"
    assert plan["move"] == 95 - 59  # just enough to drop A below High Risk


def test_relocation_never_overfills_a_target():
    plans = plan_relocations({"A": zone(95), "B": zone(92), "C": zone(10)})
    assert [p["target"] for p in plans] == ["C", "C"]
    assert sum(p["move"] for p in plans) == 59 - 10  # C only has room for 49


def test_relocation_prefers_neighbours_and_skips_unreachable_zones():
    zones = {"A": zone(95), "B": zone(20), "C": zone(5), "D": zone(0)}
    adjacency = {"A": ["B"], "B": ["A", "C"], "C": ["B"], "D": []}
    [plan] = plan_relocations(zones, adjacency)
    assert plan["target"] == "B"  # next door, though C and D are emptier


def test_relocation_without_room_calls_for_reinforcements():
    [plan] = plan_relocations({"A": zone(95), "B": zone(45)})  # B is Moderate
    assert plan["target"] is None
    assert plan["move"] == 36


def test_route_takes_the_fewest_steps_and_reports_unreachable_zones():
    graph = {"A": ["B"], "B": ["A", "C", "D"], "C": ["B", "E"], "D": ["B", "E"], "E": ["C", "D"],
             "F": []}
    assert route("A", "E", graph) == ["A", "B", "C", "E"]
    assert route("A", "A", graph) == ["A"]
    assert route("A", "F", graph) == []
