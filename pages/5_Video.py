"""Analyse a video: watch a crowd change second by second, with every head and every zone marked on the clip."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from crowdshield import counting
from shared_state import GLOBAL_CSS, init_state
from ui import kpi_cards, nav_link, page_header, section, working

st.set_page_config(page_title="Analyse a video • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Analyse a video", "See how a crowd changes second by second. Crowd Shield puts a dot on every head, "
            "colours each zone by how full it is, and raises an alarm if the crowd suddenly surges.", "Check a crowd")

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_VIDEO = SAMPLES / "paris_saint_lazare_annotated.mp4"
SAMPLE_DATA = SAMPLES / "paris_saint_lazare_analysis.json"
SAMPLE_CREDIT = ("Clip: 15 s of \"2025-11-06 17-33-16 - Paris - Saint-Lazare\" by Baidax, "
                 "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), via "
                 "[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:2025-11-06_17-33-16_-_Paris_-_Saint-Lazare.webm).")
MAX_WIDTH = 960  # frames are shrunk to this width; zone boxes are fractions of the picture, so any size works
# The free hosted demo has little memory and no GPU, so it analyses short clips. Set
# CROWDSHIELD_MAX_VIDEO_S on your own machine to allow longer ones.
MAX_SECONDS = int(os.environ.get("CROWDSHIELD_MAX_VIDEO_S", 20))
LEVEL_HEX = {"Safe": "#10b981", "Moderate": "#f59e0b", "High Risk": "#f97316", "Critical": "#ef4444",
             "Normal": "#10b981", "Crowded": "#f59e0b", "Dangerous": "#f97316", "Crush risk": "#ef4444"}
ZONE_HEX = ["#2a78d6", "#eb6834", "#1baf7a", "#8b5cf6"]
# Zone layouts as (name, left, top, right, bottom), fractions of the picture.
PRESETS = {
    "Whole picture": [("Whole view", 0, 0, 1, 1)],
    "Left and right": [("Left", 0, 0, .5, 1), ("Right", .5, 0, 1, 1)],
    "Near and far": [("Far", 0, 0, 1, .5), ("Near", 0, .5, 1, 1)],
    "Four quarters": [("Far left", 0, 0, .5, .5), ("Far right", .5, 0, 1, .5),
                      ("Near left", 0, .5, .5, 1), ("Near right", .5, .5, 1, 1)],
}

st.markdown("""
<style>
  .steps { display:grid; grid-template-columns: repeat(3, 1fr); gap:.8rem; margin:.2rem 0 1.2rem; }
  .step { background:#fff; border:1px solid #e3e8ef; border-radius:12px; padding:.75rem .9rem; }
  .step b { display:inline-flex; width:22px; height:22px; border-radius:7px; background:#0d9488; color:#fff;
            align-items:center; justify-content:center; font-size:.75rem; margin-right:.45rem; }
  .step span { font-weight:700; font-size:.88rem; color:#0f172a; }
  .step p { margin:.3rem 0 0; font-size:.8rem; color:#64748b; line-height:1.45; }
  @media (max-width: 640px) { .steps { grid-template-columns: 1fr; } }
</style>
<div class="steps">
  <div class="step"><b>1</b><span>Choose a clip</span><p>From a camera that stays still: CCTV, a drone holding
    position, or a phone on a stand.</p></div>
  <div class="step"><b>2</b><span>Mark the zones</span><p>Pick a layout (left and right, four quarters...) and
    how many people each zone holds comfortably.</p></div>
  <div class="step"><b>3</b><span>Watch the result</span><p>Your clip with every head marked, zones turning
    amber and red as they fill, and a chart of each zone over time.</p></div>
</div>
""", unsafe_allow_html=True)


# ── Shared: how a result is shown, for the example and for your own clip alike ──────────────────────
def capacity_level(people, capacity):
    from crowdshield.video_render import capacity_level as level

    return level(people, capacity)


def show_result(video, df: pd.DataFrame, events: list, capacities: dict, calibrated: bool,
                handheld: bool = False, key: str = "r"):
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.video(video)
    with right:
        section("What happened")
        for i, (zone, part) in enumerate(df.groupby("zone", sort=False)):
            peak = part.loc[part["people"].idxmax()]
            cap = capacities.get(zone)
            level = peak.get("level") if calibrated else capacity_level(peak["people"], cap)
            colour = LEVEL_HEX.get(level, ZONE_HEX[i % 4])
            detail = (f"peak {peak['per_m2']:.1f} people per m² at {peak['t']:.0f} s" if calibrated else
                      f"peak at {peak['t']:.0f} s" + (f", holds {cap} comfortably" if cap else ""))
            st.markdown(
                f"<div class='card' style='border-left:4px solid {colour};padding:.7rem .9rem;margin-bottom:.5rem'>"
                f"<div style='display:flex;justify-content:space-between'><b>{zone}</b>"
                f"<span style='color:{colour};font-weight:800;font-size:.8rem'>{level or ''}</span></div>"
                f"<div style='font-size:1.5rem;font-weight:800'>{peak['people']:.0f} "
                f"<span style='font-size:.8rem;color:#64748b;font-weight:600'>people at most</span></div>"
                f"<div style='font-size:.78rem;color:#64748b'>{detail} · average {part['people'].mean():.0f}</div>"
                f"</div>", unsafe_allow_html=True)
        if handheld:
            st.info("Surge alarm off: the camera itself moves in this clip, so movement can't be judged.")
        elif events:
            for e in events:
                st.error(f"Surge alarm at {e['t']:.1f} s: {e['event'].split(': ', 1)[-1]}")
        else:
            st.success("No surge: nobody suddenly started moving much faster than the crowd's normal pace.")

    import altair as alt

    section("Each zone over time", "Counted once a second." + (" Dashed lines: how many each zone holds "
                                                                 "comfortably." if capacities and not calibrated else ""))
    column, title = ("per_m2", "People per m²") if calibrated else ("people", "People in zone")
    names = list(dict.fromkeys(df["zone"]))
    colours = [ZONE_HEX[i % 4] for i in range(len(names))]
    lines = alt.Chart(df).mark_line(strokeWidth=2.5, interpolate="monotone", point=True).encode(
        x=alt.X("t:Q", title="Seconds into the clip"), y=alt.Y(f"{column}:Q", title=title),
        color=alt.Color("zone:N", title=None, scale=alt.Scale(domain=names, range=colours),
                        legend=alt.Legend(orient="top", labelFontSize=12, symbolStrokeWidth=3)),
        tooltip=[alt.Tooltip("zone:N", title="Zone"), alt.Tooltip("t:Q", title="Second"),
                 alt.Tooltip(f"{column}:Q", title=title, format=".1f")])
    layers = [lines]
    if capacities and not calibrated:
        caps = pd.DataFrame([{"zone": z, "cap": c} for z, c in capacities.items() if c and z in names])
        if len(caps):
            layers.append(alt.Chart(caps).mark_rule(strokeDash=[5, 4], strokeWidth=1.5).encode(
                y="cap:Q", color=alt.Color("zone:N", scale=alt.Scale(domain=names, range=colours), legend=None)))
    if events and not handheld:
        layers.append(alt.Chart(pd.DataFrame(events)).mark_rule(color="#ef4444", strokeWidth=2).encode(x="t:Q"))
    st.altair_chart(alt.layer(*layers).resolve_legend(color="shared").properties(height=280), width="stretch")

    if calibrated and not handheld:
        with st.expander("Walking speed, crowd pressure and time to danger"):
            from crowdshield.safety import HELBING_TURBULENCE_PRESSURE

            latest = df.groupby("zone").tail(1).set_index("zone")
            for zone, r in latest.iterrows():
                eta = r["eta_s"]
                when = ("no rising trend towards 5 people per m²" if eta is None or pd.isna(eta) else
                        "already above 5 people per m²" if eta == 0 else
                        f"reaches 5 people per m² in about {eta / 60:.1f} min at this trend")
                st.markdown(f"**{zone}**: walking {r['speed']:.2f} m/s · crowd pressure {r['pressure']:.3f}/s² "
                            f"(turbulent pushing began above {HELBING_TURBULENCE_PRESSURE}/s² at the 2006 Hajj "
                            f"disaster) · {when}.")
    d1, d2, _ = st.columns([1, 1, 2])
    d1.download_button("Download the readings (CSV)", df.to_csv(index=False), "crowd_readings.csv", "text/csv",
                       width="stretch", key=f"csv_{key}")
    if isinstance(video, (bytes, bytearray)):
        d2.download_button("Download the annotated video", video, "crowd_shield_video.mp4", "video/mp4",
                           width="stretch", key=f"mp4_{key}")


tab_example, tab_own = st.tabs(["Example: a busy Paris station", "Analyse your own clip"])

# ── Example: analysed in advance, so it shows instantly ─────────────────────────────────────────────
with tab_example:
    data = json.loads(SAMPLE_DATA.read_text(encoding="utf-8"))
    st.markdown("Fifteen seconds from a fixed camera above the concourse and stairs of Paris Saint-Lazare station, "
                "analysed by Crowd Shield. **Press play.**")
    show_result(SAMPLE_VIDEO.read_bytes(), pd.DataFrame(data["rows"]), data["events"],
                {z["name"]: z["capacity"] for z in data["zones"]}, calibrated=False, key="example")
    st.caption(SAMPLE_CREDIT + f" Analysed with the same code as your own clips ({data['counter']}, once a second). "
               "The zone sizes (40 and 50 people) are examples, chosen for the demo.")
    nav_link("pages/8_Live.py", "Want this on a camera that is live right now? Watch a live camera",
             ":material/sensors:", "/Live")

# ── Your own clip ─────────────────────────────────────────────────────────────────────────────────────
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
    camera = camera_motion(small, fps / step, step=1, scale=1.0) if small else 0.0
    return first, n, camera


def clip_on_disk(data: bytes, suffix: str) -> str:
    """OpenCV only reads video from a file. The caller deletes it as soon as decoding is done."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        return f.name


from crowdshield.video_render import _label  # noqa: E402


def preview(frame, corners, zones):
    out = frame.copy()
    if corners is not None:
        cv2.polylines(out, [np.int32(corners)], True, (0, 255, 255), 2)
    for i, (name, poly) in enumerate(zones):
        hexc = ZONE_HEX[i % 4].lstrip("#")
        colour = tuple(int(hexc[j:j + 2], 16) for j in (4, 2, 0))
        cv2.polylines(out, [np.int32(poly)], True, colour, 3)
        x, y = np.int32(poly).min(axis=0)
        _label(out, name, (int(x) + 10, int(y) + 24), bg=colour)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


with tab_own:
    section("1. Choose a clip")
    upload = st.file_uploader("Your clip (MP4, MOV, AVI or MKV)", type=["mp4", "avi", "mov", "mkv"])
    if upload is None:
        st.info("Upload a clip to start. A camera that stays still works best (CCTV, a drone holding position, a "
                f"phone on a stand). The hosted app analyses up to {MAX_SECONDS} seconds of it.")
        st.stop()

    data_bytes, suffix = upload.getvalue(), "." + upload.name.rsplit(".", 1)[-1].lower()
    digest = hashlib.sha1(data_bytes).hexdigest()[:12]
    max_seconds = MAX_SECONDS
    path = clip_on_disk(data_bytes, suffix)
    try:
        fps = video_fps(path)
        first, n_frames, camera = probe(path, max_seconds, fps)
    finally:
        os.remove(path)
    if first is None:
        st.error("Couldn't read this file. Try an MP4 (H.264), which every phone and CCTV system can export.")
        st.stop()
    from crowdshield.motion import CAMERA_MOVING

    h, w = first.shape[:2]
    handheld = camera > CAMERA_MOVING
    seconds = n_frames / fps
    if handheld:
        st.warning("The camera itself moves in this clip (like a handheld phone). Head counts still work, but the "
                   "surge alarm and walking speed would measure the camera, not the crowd, so they're switched off.")

    section("2. Mark the zones")
    left, right = st.columns([3, 2], gap="large")
    with right:
        layout = st.radio("Layout", list(PRESETS) + ["Custom boxes"], horizontal=True)
        boxes = PRESETS.get(layout) or [(f"Zone {chr(65 + i)}", 0, 0, 1, 1) for i in range(
            st.number_input("How many zones", 1, 4, 2))]
        zones, capacities = [], {}
        for i, (default_name, fx0, fy0, fx1, fy1) in enumerate(boxes):
            c1, c2 = st.columns([3, 2])
            name = c1.text_input(f"Zone {i + 1} name", default_name, key=f"vz_name_{layout}_{i}")
            capacities[name] = int(c2.number_input("Holds comfortably", 1, 100_000, 40, key=f"vz_cap_{layout}_{i}",
                                                   help="How many people this part of the picture holds comfortably. "
                                                        "A zone turns amber at half of it, orange at three quarters "
                                                        "and red when full."))
            if layout == "Custom boxes":
                x0, x1 = st.slider(f"{name}: left to right (%)", 0, 100, (int(i * 100 / len(boxes)),
                                   int((i + 1) * 100 / len(boxes))), key=f"vz_x_{i}")
                y0, y1 = st.slider(f"{name}: top to bottom (%)", 0, 100, (30, 100), key=f"vz_y_{i}")
                fx0, fx1, fy0, fy1 = x0 / 100, x1 / 100, y0 / 100, y1 / 100
            zones.append((name, [(w * fx0, h * fy0), (w * fx1, h * fy0), (w * fx1, h * fy1), (w * fx0, h * fy1)]))

        with st.expander("Optional: measure people per m²"):
            calibrate = st.checkbox("I know the size of a rectangle on the floor",
                                    help="Floor tiles, a doorway, parking lines, a stage edge. Then zones are judged "
                                         "by people per m² (crowd-safety levels) instead of by how many they hold.")
            corners = None
            if calibrate:
                st.caption("Its corners as they appear in the picture, in pixels: top-left, top-right, bottom-right, "
                           f"bottom-left. The picture is {w} × {h} px; the yellow outline shows where they are.")
                defaults = [(w * .35, h * .55), (w * .65, h * .55), (w * .8, h * .9), (w * .2, h * .9)]
                corners = []
                for label, (dx, dy) in zip(["Top-left", "Top-right", "Bottom-right", "Bottom-left"], defaults):
                    c1, c2 = st.columns(2)
                    corners.append((c1.number_input(f"{label} x", 0, w, int(dx), key=f"vc_x_{label}"),
                                    c2.number_input(f"{label} y", 0, h, int(dy), key=f"vc_y_{label}")))
                c1, c2 = st.columns(2)
                width_m = c1.number_input("Rectangle width (m)", 0.1, 500.0, 5.0)
                length_m = c2.number_input("Rectangle depth (m)", 0.1, 500.0, 5.0)
    with left:
        st.image(preview(first, corners, zones), width="stretch",
                 caption=f"First frame of your {seconds:.0f}-second clip, with the zones")

    settings = json.dumps([digest, zones, capacities, corners], default=str)
    run = st.button("Analyse video", type="primary", icon=":material/play_arrow:")
    done = st.session_state.get("video_result")
    if not run and not (done and done["settings"] == settings):
        st.caption(f"Counting takes a few seconds per second of video on the free server (about "
                   f"{max(1, round(seconds * 5 / 60))} min for this clip).")
        st.stop()

    if run:
        from crowdshield.config import NotEnoughMemory
        from crowdshield.geometry import GroundCalibration
        from crowdshield.monitor import VideoMonitor, Zone
        from crowdshield.video_render import PointRecorder, render

        calib = None
        if corners is not None:
            try:
                calib = GroundCalibration.from_rectangle(corners, width_m, length_m)
            except Exception as exc:
                st.error(f"Those four corners don't make a usable rectangle ({exc}).")
                st.stop()
        job = working("Analysing your clip", "Getting the counting model ready...")
        counter, counter_name = counting.make_counter()
        if counter is None:
            job.done()
            st.error(f"Can't analyse: {counter_name}.")
            st.stop()
        recorder = PointRecorder() if counter_name.startswith("point model") else None
        monitor = VideoMonitor(recorder or counter, fps, [Zone(n, p) for n, p in zones], calib=calib)
        path = clip_on_disk(data_bytes, suffix)
        out_path = path + ".annotated.mp4"
        try:
            rows, events = monitor.run(iter_frames(path, max_seconds), progress=lambda i: job.update(
                f"Counting people: second {i / fps:.0f} of {seconds:.0f}", 0.85 * (i + 1) / n_frames)
                if i % max(1, round(fps / 2)) == 0 else None)
            job.update("Drawing the dots and zones on your clip...", 0.9)
            render(iter_frames(path, max_seconds), fps, out_path, zones, rows, [] if handheld else events,
                   {} if calib else capacities, recorder.points if recorder else None, monitor.count_every)
            video = Path(out_path).read_bytes()
        except NotEnoughMemory as exc:
            job.done()
            st.error(str(exc))
            st.stop()
        finally:
            for p in (path, out_path):
                if os.path.exists(p):
                    os.remove(p)
        job.done()
        st.session_state.video_result = {"settings": settings, "video": video, "rows": rows, "events": events,
                                         "calibrated": calib is not None, "handheld": handheld,
                                         "counter": counter_name}
        done = st.session_state.video_result

    section("3. The result")
    show_result(done["video"], pd.DataFrame(done["rows"]), done["events"],
                {} if done["calibrated"] else capacities, done["calibrated"], done["handheld"], key="own")
    st.caption(f"Counted with the {done['counter']}, once a second.")
