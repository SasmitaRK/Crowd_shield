"""Crowd Shield: the app's entry point. Sets the look and the navigation, then runs the chosen page."""

import sys
from pathlib import Path

import streamlit as st

# Streamlit Community Cloud pulls new code into the running app but does not watch files, so pages
# (re-read on every run) would meet the old copies of the shared modules still in memory: a page
# importing a new helper then fails. This script runs fresh on every page view, so it notices when
# the code on disk changed and drops the app's own modules, which then load again, new.
ROOT = Path(__file__).resolve().parent
OWN_MODULES = ("ui", "shared_state", "detection", "emailer", "crowdshield")


def code_stamp() -> int:
    files = [ROOT / f"{m}.py" for m in OWN_MODULES[:-1]] + list((ROOT / "crowdshield").rglob("*.py"))
    return max((f.stat().st_mtime_ns for f in files if f.exists()), default=0)


stamp, previous = code_stamp(), getattr(sys, "crowdshield_code_stamp", None)
if previous != "tests" and previous != stamp:  # also on the first run: modules may predate it
    for name in [n for n in sys.modules if n.split(".")[0] in OWN_MODULES]:
        del sys.modules[name]
    sys.crowdshield_code_stamp = stamp

from crowdshield.notify import ready_channels  # noqa: E402
from shared_state import init_state  # noqa: E402

st.set_page_config(page_title="Crowd Shield", page_icon="assets/mark.svg", layout="wide",
                   initial_sidebar_state="auto")  # open on computers, closed on phones
st.logo("assets/logo.svg", icon_image="assets/mark.svg", size="large")
init_state()

# Organised by what a visitor wants to do, in the order they would do it.
PAGES = {
    "": [
        st.Page("pages/0_Dashboard.py", title="Home", icon=":material/home:", default=True),
    ],
    "Check a crowd": [
        st.Page("pages/2_Upload.py", title="Count people in a photo", icon=":material/photo_camera:",
                url_path="Upload"),
        st.Page("pages/5_Video.py", title="Analyse a video", icon=":material/videocam:", url_path="Video"),
        st.Page("pages/8_Live.py", title="Watch a live camera", icon=":material/sensors:", url_path="Live"),
    ],
    "Plan the response": [
        st.Page("pages/6_Map.py", title="Site map", icon=":material/map:", url_path="Map"),
        st.Page("pages/3_Analysis.py", title="Evacuation plan and alerts", icon=":material/campaign:",
                url_path="Analysis"),
    ],
    "Set up": [
        st.Page("pages/1_Agents.py", title="Team and alerts", icon=":material/groups:", url_path="Agents"),
        st.Page("pages/4_Settings.py", title="Settings", icon=":material/tune:", url_path="Settings"),
    ],
    "Proof": [
        st.Page("pages/7_Benchmark.py", title="How accurate is it?", icon=":material/verified:",
                url_path="Benchmark"),
    ],
}
page = st.navigation(PAGES)

with st.sidebar:
    counted = len(st.session_state.crowd_data)
    channels = ready_channels()
    st.markdown(
        "<div class='rail-foot'>"
        "<div style='font-weight:700;color:#94a3b8;margin-bottom:.2rem'>This session</div>"
        f"<div class='rail-status'><i style='background:{'#10b981' if counted else '#475569'}'></i>"
        f"{counted} of 5 zones counted</div>"
        f"<div class='rail-status'><i style='background:{'#10b981' if channels else '#f59e0b'}'></i>"
        f"Alerts: {' and '.join(channels) if channels else 'not set up yet'}</div>"
        "<div style='margin-top:.7rem'>"
        "<a href='https://khushi-git-7.github.io/Crowd_shield/' target='_blank'>About the project</a> · "
        "<a href='https://github.com/khushi-git-7/Crowd_shield' target='_blank'>Code</a> · "
        "<a href='https://github.com/khushi-git-7/Crowd_shield/issues/new?template=feedback.yml' target='_blank'>Send feedback</a>"
        "</div></div>",
        unsafe_allow_html=True)

page.run()
