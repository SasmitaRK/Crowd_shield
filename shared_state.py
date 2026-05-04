"""Shared session-state defaults and constants used across pages."""

import streamlit as st

SEGMENTS = ["A", "B", "C", "D", "E"]
MAX_IMAGES_PER_SEGMENT = 4

RISK_LEVELS = ["Safe", "Moderate", "High Risk", "Critical"]
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

DEFAULT_THRESHOLDS = {
    "moderate": 30,
    "high":     60,
    "critical": 90,
}

SOURCE_LABELS = {
    "auto":   "Auto (global model)",
    "drone":  "Drone / Aerial",
    "ground": "CCTV / Ground level",
}

SOURCE_MODEL_MAP = {
    "auto":   None,
    "drone":  "crowd_yolo",
    "ground": "yolov8l",
}

FRUIN_PRESETS = {
    "Conservative (outdoor open areas)": {
        "moderate": 0.5,
        "high":     1.0,
        "critical": 2.0,
    },
    "Standard (mixed venues)": {
        "moderate": 1.0,
        "high":     2.0,
        "critical": 3.5,
    },
    "Crowded events / concerts": {
        "moderate": 1.5,
        "high":     3.0,
        "critical": 4.5,
    },
    "Enclosed corridors / gates": {
        "moderate": 0.5,
        "high":     1.0,
        "critical": 1.5,
    },
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


GLOBAL_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
  }

  .stApp {
    background: #f0f2f5 !important;
    color: #111827 !important;
  }

  .main .block-container {
    max-width: 1280px;
    padding-top: 1.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
  }

  /* ── Navbar ─────────────────────────────────────────── */
  .navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1.25rem;
    margin-bottom: 1.5rem;
    border-radius: 12px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .navbar-brand {
    font-weight: 800;
    font-size: 1rem;
    letter-spacing: -0.2px;
    color: #0d9488;
  }
  .navbar-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .navbar-links a {
    color: #6b7280;
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0.35rem 0.75rem;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: all 0.15s ease;
  }
  .navbar-links a:hover {
    color: #0d9488;
    background: #f0fdfa;
    border-color: #ccfbf1;
  }

  /* ── Cards ──────────────────────────────────────────── */
  .glass-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.25rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    color: #111827;
  }
  .metric-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.25rem 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    text-align: center;
    color: #111827;
  }
  .feature-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.75rem 1.5rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    transition: box-shadow 0.2s ease, transform 0.2s ease;
  }
  .feature-card:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    transform: translateY(-2px);
  }
  .feature-icon {
    width: 44px;
    height: 44px;
    background: #f0fdfa;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1rem;
    color: #0d9488;
  }
  .feature-card h3 {
    font-size: 1rem !important;
    font-weight: 700 !important;
    color: #111827 !important;
    margin: 0 0 0.5rem 0 !important;
  }
  .feature-card p {
    font-size: 0.875rem;
    color: #6b7280;
    line-height: 1.6;
    margin: 0;
  }

  /* ── Hero ───────────────────────────────────────────── */
  .hero-section {
    text-align: center;
    padding: 4rem 1rem 3rem;
  }
  .hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #f0fdfa;
    border: 1px solid #99f6e4;
    color: #0d9488;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    margin-bottom: 1.75rem;
    letter-spacing: 0.2px;
  }
  .hero-section h1 {
    font-size: 3.25rem !important;
    font-weight: 800 !important;
    color: #111827 !important;
    line-height: 1.15 !important;
    letter-spacing: -1px !important;
    margin: 0 0 1rem 0 !important;
  }
  .hero-section p {
    font-size: 1.1rem;
    color: #6b7280;
    line-height: 1.7;
    max-width: 560px;
    margin: 0 auto 2rem;
  }
  .hero-buttons {
    display: flex;
    justify-content: center;
    gap: 0.85rem;
    flex-wrap: wrap;
  }
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #0d9488;
    color: #fff !important;
    text-decoration: none !important;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.7rem 1.5rem;
    border-radius: 10px;
    border: 2px solid #0d9488;
    transition: background 0.15s ease, transform 0.15s ease;
  }
  .btn-primary:hover {
    background: #0f766e;
    border-color: #0f766e;
    transform: translateY(-1px);
  }
  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: transparent;
    color: #374151 !important;
    text-decoration: none !important;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.7rem 1.5rem;
    border-radius: 10px;
    border: 2px solid #d1d5db;
    transition: border-color 0.15s ease, color 0.15s ease;
  }
  .btn-secondary:hover {
    border-color: #0d9488;
    color: #0d9488 !important;
  }

  /* ── Risk badges ─────────────────────────────────────── */
  .risk-badge {
    display: inline-block;
    padding: 0.25rem 0.9rem;
    border-radius: 50px;
    font-weight: 700;
    font-size: 0.75rem;
    letter-spacing: 0.6px;
    text-transform: uppercase;
  }
  .risk-safe     { background: #d1fae5; color: #065f46; }
  .risk-moderate { background: #fef3c7; color: #92400e; }
  .risk-high     { background: #ffedd5; color: #9a3412; }
  .risk-critical {
    background: #fee2e2;
    color: #991b1b;
    animation: pulse-red 1.4s ease-in-out infinite;
  }
  @keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
    50%       { box-shadow: 0 0 0 6px rgba(239,68,68,0); }
  }

  /* ── Alert cards ─────────────────────────────────────── */
  .alert-card {
    border-left: 5px solid;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
    line-height: 1.6;
  }
  .alert-safe     { border-left-color: #10b981; background: #f0fdf4; color: #111827; }
  .alert-moderate { border-left-color: #f59e0b; background: #fffbeb; color: #111827; }
  .alert-high     { border-left-color: #f97316; background: #fff7ed; color: #111827; }
  .alert-critical {
    border-left-color: #ef4444;
    border-left-width: 7px;
    background: #fef2f2;
    color: #111827;
  }

  /* ── Typography overrides ────────────────────────────── */
  h1, h2, h3, h4, h5, h6 {
    color: #111827 !important;
    font-weight: 700 !important;
  }
  p, li, span, label { color: #374151; }
  .stMarkdown p { color: #374151; }

  /* ── Section dividers ────────────────────────────────── */
  .section-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #9ca3af;
    margin-bottom: 0.75rem;
  }

  /* ── Sidebar polish ──────────────────────────────────── */
  [data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e5e7eb !important;
  }

  /* ── Streamlit widget overrides ──────────────────────── */
  .stFileUploader { background: transparent !important; }
  .stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
  }
  .stButton > button:not([kind="primary"]) {
    background: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #d1d5db !important;
  }
  .stButton > button:not([kind="primary"]):hover {
    background: #f9fafb !important;
    border-color: #9ca3af !important;
  }
  .stButton > button[kind="primary"] {
    background: #0d9488 !important;
    border-color: #0d9488 !important;
    color: #fff !important;
  }
  .stButton > button[kind="primary"]:hover {
    background: #0f766e !important;
    border-color: #0f766e !important;
  }
  .stTextInput > div > div > input {
    border-radius: 8px !important;
    border-color: #d1d5db !important;
  }
  .stNumberInput input {
    color: #111827 !important;
  }
  .stSelectbox div[data-baseweb="select"] {
    color: #111827 !important;
  }
  .stMarkdown, .stCaption, .stText, .stRadio, .stSelectbox, .stNumberInput {
    color: #111827 !important;
  }
  .stProgress > div > div > div {
    background: #0d9488 !important;
  }
  .stRadio > div { gap: 0.5rem; }
</style>
"""
