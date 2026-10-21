# Runs as a Kaggle CPU script (no GPU, internet on).
"""How fast does Crowd Shield count on an ordinary CPU (no GPU)? Times the PET point model and the
DM-Count fallback on the 21 Indian test photos at two input sizes, and records peak memory."""
import json, os, platform, resource, statistics, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working")
W = Path("/tmp/speed"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", "india-test-set",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
sys.path.insert(0, str(W / "repo"))
cpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
model_line = next((l for l in cpu.splitlines() if "Model name" in l), "")
print(model_line, "| cores:", os.cpu_count())

import cv2  # noqa: E402
import torch  # noqa: E402
assert not torch.cuda.is_available(), "this test must run on CPU"
images = sorted((W / "repo/data/india_test/images").glob("IN_*.jpg"))
results = {"cpu": model_line.split(":", 1)[-1].strip(), "cores": os.cpu_count(),
           "torch_threads": torch.get_num_threads(), "python": platform.python_version(),
           "torch": torch.__version__, "photos": len(images), "runs": []}

for max_side in (1280, 2048):
    os.environ["CROWDSHIELD_MAX_SIDE"] = str(max_side)
    for name in list(sys.modules):
        if name.startswith("crowdshield"):
            del sys.modules[name]
    from crowdshield import density, points  # noqa: E402
    for label, fn in (("PET point model", points.count_points),
                      ("DM-Count density model", lambda img: density.estimate_density(img))):
        fn(cv2.imread(str(images[0])))  # warm-up: loads weights, builds kernels
        times = []
        for p in images:
            img = cv2.imread(str(p))
            t = time.perf_counter(); fn(img); times.append(time.perf_counter() - t)
        run = {"model": label, "max_side": max_side, "median_s": round(statistics.median(times), 2),
               "p90_s": round(sorted(times)[int(0.9 * len(times)) - 1], 2), "max_s": round(max(times), 2),
               "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)}
        results["runs"].append(run)
        print(run, flush=True)

(OUT / "cpu_speed.json").write_text(json.dumps(results, indent=1))
print(json.dumps(results, indent=1))
