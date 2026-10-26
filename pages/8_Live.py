"""Watch a live camera: sample a camera stream every few seconds, count each zone, watch the trend, alert."""

import os
import time
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from ui import kpi_cards, next_step, page_header, section, working, zone_picker

from crowdshield import counting, live, notify
from crowdshield.config import NotEnoughMemory
from shared_state import GLOBAL_CSS, init_state

st.set_page_config(page_title="Watch a live camera • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Watch a live camera", "Crowd Shield looks at the camera every 30 seconds or more, counts the people "
            "in each zone, shows the trend and warns you before a zone is full.", "Check a crowd")

DEMO_CLIP = Path(__file__).resolve().parent.parent / "assets" / "samples" / "paris_saint_lazare.mp4"
MIN_INTERVAL = int(os.environ.get("CROWDSHIELD_LIVE_MIN_S", 30))
RISK_ACCENT = {"Safe": "#10b981", "Moderate": "#f59e0b", "High Risk": "#f97316", "Critical": "#ef4444"}
RISK_BGR = {"Safe": (129, 185, 16), "Moderate": (11, 158, 245), "High Risk": (22, 115, 249), "Critical": (68, 68, 239)}
DEMO_LAYOUT = {"Stairs and concourse": [("Stairs", 0.67, 0.25, 1.0, 1.0, 30), ("Concourse", 0.0, 0.53, 0.65, 1.0, 30)]}

st.caption("It looks at one picture every 30 seconds or more, not at every frame (for sudden surges, use Analyse a "
           "video). It runs while this page is open; to watch a camera all day, run it on a laptop "
           "(docs/run-on-your-laptop.md).")

# ---- 1. Source ------------------------------------------------------------
SOURCES = ["Demo feed (a recorded clip played as if live)", "A real public camera (live now)", "My own camera"]
source = st.radio("Source", SOURCES, horizontal=True, label_visibility="collapsed")
use_demo = source == SOURCES[0]
link = url = ""
if use_demo:
    st.caption("The demo steps through a 15-second clip of Paris Saint-Lazare station (Baidax, CC BY-SA 4.0, via "
               "Wikimedia Commons) one second per sample, looping, so you can see the monitor work with no camera.")
elif source == SOURCES[1]:
    camera = st.selectbox("Camera", list(live.PUBLIC_CAMERAS))
    link = live.PUBLIC_CAMERAS[camera]["link"]
    st.caption(live.PUBLIC_CAMERAS[camera]["credit"] + " Crowd Shield reads one frame at a time and keeps nothing.")
else:
    link = st.text_input("Camera address", placeholder="rtsp://camera/stream, https://example.com/live.m3u8 or an "
                         "ipcamlive.com camera link",
                         help="RTSP, an HTTP(S) stream such as HLS (.m3u8) or MJPEG, or the page link of a camera "
                              "hosted on ipcamlive.com. The camera must be reachable from the internet; this hosted "
                              "app cannot see private networks.")
    if not link:
        st.info("Paste a camera address, or pick the demo or the public camera above. For a camera on your own "
                "network (or a phone running the free IP Webcam app), run Crowd Shield on your computer with "
                "`CROWDSHIELD_ALLOW_PRIVATE_URLS=1`; see docs/run-on-your-laptop.md.")
        st.stop()
if link:
    resolved = st.session_state.setdefault("live_streams", {})
    if link not in resolved:
        with working("Connecting to the camera", "Finding its live stream..."):
            stream, why = live.resolve_stream(link)
        if stream is None:
            st.error(why)
            st.stop()
        resolved[link] = stream
    url = resolved[link]
    ok, reason = live.check_url(url)
    if not ok:
        st.error(reason)
        st.stop()

# ---- 2. First frame and zones ------------------------------------------------
key = ("demo",) if use_demo else ("url", link)
if st.session_state.get("live_key") != key:
    st.session_state.live_key, st.session_state.live_on = key, False
    st.session_state.pop("live", None)
    st.session_state.live_first = None
if st.session_state.get("live_first") is None:
    with working("Connecting to the camera", "Reading the first picture..."):
        feed = live.DemoFeed(DEMO_CLIP, step_s=1.0) if use_demo else None
        first = feed.next_frame() if use_demo else live.grab_frame(url)
    if first is None:
        st.error("Could not read a picture from that stream. Check the address, and that the camera is on and "
                 "public. Some cameras need a password in the address (rtsp://user:password@host/...).")
        st.stop()
    st.session_state.live_first = first
first = st.session_state.live_first
h, w = first.shape[:2]

left, right = st.columns([3, 2])
with right:
    st.markdown("### Zones to watch")
    picked, caps = zone_picker(w, h, "lz_demo" if use_demo else "lz", extra=DEMO_LAYOUT if use_demo else None)
    zones = {name: {"polygon": poly, "thresholds": live.capacity_thresholds(caps[name])} for name, poly in picked}


from crowdshield.video_render import _label  # noqa: E402


def draw(frame, levels=None):
    out = frame.copy()
    for name, info in zones.items():
        (x0, y0), _, (x1, y1), _ = info["polygon"]
        colour = RISK_BGR[levels[name]] if levels and name in levels else (200, 160, 0)
        cv2.rectangle(out, (int(x0), int(y0)), (int(x1), int(y1)), colour, 3)
        level = levels.get(name) if levels else None
        _label(out, f"{name} - {level}" if level else name, (int(x0) + 10, int(y0) + 24), bg=colour)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


with left:
    st.image(draw(first), caption="The camera right now, with your zones", width="stretch")

