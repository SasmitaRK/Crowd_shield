"""A monitored site as zones on a real map: areas, densities, risk and evacuation routes.

Pure functions, no UI. The Map page draws what these return.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import REPO_ROOT
from .geo import adjacency, centroid, ring_area_m2
from .risk import plan_relocations, risk_level, route, thresholds_from_area

SITES_DIR = REPO_ROOT / "sites"
DEMO_SITE = SITES_DIR / "kumbh_sangam.json"


def load_site(path: Path = DEMO_SITE) -> dict:
    """Read a site file: a name, a map centre and zones with (lon, lat) rings."""
    site = json.loads(Path(path).read_text(encoding="utf-8"))
    if not site.get("zones"):
        raise ValueError(f"{path} has no zones")
    return site


def scenario_counts(site: dict) -> dict:
    """People per zone in the site's simulated scenario: density x mapped area."""
    return {z: round(info["scenario_density"] * ring_area_m2(info["ring"]))
            for z, info in site["zones"].items() if "scenario_density" in info}


def assess(site: dict, counts: dict, preset: dict, touch_m: float = 30.0) -> dict:
    """Everything the map shows, from zone shapes, people counts and a density standard.

    Returns {"zones": {zone: row}, "adjacency": graph, "plans": [...]} where each
    row has the zone's name, ring, centre, area_m2, count, per_m2, risk and
    thresholds, and each plan from plan_relocations gains a "path" of zones to
    walk through. Zones without a count are kept for drawing, with count None.
    """
    rings = {z: info["ring"] for z, info in site["zones"].items()}
    graph = adjacency(rings, touch_m)
    rows = {}
    for z, info in site["zones"].items():
        area = ring_area_m2(info["ring"])
        thresholds = thresholds_from_area(area, preset)
        count = counts.get(z)
        rows[z] = {
            "name": info.get("name", f"Zone {z}"),
            "ring": info["ring"],
            "centre": centroid(info["ring"]),
            "area_m2": area,
            "thresholds": thresholds,
            "count": count,
            "per_m2": None if count is None else count / area,
            "risk": None if count is None else risk_level(count, thresholds),
        }
    counted = {z: r for z, r in rows.items() if r["count"] is not None}
    plans = plan_relocations(counted, adjacency=graph)
    for p in plans:
        p["path"] = route(p["high"], p["target"], graph) if p["target"] else []
    return {"zones": rows, "adjacency": graph, "plans": plans}


def site_from_drawings(features: list, names: dict, letters: dict) -> dict:
    """Turn shapes drawn on the map (GeoJSON features) into a site dict.

    `letters` maps a feature's index to the zone letter it was assigned, and
    `names` maps that letter to a display name. Unassigned shapes are skipped.
    """
    zones = {}
    for i, feature in enumerate(features):
        letter = letters.get(i)
        geometry = feature.get("geometry") or {}
        if not letter or geometry.get("type") != "Polygon":
            continue
        zones[letter] = {"name": names.get(letter) or f"Zone {letter}",
                         "ring": geometry["coordinates"][0]}
    if not zones:
        raise ValueError("no drawn polygon was assigned to a zone")
    lons = [p[0] for z in zones.values() for p in z["ring"]]
    lats = [p[1] for z in zones.values() for p in z["ring"]]
    return {"name": "My site", "short": "My site",
            "centre": [(min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2],
            "zoom": 17, "zones": zones}
