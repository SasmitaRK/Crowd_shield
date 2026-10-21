"""Site Map: every zone on real satellite terrain, coloured by live risk, with evacuation routes."""

import html

import folium
import streamlit as st
from folium.plugins import AntPath, Draw, Fullscreen, MiniMap
from streamlit_folium import st_folium

from crowdshield.geo import ring_area_m2
from crowdshield.risk import thresholds_from_area
from crowdshield.sitemap import assess, load_site, scenario_counts, site_from_drawings
from shared_state import FRUIN_PRESETS, GLOBAL_CSS, RISK_COLORS, SEGMENTS, init_state

st.set_page_config(page_title="Site Map • Crowd Shield", page_icon=None, layout="wide")
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

st.markdown("""
<style>
  .map-hero {
    background: linear-gradient(135deg, #0b1220 0%, #10243a 55%, #0d3b3a 100%);
    border-radius: 16px; padding: 1.4rem 1.6rem; color: #e5edf5; margin-bottom: 1rem;
    border: 1px solid #1f3346; position: relative; overflow: hidden;
  }
  .map-hero h1 { color: #ffffff !important; font-size: 1.7rem; margin: 0 0 .3rem 0; letter-spacing: -.3px; }
  .map-hero p  { color: #a9bccf; margin: 0; font-size: .95rem; max-width: 820px; }
  .live-dot { display:inline-block; width:8px; height:8px; border-radius:50%;
              background:#22c55e; margin-right:.45rem; box-shadow:0 0 0 0 rgba(34,197,94,.7);
              animation: livepulse 1.8s infinite; }
  @keyframes livepulse { 0% {box-shadow:0 0 0 0 rgba(34,197,94,.7);}
                         70% {box-shadow:0 0 0 9px rgba(34,197,94,0);}
                         100% {box-shadow:0 0 0 0 rgba(34,197,94,0);} }
  .hero-tag { font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; color:#7dd3c8;
              font-weight:700; margin-bottom:.5rem; }
  .kpi { background:#ffffff; border:1px solid #e5e7eb; border-radius:14px; padding:.9rem 1rem;
         box-shadow:0 1px 3px rgba(0,0,0,.05); }
  .kpi .label { font-size:.72rem; color:#6b7280; text-transform:uppercase; letter-spacing:.08em; font-weight:600; }
  .kpi .value { font-size:1.6rem; font-weight:800; color:#0f172a; line-height:1.2; margin-top:.15rem; }
  .kpi .sub   { font-size:.78rem; color:#6b7280; }
  .route-card { background:#ffffff; border:1px solid #e5e7eb; border-left:4px solid #ef4444;
                border-radius:12px; padding:.75rem 1rem; margin:.4rem 0; font-size:.9rem; color:#111827; }
  .route-card.high { border-left-color:#f97316; }
  .route-path { font-family: ui-monospace, Menlo, monospace; font-size:.82rem; color:#334155;
                background:#f1f5f9; padding:.1rem .4rem; border-radius:6px; }
  .legend-row { display:flex; flex-wrap:wrap; gap:.9rem; font-size:.82rem; color:#334155; margin:.3rem 0 .2rem; }
  .legend-row span.sw { display:inline-block; width:12px; height:12px; border-radius:3px;
                        margin-right:.35rem; vertical-align:-1px; opacity:.85; }
  .story { background:#fff7ed; border:1px solid #fed7aa; color:#7c2d12; border-radius:12px;
           padding:.7rem 1rem; font-size:.86rem; margin:.6rem 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="map-hero">
  <div class="hero-tag"><span class="live-dot"></span>Site map</div>
  <h1>Every zone on real terrain</h1>
  <p>Zones are drawn on satellite imagery, so each one's ground area comes from the map,
  not a guess. Crowd density (people per m²) sets its risk colour, and arrows show where to
  move people along walkable routes.</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Choose the site and the numbers to show
# ---------------------------------------------------------------------------
DEMO = load_site()
has_custom = "custom_site" in st.session_state
has_analysis = bool(st.session_state.crowd_data)

c1, c2, c3 = st.columns([3, 3, 3])
with c1:
    site_choice = st.radio(
        "Site", ["demo", "custom", "draw"], horizontal=True,
        format_func={"demo": DEMO["short"], "custom": "My site",
                     "draw": "Draw a new site"}.get,
        index=1 if has_custom else 0,
        help="The demo is the Maha Kumbh bathing area at the Sangam in Prayagraj.")
with c2:
    preset_name = st.selectbox("Density standard", list(FRUIN_PRESETS),
                               index=list(FRUIN_PRESETS).index("Crowded events / concerts"),
                               help="People per m² at which each risk level starts (Fruin).")
with c3:
    sources = (["scenario"] if site_choice == "demo" else []) + (["analysis"] if has_analysis else [])
    source = st.radio(
        "People counts", sources or ["none"], horizontal=True,
        format_func={"scenario": "Simulated surge", "analysis": "My latest analysis",
                     "none": "No counts yet"}.get)

if site_choice == "custom" and not has_custom:
    st.info("No saved site yet. Choose **Draw a new site**, draw your zones, then save them.")
    site_choice = "draw"

preset = FRUIN_PRESETS[preset_name]
RISK_ORDER = ["Safe", "Moderate", "High Risk", "Critical"]


def base_map(centre, zoom):
    m = folium.Map(location=[centre[1], centre[0]], zoom_start=zoom, tiles=None,
                   control_scale=True, max_zoom=20)
    folium.TileLayer("Esri.WorldImagery", name="Satellite", max_zoom=20,
                     max_native_zoom=19).add_to(m)
    folium.TileLayer("OpenStreetMap.Mapnik", name="Streets", max_zoom=20,
                     max_native_zoom=19).add_to(m)
    folium.TileLayer("Esri.WorldTopoMap", name="Terrain", max_zoom=20,
                     max_native_zoom=19).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    return m


# ---------------------------------------------------------------------------
# Draw mode: the user outlines zones and assigns each one a letter
# ---------------------------------------------------------------------------
if site_choice == "draw":
    st.markdown("#### Draw your zones")
    st.caption("Use the polygon or rectangle tool on the left of the map to outline up to five "
               "zones (A to E). Search the map by panning and zooming to your venue first. "
               "Zones that touch or lie within 30 m of each other count as connected.")
    start = st.session_state.get("custom_site", DEMO)
    m = base_map(start["centre"], start.get("zoom", 16))
    Draw(export=False, position="topleft",
         draw_options={"polyline": False, "circle": False, "circlemarker": False,
                       "marker": False,
                       "polygon": {"shapeOptions": {"color": "#38bdf8"}},
                       "rectangle": {"shapeOptions": {"color": "#38bdf8"}}},
         edit_options={"edit": True, "remove": True}).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    out = st_folium(m, height=560, use_container_width=True,
                    returned_objects=["all_drawings"], key="draw_map")
    shapes = [f for f in (out or {}).get("all_drawings") or []
              if (f.get("geometry") or {}).get("type") == "Polygon"]

    if not shapes:
        st.info("Nothing drawn yet.")
        st.stop()

    st.markdown(f"**{len(shapes)} shape(s) drawn.** Give each one a zone letter and a name.")
    letters, names = {}, {}
    for i, f in enumerate(shapes[:5]):
        a, b, c = st.columns([1, 3, 2])
        letters[i] = a.selectbox(f"Shape {i + 1}", SEGMENTS, index=i, key=f"draw_letter_{i}")
        names[letters[i]] = b.text_input("Name", key=f"draw_name_{i}",
                                         placeholder="e.g. Platform 1, North gate")
        c.metric("Area", f"{ring_area_m2(f['geometry']['coordinates'][0]):,.0f} m²")
    if len(set(letters.values())) < len(letters):
        st.warning("Two shapes share a letter; give each its own.")
    elif st.button("Save these zones", type="primary", width="stretch"):
        st.session_state.custom_site = site_from_drawings(shapes, names, letters)
        st.success("Saved. Choose **My site** above to see it with live risk.")
    st.stop()


# ---------------------------------------------------------------------------
# View mode
# ---------------------------------------------------------------------------
site = DEMO if site_choice == "demo" else st.session_state.custom_site
if source == "scenario":
    counts = scenario_counts(site)
elif source == "analysis":
    counts = {z: d["count"] for z, d in st.session_state.crowd_data.items() if z in site["zones"]}
else:
    counts = {}
view = assess(site, counts, preset)
zones, plans = view["zones"], view["plans"]

if site_choice == "demo":
    st.markdown(f"<div class='story'><b>Why this site.</b> {html.escape(DEMO['story'])}</div>",
                unsafe_allow_html=True)

# KPI strip
counted = [r for r in zones.values() if r["count"] is not None]
total_area = sum(r["area_m2"] for r in zones.values())
peak = max(counted, key=lambda r: r["per_m2"]) if counted else None
at_risk = [z for z, r in zones.items() if r["risk"] in ("High Risk", "Critical")]
k = st.columns(4)
kpis = [
    ("People in zones", f"{sum(r['count'] for r in counted):,}" if counted else "–",
     f"{len(counted)} of {len(zones)} zones counted"),
    ("Area monitored", f"{total_area / 10_000:,.1f} ha", f"{total_area:,.0f} m² from the map"),
    ("Peak density", f"{peak['per_m2']:.1f} /m²" if peak else "–",
     html.escape(peak["name"]) if peak else "no counts yet"),
    ("Zones at risk", f"{len(at_risk)}", ", ".join(at_risk) or "none"),
]
for col, (label, value, sub) in zip(k, kpis):
    col.markdown(f"<div class='kpi'><div class='label'>{label}</div>"
                 f"<div class='value'>{value}</div><div class='sub'>{sub}</div></div>",
                 unsafe_allow_html=True)

st.markdown(
    "<div class='legend-row'>" + "".join(
        f"<span><span class='sw' style='background:{RISK_COLORS[r]}'></span>{r} "
        f"(from {preset[{'Moderate': 'moderate', 'High Risk': 'high', 'Critical': 'critical'}[r]]}/m²)"
        f"</span>" if r != "Safe" else
        f"<span><span class='sw' style='background:{RISK_COLORS[r]}'></span>Safe "
        f"(under {preset['moderate']}/m²)</span>"
        for r in RISK_ORDER) +
    "<span><span class='sw' style='background:#94a3b8'></span>Not counted</span></div>",
    unsafe_allow_html=True)

m = base_map(site["centre"], site.get("zoom", 16))
m.get_root().header.add_child(folium.Element("""
<style>
  .zone-pin { display:flex; align-items:center; gap:6px; white-space:nowrap;
              font: 700 12px/1 Inter, system-ui, sans-serif; color:#0f172a;
              background:rgba(255,255,255,.94); border-radius:999px; padding:5px 9px 5px 5px;
              box-shadow:0 2px 8px rgba(0,0,0,.35); transform: translate(-50%, -50%); }
  .zone-pin b { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px;
                border-radius:50%; color:#fff; font-size:11px; }
  .zone-pin small { font-weight:600; color:#475569; }
  .pulse-ring { position:absolute; left:50%; top:50%; width:22px; height:22px; margin:-11px 0 0 -11px;
                border-radius:50%; border:3px solid currentColor; animation: ring 1.6s ease-out infinite; }
  @keyframes ring { 0% {transform:scale(.6); opacity:.9} 100% {transform:scale(3.2); opacity:0} }
</style>
"""))

zone_layer = folium.FeatureGroup(name="Zones").add_to(m)
for z, r in zones.items():
    colour = RISK_COLORS.get(r["risk"], "#94a3b8")
    critical = r["risk"] == "Critical"
    density = "not counted" if r["count"] is None else f"{r['per_m2']:.2f} people/m²"
    tip = (f"<b>Zone {z}: {html.escape(r['name'])}</b><br>"
           f"Area {r['area_m2']:,.0f} m²<br>"
           + ("" if r["count"] is None else f"People {r['count']:,}<br>")
           + f"Density {density}<br>Risk <b style='color:{colour}'>{r['risk'] or '–'}</b>")
    folium.Polygon(
        locations=[[lat, lon] for lon, lat in r["ring"]],
        color=colour, weight=3 if critical else 2, fill=True, fill_color=colour,
        fill_opacity=0.42 if critical else 0.3, tooltip=folium.Tooltip(tip, sticky=True),
    ).add_to(zone_layer)

    lon, lat = r["centre"]
    pulse = (f"<span class='pulse-ring' style='color:{colour}'></span>"
             if r["risk"] in ("Critical", "High Risk") else "")
    sub = "" if r["count"] is None else f"<small>{r['per_m2']:.1f}/m²</small>"
    folium.Marker(
        [lat, lon],
        icon=folium.DivIcon(
            html=f"<div style='position:relative'>{pulse}<div class='zone-pin'>"
                 f"<b style='background:{colour}'>{z}</b>{html.escape(r['name'])} {sub}</div></div>",
            icon_size=(0, 0)),
    ).add_to(zone_layer)

route_layer = folium.FeatureGroup(name="Evacuation routes").add_to(m)
for p in plans:
    if len(p["path"]) < 2:
        continue
    points = [[zones[z]["centre"][1], zones[z]["centre"][0]] for z in p["path"]]
    AntPath(points, color="#ffffff", pulse_color=RISK_COLORS[p["risk"]], weight=6,
            delay=700, dash_array=[14, 26], opacity=0.95,
            tooltip=f"Move ~{p['move']:,} people: {' → '.join(p['path'])}").add_to(route_layer)

MiniMap(toggle_display=True, position="bottomright", zoom_level_offset=-5).add_to(m)
folium.LayerControl(collapsed=True).add_to(m)
st_folium(m, height=600, use_container_width=True, returned_objects=[], key="site_map")

if site_choice == "demo":
    st.caption(f"{DEMO['disclaimer']} "
               + (DEMO["scenario_note"] if source == "scenario" else "")
               + " Satellite imagery © Esri; map data © OpenStreetMap contributors.")
else:
    st.caption("Satellite imagery © Esri; map data © OpenStreetMap contributors.")

# ---------------------------------------------------------------------------
# Evacuation plan and zone table
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.markdown("#### Evacuation plan")
    if not counted:
        st.caption("Add counts on the Upload page, or pick the simulated surge, to see a plan.")
    elif not plans:
        st.success("No zone is at High Risk or Critical. No one needs to move.")
    for p in plans:
        src = zones[p["high"]]
        if p["target"]:
            via = " → ".join(p["path"])
            body = (f"Move <b>~{p['move']:,}</b> people from <b>{p['high']}</b> "
                    f"({html.escape(src['name'])}) to <b>{p['target']}</b> "
                    f"({html.escape(zones[p['target']]['name'])}) "
                    f"along <span class='route-path'>{via}</span>")
        else:
            body = (f"<b>{p['high']}</b> ({html.escape(src['name'])}) needs ~{p['move']:,} people out, "
                    f"but no reachable zone has room: hold entries and call reinforcements")
        css = "" if p["risk"] == "Critical" else " high"
        st.markdown(f"<div class='route-card{css}'><b style='color:{RISK_COLORS[p['risk']]}'>"
                    f"{p['risk'].upper()}</b> · {body}</div>", unsafe_allow_html=True)

with right:
    st.markdown("#### Zones")
    st.dataframe(
        [{"Zone": z, "Name": r["name"], "Area (m²)": round(r["area_m2"]),
          "People": r["count"], "Per m²": None if r["per_m2"] is None else round(r["per_m2"], 2),
          "Risk": r["risk"] or "–", "Connected to": ", ".join(view["adjacency"][z]) or "–"}
         for z, r in zones.items()],
        hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# Send the mapped areas to the rest of the app
# ---------------------------------------------------------------------------
st.markdown("#### Use this map in the app")
st.caption("Sets each zone's area and risk limits on the Settings page from the map, and tells "
           "the Analysis page which zones connect, so it only plans moves people can walk.")
if st.button("Apply map areas and routes to the app", width="stretch"):
    for z, r in zones.items():
        st.session_state.seg_areas[z] = round(r["area_m2"])
        st.session_state.thresholds[z] = thresholds_from_area(r["area_m2"], preset)
    st.session_state.zone_adjacency = view["adjacency"]
    st.session_state.zone_names = {z: r["name"] for z, r in zones.items()}
    st.success(f"Applied areas and {preset_name.lower()} limits for zones "
               f"{', '.join(zones)}, plus the walking routes between them.")
