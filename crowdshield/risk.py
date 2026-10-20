"""Risk tiers, area-based thresholds and relocation planning. Pure functions, no UI."""

from __future__ import annotations

import math
from collections import deque

COMBINE_MODES = ("sum", "max")


def risk_level(count: int, thresholds: dict) -> str:
    """Return Safe / Moderate / High Risk / Critical for a people count."""
    if count < thresholds.get("moderate", 30):
        return "Safe"
    if count < thresholds.get("high", 60):
        return "Moderate"
    if count < thresholds.get("critical", 90):
        return "High Risk"
    return "Critical"


def thresholds_from_area(area_m2: float, preset: dict, coverage: float = 1.0) -> dict:
    """People-count thresholds for a zone: area x density limit x camera coverage.

    Coverage below 1 means the cameras see only part of the zone, so detected
    counts run low; scaling the thresholds by the same factor keeps tiers honest.
    """
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")
    moderate = max(1, math.floor(area_m2 * preset["moderate"] * coverage))
    high = max(moderate + 1, math.floor(area_m2 * preset["high"] * coverage))
    critical = max(high + 1, math.floor(area_m2 * preset["critical"] * coverage))
    return {"moderate": moderate, "high": high, "critical": critical}


def combine_counts(counts: list[int], mode: str = "sum") -> int:
    """Merge per-photo counts for one zone.

    "sum" fits photos of different parts of the zone; "max" fits photos of the
    same area from several cameras, where summing would count people twice.
    """
    if mode not in COMBINE_MODES:
        raise ValueError(f"mode must be one of {COMBINE_MODES}")
    if not counts:
        return 0
    return sum(counts) if mode == "sum" else max(counts)


def _hops_from(start: str, adjacency: dict) -> dict:
    """Breadth-first distance, in zone-to-zone steps, from start to every reachable zone."""
    hops = {start: 0}
    queue = deque([start])
    while queue:
        zone = queue.popleft()
        for neighbour in adjacency.get(zone, ()):
            if neighbour not in hops:
                hops[neighbour] = hops[zone] + 1
                queue.append(neighbour)
    return hops


def plan_relocations(zones: dict, adjacency: dict | None = None) -> list[dict]:
    """Pair each High Risk or Critical zone with a Safe zone that can absorb people.

    `zones` maps zone -> {"count", "risk", "thresholds"}. Each action zone sheds
    enough people to drop below its "high" threshold, capped by the room left in
    the target, which counts people already sent there so it is never overfilled.
    With an adjacency map (zone -> neighbouring zones) the nearest reachable zone
    wins and unreachable zones are never suggested; without one, the emptiest
    Safe zone wins. A plan with target None means nobody can take the people.
    """
    action = sorted(
        (z for z, info in zones.items() if info["risk"] in ("High Risk", "Critical")),
        key=lambda z: (zones[z]["risk"] != "Critical", -zones[z]["count"]),
    )
    incoming = {z: 0 for z, info in zones.items() if info["risk"] == "Safe"}

    def room(zone: str) -> int:
        info = zones[zone]
        return info["thresholds"]["high"] - 1 - info["count"] - incoming[zone]

    plans = []
    for zone in action:
        info = zones[zone]
        excess = max(1, info["count"] - (info["thresholds"]["high"] - 1))
        hops = _hops_from(zone, adjacency) if adjacency is not None else {}
        candidates = [z for z in incoming
                      if room(z) > 0 and (adjacency is None or z in hops)]
        candidates.sort(key=lambda z: (hops.get(z, 0), zones[z]["count"] + incoming[z]))

        target = candidates[0] if candidates else None
        move = min(excess, room(target)) if target else excess
        if target:
            incoming[target] += move
        plans.append({
            "high": zone,
            "high_count": info["count"],
            "risk": info["risk"],
            "target": target,
            "target_count": zones[target]["count"] if target else 0,
            "move": move,
            "thresholds": info["thresholds"],
        })
    return plans