# ---- 3. Run ------------------------------------------------------------------
st.markdown("---")
c1, c2, c3 = st.columns([2, 2, 3])
interval = c1.slider("Seconds between counts", MIN_INTERVAL, 300, max(MIN_INTERVAL, 45),
                     help="Counting a frame takes a few seconds to a minute depending on the server, so "
                          f"on this app it can't go below {MIN_INTERVAL} s.")
channels = notify.ready_channels()
send_alerts = c2.toggle("Send alerts", value=False, disabled=not channels,
                        help="No alert channel is set up yet: add Telegram or Gmail in Team and alerts." if not channels
                        else f"Sends to {' and '.join(channels)}. A zone reaching High Risk or Critical is sent "
                             "once, then that zone stays quiet for 10 minutes.")
running = c3.toggle("Monitoring", key="live_on", help="Start or stop counting.")

signature = (key, tuple((n, tuple(map(tuple, z["polygon"])), tuple(z["thresholds"].values())) for n, z in zones.items()))
if st.session_state.get("live_sig") != signature:
    st.session_state.live_sig = signature
    st.session_state.pop("live", None)

if running and "live" not in st.session_state:
    with working("Starting the monitor", "Getting the counting model ready. The first time takes about a minute."):
        counter, counter_name = counting.make_counter()
    if counter is None:
        st.error(f"Can't monitor: {counter_name}.")
        st.session_state.live_on = False
        st.stop()
    st.session_state.live = {
        "monitor": live.LiveMonitor(zones, counter), "t0": time.time(), "log": [], "alerts": [],
        "feed": live.DemoFeed(DEMO_CLIP, step_s=1.0) if use_demo else None, "frame": first,
        "counter": counter_name, "seconds": None}


def tick():
    state = st.session_state.live
    frame = state["feed"].next_frame() if state["feed"] else live.grab_frame(url)
    if frame is None and link and live.ipcamlive_alias(link):  # its stream address may have moved
        fresh, _ = live.resolve_stream(link)
        if fresh:
            st.session_state.live_streams[link] = fresh
            frame = live.grab_frame(fresh)
    if frame is None:
        st.warning("Could not read the stream just now. Trying again next time.")
        return
    started = time.time()
    try:
        result = state["monitor"].update(time.time() - state["t0"], frame)
    except NotEnoughMemory as exc:
        st.session_state.live_on = False
        st.error(str(exc))
        return
    state["seconds"], state["frame"] = time.time() - started, frame
    state["log"].append({"t": result["t"], **{z: r["count"] for z, r in result["zones"].items()},
                         "_risk": {z: r["risk"] for z, r in result["zones"].items()}})
    for event in result["events"]:
        info = zones[event["zone"]]
        text = notify.alert_text(event["zone"], event["zone"], event["risk"], event["count"], event["per_m2"],
                                 None if event["eta_s"] is None else event["eta_s"] / 60)
        sent = notify.broadcast(text) if send_alerts else ["alerts are off"]
        state["alerts"].append({"time": time.strftime("%H:%M:%S"), "zone": event["zone"], "risk": event["risk"],
                                "kind": event["kind"], "sent": "; ".join(sent)})
    state["last"] = result


def show():
    state = st.session_state.get("live")
    if not state or not state["log"]:
        st.caption("Switch Monitoring on to start counting." if not running else "Counting the first frame...")
        return
    last = state["last"]
    levels = {z: r["risk"] for z, r in last["zones"].items()}
    cards, accents = [], []
    for z, r in last["zones"].items():
        eta = r["eta_s"]
        sub = (f"{r['risk']} · limit {r['capacity']}" + ("" if eta is None else
               " · full now" if eta == 0 else f" · full in ~{eta / 60:.0f} min"))
        cards.append((f"Zone {z}", f"{r['count']:.0f} people", sub))
        accents.append(RISK_ACCENT[r["risk"]])
    cards.append(("Sampling", f"every {interval} s", f"last count took {state['seconds']:.0f} s · {state['counter']}"))
    accents.append(None)
    kpi_cards(cards, accents)
    pic, chart = st.columns([3, 2])
    pic.image(draw(state["frame"], levels), caption="Latest frame, zones coloured by risk", width="stretch")
    with chart:
        section("Over time", "People per zone at each sample.")
        import altair as alt

        df = pd.DataFrame([{k: v for k, v in row.items() if k != "_risk"} for row in state["log"]])
        long = df.melt("t", var_name="Zone", value_name="People")
        long["Minutes"] = long["t"] / 60
        names = list(zones)
        palette = ["#2a78d6", "#eb6834", "#1baf7a", "#8b5cf6"][:len(names)]
        st.altair_chart(
            alt.Chart(long).mark_line(strokeWidth=2, point=True, interpolate="monotone").encode(
                x=alt.X("Minutes:Q", title="Minutes since monitoring started"),
                y=alt.Y("People:Q", title="People in zone"),
                color=alt.Color("Zone:N", scale=alt.Scale(domain=names, range=palette)),
                tooltip=["Zone", alt.Tooltip("Minutes:Q", format=".1f"), alt.Tooltip("People:Q", format=".0f")]
            ).properties(height=260), width="stretch")
    if state["alerts"]:
        section("Alerts")
        st.dataframe(state["alerts"][::-1], hide_index=True, width="stretch")


@st.fragment(run_every=f"{interval}s" if running else None)
def monitor_panel():
    if st.session_state.get("live_on") and "live" in st.session_state:
        tick()
    show()


monitor_panel()

next_step("For sudden surges and walking speed, analyse a recorded clip second by second.", "pages/5_Video.py",
          "Analyse a video", "/Video")
