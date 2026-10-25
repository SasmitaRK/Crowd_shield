"""Evacuation plan and alerts: each zone's risk from the latest count, where to move people, and alerts."""

import csv
import html
import io

import cv2
import streamlit as st

from crowdshield import notify
from crowdshield.config import COUNTER_LABELS
from crowdshield.risk import plan_optimal
from detection import risk_level
from emailer import build_critical_email, build_receiving_email, email_configured, send_email
from shared_state import GLOBAL_CSS, RISK_COLORS, SEGMENTS, get_seg_thresholds, init_state, zone_label
from ui import compact, kpi_cards, nav_link, page_header, risk_pill, section

st.set_page_config(page_title="Evacuation plan and alerts • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Evacuation plan and alerts", "How crowded each zone is, where to move people from the crowded ones, "
            "and one button to tell your team.", "Plan the response")

data = st.session_state.crowd_data
agents = st.session_state.agents

if not data:
    st.info("Nothing counted yet. Count the people in a photo of each zone first; the plan appears here.")
    nav_link("pages/2_Upload.py", "Count people in a photo", ":material/photo_camera:", "/Upload")
    st.stop()

st.markdown("""
<style>
  .zbar { position:relative; height:8px; border-radius:99px; background:#f1f5f9; margin:.5rem 0 .3rem; }
  .zbar .fill { position:absolute; left:0; top:0; bottom:0; border-radius:99px; }
  .zbar .tick { position:absolute; top:-3px; width:2px; height:14px; background:#cbd5e1; border-radius:1px; }
</style>
""", unsafe_allow_html=True)

seg_info = {}
for seg in SEGMENTS:
    if seg in data:
        t = get_seg_thresholds(seg)
        seg_info[seg] = {"count": data[seg]["count"], "image_count": data[seg]["image_count"],
                         "counter": data[seg].get("counter"), "risk": risk_level(data[seg]["count"], t),
                         "thresholds": t}

adjacency = st.session_state.get("zone_adjacency")
pairings = plan_optimal(seg_info, adjacency=adjacency)
at_risk = [s for s, i in seg_info.items() if i["risk"] in ("High Risk", "Critical")]
placed = sum(p["move"] for p in pairings if p["target"])
stuck = sum(p["move"] for p in pairings if not p["target"])
channels = notify.ready_channels()

kpi_cards([
    ("People counted", compact(sum(i["count"] for i in seg_info.values())), f"in {len(seg_info)} zone(s)"),
    ("Zones at risk", f"{len(at_risk)} / {len(seg_info)}", ", ".join(at_risk) or "none"),
    ("People to move", compact(placed), "into zones with room" if placed else "no moves needed"),
    ("Nowhere to go", compact(stuck), "need more space or staff" if stuck else "everyone placed"),
    ("Alerts", "Ready" if channels else "Off", " and ".join(channels) if channels else "set up in Team and alerts"),
], accents=["#0d9488", RISK_COLORS["Critical"] if at_risk else "#10b981", "#2a78d6",
            RISK_COLORS["Critical"] if stuck else "#10b981", "#10b981" if channels else "#94a3b8"])

# ── Zones ──────────────────────────────────────────────────────────────────
section("Zones", "Each zone's count against its limits (the marks on the bar are Moderate, High Risk and "
        "Critical). Limits come from Settings, or from the Site map once you apply one.")
