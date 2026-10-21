"""Agent assignment page — map gmail addresses to segments."""

import re
import streamlit as st

from shared_state import init_state, GLOBAL_CSS, SEGMENTS

st.set_page_config(page_title="Agents • Crowd Shield",
                   page_icon=None, layout="wide")
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

st.markdown("# Agent Assignment")
st.caption("Assign a Gmail address to each segment. Alerts will be emailed directly to that agent when crowd risk thresholds are exceeded.")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Pre-populate widget state from saved agents only on first load
for seg in SEGMENTS:
    key = f"agent_input_{seg}"
    if key not in st.session_state:
        st.session_state[key] = st.session_state.agents.get(seg, "")

cols = st.columns(5)
new_vals = {}
for i, seg in enumerate(SEGMENTS):
    with cols[i]:
        saved_email  = st.session_state.agents.get(seg, "")
        current_input = st.session_state.get(f"agent_input_{seg}", saved_email)
        is_set       = bool(saved_email)
        status_color = "#10b981" if is_set else "#9ca3af"
        status_label = "Assigned" if is_set else "Unassigned"

        st.markdown(
            f"""
            <div class="glass-card" style="margin-bottom:.75rem">
              <div style="display:flex;align-items:center;justify-content:space-between;
                          margin-bottom:.75rem">
                <span style="font-size:1.1rem;font-weight:800;color:#111827">
                  Segment {seg}
                </span>
                <span style="font-size:.72rem;font-weight:600;
                             color:{status_color};background:{'#d1fae5' if is_set else '#f3f4f6'};
                             padding:.2rem .55rem;border-radius:999px">
                  {status_label}
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        new_vals[seg] = st.text_input(
            f"Agent email — Segment {seg}",
            placeholder="agent@gmail.com",
            label_visibility="collapsed",
            key=f"agent_input_{seg}",
        )

st.markdown("")
if st.button("Save agent assignments", type="primary", use_container_width=True):
    invalid = [s for s, v in new_vals.items() if v and not EMAIL_RE.match(v)]
    if invalid:
        st.error(f"Invalid email format for segment(s): {', '.join(invalid)}")
    else:
        st.session_state.agents = {s: v.strip() for s, v in new_vals.items()}
        assigned_count = sum(1 for v in new_vals.values() if v)
        st.success(f"Saved — {assigned_count} / 5 segments have agents assigned.")
        st.rerun()
