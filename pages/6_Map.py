"""Site Map: every zone on real satellite terrain, coloured by live risk, with evacuation routes."""

import html
import json

import folium
import streamlit as st
from folium.plugins import AntPath, Draw, Fullscreen, MiniMap, PolyLineTextPath
from streamlit_folium import st_folium

from crowdshield.geo import ring_area_m2
from crowdshield.risk import thresholds_from_area
from crowdshield.sitemap import (assess, list_sites, scenario_counts, site_from_drawings,
                                 timeline, to_geojson)
from shared_state import FRUIN_PRESETS, GLOBAL_CSS, RISK_COLORS, SEGMENTS, init_state
from ui import compact, next_step, page_header

st.set_page_config(page_title="Site Map • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()


st.markdown("""
<style>
  .story { border-left:3px solid #f59e0b; background:#fffbeb; color:#78350f; border-radius:0 10px 10px 0;
           padding:.6rem .9rem; font-size:.85rem; margin:.2rem 0 1rem; }
  .zone-card { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:.65rem .75rem;
               margin-bottom:.5rem; }
  .zone-card .top { display:flex; align-items:center; gap:.55rem; }
  .zone-card .badge { width:24px; height:24px; border-radius:7px; color:#fff; font-weight:800; font-size:.78rem;
                      display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .zone-card .name { font-weight:700; font-size:.84rem; color:#0f172a; line-height:1.2; flex:1; }
  .zone-card .risk { font-size:.68rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
  .zone-card .meta { display:flex; justify-content:space-between; font-size:.74rem; color:#64748b;
                     margin:.4rem 0 .3rem; font-variant-numeric: tabular-nums; }
  .bar { position:relative; height:6px; border-radius:99px; background:#f1f5f9; overflow:visible; }
  .bar .fill { position:absolute; left:0; top:0; bottom:0; border-radius:99px; }
  .bar .tick { position:absolute; top:-3px; width:2px; height:12px; background:#cbd5e1; border-radius:1px; }
  .route-card { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:.75rem .9rem;
                margin:.45rem 0; font-size:.88rem; color:#0f172a; display:flex; gap:.75rem; align-items:flex-start; }
  .route-card .pill { font-size:.66rem; font-weight:800; letter-spacing:.06em; padding:.2rem .5rem; border-radius:6px;
                      color:#fff; white-space:nowrap; margin-top:.1rem; }
  .route-path { font-family: ui-monospace, Menlo, monospace; font-size:.8rem; color:#0f172a;
                background:#f1f5f9; padding:.08rem .4rem; border-radius:6px; }
  .panel-title { font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
                 color:#64748b; margin:.1rem 0 .5rem; }
</style>
""", unsafe_allow_html=True)


RISK_ORDER = ["Safe", "Moderate", "High Risk", "Critical"]
GREY = "#94a3b8"
SITES = {s["short"]: s for s in list_sites()}

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
page_header("Site map", "Each zone of a real site on a satellite map, how crowded it is in people per m², and the "
            "walking routes to move people along. Start with the Kumbh demo and play the surge forward.",
            "Plan the response", live=True)

SIM, MINE = "An example surge (made-up numbers)", "My counted photos"
BEST, NEAREST = "Best overall", "Nearest zone first"
site_options = list(SITES) + (["My site"] if "custom_site" in st.session_state else []) + ["Draw a new site"]
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([5, 3, 3, 3])
    with c1:
        site_choice = st.selectbox("Site", site_options,
                                   help="The demo sites are real places; their zones are drawn for illustration. "
                                        "Choose Draw a new site to outline your own.")
    is_draw = site_choice == "Draw a new site"
    is_demo = site_choice in SITES
    has_analysis = bool(st.session_state.crowd_data)
    with c2:
        sources = ([SIM] if is_demo else []) + ([MINE] if has_analysis else [])
        source = st.selectbox("Crowd numbers", sources or ["Nothing counted yet"], disabled=is_draw,
                              help="Use the made-up example to see how the map works, or the people you counted "
                                   "in photos (zone A on the photo page is zone A here).")
    with c3:
        preset_name = st.selectbox("Safety limits for", list(FRUIN_PRESETS),
                                   index=list(FRUIN_PRESETS).index("Crowded events / concerts"),
                                   help="How many people per m² count as crowded, dangerous or critical. Stricter "
                                        "for corridors and gates, looser for events where people stand close "
                                        "(after Fruin's crowd-safety levels).")
    with c4:
        planner_name = st.selectbox(
            "How to plan moves", [BEST, NEAREST],
            help="Best overall looks at the whole site at once: it finds room for as many people as possible, "
                 "along the shortest walks. Nearest zone first sends each crowded zone to its nearest zone with "
                 "room, one at a time, and can leave people with nowhere to go.")
    step = None
    if is_demo and source == SIM:
        steps = timeline(SITES[site_choice])
        label = st.select_slider("Time in the example", [s["label"] for s in steps],
                                 value=next(s["label"] for s in steps if s["factor"] == 1.0),
                                 help="Move it to play the surge forward: watch zones fill up and routes appear.")
        step = next(s for s in steps if s["label"] == label)

preset = FRUIN_PRESETS[preset_name]


def base_map(centre, zoom):
    m = folium.Map(location=[centre[1], centre[0]], zoom_start=zoom, tiles=None,
                   control_scale=True, max_zoom=20, prefer_canvas=False)
    folium.TileLayer("Esri.WorldImagery", name="Satellite", max_zoom=20, max_native_zoom=19).add_to(m)
    folium.TileLayer("OpenStreetMap.Mapnik", name="Streets", max_zoom=20, max_native_zoom=19,
                     show=False).add_to(m)
    folium.TileLayer("Esri.WorldTopoMap", name="Terrain", max_zoom=20, max_native_zoom=19,
                     show=False).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
              "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Place labels", overlay=True, control=True, max_zoom=20,
        max_native_zoom=19, opacity=0.9).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    m.get_root().header.add_child(folium.Element("""
<style>
  .leaflet-container { font-family: Inter, system-ui, sans-serif; background:#0b1220; }
  .leaflet-control-attribution { font-size:9px !important; background:rgba(255,255,255,.7) !important;
                                 max-width:60%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .leaflet-control-attribution:hover { white-space:normal; }
  .leaflet-tooltip.zone-tip { border:0; border-radius:10px; box-shadow:0 8px 24px rgba(2,6,23,.25);
                              padding:8px 10px; font-size:12px; color:#0f172a; }
  .pin { position:relative; transform:translate(-50%,-50%); display:flex; align-items:center; gap:5px; }
  .pin .b { width:26px; height:26px; border-radius:8px; color:#fff; font:800 12px/26px Inter, sans-serif;
            text-align:center; border:2px solid #fff; box-shadow:0 2px 10px rgba(0,0,0,.45); }
  .pin .d { background:rgba(15,23,42,.82); color:#fff; font:700 11px/1 Inter, sans-serif; padding:4px 6px;
            border-radius:6px; white-space:nowrap; }
  .pin .n { background:rgba(255,255,255,.95); color:#0f172a; font:700 11px/1 Inter, sans-serif; padding:4px 7px;
            border-radius:6px; white-space:nowrap; box-shadow:0 1px 6px rgba(0,0,0,.3); }
  .ring { position:absolute; left:13px; top:13px; width:26px; height:26px; margin:-13px 0 0 -13px;
          border-radius:50%; border:3px solid currentColor; animation: ring 1.6s ease-out infinite; }
  @keyframes ring { 0% {transform:scale(.7); opacity:.95} 100% {transform:scale(3.4); opacity:0} }
  .map-legend { position:absolute; left:10px; bottom:26px; z-index:999; background:rgba(15,23,42,.86);
                color:#e2e8f0; border-radius:10px; padding:8px 10px; font:600 11px/1.5 Inter, sans-serif;
                box-shadow:0 4px 18px rgba(0,0,0,.35); }
  .map-legend i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px;
                  vertical-align:-1px; }
</style>"""))
    return m


