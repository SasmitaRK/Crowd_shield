"""Video — watch a fixed camera zone by zone: people per m², speed, crowd pressure, early warning."""

import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from ui import page_header

from shared_state import GLOBAL_CSS, init_state

st.set_page_config(page_title="Video • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Video monitor", "Watch a fixed camera zone by zone: people per m², walking speed, crowd pressure, sudden-surge alarms and a forecast of when a zone gets dangerous.", "Monitor")
st.caption("Upload a clip from a fixed camera. Mark a rectangle of known size on the floor "
           "and the zones to watch; Crowd Shield then reports people per m², speed, "
           "crowd pressure and how long each zone has before it reaches 5 people per m².")

MAX_WIDTH = 960  # frames are shrunk to this width; all coordinates below use it
# The free hosted demo has little memory and no GPU, so it analyses short clips. Set
# CROWDSHIELD_MAX_VIDEO_S on your own machine to allow longer ones.
MAX_SECONDS = int(os.environ.get("CROWDSHIELD_MAX_VIDEO_S", 20))
SAMPLE = {
    "path": Path(__file__).resolve().parent.parent / "assets" / "samples" / "paris_saint_lazare.mp4",
    "label": "Sample: Paris Saint-Lazare station",
    "credit": "Sample clip: 15 s from \"2025-11-06 17-33-16 - Paris - Saint-Lazare\" by Baidax, "
              "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), via "
              "[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:2025-11-06_17-33-16_-_Paris_-_Saint-Lazare.webm). "
              "A fixed camera over the concourse and stairs.",
    # Zones as fractions of the frame: the stairs on the right, the concourse floor below.
    "zones": [("Stairs", (0.67, 1.0), (0.25, 1.0)), ("Concourse", (0.0, 0.65), (0.53, 1.0))],
}
ZONE_COLOURS = [(0, 200, 255), (255, 120, 0), (180, 0, 255), (0, 220, 120)]
LEVEL_COLOURS = {"Normal": (80, 200, 80), "Crowded": (0, 200, 255),
                 "Dangerous": (0, 120, 255), "Crush risk": (0, 0, 255), None: (200, 200, 200)}


def iter_frames(path, max_seconds):
    """Yield frames one at a time, shrunk to MAX_WIDTH, so a clip never sits in memory whole."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    try:
        for _ in range(int(fps * max_seconds)):
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[1] > MAX_WIDTH:
                s = MAX_WIDTH / frame.shape[1]
                frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            yield frame
    finally:
        cap.release()


def video_fps(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()
    return fps


def probe(path, max_seconds, fps, step=3, scale=0.25):
    """First frame, frame count and how much the camera moves, keeping only tiny frames."""
    from crowdshield.motion import camera_motion

    first, n, small = None, 0, []
    for i, frame in enumerate(iter_frames(path, max_seconds)):
        if first is None:
            first = frame
        if i % step == 0:
            small.append(cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
        n += 1
    # The small frames are already every `step`th frame at `scale`, so compare neighbours as-is.
    camera = camera_motion(small, fps / step, step=1, scale=1.0) if small else 0.0
    return first, n, camera


def clip_on_disk(data: bytes, suffix: str) -> str:
    """OpenCV only reads video from a file. The caller deletes it as soon as decoding is done."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        return f.name


def make_counter():
    """The most accurate counter that can run here: point model, density model, then YOLO."""
    from crowdshield.monitor import points_to_grid

    try:
        from crowdshield.points import load_point_model, point_grid

        load_point_model()
        return point_grid, "point model (PET)"
    except Exception:
        pass
    try:
        from crowdshield.density import density_grid, load_density_model, DEFAULT_WEIGHTS

        load_density_model(str(DEFAULT_WEIGHTS))
        return density_grid, "density model (DM-Count)"
    except Exception:
        from crowdshield.detection import detect_people, load_detector

        if load_detector("crowd_yolo") is None:
            return None, "no counting model is installed (needs PyTorch and Ultralytics)"

        def yolo_grid(frame):
            boxes = detect_people(frame)["person_boxes"]
            centres = [(y + h / 2, x + w / 2) for x, y, w, h in boxes]
            return points_to_grid(centres, frame.shape)

        return yolo_grid, "YOLO (density model unavailable)"


