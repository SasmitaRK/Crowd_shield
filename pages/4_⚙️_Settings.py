"""Settings — per-segment thresholds, area auto-calculator, model, email."""

import math
import streamlit as st

from ui import page_header

from shared_state import (init_state, GLOBAL_CSS, SEGMENTS,
                          DEFAULT_THRESHOLDS, RISK_COLORS, RISK_ICONS,
                          FRUIN_PRESETS, get_seg_thresholds)
from emailer import email_configured
from detection import MODEL_REGISTRY

st.set_page_config(page_title="Settings • Crowd Shield",
                   page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Settings", "Risk limits per zone, from the zone's area and a crowd-density standard, plus the fallback detector and email alerts.", "Configure")

# ---------------------------------------------------------------------------
# 1. Detection model
# ---------------------------------------------------------------------------
st.markdown("### Detection Model")
model_keys = list(MODEL_REGISTRY.keys())
current    = st.session_state.active_model
if current not in model_keys:
    current = model_keys[0]

choice = st.radio(
    "Default / fallback active model",
    options=model_keys,
    format_func=lambda k: MODEL_REGISTRY[k]["label"],
    index=model_keys.index(current),
    horizontal=True,
)
if choice != st.session_state.active_model:
    st.session_state.active_model = choice
    st.success(f"Switched to **{MODEL_REGISTRY[choice]['label']}**. "
               "Re-run detection on the Upload page.")

st.markdown(
    f"<div class='glass-card' style='font-size:.85rem;margin-top:.5rem'>"
    f"<b>Active:</b> {MODEL_REGISTRY[st.session_state.active_model]['label']}<br>"
    f"<span style='color:#6b7280'>"
    f"Path: <code>{MODEL_REGISTRY[st.session_state.active_model]['path']}</code>"
    f"</span></div>",
    unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# 2. Area-based threshold auto-calculator
# ---------------------------------------------------------------------------
st.markdown("### Auto-Calculate Thresholds from Zone Area")
st.caption(
    "Enter the physical area (m²) for each zone and choose a density "
    "standard — thresholds are calculated using the Fruin Level of Service "
    "scale and applied in one click.")

preset_name = st.selectbox(
    "Crowd density standard",
    options=list(FRUIN_PRESETS.keys()),
    index=1,
    help="Sets the people/m² limits for each risk tier.",
)
preset = FRUIN_PRESETS[preset_name]

cov_col1, cov_col2 = st.columns([2, 3])
with cov_col1:
    coverage = st.slider(
        "Camera coverage factor",
        min_value=0.50, max_value=1.00, value=0.75, step=0.05,
        help=(
            "Fraction of the zone visible in your images. "
            "If cameras cover 75% of the area, set this to 0.75 — "
            "detected counts are divided by this to estimate true density, "
            "making the effective thresholds more conservative."
        ),
    )
with cov_col2:
    st.markdown(
        f"<div class='glass-card' style='font-size:.82rem;padding:.8rem'>"
        f"<b>How coverage works:</b><br>"
        f"Threshold = area × density × coverage.<br>"
        f"At {int(coverage*100)}% coverage your camera under-counts by "
        f"~{int((1/coverage - 1)*100)}%, so thresholds are scaled down "
        f"to stay safe."
        f"</div>",
        unsafe_allow_html=True)

st.markdown("**Enter zone areas:**")
area_cols   = st.columns(5)
area_inputs = {}
for i, seg in enumerate(SEGMENTS):
    with area_cols[i]:
        saved = st.session_state.seg_areas.get(seg, 0)
        area_inputs[seg] = st.number_input(
            f"Zone {seg} (m²)",
            min_value=0, max_value=100_000,
            value=int(saved), step=10,
            key=f"area_{seg}",
        )

if any(v > 0 for v in area_inputs.values()):
    st.markdown("**Preview of calculated thresholds:**")
    prev_cols = st.columns(5)
    for i, seg in enumerate(SEGMENTS):
        with prev_cols[i]:
            area = area_inputs[seg]
            if area > 0:
                mod  = max(1, math.floor(area * preset["moderate"] * coverage))
                hi   = max(mod + 1, math.floor(area * preset["high"] * coverage))
                crit = max(hi + 1, math.floor(area * preset["critical"] * coverage))
                st.markdown(
                    f"<div class='glass-card' style='font-size:.78rem;padding:.7rem;"
                    f"text-align:center'>"
                    f"<b>Zone {seg}</b><br>"
                    f"<span style='color:#f59e0b;font-weight:600'>{mod}</span>"
                    f"<span style='color:#d1d5db'> / </span>"
                    f"<span style='color:#f97316;font-weight:600'>{hi}</span>"
                    f"<span style='color:#d1d5db'> / </span>"
                    f"<span style='color:#ef4444;font-weight:600'>{crit}</span>"
                    f"</div>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div class='glass-card' style='font-size:.78rem;padding:.7rem;"
                    f"text-align:center;color:#9ca3af'>Zone {seg}<br>no area</div>",
                    unsafe_allow_html=True)

if st.button("Auto-calculate and apply thresholds",
             use_container_width=True,
             disabled=not any(v > 0 for v in area_inputs.values())):
    applied, skipped = [], []
    new_t = dict(st.session_state.thresholds)
    for seg in SEGMENTS:
        area = area_inputs[seg]
        st.session_state.seg_areas[seg] = area
        if area > 0:
            mod  = max(1, math.floor(area * preset["moderate"] * coverage))
            hi   = max(mod + 1, math.floor(area * preset["high"] * coverage))
            crit = max(hi + 1, math.floor(area * preset["critical"] * coverage))
            new_t[seg] = {"moderate": mod, "high": hi, "critical": crit}
            applied.append(f"Zone {seg}: {mod} / {hi} / {crit}")
        else:
            skipped.append(seg)
    st.session_state.thresholds    = new_t
    st.session_state.low_threshold  = new_t["A"]["moderate"]
    st.session_state.high_threshold = new_t["A"]["critical"]
    if applied:
        st.success("Applied:\n\n- " + "\n- ".join(applied))
    if skipped:
        st.info(f"Zones with no area entered kept their previous thresholds: "
                f"{', '.join(skipped)}")

with st.expander("Fruin density standards explained"):
    st.markdown(f"""
**Currently selected:** *{preset_name}*

| Risk Level | Density (people/m²) | Physical meaning |
|---|---|---|
| Safe      | < {preset['moderate']} p/m² | Free movement, comfortable spacing |
| Moderate  | {preset['moderate']}–{preset['high']} p/m² | Restricted but manageable |
| High Risk | {preset['high']}–{preset['critical']} p/m² | Body contact, crowd pressure |
| Critical  | > {preset['critical']} p/m² | Crush risk — emergency response |

**Formula:** `threshold = area_m² × density × camera_coverage`

Example — 200 m² segment, standard preset, 75% coverage:
```
Moderate  = 200 × {preset['moderate']} × 0.75 = {math.floor(200 * preset['moderate'] * 0.75)} people
High Risk = 200 × {preset['high']} × 0.75 = {math.floor(200 * preset['high'] * 0.75)} people
Critical  = 200 × {preset['critical']} × 0.75 = {math.floor(200 * preset['critical'] * 0.75)} people
```
The coverage factor accounts for cameras not seeing the full area —
detected counts are always *lower* than actual occupancy, so thresholds
are scaled down to stay on the safe side.
    """)

st.markdown("---")

# ---------------------------------------------------------------------------
# 3. Manual per-segment thresholds
# ---------------------------------------------------------------------------
st.markdown("### Per-Zone Risk Thresholds")
st.caption("These values are what auto-calculation writes to. "
           "You can also edit them directly here.")

hcols = st.columns([1, 2, 2, 2, 3])
hcols[0].markdown("**Seg**")
hcols[1].markdown("<span style='color:#f59e0b;font-weight:700'>Moderate</span>",
                  unsafe_allow_html=True)
hcols[2].markdown("<span style='color:#f97316;font-weight:700'>High Risk</span>",
                  unsafe_allow_html=True)
hcols[3].markdown("<span style='color:#ef4444;font-weight:700'>Critical</span>",
                  unsafe_allow_html=True)
hcols[4].markdown("*Rule*")

new_thresholds = {}
for seg in SEGMENTS:
    t = get_seg_thresholds(seg)
    c0, c1, c2, c3, c4 = st.columns([1, 2, 2, 2, 3])
    c0.markdown(f"**{seg}**")
    mod  = c1.number_input("Moderate", min_value=1, max_value=9999,
                           value=t["moderate"], step=5, key=f"t_mod_{seg}",
                           label_visibility="collapsed")
    hi   = c2.number_input("High Risk", min_value=1, max_value=9999,
                           value=t["high"], step=5, key=f"t_hi_{seg}",
                           label_visibility="collapsed")
    crit = c3.number_input("Critical", min_value=1, max_value=9999,
                           value=t["critical"], step=5, key=f"t_crit_{seg}",
                           label_visibility="collapsed")
    c4.markdown(
        f"<span style='font-size:.78rem;color:#6b7280'>"
        f"Safe &lt;{mod} · Mod {mod}–{hi-1} · High {hi}–{crit-1} · Crit ≥{crit}"
        f"</span>",
        unsafe_allow_html=True)
    new_thresholds[seg] = {"moderate": mod, "high": hi, "critical": crit}

if st.button("Save manual thresholds", use_container_width=True):
    errors = []
    for seg, t in new_thresholds.items():
        if not (t["moderate"] < t["high"] < t["critical"]):
            errors.append(f"Zone {seg}: moderate < high < critical required")
    if errors:
        for e in errors:
            st.error(e)
    else:
        st.session_state.thresholds    = new_thresholds
        st.session_state.low_threshold  = new_thresholds["A"]["moderate"]
        st.session_state.high_threshold = new_thresholds["A"]["critical"]
        st.success("Manual thresholds saved.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 4. Email config
# ---------------------------------------------------------------------------
st.markdown("### Gmail Alert Configuration")
if email_configured():
    st.success("Gmail configured — alerts with embedded detection images "
               "can be sent from the Analysis page.")
else:
    st.error("Gmail not configured.")

with st.expander("How to enable email alerts", expanded=not email_configured()):
    st.markdown("""
| Secret name | Value |
|---|---|
| `GMAIL_USER` | Gmail address that sends alerts |
| `GMAIL_APP_PASSWORD` | 16-character app password from Google |

**Steps:**
1. Enable 2-Step Verification at <https://myaccount.google.com/security>
2. Generate an app password at <https://myaccount.google.com/apppasswords>
   — choose Mail / Other (CrowdWatch Pro)
3. Add both as Replit Secrets (lock icon in sidebar)
    """)

st.markdown("---")

st.markdown("""
<style>
.stButton > button:not([kind="primary"]) {
  background: #ffffff !important;
  color: #111827 !important;
  border: 1px solid #d1d5db !important;
}
.stButton > button:not([kind="primary"]):hover {
  background: #f9fafb !important;
  border-color: #9ca3af !important;
}
.stNumberInput input {
  color: #111827 !important;
}
.stExpander {
  background: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 5. Reset controls
# ---------------------------------------------------------------------------
st.markdown("### Reset")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Clear images and results", use_container_width=True):
        st.session_state.uploaded_images = {s: [] for s in SEGMENTS}
        st.session_state.image_names     = {s: [] for s in SEGMENTS}
        st.session_state.image_sources   = {s: [] for s in SEGMENTS}
        st.session_state.crowd_data      = {}
        st.success("Cleared.")
with col2:
    if st.button("Clear agent assignments", use_container_width=True):
        st.session_state.agents = {s: "" for s in SEGMENTS}
        st.success("Cleared.")
with col3:
    if st.button("Reset thresholds to defaults", use_container_width=True):
        st.session_state.thresholds = {s: dict(DEFAULT_THRESHOLDS) for s in SEGMENTS}
        st.success("Reset to defaults (moderate=30, high=60, critical=90).")

# ---------------------------------------------------------------------------
# Server and memory
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Server")
from crowdshield import config as _cfg  # noqa: E402

_limit, _used, _own = _cfg.memory_limit_bytes(), _cfg.memory_in_use_bytes(), _cfg.own_rss_bytes()
_gb = lambda b: "unknown" if b is None else f"{b / 1e9:.1f} GB"
_work = _cfg.default_work_side()
try:
    _fit = _cfg.fit_max_side(ceiling=_work)
    _how = "one pass" if _fit >= _work else f"tiles of {_fit} px"
except _cfg.NotEnoughMemory:
    _fit, _how = None, "none fits"
st.caption("What this server can hold, and how it will count a photo right now. A server too small to run "
           "a photo in one pass counts it in tiles, which keeps the detail. If even a tile would not fit, "
           "the app says so instead of crashing.")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Memory limit", _gb(_limit))
c2.metric("In use", _gb(_used), help="Memory used by everything running on this server.")
c3.metric("This app", _gb(_own))
c4.metric("Photo detail", f"{_work} px", help="Photos are shrunk to this size (longer side) before counting.")
c5.metric("Counted in", _how, help="One pass if it fits in memory, otherwise tiles with a little overlap.")
st.caption(f"Running from `{_cfg.REPO_ROOT}`"
           f"{' (Streamlit Community Cloud)' if _cfg.on_streamlit_cloud() else ''}.")
