from crowdshield.config import FRUIN_PRESETS
from crowdshield.sitemap import assess, load_site, scenario_counts, site_from_drawings

EVENTS = FRUIN_PRESETS["Crowded events / concerts"]


def test_demo_site_zones_form_one_walkable_network():
    view = assess(load_site(), {}, EVENTS)
    assert set(view["zones"]) == {"A", "B", "C", "D", "E"}
    # The Sangam Nose (A) connects to the rest only through the Sangam Ghat approach (B).
    assert view["adjacency"]["A"] == ["B"]
    assert all(view["adjacency"][z] for z in view["zones"])
    assert all(10_000 < r["area_m2"] < 200_000 for r in view["zones"].values())


def test_demo_scenario_shows_every_risk_level_and_routes_round_the_crowd():
    site = load_site()
    view = assess(site, scenario_counts(site), EVENTS)
    risks = {z: r["risk"] for z, r in view["zones"].items()}
    assert risks == {"A": "Critical", "B": "Moderate", "C": "High Risk",
                     "D": "Safe", "E": "Safe"}
    by_zone = {p["high"]: p for p in view["plans"]}
    assert by_zone["A"]["path"] == ["A", "B", "D"]  # nearest Safe zone, through the approach
    assert by_zone["C"]["path"] == ["C", "E"]


def test_zones_without_counts_are_drawn_but_not_planned():
    view = assess(load_site(), {"A": 10}, EVENTS)
    assert view["zones"]["B"]["count"] is None and view["zones"]["B"]["risk"] is None
    assert view["plans"] == []


def test_drawn_shapes_become_a_site():
    ring = [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]
    features = [{"geometry": {"type": "Polygon", "coordinates": [ring]}},
                {"geometry": {"type": "LineString", "coordinates": ring}}]
    site = site_from_drawings(features, {"C": "North gate"}, {0: "C", 1: "D"})
    assert list(site["zones"]) == ["C"]
    assert site["zones"]["C"]["name"] == "North gate"
    assert site["centre"] == [0.0005, 0.0005]
