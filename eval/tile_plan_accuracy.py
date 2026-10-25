"""Accuracy of the two tile plans the free server can use (photo at 1024 px, memory for 704 px tiles):
'square' (the current layout) and 'padded' (tiles planned by PET's 256-px padding), plus one pass at
1024 px as the reference. ShanghaiTech A and B test photos and the 10 hand-labelled Indian photos,
scored exactly as in results/tiled_accuracy.json. Also records how many tiles each plan used."""
import json, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/tp"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "pro-2",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], check=False)
sys.path.insert(0, str(W / "repo"))

import cv2, numpy as np  # noqa: E402
from crowdshield import benchmark, points  # noqa: E402
from crowdshield.datasets import load_shanghaitech  # noqa: E402

CONFIGS = {"square-1024/704": ("square", 704), "padded-1024/704": ("padded", 704), "whole-1024": ("padded", 99999)}
tiles_used = {}
real_tiled = points.points_tiled


def counting_tiles(model, device, img, tile_side, *a, **k):
    tiles_used["n"] += len(points.tile_layout(*img.shape[:2], tile_side))
    return real_tiled(model, device, img, tile_side, *a, **k)


points.points_tiled = counting_tiles


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
    for cfg, (plan, fit) in CONFIGS.items():
        points.TILE_PLAN, points.WORK_SIDE = plan, 1024
        points.fit_max_side = lambda ceiling=None, fit=fit, **k: min(ceiling or fit, fit)
        tiles_used["n"] = 0
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
        results.setdefault(name, {})[cfg] = {"photos": len(items), "accuracy": round(acc, 4), "mae": round(float(np.mean(errs)), 2),
                                             "tiles": tiles_used["n"], "seconds": round(time.time() - t0)}
        print(f"  {cfg:>16}  accuracy {acc:.2%}  MAE {np.mean(errs):.1f}  tiles {tiles_used['n']}  ({time.time()-t0:.0f}s)", flush=True)
(OUT / "tile_plan_accuracy.json").write_text(json.dumps(results, indent=1))
