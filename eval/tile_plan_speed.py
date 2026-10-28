"""Speed and whole-process peak memory of the two tile plans on a CPU set up like the free server
(2 PyTorch threads, no GPU), each plan in its own process so peaks don't mix. Same photos for both:
the first 25 ShanghaiTech A and 25 B test photos, plus three Indian photos."""
import json, subprocess, sys
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/ts"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "pro-2",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], check=False)
CHILD = r'''
import json, os, platform, resource, statistics, sys, time
import cv2, torch
torch.set_num_threads(2)
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1])
plan, fit = sys.argv[2], int(sys.argv[3])
from crowdshield import points
from crowdshield.datasets import load_shanghaitech
points.TILE_PLAN, points.WORK_SIDE = plan, 1024
points.fit_max_side = lambda ceiling=None, **k: min(ceiling or fit, fit)
paths = [p for part in ("A", "B") for p, _ in load_shanghaitech("/kaggle/input", part, "test")[:25]]
paths += [f"data/india_test/images/IN_{n:02d}.jpg" for n in (14, 1, 19)]
points.count_points(cv2.imread(paths[0]))  # warm-up: loads the weights
times, counts = [], []
for p in paths:
    img = cv2.imread(str(p)); t = time.time()
    counts.append(round(points.count_points(img)["count"], 1)); times.append(time.time() - t)
print("RESULT", json.dumps({"plan": plan, "fit": fit, "photos": len(paths), "cpu": platform.processor() or platform.machine(),
      "torch_threads": torch.get_num_threads(), "median_s": round(statistics.median(times), 2),
      "mean_s": round(statistics.mean(times), 2), "max_s": round(max(times), 2),
      "peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024), "counts": counts}))
'''
(W / "child.py").write_text(CHILD)
res = []
for plan, fit in (("square", 704), ("padded", 704), ("padded", 99999)):
    r = subprocess.run([sys.executable, str(W / "child.py"), str(W / "repo"), plan, str(fit)], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    print(plan, fit, line or r.stderr[-800:], flush=True)
    if line: res.append(json.loads(line[7:]))
(OUT / "tile_plan_speed.json").write_text(json.dumps(res, indent=1))
