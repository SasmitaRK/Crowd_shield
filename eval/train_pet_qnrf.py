"""Crowd Shield: teach the PET counter more kinds of crowds, without forgetting ShanghaiTech.

Starts from the current app model (pet_shab.pth: PET trained on JHU-Crowd++, then ShanghaiTech) and
fine-tunes it on ShanghaiTech A (twice over) + B and UCF-QNRF (1,201 dense, varied crowd photos it has never seen),
plus the 23 people-free Indian railway photos at about 1% of the set, so gravel and tracks are seen as
empty without making the model shy. No Indian crowd photo is trained on: all 10 hand-checked Indian
photos stay a clean test.

Fixed epochs, no checkpoint picking on test data. 10% of the ShanghaiTech and QNRF training photos are
held out to refit the count correction (true ~ a * raw^b) for each model the same way. Both the current
model and the new one are then scored on the ShanghaiTech A and B tests, the QNRF test and the Indian
photos.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SMOKE = False  # quick end-to-end check: 1 epoch, few photos
EPOCHS = 1 if SMOKE else 40
MAX_SIDE = 2048  # QNRF photos are up to 9000 px; the app also counts at this size
WORK = Path("/tmp/crowd")
PET = WORK / "PET"
CODE = WORK / "crowd-shield"
SPLIT = WORK / "split"
OUT = Path("/kaggle/working/output")
RELEASE = "https://github.com/khushi-git-7/Crowd_shield/releases/download/pet-shab-v1/pet_shab.pth"


def run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def patch(path: Path, old: str, new: str):
    text = path.read_text()
    if old not in text:
        sys.exit(f"Patch target not found in {path}: {old!r}")
    path.write_text(text.replace(old, new))


def find_part(part):
    return next(p for p in Path("/kaggle/input").rglob(f"part_{part}") if (p / "train_data").is_dir())


def find_qnrf(split):
    return next(p for p in Path("/kaggle/input").rglob(split) if any(p.glob("img_*_ann.mat")))


def save_gt(path: Path, xy: np.ndarray):
    """Write head points (N x 2, x then y) in ShanghaiTech's .mat layout."""
    import scipy.io as io
    rec = np.empty((1, 1), dtype=[("location", "O"), ("number", "O")])
    rec[0, 0] = (xy.astype(float).reshape(-1, 2), np.array([[len(xy)]]))
    cell = np.empty((1, 1), dtype=object)
    cell[0, 0] = rec
    io.savemat(path, {"image_info": cell})


def inside(p, zones):
    return any(a <= p[0] <= c and b <= p[1] <= d for a, b, c, d in zones)


run(["nvidia-smi"])
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
run(["git", "clone", "--depth", "1", "https://github.com/cxliu0/PET.git", str(PET)])
run(["git", "clone", "--depth", "1", "https://github.com/khushi-git-7/Crowd_shield.git", str(CODE)])
patch(PET / "datasets/SHA.py",
      "torch.nn.functional.upsample_bilinear(img.unsqueeze(0), scale_factor=scale)",
      "torch.nn.functional.interpolate(img.unsqueeze(0), scale_factor=scale, mode='bilinear', align_corners=True)")
patch(PET / "main.py", "torch.load(args.resume, map_location='cpu')",
      "torch.load(args.resume, map_location='cpu', weights_only=False)")
patch(PET / "models/pet.py", "points_queries_win[:, v_idx].reshape(-1, 2)",
      "points_queries_win[:, v_idx.cpu()].reshape(-1, 2)")
patch(PET / "datasets/__init__.py", "'SHA': './data/ShanghaiTech/part_A/',", "'SHA': __import__('os').environ['PET_DATA'],")
(PET / "pretrained").mkdir()
run(["wget", "-q", "-O", str(PET / "pretrained/vgg16_bn-6c64b313.pth"),
     "https://download.pytorch.org/models/vgg16_bn-6c64b313.pth"])
