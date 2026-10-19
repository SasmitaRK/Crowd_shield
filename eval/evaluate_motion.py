"""Test the movement alarm on the UMN crowd-escape videos.

The UMN dataset (University of Minnesota) has 11 clips across 3 scenes. Each
starts with people walking normally, then everyone suddenly runs away. The
video marks the escape with a red "Abnormal Crowd Activity" label in the top
left. We hide that label from the optical flow, run the alarm from
crowdshield.motion on each clip, and measure:

- how many escapes it catches, and when, relative to the label
- false alarms while people are still walking normally
- frame-level ROC AUC of the speed-versus-normal score

The label runs late: looking at the frames, people are already running 1 to
1.5 seconds before it appears. So an alarm up to --label-lag seconds (default
2) before the label counts as a catch, and those ambiguous frames are left out
of the AUC.

From the repo root:

    python -m eval.evaluate_motion --video data/umn/Crowd-Activity-All.avi --out results/umn
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from crowdshield.motion import SpeedAlarm, flow_stats, optical_flow

# Where the ground-truth label is drawn, in the 320 x 240 frames: rows, columns.
LABEL_BOX = (slice(0, 30), slice(0, 175))

# UMN's clips in order: 2 on a lawn, 6 in an indoor hall, 3 on a plaza.
SCENES = ["lawn"] * 2 + ["indoor"] * 6 + ["plaza"] * 3


def label_is_on(frame: np.ndarray) -> bool:
    """True when the red "Abnormal Crowd Activity" text is drawn on a white box."""
    box = frame[LABEL_BOX].astype(int)
    b, g, r = box[..., 0], box[..., 1], box[..., 2]
    red = (r > 150) & (g < 90) & (b < 90)
    white = (r > 230) & (g > 230) & (b > 230)
    return red.sum() > 40 and white.sum() > 300


def read_video(path: Path):
    """Per frame: the flow stats (label box hidden) and whether the label is on."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    rows, prev = [], None
    mask = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if mask is None:
            mask = np.ones(gray.shape, dtype=bool)
            mask[LABEL_BOX] = False
        stats = (flow_stats(optical_flow(prev, gray), mask) if prev is not None
                 else {"speed": 0.0, "moving": 0.0, "coherence": 0.0, "turbulence": 0.0})
        rows.append({"frame": len(rows), "abnormal": label_is_on(frame), **stats})
        prev = gray
    return rows, fps


def split_clips(rows: list[dict]) -> list[tuple[int, int]]:
    """Each clip ends with its escape, so a new clip starts where the label turns off."""
    starts = [0] + [i for i in range(1, len(rows))
                    if rows[i - 1]["abnormal"] and not rows[i]["abnormal"]]
    return list(zip(starts, starts[1:] + [len(rows)]))


def roc_auc(scores, labels) -> float:
    """Probability that a random abnormal frame scores above a random normal one."""
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    order = scores.argsort(kind="mergesort")
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):  # average ranks over ties
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos, neg = labels.sum(), (~labels).sum()
    return float((ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg))


def evaluate(rows, fps, ratio=2.0, hold_frames=15, baseline_frames=90, label_lag_s=2.0):
    lag = int(round(label_lag_s * fps))
    clips, scores = [], np.zeros(len(rows))
    ambiguous = np.zeros(len(rows), dtype=bool)
    for start, end in split_clips(rows):
        onset = next((i for i in range(start, end) if rows[i]["abnormal"]), None)
        if onset is None:  # a few trailing frames after the last escape
            continue
        alarm = SpeedAlarm(baseline_frames, ratio, hold_frames)
        fired = []
        for i in range(start + 1, end):  # the first frame's flow spans the scene cut
            if alarm.update(rows[i]["speed"]):
                fired.append(i)
            if alarm.normal is not None:
                scores[i] = rows[i]["speed"] / alarm.normal
        ambiguous[max(start, onset - lag):onset] = True
        hits = [f for f in fired if f >= onset - lag]
        clips.append({
            "clip": len(clips) + 1,
            "scene": SCENES[len(clips)] if len(clips) < len(SCENES) else "",
            "start_s": round(start / fps, 1),
            "label_s": round(onset / fps, 1),
            "detected": bool(hits),
            # negative: the alarm fired before the (late) label appeared
            "alarm_vs_label_s": round((hits[0] - onset) / fps, 2) if hits else None,
            "false_alarms": sum(1 for f in fired if f < onset - lag),
        })

    scored = [i for i in range(len(rows)) if scores[i] > 0 and not ambiguous[i]]
    labels = [rows[i]["abnormal"] for i in scored]
    timings = [c["alarm_vs_label_s"] for c in clips if c["alarm_vs_label_s"] is not None]
    summary = {
        "clips": len(clips),
        "detected": sum(c["detected"] for c in clips),
        "missed_clips": [f"{c['clip']} ({c['scene']})" for c in clips if not c["detected"]],
        "false_alarms": sum(c["false_alarms"] for c in clips),
        "median_alarm_vs_label_s": float(np.median(timings)) if timings else None,
        "latest_alarm_vs_label_s": max(timings) if timings else None,
        "frame_auc_speed_ratio": roc_auc([scores[i] for i in scored], labels),
        "rule": f"alarm when speed > {ratio}x the clip's normal pace for {hold_frames} frames; "
                f"normal pace = median of the first {baseline_frames} frames",
        "label_lag_allowed_s": label_lag_s,
    }
    return clips, scores, summary


def plot(rows, scores, clips, fps, ratio, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.arange(len(rows)) / fps
    abnormal = np.array([r["abnormal"] for r in rows])
    fig, ax = plt.subplots(figsize=(12, 3.6))
    ax.fill_between(t, 0, 1, where=abnormal, transform=ax.get_xaxis_transform(),
                    color="#f4c7c3", label="People running away (ground truth)")
    ax.plot(t, scores, color="#1f5fa8", linewidth=1, label="Speed ÷ normal pace")
    ax.axhline(ratio, color="#666666", linestyle="--", linewidth=1, label=f"Alarm level ({ratio}x)")
    for c in clips:
        if c["alarm_vs_label_s"] is not None:
            ax.axvline(c["label_s"] + c["alarm_vs_label_s"], color="#b3261e", linewidth=1.2)
    ax.set(xlabel="Seconds", ylabel="Speed ÷ normal", xlim=(0, t[-1]),
           ylim=(0, max(ratio * 2.5, float(np.percentile(scores, 99.5)))),
           title="UMN crowd-escape videos: movement alarm (red lines = alarm raised)")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out / "timeline.png", dpi=150)
    plt.close(fig)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("results/umn"))
    parser.add_argument("--ratio", type=float, default=2.0)
    parser.add_argument("--hold-frames", type=int, default=15)
    parser.add_argument("--label-lag", type=float, default=2.0,
                        help="Seconds before the label in which an alarm still counts as a catch")
    args = parser.parse_args(argv)

    rows, fps = read_video(args.video)
    clips, scores, summary = evaluate(rows, fps, args.ratio, args.hold_frames,
                                      label_lag_s=args.label_lag)

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "per_frame.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[*rows[0], "score"])
        writer.writeheader()
        writer.writerows({**r, "score": round(float(s), 4)} for r, s in zip(rows, scores))
    with open(args.out / "clips.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(clips[0]))
        writer.writeheader()
        writer.writerows(clips)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    plot(rows, scores, clips, fps, args.ratio, args.out)

    print(json.dumps(summary, indent=2))
    for c in clips:
        print(c)


if __name__ == "__main__":
    main()
