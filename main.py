"""Crowd Shield: the app's entry point. Sets the look and the navigation, then runs the chosen page."""

import streamlit as st

from emailer import email_configured
from shared_state import init_state

st.set_page_config(page_title="Crowd Shield", page_icon="assets/mark.svg", layout="wide",
                   initial_sidebar_state="expanded")
st.logo("assets/logo.svg", icon_image="assets/mark.svg", size="large")
init_state()

PAGES = {
    "Overview": [
        st.Page("pages/0_🏠_Dashboard.py", title="Dashboard", icon=":material/space_dashboard:",
                default=True),
    ],
    "Monitor": [
        st.Page("pages/6_🗺️_Map.py", title="Site map", icon=":material/map:", url_path="Map"),
        st.Page("pages/5_🎥_Video.py", title="Video monitor", icon=":material/videocam:", url_path="Video"),
    ],
    "Analyse": [
        st.Page("pages/2_📤_Upload.py", title="Photo analysis", icon=":material/photo_camera:",
                url_path="Upload"),
        st.Page("pages/3_📊_Analysis.py", title="Alerts and plans", icon=":material/campaign:",
                url_path="Analysis"),
    ],
    "Results": [
        st.Page("pages/7_📈_Benchmark.py", title="India benchmark", icon=":material/insights:",
                url_path="Benchmark"),
    ],
    "Configure": [
        st.Page("pages/1_👥_Agents.py", title="Response team", icon=":material/groups:", url_path="Agents"),
        st.Page("pages/4_⚙️_Settings.py", title="Settings", icon=":material/tune:", url_path="Settings"),
    ],
}
page = st.navigation(PAGES)

with st.sidebar:
    counted = len(st.session_state.crowd_data)
    email_ok = email_configured()
    st.markdown(
        "<div class='rail-foot'>"
        f"<div class='rail-status'><i style='background:#2dd4bf'></i>Counting: PET point model</div>"
        f"<div class='rail-status'><i style='background:{'#10b981' if counted else '#475569'}'></i>"
        f"Zones counted: {counted} of 5</div>"
        f"<div class='rail-status'><i style='background:{'#10b981' if email_ok else '#f59e0b'}'></i>"
        f"Email alerts: {'ready' if email_ok else 'not set up'}</div>"
        "<div style='margin-top:.7rem'>"
        "<a href='https://khushi-git-7.github.io/Crowd_shield/' target='_blank'>Project home</a> · "
        "<a href='https://github.com/khushi-git-7/Crowd_shield' target='_blank'>Code</a> · "
        "<a href='https://huggingface.co/Khushi-7/crowd-shield-counting' target='_blank'>Models</a> · "
        "<a href='https://github.com/khushi-git-7/Crowd_shield/issues/new?template=feedback.yml' target='_blank'>Feedback</a>"
        "</div></div>",
        unsafe_allow_html=True)

page.run()
