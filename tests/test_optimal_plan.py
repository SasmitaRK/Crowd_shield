import pytest

pytest.importorskip("scipy")

from crowdshield.risk import plan_optimal, plan_relocations, plan_summary, risk_level  # noqa: E402

T = {"moderate": 30, "high": 60, "critical": 90}


def zone(count, thresholds=T):
    return {"count": count, "risk": risk_level(count, thresholds), "thresholds": thresholds}


def edges(*pairs):
    graph = {}
    for a, b in pairs:
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)
    return graph


def test_a_lone_crowded_zone_sends_its_excess_to_the_nearest_zone_with_room():
    zones = {"A": zone(100), "B": zone(10), "C": zone(10)}
    plans = plan_optimal(zones, edges(("A", "B"), ("A", "C")), {("A", "B"): 50, ("A", "C"): 200})
    assert [(p["target"], p["move"]) for p in plans] == [("B", 41)]  # 100 - 59, B has room for 49
    assert plans[0]["path"] == ["A", "B"]


def test_zones_sharing_a_destination_do_not_strand_people():
    """The simple rule fills the nearest zone for the first crowded zone and leaves the second stranded."""
    zones = {"A": zone(100), "B": zone(100), "C": zone(9), "D": zone(0)}  # C has room for 50, D for 59
    graph = edges(("A", "C"), ("B", "C"), ("C", "D"))
    simple = plan_summary(plan_relocations(zones, adjacency=graph), zones=zones)
    best = plan_summary(plan_optimal(zones, graph), zones=zones)
    assert simple["unresolved"] > 0
    assert best["unresolved"] == 0
    assert best["moved"] == 41 + 41


def test_no_zone_is_filled_past_its_limit_and_all_excess_is_accounted_for():
    zones = {"A": zone(150), "B": zone(95), "C": zone(20), "D": zone(40), "E": zone(5)}
    graph = edges(("A", "C"), ("B", "C"), ("C", "D"), ("D", "E"), ("B", "E"))
    plans = plan_optimal(zones, graph)
    received = {}
    for p in plans:
        if p["target"]:
            received[p["target"]] = received.get(p["target"], 0) + p["move"]
            assert p["path"][0] == p["high"] and p["path"][-1] == p["target"]
            assert all(b in graph[a] for a, b in zip(p["path"], p["path"][1:]))  # every step is walkable
    for z, n in received.items():
        assert zones[z]["count"] + n <= T["high"] - 1
    for z in ("A", "B"):
        assert sum(p["move"] for p in plans if p["high"] == z) == zones[z]["count"] - (T["high"] - 1)


def test_people_with_nowhere_to_go_are_reported_not_hidden():
    zones = {"A": zone(100), "B": zone(58)}  # B has room for 1
    plans = plan_optimal(zones, edges(("A", "B")))
    assert sum(p["move"] for p in plans if p["target"]) == 1
    assert sum(p["move"] for p in plans if not p["target"]) == 40


def test_an_unreachable_zone_is_never_a_target():
    zones = {"A": zone(100), "B": zone(0), "C": zone(0)}
    plans = plan_optimal(zones, edges(("A", "B")))
    assert {p["target"] for p in plans} == {"B"}


def test_it_is_never_worse_than_the_simple_rule():
    import random
    rng = random.Random(3)
    for _ in range(40):
        names = list("ABCDEF")
        zones = {n: zone(rng.randint(0, 130)) for n in names}
        pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if rng.random() < 0.4]
        graph = {n: [] for n in names}
        for a, b in pairs:
            graph[a].append(b); graph[b].append(a)
        simple = plan_summary(plan_relocations(zones, adjacency=graph), zones=zones)
        best = plan_summary(plan_optimal(zones, graph), zones=zones)
        assert best["unresolved"] <= simple["unresolved"]
        assert best["moved"] >= simple["moved"]


def test_nothing_to_do_without_a_crowded_zone():
    assert plan_optimal({"A": zone(10), "B": zone(20)}, edges(("A", "B"))) == []
