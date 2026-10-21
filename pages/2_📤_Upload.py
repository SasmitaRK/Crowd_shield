"""Upload page — two-channel input (CCTV + Drone) with automatic model routing."""

from datetime import datetime
import streamlit as st

from ui import page_header

from shared_state import (init_state, GLOBAL_CSS, SEGMENTS,
                          MAX_IMAGES_PER_SEGMENT, get_seg_thresholds)
from detection import process_segment, MODEL_REGISTRY, risk_level
from crowdshield.config import COUNTER_LABELS

st.set_page_config(page_title="Upload • Crowd Shield",
                   page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Photo analysis", "Add CCTV, drone or phone photos for each zone. The PET point model puts a dot on every head and the zone's risk follows from its count.", "Analyse")

st.markdown(
    "<div class='card' style='display:flex;gap:2rem;flex-wrap:wrap;margin-bottom:1.2rem;padding:.9rem 1.2rem'>"
    "<div><div class='sec' style='margin:0 0 .25rem'>Counts with</div>"
    "<div style='font-size:.88rem'><b>PET point model</b>, fine-tuned on ShanghaiTech: a dot per head, "
    "corrected for undercounting</div></div>"
    "<div><div class='sec' style='margin:0 0 .25rem'>Falls back to</div>"
    "<div style='font-size:.88rem'>DM-Count density model, then YOLO (the CCTV / drone tag picks which)</div></div>"
    "<div><div class='sec' style='margin:0 0 .25rem'>Privacy</div>"
    "<div style='font-size:.88rem'>Photos stay in this session only. No faces, no identities.</div></div>"
    "</div>",
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
              Zone {seg}
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
            f"CCTV — Zone {seg}",
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
            f"Drone — Zone {seg}",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"drone_{seg}",
            label_visibility="collapsed",
        )

        st.radio(
            f"Photos in Zone {seg} show",
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
            f"<b>{len(segs_ready)}</b> zone(s) ready — "
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
    run = st.button("Count people", width="stretch", icon=":material/play_arrow:",
                    disabled=(total_imgs == 0), type="primary")

if run:
    results = {}
    with st.status("Counting people...", expanded=True) as status:
        bar = st.progress(0.0)
        for idx, seg in enumerate(segs_ready):
            img_list = st.session_state.uploaded_images[seg]
            st.write(f"Zone {seg}: {len(img_list)} photo(s)")
            results[seg] = process_segment(
                img_list, per_image_sources=st.session_state.image_sources.get(seg, []),
                combine=st.session_state.get(f"combine_{seg}", "sum"))
            st.write(f"Zone {seg}: **{results[seg]['count']:,}** people, counted by the "
                     f"{COUNTER_LABELS.get(results[seg].get('counter'), 'model')}")
            bar.progress((idx + 1) / len(segs_ready))
        status.update(label=f"Counted {len(results)} zone(s)", state="complete", expanded=False)
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
        f"Done: {len(results)} zone(s) counted. Open **Alerts and plans** for risk levels, "
        "the relocation plan and email alerts."
    )

# ---------------------------------------------------------------------------
# Quick results preview
# ---------------------------------------------------------------------------
if st.session_state.crowd_data:
    st.markdown('<div class="sec">Results</div>', unsafe_allow_html=True)
    pcols = st.columns(5)
    for i, seg in enumerate(SEGMENTS):
        with pcols[i]:
            d    = st.session_state.crowd_data.get(seg)
            srcs = st.session_state.image_sources.get(seg, [])
            n_c  = sum(1 for s in srcs if s == "ground")
            n_d  = sum(1 for s in srcs if s == "drone")
            if d:
                st.metric(
                    f"Zone {seg}",
                    d["count"],
                    help=(f"Counted by the {COUNTER_LABELS.get(d.get('counter'), 'model')} · "
                          f"{n_c} CCTV, {n_d} Drone"),
                )
            else:
                st.metric(f"Zone {seg}", "—")
