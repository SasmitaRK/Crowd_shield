"""Does counting in tiles keep the accuracy that a small server loses by shrinking photos?
Configs (all through the app's own count_points, with the count correction):
  whole-704    the photo shrunk to 704 px and counted in one pass (the hosted app before tiling)
  tiled-1024   the photo shrunk to 1024 px and counted in tiles of at most 704 px (the hosted app now)
  whole-1024 / whole-2048   one pass at that size (what a big server does)
ShanghaiTech A and B test photos, plus the hand-labelled Indian photos scored the same way as the
India benchmark (model points inside ignore zones are dropped, then the count correction)."""
import csv, json, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/ta"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "tiled-counting",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], check=False)
sys.path.insert(0, str(W / "repo"))

import cv2, numpy as np  # noqa: E402
from crowdshield import benchmark, points  # noqa: E402
from crowdshield.datasets import load_shanghaitech  # noqa: E402

CONFIGS = {"whole-704": (704, 704), "tiled-1024": (1024, 704), "whole-1024": (1024, 99999), "whole-2048": (2048, 99999)}


def configure(work, fit):
    points.WORK_SIDE = work
    points.fit_max_side = lambda ceiling=None, **k: min(ceiling or fit, fit)


def sets():
    out = {}
    for part in ("A", "B"):
        out[f"ShanghaiTech {part}"] = [(p, float(len(pts)), []) for p, pts in load_shanghaitech("/kaggle/input", part, "test")]
    rows = benchmark.load(W / "repo/data/india_test")
    out["India (10 hand-labelled)"] = [(W / "repo/data/india_test/images" / r["image"], float(r["true"]), r["ignore"]) for r in rows]
    return out


results = {}
for name, items in sets().items():
    print(name, len(items), flush=True)
    for cfg, (work, fit) in CONFIGS.items():
        configure(work, fit)
        errs, total, t0 = [], 0.0, time.time()
        for path, truth, ignore in items:
            out = points.count_points(cv2.imread(str(path)))
            if ignore:
                xy = [(c, r) for r, c in out["points"]]
                pred = points.corrected_count(len(benchmark._outside(xy, ignore)))
            else:
                pred = out["count"]
            errs.append(abs(pred - truth)); total += truth
        acc = 1 - sum(errs) / total
        results.setdefault(name, {})[cfg] = {"photos": len(items), "accuracy": round(acc, 4),
                                             "mae": round(float(np.mean(errs)), 2), "seconds": round(time.time() - t0)}
        print(f"  {cfg:>11}  accuracy {acc:.1%}  MAE {np.mean(errs):.1f}  ({time.time()-t0:.0f}s)", flush=True)
(OUT / "tiled_accuracy.json").write_text(json.dumps(results, indent=1))
