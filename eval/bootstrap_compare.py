"""Paired bootstrap: is the new model's accuracy different from the current app's, photo set by photo set?

Resamples the test photos with replacement 10,000 times and recomputes accuracy (1 - total error / total
true) for both models on the same resample. Reports the observed difference and its 95% interval.
"""
import json
import sys

import numpy as np

r = json.load(open(sys.argv[1]))
rng = np.random.default_rng(0)
out = {}
for cfg, res in r["configs"].items():
    for name, row in res["tests"].items():
        t = np.array(row["truth"])
        cur = np.abs(np.array(row["current (shipped)"]["per_photo"]) - t)
        new = np.abs(np.array(row["new"]["per_photo"]) - t)
        idx = rng.integers(0, len(t), (10_000, len(t)))
        diff = (cur[idx].sum(1) - new[idx].sum(1)) / t[idx].sum(1)  # new accuracy minus current
        lo, hi = np.percentile(diff, [2.5, 97.5])
        obs = (cur.sum() - new.sum()) / t.sum()
        verdict = "new better" if lo > 0 else "new worse" if hi < 0 else "no real difference"
        out[f"{cfg} | {name}"] = {"photos": len(t), "difference_points": round(100 * obs, 2),
                                  "ci95_points": [round(100 * lo, 2), round(100 * hi, 2)], "verdict": verdict}
        print(f"{cfg:6} {name:15} n={len(t):3}  new - current = {100 * obs:+.2f} pts  "
              f"95% CI [{100 * lo:+.2f}, {100 * hi:+.2f}]  -> {verdict}")
json.dump(out, open(sys.argv[2], "w"), indent=1)