run(["wget", "-q", "-O", str(WORK / "pet_shab.pth"), RELEASE])

import cv2  # noqa: E402
import scipy.io as io  # noqa: E402
import torch  # noqa: E402

sys.path.insert(0, str(CODE))
from crowdshield.points import build_model, points_from_model  # noqa: E402

india = json.loads((CODE / "data/india_test/labels.json").read_text())["images"]
IMG_DIR = CODE / "data/india_test/images"
INDIA = sorted(n for n, r in india.items() if r.get("points"))


def sh_points(gt):
    return io.loadmat(gt)["image_info"][0][0][0][0][0].reshape(-1, 2)


def qnrf_points(img):
    return io.loadmat(img.with_name(img.stem + "_ann.mat"))["annPoints"].reshape(-1, 2)


# Every training source as (image, points x-y, name); every 10th held out for the count correction.
train_items, val_items = [], []
for part in ("A", "B"):
    src = find_part(part) / "train_data"
    for i, img in enumerate(sorted((src / "images").glob("*.jpg"))):
        item = (img, sh_points(src / "ground-truth" / f"GT_{img.stem}.mat"), f"SH{part}_{img.stem}")
        if i % 10 == 0:
            val_items.append(item)
        else:  # packed crowds (A) twice, so the new photos do not pull it away from them
            train_items += [item] if part == "B" else [item, (*item[:2], item[2] + "_2")]
for i, img in enumerate(sorted(find_qnrf("Train").glob("img_*.jpg"))):
    item = (img, qnrf_points(img), f"QN_{img.stem}")
    (val_items if i % 10 == 0 else train_items).append(item)
if SMOKE:
    train_items, val_items = train_items[::40], val_items[::20]
print(f"training photos: {len(train_items)}, held out: {len(val_items)}", flush=True)


def fit(img, pts):
    """Shrink a photo so its long side is at most MAX_SIDE and its short side at least 320 px."""
    h, w = img.shape[:2]
    s = min(1.0, MAX_SIDE / max(h, w))
    s = max(s, 320 / min(h, w))
    if s != 1.0:
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    return img, pts * s


for split in ("train_data", "test_data"):
    for sub in ("images", "ground-truth"):
        (SPLIT / split / sub).mkdir(parents=True, exist_ok=True)
for img_path, pts, name in train_items:
    img, p = fit(cv2.imread(str(img_path)), pts)
    cv2.imwrite(str(SPLIT / "train_data/images" / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    save_gt(SPLIT / "train_data/ground-truth" / f"GT_{name}.mat", p)
for neg in sorted((CODE / "data/india_negatives/images").glob("*.jpg")):
    img, _ = fit(cv2.imread(str(neg)), np.zeros((0, 2)))
    cv2.imwrite(str(SPLIT / "train_data/images" / f"NEG_{neg.stem}.jpg"), img)
    save_gt(SPLIT / "train_data/ground-truth" / f"GT_NEG_{neg.stem}.mat", np.zeros((0, 2)))
for img_path, pts, name in val_items[:2]:  # PET wants a test folder; unused (fixed epochs)
    img, p = fit(cv2.imread(str(img_path)), pts)
    cv2.imwrite(str(SPLIT / "test_data/images" / f"{name}.jpg"), img)
    save_gt(SPLIT / "test_data/ground-truth" / f"GT_{name}.mat", p)

torch.save({"model": torch.load(WORK / "pet_shab.pth", map_location="cpu", weights_only=False)["model"]},
           WORK / "init.pth")
t0 = time.time()
run([sys.executable, "main.py", "--lr=0.00005", "--lr_backbone=0.000005", "--backbone=vgg16_bn",
     "--ce_loss_coef=1.0", "--point_loss_coef=5.0", "--eos_coef=0.5", "--dec_layers=2",
     "--hidden_dim=256", "--dim_feedforward=512", "--nheads=8", "--dropout=0.0",
     f"--epochs={EPOCHS}", "--dataset_file=SHA", "--eval_freq=100000", "--num_workers=4",
     "--output_dir=qnrf", f"--resume={WORK / 'init.pth'}"],
    cwd=PET, env={**os.environ, "PET_DATA": f"{SPLIT}/"})
print(f"trained {EPOCHS} epochs in {(time.time() - t0) / 60:.1f} min", flush=True)
ckpt = torch.load(PET / "outputs/SHA/qnrf/checkpoint.pth", map_location="cpu", weights_only=False)
torch.save({"model": ckpt["model"]}, OUT / "pet_qnrf.pth")
shutil.rmtree(SPLIT)

device = "cuda"
os.chdir(PET)


def load(path):
    model = build_model(device)
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=False)["model"])
    return model.to(device).eval()


