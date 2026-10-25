"""Home: what Crowd Shield does, where to start, and (once something is counted) this session's zones."""

import html
import random

import streamlit as st

from detection import risk_level
from crowdshield.notify import ready_channels
from shared_state import GLOBAL_CSS, RISK_COLORS, SEGMENTS, get_seg_thresholds, init_state, zone_label
from ui import compact, kpi_cards, nav_link, risk_pill, section

st.set_page_config(page_title="Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

# A field of head-dots that thickens to the right: the crowd the model sees.
rng = random.Random(7)
dots = []
for _ in range(150):
    x = 300 * (rng.random() ** 0.55)
    y = 190 * rng.random()
    hot = x > 210 and 60 < y < 150
    colour = "#f87171" if hot else ("#5eead4" if x > 120 else "#64748b")
    dots.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{2.4 if hot else 2:.1f}' fill='{colour}' "
                f"style='animation-delay:{rng.random() * 3.6:.2f}s'/>")
hero_dots = f"<svg class='hero-dots' viewBox='0 0 300 190'>{''.join(dots)}</svg>"

st.markdown(f"""
<div class="hero">
  <div class="hero-grid"></div>{hero_dots}
  <div class="eyebrow"><span class="live-dot"></span>Crowd safety for Indian public spaces</div>
  <h1>See crowd danger before it becomes a crush.</h1>
  <p>Crowd Shield counts the people in camera pictures, works out how crowded each part of a site is,
  and tells the team where to move people before it becomes dangerous.</p>
  <div class="stats">
    <div class="stat"><b>92.7%</b><span>accurate on street crowds</span></div>
    <div class="stat"><b>86.5%</b><span>accurate on packed crowds</span></div>
    <div class="stat"><b>9 / 10</b><span>Indian test photos counted about 90% right</span></div>
    <div class="stat"><b>11 / 11</b><span>sudden surges caught in test videos</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Start here ─────────────────────────────────────────────────────────────
section("Start here", "Pick what you have. Each one works in a minute, and each has a ready-made example if "
        "you have nothing to hand.")
START = [
    ("photo_camera", "I have a photo", "From CCTV, a drone or a phone. Get a dot on every head and a count.",
     "pages/2_Upload.py", "Count people in a photo", "/Upload"),
    ("videocam", "I have a video clip", "See how a crowd changes second by second, and spot sudden surges.",
     "pages/5_Video.py", "Analyse a video", "/Video"),
    ("sensors", "I have a live camera", "Recount every 30 seconds and warn before a zone fills up.",
     "pages/8_Live.py", "Watch a live camera", "/Live"),
    ("map", "I'm just exploring", "Open the Kumbh Mela site map and play a crowd surge forward.",
     "pages/6_Map.py", "Open the site map", "/Map"),
]
for col, (ic, title, body, target, label, url) in zip(st.columns(4), START):
    with col:
        st.markdown(f"<div class='feature-card' style='min-height:215px'><div class='feature-icon'>"
                    f"<span style=\"font-family:'Material Symbols Rounded';font-size:22px;line-height:1\">{ic}</span></div>"
                    f"<h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)
        nav_link(target, label, ":material/arrow_forward:", url)

# ── How it works ───────────────────────────────────────────────────────────
section("How it works")
STEPS = [
    ("1", "Count every head", "An AI model puts a dot on each head, even where people overlap."),
    ("2", "Measure the space", "Zones drawn on a satellite map give each area in m², so a count becomes people "
     "per m², the number crowd-safety experts use."),
    ("3", "Spot the danger", "Each zone turns amber, orange or red as it fills. On video, a sudden rush raises "
     "an alarm."),
    ("4", "Act early", "It plans where to move people, only along routes they can walk, and alerts each "
     "zone's team by Telegram or email."),
]
for col, (n, title, body) in zip(st.columns(4), STEPS):
    col.markdown(f"<div class='card' style='height:100%'><div style='font-weight:800;color:#0d9488'>{n}</div>"
                 f"<div style='font-weight:700;margin:.2rem 0'>{title}</div>"
                 f"<div style='font-size:.85rem;color:#64748b;line-height:1.55'>{body}</div></div>",
                 unsafe_allow_html=True)

# ── This session (only once something has been counted) ────────────────────
agents = st.session_state.agents
data = st.session_state.crowd_data
history = st.session_state.get("detection_history", [])
if data:
    assigned = sum(1 for v in agents.values() if v)
    risks = {seg: risk_level(d["count"], get_seg_thresholds(seg)) for seg, d in data.items()}
    at_risk = [s for s, r in risks.items() if r in ("High Risk", "Critical")]
    channels = ready_channels()
    section("Your zones right now", "From the photos you counted in this session.")
    kpi_cards([
        ("People counted", compact(sum(d["count"] for d in data.values())), f"in {len(data)} of 5 zones"),
        ("Zones at risk", f"{len(at_risk)}", ", ".join(at_risk) or "none right now"),
        ("Team contacts", f"{assigned} / 5", "zones with someone to alert"),
        ("Alerts", "Ready" if channels else "Off", " and ".join(channels) if channels else "set up in Team and alerts"),
    ], accents=["#0d9488", RISK_COLORS["Critical"] if at_risk else "#10b981",
                "#10b981" if assigned == 5 else "#f59e0b", "#10b981" if channels else "#94a3b8"])
    st.write("")
    for col, seg in zip(st.columns(5), SEGMENTS):
        d, risk = data.get(seg), risks.get(seg)
        colour = RISK_COLORS.get(risk, "#cbd5e1")
        count = f"{d['count']:,}" if d else "–"
        col.markdown(
            f"<div class='card' style='border-top:3px solid {colour};padding:.9rem 1rem'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;gap:.3rem'>"
            f"<span style='font-weight:800;font-size:.8rem;color:#334155;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis'>{html.escape(zone_label(seg))}</span>{risk_pill(risk)}</div>"
            f"<div style='font-size:1.7rem;font-weight:800;margin:.45rem 0 .1rem'>{count}</div>"
            f"<div style='font-size:.75rem;color:#64748b'>{'people' if d else 'not counted'}</div></div>",
            unsafe_allow_html=True)
    nav_link("pages/3_Analysis.py", "See the evacuation plan and send alerts", ":material/campaign:", "/Analysis")
    if history:
        with st.expander(f"Earlier counts in this session ({len(history)})"):
            for entry in history[:8]:
                pills = " ".join(risk_pill(v["risk"], f"{k} · {v['count']:,}") for k, v in entry["results"].items())
                st.markdown(f"<div style='margin:.3rem 0'><b>{entry['timestamp']}</b> · {entry['total']:,} people "
                            f"&nbsp; {pills}</div>", unsafe_allow_html=True)

st.caption("The accuracy figures come from test photos the model never saw in training, and from 10 hand-counted "
           "Indian photos where one railway photo is a known failure.")
nav_link("pages/7_Benchmark.py", "How accurate is it? See every test photo", ":material/verified:", "/Benchmark")