# ---------------------------------------------------------------------------
# Draw mode: the user outlines zones and assigns each one a letter
# ---------------------------------------------------------------------------
if is_draw:
    st.markdown("#### Draw your zones")
    st.caption("Pan to your venue, then outline up to five zones with the polygon or rectangle "
               "tool on the left of the map. Zones that touch, or lie within 30 m, count as connected.")
    start = st.session_state.get("custom_site", next(iter(SITES.values())))
    m = base_map(start["centre"], start.get("zoom", 16))
    Draw(export=False, position="topleft",
         draw_options={"polyline": False, "circle": False, "circlemarker": False, "marker": False,
                       "polygon": {"shapeOptions": {"color": "#38bdf8"}},
                       "rectangle": {"shapeOptions": {"color": "#38bdf8"}}},
         edit_options={"edit": True, "remove": True}).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    out = st_folium(m, height=580, use_container_width=True,
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
# Assess the site
# ---------------------------------------------------------------------------
site = SITES[site_choice] if is_demo else st.session_state.custom_site
if source == SIM:
    counts = scenario_counts(site, step["factor"])
elif source == MINE:
    counts = {z: d["count"] for z, d in st.session_state.crowd_data.items() if z in site["zones"]}
else:
    counts = {}
planner = "optimal" if planner_name == BEST else "simple"
if source == MINE and not st.session_state.get("limits_source", "").startswith(f"each zone's area on the {site_choice}"):
    st.info("This map judges your counts by people per m² of each zone. The photo and evacuation-plan pages still "
            f"use limits from {st.session_state.get('limits_source')}, so a zone can look different there. To use "
            "this map everywhere, press Apply map areas and routes in the Export and apply tab below.")
view = assess(site, counts, preset, planner=planner)
zones, plans = view["zones"], view["plans"]

if is_demo:
    st.markdown(f"<div class='story'><b>Why this place.</b> {html.escape(site['story'])}</div>",
                unsafe_allow_html=True)

counted = [r for r in zones.values() if r["count"] is not None]
total_area = sum(r["area_m2"] for r in zones.values())
peak = max(counted, key=lambda r: r["per_m2"]) if counted else None
at_risk = [z for z, r in zones.items() if r["risk"] in ("High Risk", "Critical")]
moving = sum(p["move"] for p in plans if p["target"])
chip = ("<span class='pill warn'>Simulated counts</span> <span class='pill neutral'>Illustrative zones, "
        "not the official layout</span>" if source == SIM and is_demo
        else "<span class='pill warn'>Simulated counts</span>" if source == SIM
        else "<span class='pill brand'>Counts from your photos</span> <span class='pill neutral'>Illustrative "
             "zones, not the official layout</span>" if counted and is_demo
        else "<span class='pill brand'>Counts from your photos</span>" if counted else "")
kpis = [
    ("People in zones", compact(sum(r["count"] for r in counted)) if counted else "–",
     f"{len(counted)} of {len(zones)} zones counted"),
    ("Area monitored", f"{total_area / 10_000:,.1f} ha", f"{total_area:,.0f} m² measured on the map"),
    ("Peak density", f"{peak['per_m2']:.1f} /m²" if peak else "–",
     html.escape(peak["name"]) if peak else "no counts yet"),
    ("Zones at risk", f"{len(at_risk)} / {len(zones)}", ", ".join(at_risk) or "none"),
    ("People to move", compact(moving) if plans else "0",
     f"{len(plans)} route(s) planned" if plans else "no moves needed"),
]
cols = st.columns(len(kpis))
for col, (label, value, sub) in zip(cols, kpis):
    col.markdown(f"<div class='kpi'><div class='label'>{label}</div>"
                 f"<div class='value'>{value}</div><div class='sub'>{sub}</div></div>",
                 unsafe_allow_html=True)
st.markdown(f"<div style='margin:.6rem 0 .2rem'>{chip}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Map + zone panel
# ---------------------------------------------------------------------------
map_col, panel_col = st.columns([7, 3], gap="medium")
with map_col:
    show_names = st.toggle("Zone names on the map", value=False)
    m = base_map(site["centre"], site.get("zoom", 16))
    zone_layer = folium.FeatureGroup(name="Zones").add_to(m)
    for z, r in zones.items():
        colour = RISK_COLORS.get(r["risk"], GREY)
        hot = r["risk"] in ("High Risk", "Critical")
        density = "not counted" if r["count"] is None else f"{r['per_m2']:.2f} people/m²"
        tip = (f"<div style='font-weight:800;margin-bottom:4px'>Zone {z} · {html.escape(r['name'])}</div>"
               f"<div>Area <b>{r['area_m2']:,.0f} m²</b></div>"
               + ("" if r["count"] is None else f"<div>People <b>{r['count']:,}</b></div>")
               + f"<div>Density <b>{density}</b></div>"
               f"<div>Risk <b style='color:{colour}'>{r['risk'] or '–'}</b></div>"
               f"<div style='color:#64748b'>Connects to {', '.join(view['adjacency'][z]) or 'nothing'}</div>")
        style = {"color": colour, "weight": 3 if hot else 2, "fillColor": colour,
                 "fillOpacity": 0.4 if hot else 0.28}
        folium.GeoJson(
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [r["ring"]]}},
            style_function=lambda _, s=style: s,
            highlight_function=lambda _, c=colour: {"weight": 4, "fillOpacity": 0.55, "color": "#ffffff",
                                                    "fillColor": c},
            tooltip=folium.Tooltip(tip, sticky=True, class_name="zone-tip"),
        ).add_to(zone_layer)

        lon, lat = r["centre"]
        ring = f"<span class='ring' style='color:{colour}'></span>" if hot else ""
        density_tag = "" if r["count"] is None else f"<span class='d'>{r['per_m2']:.1f}/m²</span>"
        name_tag = f"<span class='n'>{html.escape(r['name'])}</span>" if show_names else ""
        folium.Marker([lat, lon], icon=folium.DivIcon(
            html=f"<div class='pin'>{ring}<span class='b' style='background:{colour}'>{z}</span>"
                 f"{density_tag}{name_tag}</div>", icon_size=(0, 0))).add_to(zone_layer)

    route_layer = folium.FeatureGroup(name="Evacuation routes").add_to(m)
    for p in plans:
        if len(p["path"]) < 2:
            continue
        points = [[zones[z]["centre"][1], zones[z]["centre"][0]] for z in p["path"]]
        tip = f"Move ~{p['move']:,} people: {' → '.join(p['path'])}"
        AntPath(points, color="#ffffff", pulse_color=RISK_COLORS[p["risk"]], weight=6, delay=650,
                dash_array=[14, 26], opacity=0.95, tooltip=tip).add_to(route_layer)
        arrows = folium.PolyLine(points, weight=0, opacity=0).add_to(route_layer)
        PolyLineTextPath(arrows, "      ➤      ", repeat=True, offset=5,
                         attributes={"fill": "#ffffff", "font-size": "15", "font-weight": "bold"}
                         ).add_to(route_layer)

    legend = "".join(
        f"<div><i style='background:{RISK_COLORS[k]}'></i>{k}"
        f"{'' if k == 'Safe' else ' ≥ ' + str(preset[{'Moderate': 'moderate', 'High Risk': 'high', 'Critical': 'critical'}[k]]) + '/m²'}"
        f"{' < ' + str(preset['moderate']) + '/m²' if k == 'Safe' else ''}</div>"
        for k in RISK_ORDER)
    m.get_root().html.add_child(folium.Element(
        f"<div class='map-legend'>{legend}<div><i style='background:{GREY}'></i>Not counted</div></div>"))
    MiniMap(toggle_display=True, position="bottomright", zoom_level_offset=-5).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, height=640, use_container_width=True, returned_objects=[], key="site_map")

