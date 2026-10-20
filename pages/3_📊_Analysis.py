"""Analysis page — detection breakdown, charts, alert plan, email dispatch."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgb
import matplotlib.patches as mpatches_rect

import csv
import io
import cv2
import streamlit as st

from shared_state import (init_state, GLOBAL_CSS, SEGMENTS,
                          RISK_COLORS, RISK_ICONS, get_seg_thresholds)
from detection import risk_level, MODEL_REGISTRY
from crowdshield.risk import plan_relocations
from emailer import (email_configured, send_email,
                     build_critical_email, build_receiving_email)

st.set_page_config(page_title="Analysis • Crowd Shield",
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
        <a href="/Settings">Settings</a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("# Analysis & Alerts")

data   = st.session_state.crowd_data
agents = st.session_state.agents

if not data:
    st.info("No analysis yet — go to Upload, add images and click Run Detection.")
    st.stop()

# ---------------------------------------------------------------------------
# Build seg_info
# ---------------------------------------------------------------------------
seg_info = {}
for seg in SEGMENTS:
    if seg not in data:
        continue
    d = data[seg]
    t = get_seg_thresholds(seg)
    seg_info[seg] = {
        "count":       d["count"],
        "body_count":  d["body_count"],
        "head_count":  d["head_count"],
        "image_count": d["image_count"],
        "risk":        risk_level(d["count"], t),
        "thresholds":  t,
    }

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
total      = sum(s["count"] for s in seg_info.values())
critical_n = sum(1 for s in seg_info.values() if s["risk"] == "Critical")
high_n     = sum(1 for s in seg_info.values() if s["risk"] == "High Risk")
moderate_n = sum(1 for s in seg_info.values() if s["risk"] == "Moderate")
safe_n     = sum(1 for s in seg_info.values() if s["risk"] == "Safe")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total People",  total)
c2.metric("Critical",      critical_n)
c3.metric("High Risk",     high_n)
c4.metric("Safe",          safe_n)
c5.metric("Segments Done", len(seg_info))

st.markdown("---")

# ---------------------------------------------------------------------------
# Per-segment detection cards
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Detection Breakdown</div>',
            unsafe_allow_html=True)

RISK_CSS = {
    "Safe":      "risk-safe",
    "Moderate":  "risk-moderate",
    "High Risk": "risk-high",
    "Critical":  "risk-critical",
}
BAR_COL = {
    "Safe":      "#10b981",
    "Moderate":  "#f59e0b",
    "High Risk": "#f97316",
    "Critical":  "#ef4444",
}

segs_list = list(seg_info.keys())

det_cols = st.columns(len(segs_list))
for i, (seg, info) in enumerate(seg_info.items()):
    with det_cols[i]:
        d     = data[seg]
        risk  = info["risk"]
        color = RISK_COLORS[risk]
        css   = RISK_CSS[risk]

        st.markdown(
            f"<div style='border-top:3px solid {color};padding-top:.6rem;"
            f"margin-bottom:.4rem'>"
            f"<b style='font-size:.95rem;color:#111827'>Segment {seg}</b>"
            f"</div>",
            unsafe_allow_html=True)

        per_img = d.get("per_image", [])
        if per_img:
            lead = max(per_img, key=lambda r: r["count"])
            if lead["overlay"] is not None:
                rgb = cv2.cvtColor(lead["overlay"], cv2.COLOR_BGR2RGB)
                st.image(rgb, use_container_width=True,
                         caption=f"Peak — {lead['count']} people")
            if len(per_img) > 1:
                with st.expander(f"All {len(per_img)} images"):
                    for j, r in enumerate(per_img, start=1):
                        if r["overlay"] is not None:
                            rgb2 = cv2.cvtColor(r["overlay"], cv2.COLOR_BGR2RGB)
                            st.image(rgb2, caption=f"Image {j}: {r['count']}",
                                     use_container_width=True)

        t = info["thresholds"]
        st.markdown(
            f"<div style='margin:.4rem 0'>"
            f"<span style='font-size:1.4rem;font-weight:800;color:#111827'>"
            f"{info['count']}</span>"
            f"<span style='font-size:.8rem;color:#6b7280;margin-left:.3rem'>people</span>"
            f"</div>",
            unsafe_allow_html=True)
        st.caption(f"{info['body_count']} people boxed by YOLO")
        st.caption(f"Thresholds: {t['moderate']} / {t['high']} / {t['critical']}")
        st.markdown(f'<span class="risk-badge {css}">{risk}</span>',
                    unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Shared chart constants
# ---------------------------------------------------------------------------
CHART_BG  = "#ffffff"
FACE_COL  = "#f9fafb"
TEXT_COL  = "#111827"
GRID_COL  = "#e5e7eb"
SPINE_COL = "#d1d5db"

def _style_ax(ax, fig):
    fig.patch.set_facecolor(CHART_BG)
    ax.set_facecolor(FACE_COL)
    for spine in ax.spines.values():
        spine.set_color(SPINE_COL)
    ax.tick_params(colors=TEXT_COL)
    ax.set_axisbelow(True)

# Risk colour palette — vivid enough to read, soft enough for the theme
SOFT_COL = {
    "Safe":      "#10b981",   # emerald-500
    "Moderate":  "#f59e0b",   # amber-500
    "High Risk": "#f97316",   # orange-500
    "Critical":  "#ef4444",   # red-500
}

counts    = [seg_info[s]["count"]                   for s in segs_list]
bar_cols  = [SOFT_COL[seg_info[s]["risk"]]          for s in segs_list]
all_crits = [seg_info[s]["thresholds"]["critical"]  for s in segs_list]

# Shared Y ceiling — fits every bar AND every critical threshold
y_ceiling = max(max(counts, default=0), max(all_crits, default=1)) * 1.25

BW          = 0.52          # bar width
SHADOW_DX   = 0.13          # large right-offset so shadow clearly peeks out
SHADOW_DY   = -0.03         # fraction of bar height to drop shadow down
SHADOW_COL  = "#94a3b8"     # slate-400 — dark enough to see
SHEEN_ALPHA = 0.25          # white highlight opacity on top of bars

# ── Gradient bar helper ───────────────────────────────────────────────────────
def _grad_bar_v(ax, xi, h, bw, color, n=28, zorder=3):
    """Vertical gradient bar: rich colour at base, 40% lighter at top."""
    if h <= 0:
        return
    r, g, b = to_rgb(color)
    blend = 0.40
    tr, tg, tb = r+(1-r)*blend, g+(1-g)*blend, b+(1-b)*blend
    sh = h / n
    for i in range(n):
        frac = i / (n - 1)
        fc = (r*(1-frac)+tr*frac, g*(1-frac)+tg*frac, b*(1-frac)+tb*frac)
        ax.bar(xi, sh, width=bw, bottom=i*sh, color=fc,
               edgecolor="none", linewidth=0, zorder=zorder)
    # crisp white edge on top
    ax.bar(xi, h, width=bw, color="none",
           edgecolor="white", linewidth=1.4, zorder=zorder + 0.1)
    # top-sheen highlight (white fade in top 25% of bar)
    sheen_h = h * 0.25
    ax.bar(xi, sheen_h, width=bw, bottom=h - sheen_h,
           color="white", edgecolor="none",
           alpha=SHEEN_ALPHA, linewidth=0, zorder=zorder + 0.2)

def _grad_bar_h(ax, yi, w, bh, color, n=28, zorder=3):
    """Horizontal gradient bar: rich colour at left, 40% lighter at right."""
    if w <= 0:
        return
    r, g, b = to_rgb(color)
    blend = 0.40
    tr, tg, tb = r+(1-r)*blend, g+(1-g)*blend, b+(1-b)*blend
    sw = w / n
    for i in range(n):
        frac = i / (n - 1)
        fc = (r*(1-frac)+tr*frac, g*(1-frac)+tg*frac, b*(1-frac)+tb*frac)
        ax.barh(yi, sw, left=i*sw, height=bh, color=fc,
                edgecolor="none", linewidth=0, zorder=zorder)
    ax.barh(yi, w, height=bh, color="none",
            edgecolor="white", linewidth=1.4, zorder=zorder + 0.1)
    # right-sheen highlight
    sheen_w = w * 0.22
    ax.barh(yi, sheen_w, left=w - sheen_w, height=bh,
            color="white", edgecolor="none",
            alpha=SHEEN_ALPHA, linewidth=0, zorder=zorder + 0.2)

# ── Threshold styles: (key, hex-color, linestyle, linewidth, label) ──────────
T_STYLES = [
    ("moderate", "#d97706", "--",  1.8, "Moderate"),
    ("high",     "#ea580c", "-.",  2.0, "High Risk"),
    ("critical", "#dc2626", "-",   2.5, "Critical"),
]

# ---------------------------------------------------------------------------
# Chart 1 — Gradient bar chart with per-segment threshold badges
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Crowd Count vs Risk Thresholds</div>',
            unsafe_allow_html=True)

x_pos = list(range(len(segs_list)))
fig1, ax1 = plt.subplots(figsize=(10, 5.8))
fig1.patch.set_facecolor("#f8fafc")
ax1.set_facecolor("#f8fafc")
for sp in ax1.spines.values():
    sp.set_color("#e2e8f0")
ax1.tick_params(colors=TEXT_COL, labelsize=11)
ax1.set_axisbelow(True)
ax1.yaxis.grid(True, color="#e2e8f0", linewidth=0.9, zorder=0)
ax1.set_xlim(-0.65, len(segs_list) - 0.35)
ax1.set_ylim(0, y_ceiling * 1.10)
ax1.spines["right"].set_visible(False)
ax1.spines["top"].set_visible(False)

for xi, count, col in zip(x_pos, counts, bar_cols):
    # Shadow — clearly offset so it visibly peeks out bottom-right
    shadow_h = max(1, count + count * SHADOW_DY)
    ax1.bar(xi + SHADOW_DX, shadow_h, width=BW,
            color=SHADOW_COL, zorder=1, linewidth=0, alpha=0.70)
    # Gradient main bar
    _grad_bar_v(ax1, xi, count, BW, col, zorder=3)
    # Count label above bar
    ax1.text(xi, count + y_ceiling * 0.022, str(count),
             ha="center", va="bottom",
             color=TEXT_COL, fontsize=12, fontweight="bold", zorder=7)

# Per-segment threshold lines + coloured badge labels
tick_ext = 0.08
for xi, seg in zip(x_pos, segs_list):
    t  = seg_info[seg]["thresholds"]
    x0 = xi - BW / 2 - tick_ext
    x1 = xi + BW / 2 + tick_ext
    for level, lc, ls, lw, lbl in T_STYLES:
        val = t[level]
        # Horizontal tick line spanning exactly this bar
        ax1.hlines(val, x0, x1,
                   colors=lc, linewidths=lw, linestyles=ls, zorder=5)
        # Coloured badge at the right end of the tick
        ax1.annotate(
            f" {val} ",
            xy=(x1, val),
            xytext=(x1 + 0.05, val),
            va="center", ha="left",
            fontsize=7.5, fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor=lc, edgecolor="none", alpha=0.88),
            zorder=8,
        )

ax1.set_xticks(x_pos)
ax1.set_xticklabels([f"Seg {s}" for s in segs_list],
                    color=TEXT_COL, fontsize=11)
ax1.set_ylabel("People detected", color=TEXT_COL, fontsize=10)

legend_items = [
    mpatches.Patch(facecolor="#10b981", label="Safe"),
    mpatches.Patch(facecolor="#f59e0b", label="Moderate"),
    mpatches.Patch(facecolor="#f97316", label="High Risk"),
    mpatches.Patch(facecolor="#ef4444", label="Critical"),
    plt.Line2D([0],[0], color="#d97706", lw=2,   ls="--", label="Moderate threshold"),
    plt.Line2D([0],[0], color="#ea580c", lw=2,   ls="-.", label="High Risk threshold"),
    plt.Line2D([0],[0], color="#dc2626", lw=2.5, ls="-",  label="Critical threshold"),
]
ax1.legend(handles=legend_items, loc="upper center",
           bbox_to_anchor=(0.5, 1.18), ncol=2,
           facecolor="white", edgecolor="#e2e8f0",
           labelcolor=TEXT_COL, fontsize=8.5, framealpha=0.96)

fig1.tight_layout()
st.pyplot(fig1)
plt.close(fig1)

st.markdown("---")

# ---------------------------------------------------------------------------
# Chart 2 — Remaining Capacity by Risk Zone (shared X-axis, gradient bars)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Remaining Capacity by Risk Zone</div>',
            unsafe_allow_html=True)
st.caption(
    "Each bar shows current occupancy vs. the full risk-zone spectrum for "
    "that segment. All segments share the same X-axis scale so you can "
    "compare headroom directly. +N = people remaining before next threshold."
)

x_ceiling = max(all_crits) if all_crits else 100

y_pos  = list(range(len(segs_list)))
bar_h  = 0.54
Z_MOD  = "#fef3c7"   # amber-100
Z_HIGH = "#ffedd5"   # orange-50
Z_CRIT = "#fee2e2"   # red-50
BORDER_MOD  = "#d97706"
BORDER_HIGH = "#ea580c"
BORDER_CRIT = "#dc2626"

fig2, ax2 = plt.subplots(figsize=(10, max(4.4, len(segs_list) * 1.12)))
fig2.patch.set_facecolor("#f8fafc")
ax2.set_facecolor("#f8fafc")
for sp in ax2.spines.values():
    sp.set_color("#e2e8f0")
ax2.tick_params(colors=TEXT_COL, labelsize=11)
ax2.set_axisbelow(True)
ax2.xaxis.grid(True, color="#e2e8f0", linewidth=0.9, zorder=0)
ax2.set_xlim(0, x_ceiling * 1.10)
ax2.spines["right"].set_visible(False)
ax2.spines["top"].set_visible(False)

for yi, seg in enumerate(segs_list):
    info  = seg_info[seg]
    count = info["count"]
    t     = info["thresholds"]
    mod, high, crit = t["moderate"], t["high"], t["critical"]
    display_count = min(count, crit)
    overflow      = max(0, count - crit)

    # ── Zone tint bands ───────────────────────────────────────────────────────
    for bx0, bx1, bfc in [
        (0,    mod,  Z_MOD),
        (mod,  high, Z_HIGH),
        (high, crit, Z_CRIT),
    ]:
        ax2.barh(yi, bx1 - bx0, left=bx0, height=bar_h,
                 color=bfc, edgecolor="none", zorder=1, alpha=0.65)

    # ── Zone divider lines (span full bar height, no badges here) ────────────
    for div_x, div_col in [
        (mod,  BORDER_MOD),
        (high, BORDER_HIGH),
        (crit, BORDER_CRIT),
    ]:
        ax2.vlines(div_x, yi - bar_h / 2, yi + bar_h / 2,
                   colors=div_col, linewidths=1.8, zorder=4, alpha=0.75)

    # ── Gradient occupancy bar ────────────────────────────────────────────────
    _grad_bar_h(ax2, yi, display_count, bar_h,
                SOFT_COL[info["risk"]], zorder=3)

    # Overflow hatch
    if overflow > 0:
        ax2.barh(yi, overflow, left=crit, height=bar_h,
                 color="#ef4444", edgecolor="white",
                 linewidth=1.0, zorder=3, hatch="////", alpha=0.50)

    # Count inside bar
    if display_count > x_ceiling * 0.07:
        ax2.text(display_count / 2, yi, str(count),
                 ha="center", va="center",
                 color="white", fontsize=9, fontweight="bold",
                 zorder=6)

    # Headroom "+N" labels — centred vertically in each remaining zone
    w_to_mod  = max(0, min(mod,  crit) - count)
    w_to_high = max(0, min(high, crit) - max(count, mod))
    w_to_crit = max(0, crit            - max(count, high))
    for width, cx, lc in [
        (w_to_mod,  min(count, mod)  + w_to_mod  / 2, BORDER_MOD),
        (w_to_high, max(count, mod)  + w_to_high / 2, BORDER_HIGH),
        (w_to_crit, max(count, high) + w_to_crit / 2, BORDER_CRIT),
    ]:
        if width > x_ceiling * 0.05:
            ax2.text(cx, yi, f"+{int(width)}",
                     ha="center", va="center",
                     color=lc, fontsize=8.5, fontweight="bold", zorder=6)

# ── Threshold badges — drawn ONCE above the top axis, outside the plot ───────
y_badge = len(segs_list) - 0.5   # top of highest bar
seen_x: set = set()
for seg in segs_list:
    t = seg_info[seg]["thresholds"]
    for div_x, div_col, div_lbl in [
        (t["moderate"], BORDER_MOD,  str(t["moderate"])),
        (t["high"],     BORDER_HIGH, str(t["high"])),
        (t["critical"], BORDER_CRIT, str(t["critical"])),
    ]:
        if div_x not in seen_x:
            seen_x.add(div_x)
            ax2.annotate(
                f" {div_lbl} ",
                xy=(div_x, y_badge),
                xytext=(div_x, y_badge + 0.28),
                va="bottom", ha="center",
                fontsize=7.5, fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor=div_col, edgecolor="none", alpha=0.88),
                annotation_clip=False,
                zorder=9,
            )

ax2.set_yticks(y_pos)
ax2.set_yticklabels([f"Segment {s}" for s in segs_list],
                    color=TEXT_COL, fontsize=11)
ax2.set_xlabel("People count", color=TEXT_COL, fontsize=10)
# Give enough headroom at top for the badges
ax2.set_ylim(-0.6, len(segs_list) - 0.5 + 0.7)

legend_items2 = [
    mpatches.Patch(facecolor="#10b981", edgecolor="white", label="Safe"),
    mpatches.Patch(facecolor="#f59e0b", edgecolor="white", label="Moderate"),
    mpatches.Patch(facecolor="#f97316", edgecolor="white", label="High Risk"),
    mpatches.Patch(facecolor="#ef4444", edgecolor="white", label="Critical"),
    mpatches.Patch(facecolor=Z_MOD,  edgecolor=BORDER_MOD,  alpha=0.8, label="Room to Moderate"),
    mpatches.Patch(facecolor=Z_HIGH, edgecolor=BORDER_HIGH, alpha=0.8, label="Room to High Risk"),
    mpatches.Patch(facecolor=Z_CRIT, edgecolor=BORDER_CRIT, alpha=0.8, label="Room to Critical"),
]
ax2.legend(handles=legend_items2, loc="upper center",
           bbox_to_anchor=(0.5, -0.12), ncol=4,
           facecolor="white", edgecolor="#e2e8f0",
           labelcolor=TEXT_COL, fontsize=8.5, framealpha=0.96)

fig2.tight_layout()
st.pyplot(fig2)
plt.close(fig2)

st.markdown("---")

# ---------------------------------------------------------------------------
# Chart 3 — Risk distribution donut
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Risk Distribution</div>',
            unsafe_allow_html=True)

risk_counts = {
    "Critical":  critical_n,
    "High Risk": high_n,
    "Moderate":  moderate_n,
    "Safe":      safe_n,
}
non_zero = {k: v for k, v in risk_counts.items() if v > 0}

if non_zero:
    fig3, ax3 = plt.subplots(figsize=(4, 3.4))
    fig3.patch.set_facecolor(CHART_BG)
    ax3.set_facecolor(CHART_BG)

    donut_colors = [BAR_COL[k] for k in non_zero]
    wedges, texts, autotexts = ax3.pie(
        list(non_zero.values()),
        labels=list(non_zero.keys()),
        autopct="%1.0f%%",
        colors=donut_colors,
        startangle=90,
        wedgeprops={"linewidth": 2.5, "edgecolor": CHART_BG},
        pctdistance=0.72,
    )
    for t in texts:
        t.set_color(TEXT_COL)
        t.set_fontsize(9)
        t.set_fontweight("600")
    for at in autotexts:
        at.set_color("#ffffff")
        at.set_fontsize(8)
        at.set_fontweight("bold")

    hole = plt.Circle((0, 0), 0.48, fc=CHART_BG)
    ax3.add_patch(hole)
    ax3.text(0, 0.06, str(len(seg_info)), ha="center", va="center",
             color=TEXT_COL, fontsize=16, fontweight="bold")
    ax3.text(0, -0.16, "segments", ha="center", va="center",
             color="#6b7280", fontsize=8)

    fig3.tight_layout()
    _, donut_col, _ = st.columns([1, 1, 1])
    with donut_col:
        st.pyplot(fig3)
    plt.close(fig3)
else:
    st.caption("No segments analysed yet.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Zone Heatmap — visual floor-plan view of all segments
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Zone Risk Map</div>',
            unsafe_allow_html=True)
st.caption("At-a-glance view of risk level across all monitored zones.")

HEATMAP_ALPHA = 0.88
ZONE_COLORS = {
    "Safe":      ("#10b981", "#065f46"),   # bg, text
    "Moderate":  ("#f59e0b", "#451a03"),
    "High Risk": ("#f97316", "#431407"),
    "Critical":  ("#ef4444", "#450a0a"),
}

fig_hm, ax_hm = plt.subplots(figsize=(10, 2.6))
fig_hm.patch.set_facecolor("#f8fafc")
ax_hm.set_facecolor("#f8fafc")
ax_hm.axis("off")

n_segs = len(segs_list)
gap    = 0.07
w      = (1.0 - gap * (n_segs + 1)) / n_segs

for i, seg in enumerate(segs_list):
    info  = seg_info[seg]
    risk  = info["risk"]
    bg, fg = ZONE_COLORS[risk]
    x0    = gap + i * (w + gap)

    # Shadow rectangle
    shadow = mpatches.FancyBboxPatch(
        (x0 + 0.01, -0.04), w, 1.0,
        boxstyle="round,pad=0.02",
        facecolor="#94a3b8", edgecolor="none",
        alpha=0.35, zorder=1,
    )
    ax_hm.add_patch(shadow)

    # Main coloured zone tile
    tile = mpatches.FancyBboxPatch(
        (x0, 0), w, 0.96,
        boxstyle="round,pad=0.02",
        facecolor=bg, edgecolor="white",
        linewidth=2.0, alpha=HEATMAP_ALPHA, zorder=2,
    )
    ax_hm.add_patch(tile)

    # Sheen (lighter overlay on top quarter)
    sheen = mpatches.FancyBboxPatch(
        (x0 + 0.005, 0.70), w - 0.01, 0.24,
        boxstyle="round,pad=0.01",
        facecolor="white", edgecolor="none",
        alpha=0.18, zorder=3,
    )
    ax_hm.add_patch(sheen)

    cx = x0 + w / 2
    ax_hm.text(cx, 0.76, f"Zone {seg}",
               ha="center", va="center",
               color=fg, fontsize=9, fontweight="700", zorder=4)
    ax_hm.text(cx, 0.48, str(info["count"]),
               ha="center", va="center",
               color="white", fontsize=20, fontweight="900", zorder=4)
    ax_hm.text(cx, 0.18, risk,
               ha="center", va="center",
               color="white", fontsize=7.5, fontweight="600",
               alpha=0.92, zorder=4)

ax_hm.set_xlim(0, 1)
ax_hm.set_ylim(-0.08, 1.05)
fig_hm.tight_layout(pad=0.2)
st.pyplot(fig_hm)
plt.close(fig_hm)

st.markdown("---")

# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)

_csv_buf = io.StringIO()
_writer  = csv.writer(_csv_buf)
_writer.writerow(["Segment", "Count", "Risk Level", "Bodies", "Heads",
                  "Moderate Threshold", "High Risk Threshold", "Critical Threshold"])
for _seg, _info in seg_info.items():
    _t = _info["thresholds"]
    _writer.writerow([f"Segment {_seg}", _info["count"], _info["risk"],
                      _info["body_count"], _info["head_count"],
                      _t["moderate"], _t["high"], _t["critical"]])

_dl_left, _dl_btn = st.columns([5, 1])
with _dl_btn:
    st.download_button(
        "Download CSV",
        _csv_buf.getvalue(),
        file_name="crowd_shield_report.csv",
        mime="text/csv",
        use_container_width=True,
    )
with _dl_left:
    st.caption(
        f"Report contains {len(seg_info)} segment(s) — "
        "counts, risk levels and thresholds."
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Alert plan
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown('<div class="section-label">Alert Plan & Operational Orders</div>',
            unsafe_allow_html=True)

pairings = plan_relocations(seg_info,
                            adjacency=st.session_state.get("zone_adjacency"))

for seg in SEGMENTS:
    if seg not in seg_info:
        continue
    info      = seg_info[seg]
    risk      = info["risk"]
    color     = RISK_COLORS[risk]
    agent     = agents.get(seg, "") or "<i style='color:#9ca3af'>no agent assigned</i>"
    t         = info["thresholds"]
    allowable = max(0, t["critical"] - info["count"])

    if risk in ("High Risk", "Critical"):
        pair   = next((p for p in pairings if p["high"] == seg), None)
        target = pair["target"] if pair else None
        move   = pair["move"]   if pair else 0
        dest   = (f' to Segment <b>{target}</b> '
                  f'(current: {seg_info[target]["count"]})'
                  if target else " — call reinforcements")
        emerg  = "<b>EMERGENCY: </b>" if risk == "Critical" else ""
        msg = (
            f"<b style='color:#111827'>{risk.upper()} — Segment {seg}</b> "
            f"<span style='color:#6b7280;font-size:.85rem'>"
            f"({info['count']} people · {allowable} to Critical)</span><br>"
            f"{emerg}Relocate <b>~{move}</b> people{dest}.<br>"
            f"Close all entries · Open all exits · Block incoming routes.<br>"
            f"<span style='font-size:.83rem;color:#6b7280'>Agent: {agent}</span>"
        )
        css = "alert-critical" if risk == "Critical" else "alert-high"

    elif risk == "Moderate":
        incoming = [p for p in pairings if p["target"] == seg]
        if incoming:
            inc = incoming[0]
            msg = (
                f"<b style='color:#111827'>INCOMING — Segment {seg}</b> "
                f"<span style='color:#6b7280;font-size:.85rem'>({info['count']} people)</span><br>"
                f"Prepare for ~{inc['move']} arriving from Segment {inc['high']}.<br>"
                f"<span style='font-size:.83rem;color:#6b7280'>Agent: {agent}</span>"
            )
        else:
            msg = (
                f"<b style='color:#111827'>MODERATE — Segment {seg}</b> "
                f"<span style='color:#6b7280;font-size:.85rem'>({info['count']} people)</span>"
                f" — monitor closely.<br>"
                f"<span style='font-size:.83rem;color:#6b7280'>Agent: {agent}</span>"
            )
        css = "alert-moderate"

    else:
        incoming = [p for p in pairings if p["target"] == seg]
        if incoming:
            inc = incoming[0]
            msg = (
                f"<b style='color:#111827'>SAFE (receiving) — Segment {seg}</b> "
                f"<span style='color:#6b7280;font-size:.85rem'>({info['count']} people)</span><br>"
                f"Receiving ~{inc['move']} from Segment {inc['high']}. "
                f"Open entries, guide arrivals.<br>"
                f"<span style='font-size:.83rem;color:#6b7280'>Agent: {agent}</span>"
            )
        else:
            msg = (
                f"<b style='color:#111827'>SAFE — Segment {seg}</b> "
                f"<span style='color:#6b7280;font-size:.85rem'>({info['count']} people)</span><br>"
                f"<span style='font-size:.83rem;color:#6b7280'>Agent: {agent}</span>"
            )
        css = "alert-safe"

    st.markdown(f'<div class="alert-card {css}">{msg}</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Email dispatch
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown('<div class="section-label">Dispatch Email Alerts</div>',
            unsafe_allow_html=True)


def _peak_image_bytes(seg: str):
    d       = data.get(seg, {})
    per_img = d.get("per_image", [])
    if not per_img:
        return None
    lead = max(per_img, key=lambda r: r["count"])
    if lead["overlay"] is None:
        return None
    ok, buf = cv2.imencode(".jpg", lead["overlay"],
                           [cv2.IMWRITE_JPEG_QUALITY, 85])
    return bytes(buf) if ok else None


if not email_configured():
    st.warning("Gmail credentials not configured. Open Settings to add them.")
elif not pairings:
    st.success("No high-risk or critical segments — no alerts needed.")
else:
    st.caption("Each email includes operational orders and the peak detection "
               "image from the flagged segment.")

    for p in pairings:
        h_email = agents.get(p["high"], "")
        t_email = agents.get(p["target"], "") if p["target"] else ""
        risk_c  = RISK_COLORS[p["risk"]]
        st.markdown(
            f"<div class='glass-card' style='margin:.4rem 0;font-size:.875rem'>"
            f"<b style='color:{risk_c}'>Segment {p['high']}</b>"
            f" → <code style='background:#f3f4f6;padding:.1rem .35rem;"
            f"border-radius:4px'>{h_email or 'unassigned'}</code>"
            f" — evacuate ~{p['move']}"
            f"{', to Seg ' + p['target'] if p['target'] else ''}"
            f"</div>",
            unsafe_allow_html=True)
        if p["target"] and t_email:
            st.markdown(
                f"<div class='glass-card' style='margin:.3rem 0 .3rem 1.5rem;"
                f"font-size:.875rem'>"
                f"<b style='color:#10b981'>Segment {p['target']}</b>"
                f" → <code style='background:#f3f4f6;padding:.1rem .35rem;"
                f"border-radius:4px'>{t_email}</code>"
                f" — prepare for ~{p['move']} incoming"
                f"</div>",
                unsafe_allow_html=True)

    if st.button("Send all alerts", use_container_width=True, type="primary"):
        sent, failed = [], []
        for p in pairings:
            h_email   = agents.get(p["high"], "")
            t_email   = agents.get(p["target"], "") if p["target"] else ""
            img_bytes = _peak_image_bytes(p["high"])

            if h_email:
                subj, body = build_critical_email(
                    seg=p["high"], count=p["high_count"],
                    target_seg=p["target"], target_count=p["target_count"],
                    move_count=p["move"], risk_level=p["risk"],
                    thresholds=p["thresholds"], has_image=bool(img_bytes))
                ok, msg = send_email(h_email, subj, body, img_bytes)
                (sent if ok else failed).append(
                    f"Agent {p['high']} ({h_email}): {msg}")
            else:
                failed.append(f"Segment {p['high']}: no agent email assigned")

            if p["target"] and t_email:
                subj, body = build_receiving_email(
                    seg=p["target"], count=p["target_count"],
                    source_seg=p["high"], source_count=p["high_count"],
                    move_count=p["move"],
                    thresholds=get_seg_thresholds(p["target"]))
                ok, msg = send_email(t_email, subj, body)
                (sent if ok else failed).append(
                    f"Agent {p['target']} ({t_email}): {msg}")
            elif p["target"]:
                failed.append(f"Segment {p['target']}: no agent email assigned")

        if sent:
            st.success("Sent:\n\n- " + "\n- ".join(sent))
            st.session_state.alert_count += len(sent)
        if failed:
            st.error("Issues:\n\n- " + "\n- ".join(failed))