cols = st.columns(len(seg_info))
for col, (seg, info) in zip(cols, seg_info.items()):
    t, count, colour = info["thresholds"], info["count"], RISK_COLORS[info["risk"]]
    scale = t["critical"] * 1.25
    ticks = "".join(f"<div class='tick' style='left:{t[k] / scale * 100:.1f}%'></div>"
                    for k in ("moderate", "high", "critical"))
    room = t["critical"] - count
    with col, st.container(border=True):
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;gap:.4rem'>"
            f"<b style='font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"
            f"{html.escape(zone_label(seg))}</b>{risk_pill(info['risk'])}</div>"
            f"<div style='font-size:1.7rem;font-weight:800;font-variant-numeric:tabular-nums;margin-top:.3rem'>"
            f"{count:,}<span style='font-size:.8rem;color:#64748b;font-weight:600'> people</span></div>"
            f"<div class='zbar'><div class='fill' style='width:{min(count / scale, 1) * 100:.1f}%;"
            f"background:{colour}'></div>{ticks}</div>"
            f"<div style='font-size:.76rem;color:#64748b'>"
            + (f"{room:,} more before Critical" if room > 0 else f"<b style='color:{colour}'>{-room:,} over "
               "Critical</b>")
            + f" · limits {t['moderate']} / {t['high']} / {t['critical']}</div>",
            unsafe_allow_html=True)
        per_img = data[seg].get("per_image") or []
        shown = [r for r in per_img if r.get("overlay") is not None]
        if shown:
            lead = max(shown, key=lambda r: r["count"])
            st.image(cv2.cvtColor(lead["overlay"], cv2.COLOR_BGR2RGB), width="stretch",
                     caption=f"Busiest photo: {lead['count']:,} people" if len(per_img) > 1 else None)
        st.caption(f"Counted by the {COUNTER_LABELS.get(info['counter'], 'model')} from "
                   f"{info['image_count']} photo(s)")
        if any((r.get("check") or {}).get("disagree") for r in per_img):
            st.warning("Check this count: a second model found far fewer people. Look at the dots on "
                       "Count people in a photo before acting on it.", icon=":material/visibility:")

# ── Plan ───────────────────────────────────────────────────────────────────
section("Evacuation plan",
        "Worked out by the optimiser, which moves as many people as the other zones can take along the "
        "shortest walks. " + ("It uses the routes from your site map." if adjacency else
                              "No site map is applied, so it treats every zone as reachable from every other; "
                              "apply a map on Site map to use real walking routes."))


def contact(seg):
    return html.escape(agents.get(seg, "")) or "<i style='color:#94a3b8'>no contact set</i>"


for seg, info in seg_info.items():
    risk, count = info["risk"], info["count"]
    head = (f"<b>{html.escape(zone_label(seg))}</b> <span style='color:#64748b;font-size:.85rem'>"
            f"({count:,} people)</span>")
    incoming = [p for p in pairings if p["target"] == seg]
    if risk in ("High Risk", "Critical"):
        mine = [p for p in pairings if p["high"] == seg]
        move = sum(p["move"] for p in mine)
        dest = ", ".join(f"Zone <b>{p['target']}</b> (~{p['move']:,}, now {p['target_count']:,})"
                         for p in mine if p["target"])
        nowhere = sum(p["move"] for p in mine if not p["target"])
        body = (f"<b>{risk.upper()}</b> · {head}<br>"
                + ("<b>Emergency.</b> " if risk == "Critical" else "")
                + f"Relocate <b>~{move:,}</b> people" + (f" to {dest}" if dest else "") + "."
                + (f" <b>~{nowhere:,} have nowhere safe to go:</b> call reinforcements." if nowhere else "")
                + "<br>Close entries to this zone, open its exits, and stop people walking towards it.")
        css = "alert-critical" if risk == "Critical" else "alert-high"
    elif incoming:
        arriving = ", ".join(f"~{p['move']:,} from Zone {p['high']}" for p in incoming)
        body = (f"<b>RECEIVING</b> · {head}<br>Expect {arriving}. Open entries and guide arrivals to the "
                "emptier parts of the zone.")
        css = "alert-moderate" if risk == "Moderate" else "alert-safe"
    elif risk == "Moderate":
        body = f"<b>MODERATE</b> · {head}<br>Busy but manageable. Watch it closely."
        css = "alert-moderate"
    else:
        body = f"<b>SAFE</b> · {head}<br>No action needed."
        css = "alert-safe"
    st.markdown(f"<div class='alert-card {css}'>{body}<br>"
                f"<span style='font-size:.82rem;color:#64748b'>Contact: {contact(seg)}</span></div>",
                unsafe_allow_html=True)

# ── Send alerts ────────────────────────────────────────────────────────────
section("Send alerts")


def peak_image(seg):
    shown = [r for r in data.get(seg, {}).get("per_image") or [] if r.get("overlay") is not None]
    if not shown:
        return None
    ok, buf = cv2.imencode(".jpg", max(shown, key=lambda r: r["count"])["overlay"], [cv2.IMWRITE_JPEG_QUALITY, 85])
    return bytes(buf) if ok else None


