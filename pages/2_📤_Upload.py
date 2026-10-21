"""Upload page — two-channel input (CCTV + Drone) with automatic model routing."""

from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

from shared_state import (init_state, GLOBAL_CSS, SEGMENTS,
                          MAX_IMAGES_PER_SEGMENT, get_seg_thresholds)
from detection import process_segment, MODEL_REGISTRY, risk_level
from crowdshield.config import COUNTER_LABELS

st.set_page_config(page_title="Upload • Crowd Shield",
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

st.markdown("# Image Upload")

# Model routing info card
st.markdown(
    """
    <div class="glass-card" style="margin-bottom:1.25rem;display:flex;
         gap:2.5rem;flex-wrap:wrap;align-items:flex-start">
      <div>
        <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:.8px;color:#0d9488;margin-bottom:.3rem">
          CCTV / Ground-level
        </div>
        <div style="font-size:.875rem;color:#374151">
          Routed to <code style="background:#f0fdfa;color:#0d9488;padding:.1rem .4rem;
          border-radius:4px;font-size:.8rem">YOLOv8l (COCO)</code>
          — optimised for close-range pedestrian detection
        </div>
      </div>
      <div style="width:1px;background:#e5e7eb;align-self:stretch"></div>
      <div>
        <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:.8px;color:#0d9488;margin-bottom:.3rem">
          Drone / Aerial
        </div>
        <div style="font-size:.875rem;color:#374151">
          Routed to <code style="background:#f0fdfa;color:#0d9488;padding:.1rem .4rem;
          border-radius:4px;font-size:.8rem">Crowd YOLO (VisDrone)</code>
          — trained on top-down crowd scenes
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    .stFileUploader {
      background: #ffffff !important;
      border-radius: 12px !important;
    }
    .stButton > button:not([kind="primary"]) {
      background: #ffffff !important;
      color: #111827 !important;
      border: 1px solid #d1d5db !important;
    }
    .stButton > button:not([kind="primary"]):hover {
      background: #f9fafb !important;
      border-color: #9ca3af !important;
    }
    .stMarkdown, .stCaption, .stText, .stFileUploader, .stMetric {
      color: #111827 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

MAX_HALF = MAX_IMAGES_PER_SEGMENT // 2

# ---------------------------------------------------------------------------
# Per-segment upload columns
# ---------------------------------------------------------------------------
seg_cols = st.columns(5)
for i, seg in enumerate(SEGMENTS):
    with seg_cols[i]:
        existing_sources = st.session_state.image_sources.get(seg, [])
        n_cctv  = sum(1 for s in existing_sources if s == "ground")
        n_drone = sum(1 for s in existing_sources if s == "drone")

        st.markdown(
            f"""
            <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:.8px;color:#9ca3af;margin-bottom:.6rem;
                        padding-bottom:.4rem;border-bottom:2px solid #e5e7eb">
              Segment {seg}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div style='font-size:.8rem;font-weight:600;color:#374151;"
            "margin-bottom:.25rem'>CCTV / Ground</div>",
            unsafe_allow_html=True,
        )
        cctv_files = st.file_uploader(
            f"CCTV — Seg {seg}",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"cctv_{seg}",
            label_visibility="collapsed",
        )

        st.markdown(
            "<div style='font-size:.8rem;font-weight:600;color:#374151;"
            "margin-top:.6rem;margin-bottom:.25rem'>Drone / Aerial</div>",
            unsafe_allow_html=True,
        )
        drone_files = st.file_uploader(
            f"Drone — Seg {seg}",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"drone_{seg}",
            label_visibility="collapsed",
        )

        st.radio(
            f"Photos in Segment {seg} show",
            options=["sum", "max"],
            format_func=lambda m: ("Different parts: add counts" if m == "sum"
                                   else "Same area: keep highest"),
            key=f"combine_{seg}",
            help="Adding up two photos of the same spot counts those people twice.",
        )

        if cctv_files or drone_files:
            cctv_clipped  = cctv_files[:MAX_HALF]  if cctv_files  else []
            drone_clipped = drone_files[:MAX_HALF]  if drone_files else []

            all_bytes   = [f.getvalue() for f in cctv_clipped + drone_clipped]
            all_names   = [f.name       for f in cctv_clipped + drone_clipped]
            all_sources = (["ground"] * len(cctv_clipped)
                           + ["drone"]  * len(drone_clipped))

            st.session_state.uploaded_images[seg] = all_bytes
            st.session_state.image_names[seg]     = all_names
            st.session_state.image_sources[seg]   = all_sources

        stored = st.session_state.uploaded_images.get(seg, [])
        srcs   = st.session_state.image_sources.get(seg, [])
        n_c    = sum(1 for s in srcs if s == "ground")
        n_d    = sum(1 for s in srcs if s == "drone")
        if stored:
            st.markdown(
                f"<div style='margin-top:.5rem;font-size:.78rem;color:#6b7280'>"
                f"{n_c} CCTV &nbsp;·&nbsp; {n_d} Drone"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='margin-top:.5rem;font-size:.78rem;color:#6b7280'>"
                "No images yet</div>",
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Run detection
# ---------------------------------------------------------------------------
st.markdown("---")
total_imgs = sum(len(v) for v in st.session_state.uploaded_images.values())
segs_ready = [s for s in SEGMENTS if st.session_state.uploaded_images.get(s)]

c1, c2 = st.columns([3, 1])
with c1:
    if segs_ready:
        st.markdown(
            f"<div style='font-size:.9rem;color:#374151;padding-top:.5rem'>"
            f"<b>{len(segs_ready)}</b> segment(s) ready — "
            f"<b>{total_imgs}</b> total image(s)</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='font-size:.9rem;color:#9ca3af;padding-top:.5rem'>"
            "Upload images above to enable detection.</div>",
            unsafe_allow_html=True,
        )
with c2:
    run = st.button("Run Detection", use_container_width=True,
                    disabled=(total_imgs == 0), type="primary")

if run:
    _ANIM_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:1px 2px 2px}
.card{
  background:linear-gradient(155deg,#141c2e 0%,#0d1117 100%);
  border:1px solid #1e2d40;border-radius:18px;
  padding:17px 22px 15px;
  box-shadow:0 20px 60px rgba(0,0,0,.65),inset 0 1px 0 rgba(255,255,255,.04);
}
.hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:13px;gap:14px}
.pct{font-size:32px;font-weight:900;line-height:1;letter-spacing:-1.5px;color:#ef4444;transition:color .5s}
.slabel{font-size:11px;text-transform:uppercase;letter-spacing:.9px;color:#475569;margin-top:6px;font-weight:600}
.ttl{text-align:right}
.ttl-main{font-size:13px;font-weight:700;color:#94a3b8}
.ttl-sub{font-size:11px;color:#334155;margin-top:3px}

.track{
  position:relative;height:108px;border-radius:14px;
  background:linear-gradient(180deg,#0d1218 0%,#161e2e 100%);
  border:1px solid #1a2540;
  box-shadow:inset 0 3px 12px rgba(0,0,0,.55);
  overflow:hidden;
}
/* subtle vertical grid lines */
.track::before{
  content:'';position:absolute;inset:0;
  background-image:repeating-linear-gradient(90deg,transparent,transparent 59px,rgba(255,255,255,.022) 60px);
  pointer-events:none;z-index:0;
}
.lane{position:absolute;left:0;right:0;top:6px;bottom:26px;z-index:1}
.bar-bg{position:absolute;left:12px;right:12px;bottom:13px;height:6px;border-radius:999px;background:rgba(255,255,255,.06);z-index:2}
.bar-fill{height:100%;width:0%;border-radius:999px;
  background:linear-gradient(90deg,#ef4444 0%,#f97316 33%,#facc15 66%,#22c55e 100%);
  box-shadow:0 0 14px rgba(239,68,68,.4)}
.bar-dot{position:absolute;bottom:11px;left:12px;
  width:10px;height:10px;border-radius:50%;
  transform:translateX(-50%);background:#ef4444;
  box-shadow:0 0 18px rgba(239,68,68,.9);z-index:3}

.p{position:absolute;bottom:0;will-change:transform;z-index:4}

/* ── keyframes ── */
/* Torso slight forward lean bob */
@keyframes tbob{0%,100%{transform:rotate(-4deg)}50%{transform:rotate(-1deg)}}
/* Front arm swings backward then forward */
@keyframes afk{0%,100%{transform:rotate(-30deg)}50%{transform:rotate(22deg)}}
/* Back arm opposite */
@keyframes abk{0%,100%{transform:rotate(30deg)}50%{transform:rotate(-22deg)}}
/* Front thigh */
@keyframes lfhk{0%,100%{transform:rotate(-35deg)}50%{transform:rotate(24deg)}}
/* Front shin (bends at knee, follows thigh + extra) */
@keyframes lfsk{0%,100%{transform:rotate(42deg)}50%{transform:rotate(2deg)}}
/* Back thigh */
@keyframes lbhk{0%,100%{transform:rotate(32deg)}50%{transform:rotate(-28deg)}}
/* Back shin */
@keyframes lbsk{0%,100%{transform:rotate(2deg)}50%{transform:rotate(44deg)}}
</style>
</head>
<body>
<div class="card">
  <div class="hdr">
    <div>
      <div class="pct" id="pct">0%</div>
      <div class="slabel" id="slbl">Detecting Crowd...</div>
    </div>
    <div class="ttl">
      <div class="ttl-main">Crowd Dispersion Loading Animation</div>
      <div class="ttl-sub">From congestion to safety &mdash; AI-powered crowd analysis in progress</div>
    </div>
  </div>
  <div class="track">
    <div class="lane" id="lane"></div>
    <div class="bar-bg"><div class="bar-fill" id="bf"></div></div>
    <div class="bar-dot" id="bd"></div>
  </div>
</div>

<script>
const STAGES=[
  {at:0,   label:'Detecting Crowd...'},
  {at:.25, label:'Analyzing Density...'},
  {at:.5,  label:'Segmenting Zones...'},
  {at:.75, label:'Optimizing Flow...'},
  {at:.98, label:'Safe & Clear'}
];

const lane=document.getElementById('lane');
const bf  =document.getElementById('bf');
const bd  =document.getElementById('bd');
const pctEl=document.getElementById('pct');
const slbl =document.getElementById('slbl');

/* ── runner silhouette builder ─────────────────────────────────────
   All limb <g> elements use transform-box:fill-box so
   transform-origin percentages are relative to each element's bbox.
   Negative animation-delay pre-phases them into the cycle.
────────────────────────────────────────────────────────────────── */
const PALS=[
  // head, torso, front-limb, back-limb, shoe
  ['#e2e8f0','#94a3b8','#64748b','#475569','#1e293b'], // light grey lead
  ['#cbd5e1','#7dd3c8','#4db8b0','#2d8a82','#164e4a'], // teal
  ['#d1d5db','#9ca3af','#6b7280','#4b5563','#1f2937'], // slate
  ['#c7d2fe','#818cf8','#6366f1','#4f46e5','#1e1b4b'], // indigo
  ['#fde68a','#fbbf24','#d97706','#92400e','#451a03'], // amber
  ['#bbf7d0','#4ade80','#16a34a','#14532d','#052e16'], // green
];

function runner(i){
  const lead=i===0;
  const pal=PALS[lead?0:(i%PALS.length)];
  const [ch,ct,clf,clb,csh]=pal;
  const spd=(0.40+(i%7)*0.028).toFixed(3);
  const del=(-(i*0.072)%parseFloat(spd)).toFixed(3);
  const ds=`s ease-in-out infinite ${del}s`;
  /* all animated groups need: transform-box:fill-box + their origin */
  const G=(cls,orig,kf,extra='')=>
    `style="transform-box:fill-box;transform-origin:${orig};animation:${kf} ${spd}${ds};${extra}"`;

  return `<svg width="22" height="48" viewBox="0 0 22 48" fill="none" style="overflow:visible;display:block">
  <!-- head -->
  <circle cx="11" cy="4.8" r="4.2" fill="${ch}"/>
  <!-- torso (lean forward slightly) -->
  <g ${G('torso','50% 30%','tbob .'+spd+ds)}>
    <path d="M7.5 9.2 C9 8.2 13 8.2 14.5 9.2 L15.8 23 Q11 25.5 6.2 23 Z" fill="${ct}"/>
  </g>
  <!-- back arm (dark, swings backward first) -->
  <g ${G('barm','95% 30%','abk',``)}>
    <rect x="4.2" y="11" width="7.2" height="2.4" rx="1.2" fill="${clb}"/>
  </g>
  <!-- front arm (bright, swings forward first) -->
  <g ${G('farm','5% 30%','afk',``)}>
    <rect x="10.6" y="11" width="7.2" height="2.4" rx="1.2" fill="${clf}"/>
  </g>
  <!-- back leg -->
  <g ${G('blh','50% 0%','lbhk',``)}>
    <rect x="7.8" y="22.5" width="3.4" height="10" rx="1.7" fill="${clb}" opacity=".85"/>
    <g ${G('bls','50% 0%','lbsk',``)}>
      <rect x="7.8" y="32" width="3.2" height="8.5" rx="1.6" fill="${clb}" opacity=".78"/>
      <ellipse cx="9.5" cy="41.5" rx="4.2" ry="1.5" fill="${csh}" opacity=".7"/>
    </g>
  </g>
  <!-- front leg (brighter, in front) -->
  <g ${G('flh','50% 0%','lfhk',``)}>
    <rect x="10.8" y="22.5" width="3.4" height="10" rx="1.7" fill="${clf}"/>
    <g ${G('fls','50% 0%','lfsk',``)}>
      <rect x="10.8" y="32" width="3.2" height="8.5" rx="1.6" fill="${clf}" opacity=".9"/>
      <ellipse cx="13" cy="41.5" rx="4.2" ry="1.5" fill="${clf}" opacity=".85"/>
    </g>
  </g>
</svg>`;
}

const N=22;
const people=[];
for(let i=0;i<N;i++){
  const d=document.createElement('div');
  d.className='p';
  d.innerHTML=runner(i);
  d.style.opacity=i===0?'1':'0.82';
  lane.appendChild(d);
  people.push(d);
}

/* ── animation loop ─────────────────────────────────────────────── */
function lerp(a,b,t){return a+(b-a)*t}
function ease(t){return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2}
function col(t){
  return `rgb(${Math.round(lerp(239,34,t))},${Math.round(lerp(68,197,t))},${Math.round(lerp(68,94,t))})`;
}
function pickStage(t){let s=STAGES[0];for(const x of STAGES)if(t>=x.at)s=x;return s}

/* Duration 8 s – always plays the full cycle even for very fast runs */
const DUR=8000;
let t0=null;

function frame(ts){
  if(!t0)t0=ts;
  const raw=Math.min(1,(ts-t0)/DUR);
  const t=ease(raw);
  const lw=lane.clientWidth-26;

  /* bar */
  bf.style.width=(raw*100)+'%';
  const c=col(raw);
  bf.style.boxShadow=`0 0 ${8+raw*20}px ${c}55`;
  bd.style.left=(12+raw*lw)+'px';
  bd.style.background=c;
  bd.style.boxShadow=`0 0 18px ${c}CC`;

  /* labels */
  pctEl.textContent=Math.round(raw*100)+'%';
  pctEl.style.color=c;
  slbl.textContent=pickStage(raw).label;

  /* people */
  for(let i=0;i<N;i++){
    const lead=i===0;
    let x,y,sc,op;
    if(lead){
      /* Leader stays ahead of the crowd front edge */
      x=t*(lw-22)+4;
      y=Math.sin(ts*.009)*1.5;
      sc=1.08; op=1;
    } else {
      /* At t=0: all packed in ~first 20px (tight cluster behind leader)
         At t=1: evenly distributed from 2px to lw
         Each person has a unique stagger so they don't move in unison */
      const norm=(i-1)/(N-2);          // 0..1
      const startX=Math.min(i*1.2,20); // tight start
      const endX=norm*(lw-20)+2;       // spread target
      x=lerp(startX,endX,t);
      /* independent bob with stagger */
      y=Math.sin(ts*.009*(1+(i%5)*.04)+i*.58)*(1.5+(i%4)*.35);
      sc=0.88+t*.13;
      op=0.72+t*.25;
    }
    people[i].style.transform=`translate(${x.toFixed(1)}px,${y.toFixed(2)}px) scale(${sc.toFixed(3)})`;
    people[i].style.opacity=op.toFixed(3);
    people[i].style.zIndex=lead?'20':String(N-i);
  }

  if(raw<1) requestAnimationFrame(frame);
}

requestAnimationFrame(frame);
</script>
</body></html>"""

    anim_slot = st.empty()
    with anim_slot:
        components.html(_ANIM_HTML, height=212, scrolling=False)

    results  = {}
    for idx, seg in enumerate(segs_ready):
        img_list = st.session_state.uploaded_images[seg]
        img_srcs = st.session_state.image_sources.get(seg, [])
        results[seg] = process_segment(
            img_list, per_image_sources=img_srcs,
            combine=st.session_state.get(f"combine_{seg}", "sum"))

    anim_slot.empty()
    st.session_state.crowd_data     = results
    st.session_state.last_run_model = "mixed"

    # Record in detection history
    seg_results = {
        seg: {
            "count": r["count"],
            "risk":  risk_level(r["count"], get_seg_thresholds(seg)),
        }
        for seg, r in results.items()
    }
    hist_entry = {
        "timestamp":  datetime.now().strftime("%b %d, %Y  %H:%M"),
        "seg_count":  len(results),
        "total":      sum(r["count"] for r in results.values()),
        "critical":   sum(1 for v in seg_results.values() if v["risk"] == "Critical"),
        "high":       sum(1 for v in seg_results.values() if v["risk"] == "High Risk"),
        "results":    seg_results,
    }
    st.session_state.detection_history.insert(0, hist_entry)
    if len(st.session_state.detection_history) > 10:
        st.session_state.detection_history = st.session_state.detection_history[:10]

    st.success(
        f"Detection complete — {len(results)} segment(s) analysed. "
        "Open Analysis to review results and dispatch alerts."
    )

# ---------------------------------------------------------------------------
# Quick results preview
# ---------------------------------------------------------------------------
if st.session_state.crowd_data:
    st.markdown('<div class="section-label" style="margin-top:1.5rem">Detection Preview</div>', unsafe_allow_html=True)
    pcols = st.columns(5)
    for i, seg in enumerate(SEGMENTS):
        with pcols[i]:
            d    = st.session_state.crowd_data.get(seg)
            srcs = st.session_state.image_sources.get(seg, [])
            n_c  = sum(1 for s in srcs if s == "ground")
            n_d  = sum(1 for s in srcs if s == "drone")
            if d:
                st.metric(
                    f"Segment {seg}",
                    d["count"],
                    help=(f"Counted by the {COUNTER_LABELS.get(d.get('counter'), 'model')} · "
                          f"{n_c} CCTV, {n_d} Drone"),
                )
            else:
                st.metric(f"Segment {seg}", "—")