with panel_col:
    st.markdown("<div class='panel-title'>Zones</div>", unsafe_allow_html=True)
    scale = preset["critical"] * 1.25
    for z, r in sorted(zones.items(), key=lambda kv: -(kv[1]["per_m2"] or -1)):
        colour = RISK_COLORS.get(r["risk"], GREY)
        if r["count"] is None:
            meta = f"<span>{r['area_m2']:,.0f} m²</span><span>not counted</span>"
            fill = ""
        else:
            meta = (f"<span>{compact(r['count'])} people</span>"
                    f"<span><b style='color:#0f172a'>{r['per_m2']:.2f}</b> /m²</span>")
            fill = (f"<div class='fill' style='width:{min(r['per_m2'] / scale, 1) * 100:.1f}%;"
                    f"background:{colour}'></div>")
        ticks = "".join(f"<div class='tick' style='left:{preset[k] / scale * 100:.1f}%'></div>"
                        for k in ("moderate", "high", "critical"))
        st.markdown(
            f"<div class='zone-card'><div class='top'><div class='badge' style='background:{colour}'>{z}</div>"
            f"<div class='name'>{html.escape(r['name'])}</div>"
            f"<div class='risk' style='color:{colour}'>{r['risk'] or ''}</div></div>"
            f"<div class='meta'>{meta}</div><div class='bar'>{fill}{ticks}</div></div>",
            unsafe_allow_html=True)
    st.caption("Bar: density against the Moderate, High and Critical marks.")