def team_message():
    """One short message for the team chat: every zone that needs action and where its people go."""
    lines = [f"Crowd Shield: {len(at_risk)} zone(s) need action"]
    for seg in at_risk:
        info = seg_info[seg]
        moves = [f"~{p['move']:,} to {p['target']}" if p["target"] else f"~{p['move']:,} with nowhere to go"
                 for p in pairings if p["high"] == seg]
        lines.append(f"{zone_label(seg)}: {info['risk'].upper()}, {info['count']:,} people. "
                     + ("Move " + ", ".join(moves) + "." if moves else ""))
    lines.append("Close entries to these zones and open their exits.")
    return "\n".join(lines)


if not pairings:
    st.success("No zone is at High Risk or Critical, so there is nothing to send.")
elif not channels:
    st.warning("No alert channel is set up. Add Telegram (free, on your phone) or Gmail in Team and alerts, then come "
               "back here to send.")
    nav_link("pages/1_Agents.py", "Set up alerts in Team and alerts", ":material/groups:", "/Agents")
else:
    plan_lines = []
    if "Telegram" in channels:
        plan_lines.append("**Telegram team chat:** one message listing every zone that needs action, with the "
                          "busiest photo.")
    if "email" in channels:
        for seg in sorted({p["high"] for p in pairings}):
            plan_lines.append(f"**{zone_label(seg)}** ({agents.get(seg) or 'no contact set'}): its orders "
                              "and photo.")
        for seg in sorted({p["target"] for p in pairings if p["target"]}):
            plan_lines.append(f"**{zone_label(seg)}** ({agents.get(seg) or 'no contact set'}): how many people "
                              "to expect.")
    st.markdown("This will send:\n\n- " + "\n- ".join(plan_lines))
    if st.button("Send alerts", type="primary", icon=":material/send:"):
        sent, failed = [], []
        if "Telegram" in channels:
            worst = max(at_risk, key=lambda s: seg_info[s]["count"] / seg_info[s]["thresholds"]["critical"])
            ok, msg = notify.send_telegram(team_message(), peak_image(worst))
            (sent if ok else failed).append(f"Telegram: {msg}")
        if "email" in channels:
            for seg in sorted({p["high"] for p in pairings}):
                address = agents.get(seg, "")
                if not address:
                    failed.append(f"{zone_label(seg)}: no contact email (add one in Team and alerts)")
                    continue
                moves = [p for p in pairings if p["high"] == seg]
                first, image = moves[0], peak_image(seg)
                subject, body = build_critical_email(
                    seg=seg, count=first["high_count"], target_seg=first["target"],
                    target_count=first["target_count"], move_count=first["move"], risk_level=first["risk"],
                    thresholds=first["thresholds"], has_image=bool(image), moves=moves)
                ok, msg = send_email(address, subject, body, image)
                (sent if ok else failed).append(f"{zone_label(seg)}: {msg}")
            for p in pairings:
                if not p["target"]:
                    continue
                address = agents.get(p["target"], "")
                if not address:
                    failed.append(f"{zone_label(p['target'])}: no contact email (add one in Team and alerts)")
                    continue
                subject, body = build_receiving_email(
                    seg=p["target"], count=p["target_count"], source_seg=p["high"], source_count=p["high_count"],
                    move_count=p["move"], thresholds=get_seg_thresholds(p["target"]))
                ok, msg = send_email(address, subject, body)
                (sent if ok else failed).append(f"{zone_label(p['target'])}: {msg}")
        if sent:
            st.success("Sent:\n\n- " + "\n- ".join(sent))
            st.session_state.alert_count += len(sent)
        if failed:
            st.error("Not sent:\n\n- " + "\n- ".join(failed))

# ── Export ─────────────────────────────────────────────────────────────────
section("Export")
buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(["Zone", "Name", "People", "Risk", "Counted by", "Moderate from", "High Risk from", "Critical from",
                 "Move out", "Move to"])
for seg, info in seg_info.items():
    t = info["thresholds"]
    mine = [p for p in pairings if p["high"] == seg]
    writer.writerow([seg, st.session_state.get("zone_names", {}).get(seg, ""), info["count"], info["risk"],
                     COUNTER_LABELS.get(info["counter"], ""), t["moderate"], t["high"], t["critical"],
                     sum(p["move"] for p in mine),
                     "; ".join(f"{p['target'] or 'nowhere'} ({p['move']})" for p in mine)])
st.download_button("Download the counts and plan (CSV)", buf.getvalue(), file_name="crowd_shield_report.csv",
                   mime="text/csv", icon=":material/download:")
