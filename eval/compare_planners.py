"""Compare the simple relocation rule with the optimised (minimum-cost flow) plan on the demo sites.

For every step of each site's simulated surge, both planners get the same zone counts. Writes
results/planner_comparison.md. Run from the repo root: python -m eval.compare_planners
"""
from pathlib import Path

from crowdshield.config import FRUIN_PRESETS
from crowdshield.risk import plan_summary
from crowdshield.sitemap import assess, list_sites, scenario_counts, timeline

PRESET = FRUIN_PRESETS["Crowded events / concerts"]
OUT = Path(__file__).resolve().parent.parent / "results" / "planner_comparison.md"

lines = ["# Simple rule vs optimised evacuation plan", "",
         "Same zone counts for both. Left over = people the plan found no place for (the simple rule",
         "does not report them; they are what its crowded zones had to shed minus what its plans placed).",
         "People x metres is the total walking between zone centres.", ""]
totals = {"simple": [0, 0, 0.0], "optimal": [0, 0, 0.0]}
for site in list_sites():
    steps = timeline(site)
    lines += [f"## {site['short']}", "",
              "| Surge step | People to move | Left over (simple) | Left over (optimised) | Walking, simple | Walking, optimised |",
              "|---|---:|---:|---:|---:|---:|"]
    for step in steps:
        counts = scenario_counts(site, step["factor"])
        row = {}
        for key in ("simple", "optimal"):
            view = assess(site, counts, PRESET, planner=key)
            counted = {z: r for z, r in view["zones"].items() if r["count"] is not None}
            row[key] = plan_summary(view["plans"], view["distance_m"], counted)
        need = row["optimal"]["moved"] + row["optimal"]["unresolved"]
        if need == 0:
            continue
        lines.append(f"| {step['label']} | {need:,} | {row['simple']['unresolved']:,} | {row['optimal']['unresolved']:,} "
                     f"| {row['simple']['people_metres']:,.0f} | {row['optimal']['people_metres']:,.0f} |")
        for key in totals:
            totals[key][0] += row[key]["moved"]
            totals[key][1] += row[key]["unresolved"]
            totals[key][2] += row[key]["people_metres"]
    lines.append("")
lines += ["## Over all steps with anyone to move", "",
          "| Planner | People placed | Left over | People x metres |", "|---|---:|---:|---:|"]
for key, name in (("simple", "Simple rule"), ("optimal", "Optimised")):
    moved, left, metres = totals[key]
    lines.append(f"| {name} | {moved:,} | {left:,} | {metres:,.0f} |")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