if is_demo:
    st.caption(f"{site['disclaimer']} "
               + (site["scenario_note"] if source == SIM else "")
               + " Imagery © Esri, Maxar; map data © OpenStreetMap contributors.")
else:
    st.caption("Imagery © Esri, Maxar; map data © OpenStreetMap contributors.")

# ---------------------------------------------------------------------------
# Plan, table, export
# ---------------------------------------------------------------------------
tab_plan, tab_table, tab_use = st.tabs(["Evacuation plan", "Zone table", "Export and apply"])
with tab_plan:
    if not counted:
        st.caption("Count people in a photo of each zone, or pick the simulated surge, to see a plan.")
    elif not plans:
        st.success("No zone is at High Risk or Critical. No one needs to move.")
    else:
        from crowdshield.risk import plan_summary

        counted_rows = {z: r for z, r in zones.items() if r["count"] is not None}
        both = {name: plan_summary(assess(site, counts, preset, planner=key)["plans"],
                                   view["distance_m"], counted_rows)
                for name, key in ((NEAREST, "simple"), (BEST, "optimal"))}
        st.dataframe(
            [{"Way of planning": name, "People moved": f"{r['moved']:,}",
              "Left with nowhere to go": f"{r['unresolved']:,}",
              "Total walking (person-metres)": f"{r['people_metres']:,.0f}"} for name, r in both.items()],
            hide_index=True, width="stretch")
        if both[NEAREST]["unresolved"] > both[BEST]["unresolved"]:
            st.caption("Nearest zone first gives up on people once the nearest zone is full. Best overall finds "
                       "room for them in other zones, even ones reached through a busy zone.")
        else:
            st.caption("Total walking is every person's walk added up: lower is easier to carry out.")
    for p in plans:
        src = zones[p["high"]]
        if p["target"]:
            body = (f"Move <b>~{p['move']:,}</b> people from <b>{p['high']}</b> "
                    f"({html.escape(src['name'])}) to <b>{p['target']}</b> "
                    f"({html.escape(zones[p['target']]['name'])}) along "
                    f"<span class='route-path'>{' → '.join(p['path'])}</span>. "
                    f"Close entries to {p['high']}; open its exits towards {p['path'][1]}.")
        else:
            body = (f"<b>{p['high']}</b> ({html.escape(src['name'])}) needs ~{p['move']:,} people out, "
                    f"but no connected zone has room. Hold all entries and call reinforcements.")
        st.markdown(f"<div class='route-card'><span class='pill' style='background:{RISK_COLORS[p['risk']]}'>"
                    f"{p['risk'].upper()}</span><div>{body}</div></div>", unsafe_allow_html=True)

