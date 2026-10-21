"""Response team: one contact per zone, who gets the email alerts for that zone."""

import re

import streamlit as st

from emailer import email_configured
from shared_state import GLOBAL_CSS, SEGMENTS, init_state
from ui import kpi_cards, page_header

st.set_page_config(page_title="Response team • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Response team", "Give each zone a contact. When a zone turns High Risk or Critical, its "
            "contact and the receiving zone's contact get an email with the counts and the plan.",
            "Configure")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
names = st.session_state.get("zone_names", {})

# Pre-populate widget state from saved contacts only on first load
for seg in SEGMENTS:
    key = f"agent_input_{seg}"
    if key not in st.session_state:
        st.session_state[key] = st.session_state.agents.get(seg, "")

assigned = sum(1 for v in st.session_state.agents.values() if v)
kpi_cards([
    ("Zones with a contact", f"{assigned} / 5", "each zone needs one person on call"),
    ("Email alerts", "Ready" if email_configured() else "Off",
     "Gmail is configured" if email_configured() else "add Gmail details in Settings"),
    ("Alerts sent", f"{st.session_state.alert_count}", "this session"),
], accents=["#10b981" if assigned == 5 else "#f59e0b",
            "#10b981" if email_configured() else "#94a3b8", "#2a78d6"])
st.write("")

new_vals = {}
with st.container(border=True):
    head = st.columns([1, 3, 4, 2])
    for col, title in zip(head, ["Zone", "Place", "Contact email", "Status"]):
        col.markdown(f"<div class='sec' style='margin:.1rem 0'>{title}</div>", unsafe_allow_html=True)
    for seg in SEGMENTS:
        saved = st.session_state.agents.get(seg, "")
        c0, c1, c2, c3 = st.columns([1, 3, 4, 2], vertical_alignment="center")
        c0.markdown(f"<div style='width:30px;height:30px;border-radius:8px;background:#0f172a;color:#fff;"
                    f"font-weight:800;display:flex;align-items:center;justify-content:center'>{seg}</div>",
                    unsafe_allow_html=True)
        c1.markdown(f"<span style='font-size:.88rem;color:#334155'>{names.get(seg, f'Zone {seg}')}</span>",
                    unsafe_allow_html=True)
        new_vals[seg] = c2.text_input(f"Contact email for zone {seg}", placeholder="name@example.com",
                                      label_visibility="collapsed", key=f"agent_input_{seg}")
        c3.markdown("<span class='pill brand'>Assigned</span>" if saved
                    else "<span class='pill neutral'>No contact</span>", unsafe_allow_html=True)

if st.button("Save contacts", type="primary", width="stretch", icon=":material/save:"):
    invalid = [s for s, v in new_vals.items() if v and not EMAIL_RE.match(v)]
    if invalid:
        st.error(f"Check the email address for zone(s): {', '.join(invalid)}")
    else:
        st.session_state.agents = {s: v.strip() for s, v in new_vals.items()}
        st.success(f"Saved: {sum(1 for v in new_vals.values() if v)} of 5 zones have a contact.")
        st.rerun()

st.caption("Place names come from the Site map when you apply a map to the app. Contacts are kept for this "
           "session only.")
