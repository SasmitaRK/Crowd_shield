"""Whole-process peak memory and time of the app counting a photo like the free server does (CPU, no GPU):
tiled at 1024 px work size with tiles of at most 704 px, against one pass at 704 and at 1024."""
import json, os, resource, subprocess, sys
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/tm"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "tiled-counting",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], check=False)
CHILD = r'''
import json, os, resource, sys, time, cv2
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1])
work, fit = int(sys.argv[2]), int(sys.argv[3])
from crowdshield import points
points.WORK_SIDE = work
points.fit_max_side = lambda ceiling=None, **k: min(ceiling or fit, fit)
imgs = [cv2.imread(f"data/india_test/images/IN_{n:02d}.jpg") for n in (14, 1, 19)]
points.count_points(imgs[1])  # warm-up: loads the weights
t = time.time(); counts = [round(points.count_points(i)["count"], 1) for i in imgs]
print("RESULT", json.dumps({"work": work, "fit": fit, "peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
                            "seconds_per_photo": round((time.time() - t) / 3, 1), "counts": counts}))
'''
(W / "child.py").write_text(CHILD)
res = []
for work, fit in ((704, 704), (1024, 704), (1024, 99999), (1024, 576)):
    r = subprocess.run([sys.executable, str(W / "child.py"), str(W / "repo"), str(work), str(fit)], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    print(work, fit, line or r.stderr[-600:], flush=True)
    if line: res.append(json.loads(line[7:]))
(OUT / "tiled_memory.json").write_text(json.dumps(res, indent=1))