with tab_table:
    st.dataframe(
        [{"Zone": z, "Name": r["name"], "Area (m²)": round(r["area_m2"]),
          "People": r["count"], "Per m²": None if r["per_m2"] is None else round(r["per_m2"], 2),
          "Risk": r["risk"] or "–", "Connected to": ", ".join(view["adjacency"][z]) or "–"}
         for z, r in zones.items()],
        hide_index=True, width="stretch")

with tab_use:
    a, b = st.columns(2)
    with a:
        st.markdown("**Download**")
        st.download_button("Zones as GeoJSON (for QGIS, Google Earth)",
                           json.dumps(to_geojson(view), indent=1),
                           file_name="crowd_shield_zones.geojson", mime="application/geo+json",
                           width="stretch")
        rows = ["from,to,path,people"] + [
            f"{p['high']},{p['target'] or ''},{'>'.join(p['path'])},{p['move']}" for p in plans]
        st.download_button("Evacuation plan (CSV)", "\n".join(rows) + "\n",
                           file_name="crowd_shield_evacuation_plan.csv", mime="text/csv",
                           width="stretch")
    with b:
        st.markdown("**Use this map in the app**")
        st.caption("Sets each zone's area, name and risk limits from the map, and tells the evacuation plan "
                   "which zones connect, so it only plans walkable moves.")
        if st.button("Apply map areas and routes", width="stretch"):
            for z, r in zones.items():
                st.session_state.seg_areas[z] = round(r["area_m2"])
                st.session_state.thresholds[z] = thresholds_from_area(r["area_m2"], preset)
            st.session_state.zone_adjacency = view["adjacency"]
            st.session_state.zone_names = {z: r["name"] for z, r in zones.items()}
            st.session_state.limits_source = (f"each zone's area on the {site_choice} map, at the "
                                              f"\"{preset_name}\" safety limits")
            st.success(f"Applied areas and {preset_name.lower()} limits for zones "
                       f"{', '.join(zones)}, plus the routes between them.")

next_step("Put your own numbers on the map: count the people in a photo of each zone, then pick My counted "
          "photos above.", "pages/2_Upload.py", "Count people in a photo", "/Upload")
