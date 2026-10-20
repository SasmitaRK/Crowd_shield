"""Compare counting methods on ShanghaiTech: accuracy overall and by crowd size, with a chart.

Accuracy here is 1 - (total absolute error / total true count) within a group of
photos: 90% means the counts were off by 10% of the people, on average.

Each --series is NAME=CSV:COLUMN, pointing at a per_image.csv written by
evaluate_counting.py (or the PET training run) and the column holding that
method's counts. Give one set per part:

    python -m eval.compare_counting --out results/shanghaitech \\
        --series "A|Original app=results/a_base.csv:original_drone" \\
        --series "A|DM-Count=results/a_dm.csv:dmcount" ...
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

BUCKETS = [(0, 100), (100, 250), (250, 500), (500, 1000), (1000, np.inf)]
# Validated categorical slots (light surface): blue, orange, aqua, in fixed order.
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(spec: str):
    part_name, source = spec.split("=", 1)
    part, name = part_name.split("|", 1)
    path, column = source.rsplit(":", 1)
    rows = list(csv.DictReader(open(path)))
    by_image = {r["image"]: (float(r["true"]), float(r[column])) for r in rows}
    return part, name, by_image


def accuracy(true, pred) -> float:
    true, pred = np.asarray(true), np.asarray(pred)
    return max(0.0, 1 - np.abs(pred - true).sum() / true.sum()) if true.sum() else float("nan")


def bucket_label(lo, hi) -> str:
    return f"{lo:g}+" if np.isinf(hi) else f"{lo:g}–{hi:g}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--series", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    parts: dict[str, dict[str, dict]] = {}
    for spec in args.series:
        part, name, data = load(spec)
        parts.setdefault(part, {})[name] = data

    table = ["| Part | Method | Accuracy | MAE | " +
             " | ".join(bucket_label(*b) for b in BUCKETS) + " |",
             "|---|---|---:|---:|" + "---:|" * len(BUCKETS)]
    results = {}
    for part, methods in parts.items():
        images = sorted(set.intersection(*(set(d) for d in methods.values())))
        for name, data in methods.items():
            true = np.array([data[i][0] for i in images])
            pred = np.array([data[i][1] for i in images])
            per_bucket = []
            for lo, hi in BUCKETS:
                m = (true >= lo) & (true < hi)
                per_bucket.append((accuracy(true[m], pred[m]), int(m.sum())))
            results[(part, name)] = per_bucket
            cells = [f"{a:.0%} ({n})" if n else "–" for a, n in per_bucket]
            table.append(f"| {part} | {name} | {accuracy(true, pred):.1%} | "
                         f"{np.abs(pred - true).mean():.1f} | " + " | ".join(cells) + " |")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "comparison.md").write_text(
        "Accuracy = 1 − total absolute error ÷ total true count. Brackets: photos per group.\n\n"
        + "\n".join(table) + "\n", encoding="utf-8")
    plot(parts, results, args.out / "accuracy_by_crowd_size.png")
    print("\n".join(table))


def plot(parts, results, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(dict.fromkeys(n for methods in parts.values() for n in methods))
    fig, axes = plt.subplots(1, len(parts), figsize=(5.2 * len(parts), 4.2), sharey=True)
    axes = np.atleast_1d(axes)
    titles = {"A": "Part A: packed crowds", "B": "Part B: busy streets"}
    for ax, (part, methods) in zip(axes, parts.items()):
        kept = [i for i, b in enumerate(BUCKETS)
                if all(results[(part, n)][i][1] for n in methods)]
        x = np.arange(len(kept))
        width = 0.8 / len(names)
        for j, name in enumerate(names):
            if name not in methods:
                continue
            values = [results[(part, name)][i][0] * 100 for i in kept]
            bars = ax.bar(x + (j - (len(names) - 1) / 2) * width, values, width * 0.9,
                          color=COLOURS[j], label=name, edgecolor="#fcfcfb", linewidth=1)
            if j == len(names) - 1:  # label the newest method only
                for b, v in zip(bars, values):
                    ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%",
                            ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(x, [bucket_label(*BUCKETS[i]) for i in kept], color=MUTED, fontsize=9)
        ax.set_xlabel("True number of people in the photo", color=MUTED, fontsize=9)
        ax.set_title(titles.get(part, part), color=INK, fontsize=11, loc="left")
        ax.set_ylim(0, 105)
        ax.set_facecolor("#fcfcfb")
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(axis="y", colors=MUTED, labelsize=9, length=0)
    axes[0].set_ylabel("Counting accuracy (%)", color=MUTED, fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, loc="upper left",
               bbox_to_anchor=(0.01, 0.93), ncol=len(labels))
    fig.suptitle("How accurately each method counts people, by crowd size (ShanghaiTech test photos)",
                 color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    fig.savefig(path, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)


if __name__ == "__main__":
    main()
