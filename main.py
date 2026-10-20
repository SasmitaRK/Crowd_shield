"""Crowd Shield — Home / landing page."""

import streamlit as st
from shared_state import (init_state, GLOBAL_CSS, SEGMENTS,
                          RISK_COLORS, get_seg_thresholds)
from detection import risk_level
from emailer import email_configured

st.set_page_config(
    page_title="Crowd Shield",
    page_icon="assets/favicon.png" if False else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

# ── Navbar ───────────────────────────────────────────────────────────────────
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
        <a href="/Settings">Settings</a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Hero section ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-section">
      <div class="hero-badge">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <circle cx="5" cy="5" r="5" fill="#0d9488"/>
        </svg>
        Crowd Risk Analysis
      </div>
      <h1>Prevent stampedes<br>before they start.</h1>
      <p>
        AI crowd monitoring for high-density venues.
        Count people in CCTV and drone photos, rate each zone's risk,
        and alert response teams by email.
      </p>
      <div class="hero-buttons">
        <a href="/Upload" class="btn-primary">
          Open Command Center &nbsp;&#8594;
        </a>
        <a href="/Agents" class="btn-secondary">
          Register Response Agent
        </a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Feature cards ─────────────────────────────────────────────────────────────
SVG_EYE = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
  viewBox="0 0 24 24" fill="none" stroke="#0d9488" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round">
  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
  <circle cx="12" cy="12" r="3"/>
</svg>"""

SVG_ACTIVITY = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
  viewBox="0 0 24 24" fill="none" stroke="#0d9488" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round">
  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
</svg>"""

SVG_SHIELD = """<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
  viewBox="0 0 24 24" fill="none" stroke="#0d9488" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
</svg>"""

features = [
    (SVG_EYE,      "Computer Vision",
     "Upload CCTV or drone photos to count people and map where the "
     "crowd is densest."),
    (SVG_ACTIVITY, "Zone Analysis",
     "Automatically segment crowds into operational zones (A–E) to isolate "
     "risk levels and manage flow effectively."),
    (SVG_SHIELD,   "Automated Dispatch",
     "When a zone turns high-risk, its agent and the receiving zone's agent "
     "get an email with the counts and a relocation plan."),
]

cols = st.columns(3)
for col, (icon, title, desc) in zip(cols, features):
    with col:
        st.markdown(
            f"""
            <div class="feature-card">
              <div class="feature-icon">{icon}</div>
              <h3>{title}</h3>
              <p>{desc}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Status dashboard ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-label">System Status</div>', unsafe_allow_html=True)

agents   = st.session_state.agents
imgs     = st.session_state.uploaded_images
data     = st.session_state.crowd_data
assigned = sum(1 for v in agents.values() if v)
uploaded = sum(1 for v in imgs.values()   if v)
analyzed = len(data)
email_ok = email_configured()

stat_cols = st.columns(4)
stats = [
    ("Agents Assigned",       f"{assigned} / 5"),
    ("Segments with Images",  f"{uploaded} / 5"),
    ("Segments Analysed",     f"{analyzed} / 5"),
    ("Email Alerts",          "Ready" if email_ok else "Not configured"),
]
status_colors = [
    "#10b981" if assigned  == 5 else "#f59e0b",
    "#10b981" if uploaded  == 5 else "#f59e0b",
    "#10b981" if analyzed  == 5 else "#f59e0b",
    "#10b981" if email_ok       else "#ef4444",
]
for col, (label, value), color in zip(stat_cols, stats, status_colors):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
              <div style="font-size:.75rem;font-weight:600;color:#9ca3af;
                          text-transform:uppercase;letter-spacing:.5px;
                          margin-bottom:.5rem">{label}</div>
              <div style="font-size:1.6rem;font-weight:800;color:{color}">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Segment snapshot ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-label">Segment Snapshot</div>', unsafe_allow_html=True)

seg_cols = st.columns(5)
_risk_border = {
    "Safe":      "#10b981",
    "Moderate":  "#f59e0b",
    "High Risk": "#f97316",
    "Critical":  "#ef4444",
}
for i, seg in enumerate(SEGMENTS):
    with seg_cols[i]:
        n_imgs      = len(imgs.get(seg, []))
        agent_email = agents.get(seg, "")
        seg_d       = data.get(seg, {})
        raw_count   = seg_d.get("count")
        count_disp  = raw_count if raw_count is not None else "—"
        has_agent   = bool(agent_email)

        # Compute risk from stored count + thresholds
        if raw_count is not None:
            seg_risk = risk_level(raw_count, get_seg_thresholds(seg))
        else:
            seg_risk = ""
        border_col = _risk_border.get(seg_risk, "#e5e7eb")

        agent_display = (
            f'<span style="font-size:.8rem;color:#0d9488;font-weight:500">'
            f'{agent_email}</span>'
            if has_agent else
            '<span style="font-size:.8rem;color:#9ca3af">No agent assigned</span>'
        )

        st.markdown(
            f"""
            <div class="glass-card" style="text-align:center;
                 border-top:3px solid {border_col}">
              <div style="font-size:.7rem;font-weight:700;color:#9ca3af;
                          text-transform:uppercase;letter-spacing:.8px;
                          margin-bottom:.5rem">Segment {seg}</div>
              <div style="font-size:2rem;font-weight:800;color:#111827;
                          margin:.4rem 0">{count_disp}</div>
              <div style="font-size:.75rem;color:#6b7280;margin-bottom:.6rem">
                people detected</div>
              <div style="border-top:1px solid #f3f4f6;padding-top:.6rem;
                          margin-top:.2rem">
                <div style="font-size:.75rem;color:#6b7280">
                  {n_imgs} / 4 images
                </div>
                <div style="margin-top:.35rem">{agent_display}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Detection History ──────────────────────────────────────────────────────────
history = st.session_state.get("detection_history", [])
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-label">Detection History</div>',
            unsafe_allow_html=True)

if not history:
    st.markdown(
        "<div class='glass-card' style='color:#9ca3af;font-size:.9rem'>"
        "No detection runs yet — upload images and click Run Detection to start."
        "</div>",
        unsafe_allow_html=True,
    )
else:
    risk_dot = {
        "Safe":      "#10b981",
        "Moderate":  "#f59e0b",
        "High Risk": "#f97316",
        "Critical":  "#ef4444",
    }
    for entry in history[:8]:
        pills = []
        for k, v in entry["results"].items():
            rc  = risk_dot.get(v["risk"], "#e5e7eb")
            cnt = v["count"]
            pills.append(
                f"<span style='display:inline-block;padding:.15rem .5rem;"
                f"background:{rc}22;color:{rc};"
                f"border:1px solid {rc};"
                f"border-radius:6px;font-size:.72rem;font-weight:600;margin:.1rem'>"
                f"Seg {k}: {cnt}</span>"
            )
        seg_pills = "".join(pills)
        n_crit    = entry["critical"]
        crit_badge = (
            f"<span style='background:#fee2e2;color:#991b1b;padding:.2rem .55rem;"
            f"border-radius:999px;font-size:.7rem;font-weight:700;margin-left:.5rem'>"
            f"{n_crit} Critical</span>"
            if n_crit > 0 else ""
        )
        ts        = entry["timestamp"]
        n_segs    = entry["seg_count"]
        n_total   = entry["total"]
        st.markdown(
            f"""
            <div class="glass-card" style="margin-bottom:.6rem;padding:.9rem 1.1rem">
              <div style="display:flex;justify-content:space-between;
                          align-items:center;margin-bottom:.5rem">
                <span style="font-size:.85rem;font-weight:700;color:#111827">
                  {ts}
                </span>
                <span style="font-size:.8rem;color:#6b7280">
                  {n_segs} segments &nbsp;·&nbsp;
                  <b style="color:#111827">{n_total}</b> people total
                  {crit_badge}
                </span>
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:.3rem">{seg_pills}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
