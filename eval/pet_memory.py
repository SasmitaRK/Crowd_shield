# Runs as a Kaggle CPU script (no GPU, internet on). Output: results/pet_memory.json.
"""Peak memory of the PET point model alone, at several input sizes, each in a fresh process,
to pick a photo size that fits the free Streamlit Community Cloud server (about 2.7 GB)."""
import json, os, subprocess, sys
from pathlib import Path

OUT = Path("/kaggle/working")
W = Path("/tmp/mem"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)

CHILD = r'''
import os, resource, sys, time, cv2
sys.path.insert(0, sys.argv[1])
os.environ["CROWDSHIELD_MAX_SIDE"] = sys.argv[2]
from crowdshield import points
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
out = []
for p in sys.argv[3:]:
    img = cv2.imread(p)
    t = time.perf_counter(); r = points.count_points(img); dt = time.perf_counter() - t
    out.append((os.path.basename(p), img.shape[:2], r["raw_count"], round(r["count"], 1), round(dt, 1)))
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print("RESULT", {"max_side": int(sys.argv[2]), "peak_rss_mb": round(peak / 1024), "photos": out})
'''
(W / "child.py").write_text(CHILD)
imgs = [str(W / "repo/data/india_test/images" / f"IN_{n:02d}.jpg") for n in (14, 1, 3, 19)]
results = []
for side in (640, 800, 1024, 1280, 1600, 2048):
    r = subprocess.run([sys.executable, str(W / "child.py"), str(W / "repo"), str(side)] + imgs,
                       capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    print(side, line or r.stderr[-800:], flush=True)
    if line:
        results.append(eval(line[7:]))
(OUT / "pet_memory.json").write_text(json.dumps(results, indent=1))
