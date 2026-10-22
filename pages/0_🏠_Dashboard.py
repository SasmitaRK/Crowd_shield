"""Dashboard: what Crowd Shield does, how well it works, and the state of today's zones."""

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
  <p>Crowd Shield counts every head in CCTV, drone and phone photos, turns counts into people per
  square metre on a real map, watches camera feeds for zones filling up or surging, and tells each
  zone's team where to move people.</p>
  <div class="stats">
    <div class="stat"><b>92.7%</b><span>counting accuracy, street crowds</span></div>
    <div class="stat"><b>86.5%</b><span>on packed crowds (ShanghaiTech A)</span></div>
    <div class="stat"><b>9 / 10</b><span>Indian test photos counted about 90% right</span></div>
    <div class="stat"><b>11 / 11</b><span>escape events caught in video</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

b1, b2, b3, b4, _ = st.columns([1.2, 1.2, 1.2, 1.2, 1.6])
with b1:
    nav_link("pages/6_🗺️_Map.py", "Open the site map", ":material/map:", "/Map")
with b2:
    nav_link("pages/2_📤_Upload.py", "Count a photo", ":material/photo_camera:", "/Upload")
with b3:
    nav_link("pages/5_🎥_Video.py", "Analyse a video", ":material/videocam:", "/Video")
with b4:
    nav_link("pages/8_📡_Live.py", "Watch a live feed", ":material/sensors:", "/Live")

# ── Today's operations ─────────────────────────────────────────────────────
agents = st.session_state.agents
data = st.session_state.crowd_data
assigned = sum(1 for v in agents.values() if v)
risks = {seg: risk_level(d["count"], get_seg_thresholds(seg)) for seg, d in data.items()}
at_risk = [s for s, r in risks.items() if r in ("High Risk", "Critical")]
channels = ready_channels()

section("Today's operations", "From this session: counts appear after you count photos on Photo analysis.")
kpi_cards([
    ("Zones counted", f"{len(data)} / 5", "from photo analysis"),
    ("People counted", compact(sum(d["count"] for d in data.values())) if data else "–",
     "across all zones"),
    ("Zones at risk", f"{len(at_risk)}", ", ".join(at_risk) or "none right now"),
    ("Response team", f"{assigned} / 5", "zones with a contact"),
    ("Alerts", "Ready" if channels else "Off", " and ".join(channels) if channels else "set up in Settings"),
], accents=["#0d9488", "#2a78d6", RISK_COLORS["Critical"] if at_risk else "#10b981",
            "#10b981" if assigned == 5 else "#f59e0b", "#10b981" if channels else "#94a3b8"])

cols = st.columns(5)
for col, seg in zip(cols, SEGMENTS):
    d = data.get(seg)
    risk = risks.get(seg)
    colour = RISK_COLORS.get(risk, "#cbd5e1")
    count = f"{d['count']:,}" if d else "–"
    contact = agents.get(seg) or "no contact yet"
    col.markdown(
        f"<div class='card' style='border-top:3px solid {colour};padding:.9rem 1rem'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center'>"
        f"<span style='font-weight:800;font-size:.8rem;color:#334155;letter-spacing:.06em;white-space:nowrap;"
        f"overflow:hidden;text-overflow:ellipsis'>{html.escape(zone_label(seg).upper())}</span>"
        f"{risk_pill(risk)}</div>"
        f"<div style='font-size:1.7rem;font-weight:800;margin:.45rem 0 .1rem;"
        f"font-variant-numeric:tabular-nums'>{count}</div>"
        f"<div style='font-size:.75rem;color:#64748b'>people · "
        f"{len(st.session_state.uploaded_images.get(seg, []))} photo(s)</div>"
        f"<div style='font-size:.74rem;color:#94a3b8;margin-top:.45rem;white-space:nowrap;overflow:hidden;"
        f"text-overflow:ellipsis'>{contact}</div></div>",
        unsafe_allow_html=True)

# ── What it does ───────────────────────────────────────────────────────────
ICONS = {
    "map": "<path d='M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z'/><path d='M9 4v14M15 6v14'/>",
    "dots": "<circle cx='6' cy='7' r='2'/><circle cx='12' cy='5' r='2'/><circle cx='18' cy='8' r='2'/>"
            "<circle cx='8' cy='14' r='2'/><circle cx='15' cy='15' r='2'/><circle cx='11' cy='20' r='2'/>",
    "wave": "<polyline points='2 12 6 12 9 4 15 20 18 12 22 12'/>",
    "route": "<circle cx='6' cy='19' r='2.5'/><circle cx='18' cy='5' r='2.5'/>"
             "<path d='M8.5 19H15a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h6.5'/>",
}


def icon(name):
    return (f"<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='#0d9488' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{ICONS[name]}</svg>")


section("What Crowd Shield does")
features = [
    ("dots", "Counts every head", "A point model (PET) puts a dot on each head, so it keeps working when "
     "bodies overlap. Tested on ShanghaiTech and on Indian photos.", "pages/2_📤_Upload.py", "Count a photo"),
    ("map", "Density on a real map", "Zones drawn on satellite imagery give true ground area, so counts "
     "become people per m², the number crowd-safety science uses.", "pages/6_🗺️_Map.py", "Open the map"),
    ("wave", "Watches cameras", "On a video clip, optical flow spots a sudden surge. On a live stream it "
     "recounts every zone every 30 s or more and warns before a zone is full.", "pages/8_📡_Live.py",
     "Watch a live feed"),
    ("route", "Plans the response", "An optimiser finds where to move people from crowded zones, only "
     "along walkable routes, and alerts each zone's team by email or Telegram.", "pages/3_📊_Analysis.py",
     "See alerts and plans"),
]
cols = st.columns(4)
for col, (ic, title, body, target, label) in zip(cols, features):
    with col:
        st.markdown(f"<div class='feature-card'><div class='feature-icon'>{icon(ic)}</div>"
                    f"<h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)
        nav_link(target, label, ":material/arrow_forward:", "/" + target.split("_")[-1][:-3])
        if ic == "wave":
            nav_link("pages/5_🎥_Video.py", "Analyse a video", ":material/arrow_forward:", "/Video")

# ── Recent runs ────────────────────────────────────────────────────────────
section("Recent photo analyses")
history = st.session_state.get("detection_history", [])
if not history:
    st.markdown("<div class='card' style='color:#64748b;font-size:.9rem'>No analyses yet. Add photos on "
                "<b>Photo analysis</b> and run the count; each run shows up here.</div>",
                unsafe_allow_html=True)
for entry in history[:8]:
    pills = " ".join(risk_pill(v["risk"], f"{k} · {v['count']:,}") for k, v in entry["results"].items())
    st.markdown(
        f"<div class='card' style='margin-bottom:.5rem;padding:.75rem 1rem;display:flex;"
        f"justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap'>"
        f"<div><div style='font-weight:700;font-size:.86rem'>{entry['timestamp']}</div>"
        f"<div style='font-size:.78rem;color:#64748b'>{entry['seg_count']} zones · "
        f"<b style='color:#0f172a'>{entry['total']:,}</b> people</div></div><div>{pills}</div></div>",
        unsafe_allow_html=True)

st.caption("Accuracy figures come from held-out test photos (ShanghaiTech) and a 10-photo hand-labelled "
           "Indian pilot set, where one railway photo is a known failure (see India benchmark). The video "
           "figure is from the UMN crowd-escape clips. Details are in the README.")