def raw_count(model, img, zones=()):
    """Count at most MAX_SIDE px on the long side (shrunk, never enlarged), outside ignore zones."""
    s = min(1.0, MAX_SIDE / max(img.shape[:2]))
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    pts = points_from_model(model, device, img) / s  # (row, col) in the original photo
    return sum(1 for r, c in pts if not inside((c, r), zones))


models = {"current": load(WORK / "init.pth"), "new": load(OUT / "pet_qnrf.pth")}


def raw_all(items):
    """Raw counts of both models for (image path, true count, ignore zones) items."""
    rows = []
    for img_path, true, zones in items:
        img = cv2.imread(str(img_path))
        row = {"image": Path(img_path).name, "true": int(true)}
        for k, m in models.items():
            row[k] = raw_count(m, img, zones)
        rows.append(row)
    return rows


# Count correction for each model, refit on the held-out training photos.
val = raw_all([(p, len(pts), ()) for p, pts, _ in val_items])
corr = {}
for k in models:
    t = np.array([r["true"] for r in val], float)
    p = np.array([r[k] for r in val], float)
    ok = (t > 0) & (p > 0)
    b, a = np.polyfit(np.log(p[ok]), np.log(t[ok]), 1)
    corr[k] = (float(np.exp(a)), float(b))
print("corrections:", corr, flush=True)


def score(name, items):
    rows = raw_all(items)
    for r in rows:
        for k, (a, b) in corr.items():
            r[k] = round(a * r[k] ** b, 1) if r[k] > 0 else 0.0
    t = np.array([r["true"] for r in rows], float)
    summary = {}
    for k in models:
        p = np.array([r[k] for r in rows], float)
        summary[k] = {"mae": round(float(np.abs(p - t).mean()), 2),
                      "accuracy": round(float(1 - np.abs(p - t).sum() / t.sum()), 4)}
    print(f"{name}: {summary}", flush=True)
    return {"summary": summary, "rows": rows}


results = {"protocol": __doc__, "epochs": EPOCHS, "corrections": corr, "tests": {}}
for part in ("A", "B"):
    src = find_part(part) / "test_data"
    imgs = sorted((src / "images").glob("*.jpg"))[: 6 if SMOKE else None]
    results["tests"][f"shanghaitech_{part}"] = score(
        f"ShanghaiTech {part}", [(p, len(sh_points(src / "ground-truth" / f"GT_{p.stem}.mat")), ()) for p in imgs])
imgs = sorted(find_qnrf("Test").glob("img_*.jpg"))[: 6 if SMOKE else None]
results["tests"]["qnrf"] = score("UCF-QNRF", [(p, len(qnrf_points(p)), ()) for p in imgs])
results["tests"]["india"] = score("India", [
    (IMG_DIR / n, sum(1 for q in india[n]["points"] if not inside(q, india[n]["ignore"])), india[n]["ignore"])
    for n in INDIA])
(OUT / "results.json").write_text(json.dumps(results, indent=1))
shutil.rmtree(WORK)
