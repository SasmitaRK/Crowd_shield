"""Current app model against the QNRF fine-tune, both through the app's own count_points.

Configs: "hosted" counts at 1024 px in tiles of at most 704 px (the Streamlit Cloud app); "full" counts
at 2048 px in one pass (a laptop or a big server). Each model's count correction (true ~ a * raw^b) is
refit per config on the same held-out ShanghaiTech training photos (every 10th of A and B), never on
test photos; the current model is also scored with the correction the app ships. Test sets:
ShanghaiTech A and B tests, the UCF-QNRF test and the 10 hand-labelled Indian photos (model points
inside ignore zones dropped, as on the accuracy page).
"""
import json, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/cmp"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/khushi-git-7/Crowd_shield.git",
                str(W / "repo")], check=True)
sys.path.insert(0, str(W / "repo"))

import cv2, numpy as np, torch  # noqa: E402
import scipy.io as io  # noqa: E402
from crowdshield import benchmark, points  # noqa: E402
from crowdshield.datasets import load_shanghaitech  # noqa: E402
from crowdshield.weights import fetch  # noqa: E402

CONFIGS = {"hosted": (1024, 704), "full": (2048, 99999)}
NEW = next(Path("/kaggle/input").rglob("pet_qnrf.pth"))
CURRENT = fetch(points.WEIGHTS, points.WEIGHTS_URL, points.WEIGHTS_SHA256)


def load(path):
    model = points.build_model("cuda")
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=False)["model"])
    return model.to("cuda").eval()


MODELS = {"current": load(CURRENT), "new": load(NEW)}


def find_part(part):
    return next(p for p in Path("/kaggle/input").rglob(f"part_{part}") if (p / "train_data").is_dir())


def qnrf_test():
    d = next(p for p in Path("/kaggle/input").rglob("Test") if any(p.glob("img_*_ann.mat")))
    return [(p, float(len(io.loadmat(p.with_name(p.stem + "_ann.mat"))["annPoints"])), [])
            for p in sorted(d.glob("img_*.jpg"))]


val = []
for part in ("A", "B"):
    src = find_part(part) / "train_data"
    for i, img in enumerate(sorted((src / "images").glob("*.jpg"))):
        if i % 10 == 0:
            gt = io.loadmat(src / "ground-truth" / f"GT_{img.stem}.mat")["image_info"][0][0][0][0][0]
            val.append((img, float(len(gt)), []))
tests = {f"ShanghaiTech {p}": [(q, float(len(pts)), []) for q, pts in load_shanghaitech("/kaggle/input", p, "test")]
         for p in ("A", "B")}
tests["UCF-QNRF"] = qnrf_test()
india = benchmark.load(W / "repo/data/india_test")
tests["India"] = [(W / "repo/data/india_test/images" / r["image"], float(r["true"]), r["ignore"]) for r in india]


def raw_counts(model, items):
    points.load_point_model = lambda: (model, "cuda")
    out = []
    for path, truth, ignore in items:
        res = points.count_points(cv2.imread(str(path)))
        xy = [(c, r) for r, c in res["points"]]
        out.append(len(benchmark._outside(xy, ignore)) if ignore else res["raw_count"])
    return np.array(out, float)


def fit(raw, true):
    ok = (raw > 0) & (true > 0)
    b, a = np.polyfit(np.log(raw[ok]), np.log(true[ok]), 1)
    return float(np.exp(a)), float(b)


def correct(raw, ab):
    a, b = ab
    return np.where(raw > 0, a * np.maximum(raw, 1e-9) ** b, 0.0)


results = {"protocol": __doc__, "configs": {}}
for cfg, (work, fit_side) in CONFIGS.items():
    points.WORK_SIDE = work
    points.fit_max_side = lambda ceiling=None, _f=fit_side, **k: min(ceiling or _f, _f)
    vt = np.array([t for _, t, _ in val])
    corr = {k: fit(raw_counts(m, val), vt) for k, m in MODELS.items()}
    corr["current (shipped)"] = points.CORRECTION
    res = {"corrections": corr, "tests": {}}
    for name, items in tests.items():
        t0 = time.time()
        truth = np.array([t for _, t, _ in items])
        raws = {k: raw_counts(m, items) for k, m in MODELS.items()}
        raws["current (shipped)"] = raws["current"]
        row = {}
        for k, ab in corr.items():
            pred = correct(raws[k], ab)
            row[k] = {"accuracy": round(float(1 - np.abs(pred - truth).sum() / truth.sum()), 4),
                      "mae": round(float(np.abs(pred - truth).mean()), 2)}
            row[k]["per_photo"] = [round(float(x), 2) for x in pred]
        row["truth"] = truth.tolist()
        res["tests"][name] = row
        print(cfg, name, {k: v["accuracy"] for k, v in row.items() if isinstance(v, dict)},
              f"({time.time() - t0:.0f}s)", flush=True)
    results["configs"][cfg] = res
(OUT / "app_compare.json").write_text(json.dumps(results, indent=1))