def draw(frame, corners, zones, levels=None):
    out = frame.copy()
    if corners is not None:
        cv2.polylines(out, [np.int32(corners)], True, (0, 255, 255), 2)
    for i, (name, poly) in enumerate(zones):
        colour = LEVEL_COLOURS[levels.get(name)] if levels else ZONE_COLOURS[i % 4]
        cv2.polylines(out, [np.int32(poly)], True, colour, 3)
        x, y = np.int32(poly).min(axis=0)
        cv2.putText(out, name, (int(x) + 6, int(y) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    colour, 2, cv2.LINE_AA)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


source = st.radio("Clip", ["Upload a clip", SAMPLE["label"]], horizontal=True,
                  label_visibility="collapsed")
use_sample = source == SAMPLE["label"]
if use_sample:
    data, suffix = SAMPLE["path"].read_bytes(), ".mp4"
    st.caption(SAMPLE["credit"])
else:
    upload = st.file_uploader("Video clip (MP4, MOV, AVI or MKV)", type=["mp4", "avi", "mov", "mkv"])
    if upload is None:
        st.info("Upload a clip to start, or pick the sample above. A fixed camera such as CCTV "
                "works best; a handheld phone gives people counts only.")
        st.stop()
    data, suffix = upload.getvalue(), "." + upload.name.rsplit(".", 1)[-1].lower()

max_seconds = st.slider("Seconds of video to analyse", 5, MAX_SECONDS, min(15, MAX_SECONDS),
                        help=f"The hosted demo analyses up to {MAX_SECONDS} s, counting once per "
                             "second. Run Crowd Shield on your own machine for longer clips.")
from crowdshield.motion import CAMERA_MOVING  # noqa: E402

video_path = clip_on_disk(data, suffix)
try:
    fps = video_fps(video_path)
    first, n_frames, camera = probe(video_path, max_seconds, fps)
finally:
    os.remove(video_path)
if first is None:
    st.error("Couldn't read this file. Try an MP4 (H.264), which every phone and CCTV system can export.")
    st.stop()
h, w = first.shape[:2]
st.caption(f"{n_frames} frames · {fps:.0f} fps · {w}×{h} px")
handheld = camera > CAMERA_MOVING
if handheld:
    st.warning(f"The camera itself is moving (the picture slides about {camera:.0%} of its width per "
               "second), as with a handheld phone. People counts are still fine, but speed, crowd pressure "
               "and the panic alarm would measure the camera, not the crowd, so they're switched off for "
               "this clip. Use a fixed camera for those.")

left, right = st.columns([3, 2])
with right:
    st.markdown("### 1. Calibrate the floor")
    calibrate = st.checkbox("I know the size of a rectangle on the floor", value=not use_sample,
                            help="Floor tiles, a doorway, parking lines, a stage edge. "
                                 "Without this you get counts and speeds in pixels, "
                                 "but no people per m².")
    corners = None
    if calibrate:
        st.caption("Corners as they appear in the frame (pixels): "
                   "top-left, top-right, bottom-right, bottom-left.")
        defaults = [(w * .35, h * .55), (w * .65, h * .55), (w * .8, h * .9), (w * .2, h * .9)]
        names = ["Top-left", "Top-right", "Bottom-right", "Bottom-left"]
        corners = []
        for name, (dx, dy) in zip(names, defaults):
            c1, c2 = st.columns(2)
            x = c1.number_input(f"{name} x", 0, w, int(dx), key=f"cx_{name}")
            y = c2.number_input(f"{name} y", 0, h, int(dy), key=f"cy_{name}")
            corners.append((x, y))
        c1, c2 = st.columns(2)
        width_m = c1.number_input("Rectangle width (m)", 0.1, 500.0, 5.0)
        length_m = c2.number_input("Rectangle depth (m)", 0.1, 500.0, 5.0)

    st.markdown("### 2. Zones to watch")
    n_zones = st.number_input("Number of zones", 1, 4, 2)
    zones = []
    tag = "s" if use_sample else "u"  # separate widget state, so each source keeps its own defaults
    for i in range(int(n_zones)):
        if use_sample and i < len(SAMPLE["zones"]):
            label, (fx0, fx1), (fy0, fy1) = SAMPLE["zones"][i]
        else:
            label, (fx0, fx1), (fy0, fy1) = chr(65 + i), (i / n_zones, (i + 1) / n_zones), (.4, 1)
        name = st.text_input(f"Zone {i + 1} name", label, key=f"zn_{tag}_{i}")
        x0, x1 = st.slider(f"{name}: left–right (px)", 0, w, (int(w * fx0), int(w * fx1)),
                           key=f"zx_{tag}_{i}")
        y0, y1 = st.slider(f"{name}: top–bottom (px)", 0, h, (int(h * fy0), int(h * fy1)),
                           key=f"zy_{tag}_{i}")
        zones.append((name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))

with left:
    st.image(draw(first, corners, zones), caption="First frame: calibration rectangle "
             "in yellow, zones in colour", width="stretch")

if not st.button("Analyse video", type="primary"):
    st.stop()

from crowdshield.geometry import GroundCalibration  # noqa: E402
from crowdshield.monitor import VideoMonitor, Zone  # noqa: E402
from crowdshield.safety import HELBING_TURBULENCE_PRESSURE  # noqa: E402

calib = None
if calibrate:
    try:
        calib = GroundCalibration.from_rectangle(corners, width_m, length_m)
    except Exception as exc:
        st.error(f"Those four corners don't make a usable rectangle ({exc}).")
        st.stop()

with st.spinner("Loading the counting model..."):
    counter, counter_name = make_counter()
if counter is None:
    st.error(f"Can't analyse: {counter_name}.")
    st.stop()
bar = st.progress(0.0, text="Reading the crowd...")
monitor = VideoMonitor(counter, fps, [Zone(n, p) for n, p in zones], calib=calib)
last = {}


def keep_last(frames):
    for frame in frames:
        last["frame"] = frame
        yield frame


video_path = clip_on_disk(data, suffix)
try:
    rows, events = monitor.run(keep_last(iter_frames(video_path, max_seconds)),
                               progress=lambda i: bar.progress(
                                   min(1.0, (i + 1) / n_frames), text=f"Frame {i + 1} of {n_frames}"))
finally:
    os.remove(video_path)
bar.empty()
df = pd.DataFrame(rows)
st.caption(f"Counted with the {counter_name}, once per second.")

st.markdown("## Results")
latest = df.groupby("zone").tail(1).set_index("zone")
cols = st.columns(len(latest))
for col, (name, r) in zip(cols, latest.iterrows()):
    with col:
        st.markdown(f"### Zone {name}")
        if calib is not None:
            st.metric("People per m²", f"{r['per_m2']:.2f}", help=f"{r['level']}")
            st.caption(f"{r['level']} · {r['people']:.0f} people in {r['area_m2']:.0f} m²")
            if not handheld:
                st.metric("Speed", f"{r['speed']:.2f} m/s")
                st.metric("Crowd pressure", f"{r['pressure']:.3f} /s²",
                          help="Density × velocity variance (Helbing et al., 2007). Turbulent "
                               f"motion began above {HELBING_TURBULENCE_PRESSURE}/s² at the 2006 "
                               "Hajj disaster.")
            eta = r["eta_s"]
            if eta is None or pd.isna(eta):
                st.success("No rising trend towards 5 people per m².")
            elif eta == 0:
                st.error("Already above 5 people per m².")
            else:
                st.warning(f"At the current trend, reaches 5 people per m² in about "
                           f"{eta / 60:.1f} min.")
        else:
            st.metric("People", f"{r['people']:.0f}")
            if not handheld:
                st.metric("Speed", f"{r['speed']:.0f} px/s")

if handheld:
    st.info("Panic alarm off: the camera is moving.")
elif events:
    for e in events:
        st.error(f"⚠ {e['t']:.1f} s — {e['event']}")
else:
    st.info("No sudden movement detected.")

measure = "per_m2" if calib is not None else "people"
st.markdown("#### " + ("People per m² over time" if calib is not None else "People over time"))
st.line_chart(df.pivot(index="t", columns="zone", values=measure))
if not handheld:
    st.markdown("#### Speed over time" + (" (m/s)" if calib is not None else " (px/s)"))
    st.line_chart(df.pivot(index="t", columns="zone", values="speed"))
if calib is not None and not handheld:
    st.markdown("#### Crowd pressure over time (1/s²)")
    st.line_chart(df.pivot(index="t", columns="zone", values="pressure"))

levels = latest["level"].to_dict() if calib is not None else None
st.image(draw(last.get("frame", first), corners, zones, levels), width="stretch",
         caption="Last frame, zones coloured by density level")
st.download_button("Download readings (CSV)", df.to_csv(index=False), "crowd_readings.csv",
                   "text/csv")
