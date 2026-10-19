"""Measure how accurately Crowd Shield counts people, on photos where every head is labelled.

Runs each counting method over ShanghaiTech (Part A: packed crowds, Part B:
street scenes) and writes per-image counts, overall and per-crowd-size errors,
and charts. From the repo root:

    python -m eval.evaluate_counting --data /kaggle/input/shanghaitech --part A \
        --out results/shanghaitech_A
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from crowdshield.datasets import load_shanghaitech
from crowdshield.metrics import summarise

# name -> (model key, detect_people settings). Each step changes one thing.
METHODS = {
    # What the app did before v2: 640px input, Ultralytics' 300-box cap, faces on.
    "original_ground":   ("yolov8l",    {"use_faces": True,  "imgsz": 640,  "max_det": 300}),
    "original_drone":    ("crowd_yolo", {"use_faces": True,  "imgsz": 640,  "max_det": 300}),
    "ground_nofaces":    ("yolov8l",    {"use_faces": False, "imgsz": 640,  "max_det": 300}),
    "drone_nofaces":     ("crowd_yolo", {"use_faces": False, "imgsz": 640,  "max_det": 300}),
    "ground_nocap":      ("yolov8l",    {"use_faces": False, "imgsz": 640,  "max_det": 3000}),
    "drone_nocap":       ("crowd_yolo", {"use_faces": False, "imgsz": 640,  "max_det": 3000}),
    "ground_nocap_1280": ("yolov8l",    {"use_faces": False, "imgsz": 1280, "max_det": 3000}),
    "drone_nocap_1280":  ("crowd_yolo", {"use_faces": False, "imgsz": 1280, "max_det": 3000}),
}


def count_with(name: str, img: np.ndarray) -> int:
    from crowdshield.detection import detect_people

    key, settings = METHODS[name]
    return detect_people(img, key, allow_fallback=False, **settings)["count"]


def run(samples, methods, progress_every: int = 20) -> list[dict]:
    import cv2

    def read(path):
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Could not read {path}")
        return img

    first = read(samples[0][0])
    for name in methods:  # load every model once so timings exclude start-up
        count_with(name, first)

    rows = []
    for i, (image_path, points) in enumerate(samples, 1):
        img = read(image_path)
        row = {"image": image_path.name, "true": len(points)}
        for name in methods:
            start = time.perf_counter()
            row[name] = count_with(name, img)
            row[f"{name}_ms"] = round((time.perf_counter() - start) * 1000, 1)
        rows.append(row)
        if i % progress_every == 0 or i == len(samples):
            print(f"{i}/{len(samples)} images", flush=True)
    return rows


def summarise_rows(rows: list[dict], methods: list[str]) -> dict:
    true = [r["true"] for r in rows]
    return {
        name: {**summarise([r[name] for r in rows], true),
               "mean_ms": float(np.mean([r[f"{name}_ms"] for r in rows]))}
        for name in methods
    }


def markdown_report(title: str, n_images: int, summary: dict) -> str:
    lines = [f"# {title}", "", f"{n_images} images. Lower error is better; "
             "negative bias means the method undercounts.", "",
             "| Method | MAE | RMSE | Bias | ms / image |", "|---|---:|---:|---:|---:|"]
    for name, s in summary.items():
        lines.append(f"| {name} | {s['mae']:.1f} | {s['rmse']:.1f} | "
                     f"{s['bias']:+.1f} | {s['mean_ms']:.0f} |")

    ranges = [b["range"] for b in next(iter(summary.values()))["buckets"]]
    lines += ["", "## Error by crowd size (MAE, with bias in brackets)", "",
              "| True count | Images | " + " | ".join(summary) + " |",
              "|---|---:|" + "---:|" * len(summary)]
    for i, rng in enumerate(ranges):
        first = next(iter(summary.values()))["buckets"][i]
        cells = [f"{s['buckets'][i]['mae']:.0f} ({s['buckets'][i]['bias']:+.0f})"
                 for s in summary.values()]
        lines.append(f"| {rng} | {first['images']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def plot(rows: list[dict], summary: dict, title: str, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    true = np.array([r["true"] for r in rows])
    fig, ax = plt.subplots(figsize=(6, 6))
    top = true.max() * 1.05
    ax.plot([0, top], [0, top], color="#999999", linewidth=1, label="Perfect count")
    for name in summary:
        ax.scatter(true, [r[name] for r in rows], s=10, alpha=0.6, label=name)
    ax.set(xlabel="True count", ylabel="Predicted count", title=title,
           xlim=(0, top), ylim=(0, top))
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out / "counts.png", dpi=150)
    plt.close(fig)

    ranges = [b["range"] for b in next(iter(summary.values()))["buckets"]]
    x = np.arange(len(ranges))
    width = 0.8 / len(summary)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (name, s) in enumerate(summary.items()):
        ax.bar(x + i * width, [b["bias"] for b in s["buckets"]], width, label=name)
    ax.axhline(0, color="#999999", linewidth=1)
    ax.set_xticks(x + width * (len(summary) - 1) / 2, ranges)
    ax.set(xlabel="True count per image", ylabel="Average error (people)",
           title=f"{title}: over- and undercounting by crowd size")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out / "error_by_size.png", dpi=150)
    plt.close(fig)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True,
                        help="Folder that contains ShanghaiTech's part_A / part_B")
    parser.add_argument("--part", choices=["A", "B"], default="A")
    parser.add_argument("--split", choices=["train", "test"], default="test")
    parser.add_argument("--methods", default=",".join(METHODS),
                        help="Comma-separated names from: " + ", ".join(METHODS))
    parser.add_argument("--limit", type=int, default=0, help="Only the first N images")
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args(argv)

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    unknown = sorted(set(methods) - METHODS.keys())
    if unknown:
        parser.error(f"unknown methods: {', '.join(unknown)}")

    samples = load_shanghaitech(args.data, args.part, args.split)
    if args.limit:
        samples = samples[:args.limit]
    title = f"ShanghaiTech Part {args.part} ({args.split})"
    print(f"{title}: {len(samples)} images, methods: {', '.join(methods)}", flush=True)

    rows = run(samples, methods)
    summary = summarise_rows(rows, methods)

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "per_image.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "summary.json").write_text(json.dumps(
        {"dataset": title, "images": len(rows), "methods": summary}, indent=2))
    report = markdown_report(title, len(rows), summary)
    (args.out / "summary.md").write_text(report)
    plot(rows, summary, title, args.out)
    print(report)


if __name__ == "__main__":
    main()
