"""Video — watch a fixed camera zone by zone: people per m², speed, crowd pressure, early warning."""

import tempfile

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from shared_state import GLOBAL_CSS, init_state

st.set_page_config(page_title="Video • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()
st.markdown(
    """
    <div class="navbar">
      <span class="navbar-brand">Crowd Shield</span>
      <div class="navbar-links">
        <a href="/">Dashboard</a>
        <a href="/Agents">Agents</a>
        <a href="/Upload">Upload</a>
        <a href="/Analysis">Analysis</a>
        <a href="/Video">Video</a>
        <a href="/Map">Map</a>
        <a href="/Settings">Settings</a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("# Video Monitor")
st.caption("Upload a clip from a fixed camera. Mark a rectangle of known size on the floor "
           "and the zones to watch; Crowd Shield then reports people per m², speed, "
           "crowd pressure and how long each zone has before it reaches 5 people per m².")

MAX_WIDTH = 960  # frames are shrunk to this width; all coordinates below use it
ZONE_COLOURS = [(0, 200, 255), (255, 120, 0), (180, 0, 255), (0, 220, 120)]
LEVEL_COLOURS = {"Normal": (80, 200, 80), "Crowded": (0, 200, 255),
                 "Dangerous": (0, 120, 255), "Crush risk": (0, 0, 255), None: (200, 200, 200)}


def read_frames(path, max_seconds):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    limit = int(fps * max_seconds)
    frames = []
    while len(frames) < limit:
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape[1] > MAX_WIDTH:
            s = MAX_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        frames.append(frame)
    cap.release()
    return frames, fps


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


upload = st.file_uploader("Video clip", type=["mp4", "avi", "mov", "mkv"])
if upload is None:
    st.info("Upload a clip to start. A camera that doesn't move works best.")
    st.stop()

with tempfile.NamedTemporaryFile(suffix="." + upload.name.rsplit(".", 1)[-1], delete=False) as f:
    f.write(upload.getbuffer())
    video_path = f.name

max_seconds = st.slider("Seconds of video to analyse", 5, 120, 30)
frames, fps = read_frames(video_path, max_seconds)
if not frames:
    st.error("Couldn't read any frames from this file.")
    st.stop()
h, w = frames[0].shape[:2]
st.caption(f"{len(frames)} frames · {fps:.0f} fps · {w}×{h} px")

left, right = st.columns([3, 2])
with right:
    st.markdown("### 1. Calibrate the floor")
    calibrate = st.checkbox("I know the size of a rectangle on the floor", value=True,
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
    for i in range(int(n_zones)):
        name = st.text_input(f"Zone {i + 1} name", chr(65 + i), key=f"zn_{i}")
        x0, x1 = st.slider(f"{name}: left–right (px)", 0, w,
                           (int(w * i / n_zones), int(w * (i + 1) / n_zones)), key=f"zx_{i}")
        y0, y1 = st.slider(f"{name}: top–bottom (px)", 0, h, (int(h * .4), h), key=f"zy_{i}")
        zones.append((name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))

with left:
    st.image(draw(frames[0], corners, zones), caption="First frame: calibration rectangle "
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
rows, events = monitor.run(frames, progress=lambda i: bar.progress(
    (i + 1) / len(frames), text=f"Frame {i + 1} of {len(frames)}"))
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
            st.metric("Speed", f"{r['speed']:.0f} px/s")

if events:
    for e in events:
        st.error(f"⚠ {e['t']:.1f} s — {e['event']}")
else:
    st.info("No sudden movement detected.")

measure = "per_m2" if calib is not None else "people"
st.markdown("#### " + ("People per m² over time" if calib is not None else "People over time"))
st.line_chart(df.pivot(index="t", columns="zone", values=measure))
st.markdown("#### Speed over time" + (" (m/s)" if calib is not None else " (px/s)"))
st.line_chart(df.pivot(index="t", columns="zone", values="speed"))
if calib is not None:
    st.markdown("#### Crowd pressure over time (1/s²)")
    st.line_chart(df.pivot(index="t", columns="zone", values="pressure"))

levels = latest["level"].to_dict() if calib is not None else None
st.image(draw(frames[-1], corners, zones, levels), width="stretch",
         caption="Last frame, zones coloured by density level")
st.download_button("Download readings (CSV)", df.to_csv(index=False), "crowd_readings.csv",
                   "text/csv")
