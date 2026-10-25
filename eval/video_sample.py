"""Analyse the built-in sample clip exactly as the Video page does, and save the result so the page can
show it instantly: the annotated MP4 and the readings (per zone, once per second), surge events and
settings as JSON."""
import json, subprocess, sys, time
from pathlib import Path

OUT = Path("/kaggle/working"); W = Path("/tmp/vs"); W.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "video-rebuild",
                "https://github.com/khushi-git-7/Crowd_shield.git", str(W / "repo")], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy", "imageio-ffmpeg"], check=False)
sys.path.insert(0, str(W / "repo"))
import os; os.chdir(W / "repo")
import cv2, numpy as np  # noqa: E402
from crowdshield import points  # noqa: E402
from crowdshield.monitor import VideoMonitor, Zone  # noqa: E402
from crowdshield.video_render import PointRecorder, render  # noqa: E402

points.WORK_SIDE = 1024  # as the free server counts
CLIP = "assets/samples/paris_saint_lazare.mp4"
cap = cv2.VideoCapture(CLIP); fps = cap.get(cv2.CAP_PROP_FPS); w = int(cap.get(3)); h = int(cap.get(4)); cap.release()


def frames():
    cap = cv2.VideoCapture(CLIP)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        yield f
    cap.release()


box = lambda fx0, fx1, fy0, fy1: [(w * fx0, h * fy0), (w * fx1, h * fy0), (w * fx1, h * fy1), (w * fx0, h * fy1)]
zones = [("Stairs", box(0.67, 1.0, 0.25, 1.0)), ("Concourse", box(0.0, 0.65, 0.53, 1.0))]
capacities = {"Stairs": 40, "Concourse": 50}
rec = PointRecorder()
t0 = time.time()
monitor = VideoMonitor(rec, fps, [Zone(n, p) for n, p in zones])
rows, events = monitor.run(frames())
print("analysed in", round(time.time() - t0), "s;", len(rows), "readings,", len(events), "events", flush=True)
render(frames(), fps, OUT / "paris_saint_lazare_annotated.mp4", zones, rows, events, capacities, rec.points,
       monitor.count_every)
clean = lambda v: None if isinstance(v, float) and not np.isfinite(v) else v
(OUT / "paris_saint_lazare_analysis.json").write_text(json.dumps({
    "clip": CLIP, "fps": fps, "size": [w, h], "counter": "point model (PET)",
    "zones": [{"name": n, "polygon": [list(map(float, p)) for p in poly], "capacity": capacities[n]} for n, poly in zones],
    "rows": [{k: clean(v) for k, v in r.items()} for r in rows], "events": events}, indent=1))
print("peak per zone:", {z: max(r["people"] for r in rows if r["zone"] == z) for z, _ in zones}, events, flush=True)
