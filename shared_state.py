"""Shared session-state defaults and constants used across pages."""

import streamlit as st

# Constants live in the core package; re-exported here for the pages.
from crowdshield.config import (  # noqa: F401
    DEFAULT_THRESHOLDS, FRUIN_PRESETS, MAX_IMAGES_PER_SEGMENT, RISK_LEVELS,
    SEGMENTS, SOURCE_MODEL_MAP,
)

RISK_COLORS = {
    "Safe":      "#10b981",
    "Moderate":  "#f59e0b",
    "High Risk": "#f97316",
    "Critical":  "#ef4444",
}
RISK_ICONS = {
    "Safe":      "Safe",
    "Moderate":  "Moderate",
    "High Risk": "High Risk",
    "Critical":  "Critical",
}

SOURCE_LABELS = {
    "auto":   "Auto (global model)",
    "drone":  "Drone / Aerial",
    "ground": "CCTV / Ground level",
}


def init_state():
    if "agents" not in st.session_state:
        st.session_state.agents = {s: "" for s in SEGMENTS}
    if "uploaded_images" not in st.session_state:
        st.session_state.uploaded_images = {s: [] for s in SEGMENTS}
    if "image_names" not in st.session_state:
        st.session_state.image_names = {s: [] for s in SEGMENTS}
    if "image_sources" not in st.session_state:
        st.session_state.image_sources = {s: [] for s in SEGMENTS}
    if "crowd_data" not in st.session_state:
        st.session_state.crowd_data = {}
    if "active_model" not in st.session_state:
        st.session_state.active_model = "crowd_yolo"
    if "thresholds" not in st.session_state:
        st.session_state.thresholds = {
            s: dict(DEFAULT_THRESHOLDS) for s in SEGMENTS
        }
    if "seg_areas" not in st.session_state:
        st.session_state.seg_areas = {s: 0 for s in SEGMENTS}
    if "alert_count" not in st.session_state:
        st.session_state.alert_count = 0
    if "low_threshold" not in st.session_state:
        st.session_state.low_threshold = DEFAULT_THRESHOLDS["moderate"]
    if "high_threshold" not in st.session_state:
        st.session_state.high_threshold = DEFAULT_THRESHOLDS["critical"]
    if "detection_history" not in st.session_state:
        st.session_state.detection_history = []


def get_seg_thresholds(seg: str) -> dict:
    t = st.session_state.get("thresholds", {})
    if seg not in t:
        t[seg] = dict(DEFAULT_THRESHOLDS)
        st.session_state.thresholds = t
    return t[seg]


from ui import GLOBAL_CSS  # noqa: E402,F401  (the design system lives in ui.py)
