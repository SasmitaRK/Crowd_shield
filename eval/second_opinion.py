"""Can a second model flag the photos where PET overcounts (railway gravel, waves), cheaply enough for
the free server? In one process, like the app: PET as the free server runs it (1024 px, 704 px tiles),
then DM-Count on the same photo shrunk to 512 and to 768 px. Records PET / DM-Count per photo, with the
true count where there is one, and the process's peak memory and DM-Count's time."""
import json, resource, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/dc"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "pro-2",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], check=False)
sys.path.insert(0, str(W / "repo"))
import os; os.chdir(W / "repo")
import cv2, torch  # noqa: E402
torch.set_num_threads(4)
from crowdshield import benchmark, density, points  # noqa: E402
from crowdshield.datasets import load_shanghaitech  # noqa: E402

points.WORK_SIDE = 1024
points.fit_max_side = lambda ceiling=None, **k: min(ceiling or 704, 704)
truth = {r["image"]: r["true"] for r in benchmark.load()}
items = [(f"india/{p.name}", p, truth.get(p.name)) for p in sorted(Path("data/india_test/images").glob("*.jpg"))]
for part in ("A", "B"):
    items += [(f"SH{part}/{Path(p).name}", p, float(len(pts))) for p, pts in load_shanghaitech("/kaggle/input", part, "test")]

dm_model, dm_device = density.load_density_model()
rows, dm_time = [], {512: 0.0, 768: 0.0}
for i, (name, path, true) in enumerate(items):
    img = cv2.imread(str(path))
    pet = points.count_points(img)["count"]
    row = {"photo": name, "true": true, "pet": round(pet, 1)}
    for side in (512, 768):
        s = min(1.0, side / max(img.shape[:2]))
        small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
        t = time.time(); row[f"dm{side}"] = round(float(density.density_from_model(dm_model, dm_device, small).sum()), 1)
        dm_time[side] += time.time() - t
    rows.append(row)
    if i % 25 == 0:
        print(i, row, "peak MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)
summary = {"photos": len(rows), "peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
           "dm_seconds_per_photo": {k: round(v / len(rows), 2) for k, v in dm_time.items()}}
print(summary, flush=True)
(OUT / "disagreement.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
