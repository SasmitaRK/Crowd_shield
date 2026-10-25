"""Photo analysis: add up to four photos per zone, count every head, and see each zone's risk."""

import time
from datetime import datetime

import streamlit as st

from crowdshield import benchmark
from crowdshield.config import COUNTER_LABELS, NotEnoughMemory
from crowdshield.points import on_tile_progress
from detection import process_segment, risk_level
from shared_state import (GLOBAL_CSS, MAX_IMAGES_PER_SEGMENT, SEGMENTS, get_seg_thresholds, init_state,
                          zone_label)
from ui import nav_link, page_header, risk_pill, section

st.set_page_config(page_title="Photo analysis • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Photo analysis", "Add CCTV, drone or phone photos for each zone. The PET point model puts a dot on "
            "every head, and each zone's risk follows from its count.", "Analyse")

st.markdown(
    "<div class='card' style='display:flex;gap:2rem;flex-wrap:wrap;margin-bottom:1.2rem;padding:.9rem 1.2rem'>"
    "<div><div class='sec' style='margin:0 0 .25rem'>Counts with</div>"
    "<div style='font-size:.88rem'><b>PET point model</b>, fine-tuned on ShanghaiTech: a dot per head, "
    "corrected for undercounting</div></div>"
    "<div><div class='sec' style='margin:0 0 .25rem'>If it can't run</div>"
    "<div style='font-size:.88rem'>DM-Count density model, then YOLO</div></div>"
    "<div><div class='sec' style='margin:0 0 .25rem'>Privacy</div>"
    "<div style='font-size:.88rem'>Photos stay in this session only. No faces, no identities.</div></div>"
    "</div>",
    unsafe_allow_html=True,
)


# ── Samples: instant, nothing runs on the server ────────────────────────────
def sample_photos():
    """Hand-checked Indian photos with the model's stored head points: instant, nothing to run."""
    rows = [r for r in benchmark.load() if (benchmark.INDIA / "images" / r["image"]).exists()]
    return sorted(rows, key=lambda r: abs(r["error"]) / max(r["true"], 1))[:6]  # the model's best six


samples = sample_photos()
if samples:
    with st.container(border=True):
        top, pick = st.columns([3, 2])
        top.markdown("**No photo handy? Try a sample.** These are real Indian crowd photos that were "
                     "counted by hand, with the model's head points already computed, so this is "
                     "instant and runs nothing on the server.")
        chosen = pick.selectbox("Sample photo", samples, format_func=lambda r: r["title"][:60],
                                label_visibility="collapsed", key="sample_choice")
        if pick.button("Show the count", key="sample_show", width="stretch"):
            st.session_state.sample_shown = chosen["image"]
        shown = next((r for r in samples if r["image"] == st.session_state.get("sample_shown")), None)
        if shown:
            import cv2
            from crowdshield.detection import render_overlay

            img = cv2.imread(str(benchmark.INDIA / "images" / shown["image"]))
            overlay = render_overlay(img, [], [], None, benchmark.points_rc(shown["model_points"]))
            left, right = st.columns([3, 1])
            left.image(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB), width="stretch")
            right.metric("Model count", f"{shown['model']:.0f}")
            right.metric("Counted by hand", f"{shown['true']}")
            right.caption(f"{shown['scene']}. Photo by {shown['author']}, {shown['license']}, via "
                          f"[Wikimedia Commons]({shown['source']}).")

# ── Your photos, zone by zone ──────────────────────────────────────────────
section("Your photos", f"Up to {MAX_IMAGES_PER_SEGMENT} photos per zone (JPG or PNG). Zones without photos "
        "are skipped.")
seg_cols = st.columns(5)
for col, seg in zip(seg_cols, SEGMENTS):
    with col:
        st.markdown(f"<div style='font-weight:800;font-size:.85rem;color:#334155;margin-bottom:.3rem;"
                    f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{zone_label(seg)}</div>",
                    unsafe_allow_html=True)
        files = st.file_uploader(f"Photos of {zone_label(seg)}", type=["jpg", "jpeg", "png"],
                                 accept_multiple_files=True, key=f"photos_{seg}", label_visibility="collapsed")
        st.radio(f"Photos in Zone {seg} show", options=["sum", "max"],
                 format_func=lambda m: "Different parts: add counts" if m == "sum" else "Same area: keep highest",
                 key=f"combine_{seg}",
                 help="Adding up two photos of the same spot counts those people twice.")
        if files:
            if len(files) > MAX_IMAGES_PER_SEGMENT:
                st.caption(f"Only the first {MAX_IMAGES_PER_SEGMENT} photos are used.")
            files = files[:MAX_IMAGES_PER_SEGMENT]
            st.session_state.uploaded_images[seg] = [f.getvalue() for f in files]
            st.session_state.image_names[seg] = [f.name for f in files]
            st.session_state.image_sources[seg] = ["auto"] * len(files)

# ── Count ──────────────────────────────────────────────────────────────────
st.markdown("---")
total_imgs = sum(len(v) for v in st.session_state.uploaded_images.values())
segs_ready = [s for s in SEGMENTS if st.session_state.uploaded_images.get(s)]

c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f"<div style='font-size:.9rem;color:#334155;padding-top:.5rem'><b>{total_imgs}</b> photo(s) in "
                f"<b>{len(segs_ready)}</b> zone(s) ready to count.</div>" if segs_ready else
                "<div style='font-size:.9rem;color:#64748b;padding-top:.5rem'>Add photos to at least one zone "
                "to count.</div>", unsafe_allow_html=True)
run = c2.button("Count people", width="stretch", icon=":material/play_arrow:", disabled=not total_imgs,
                type="primary")

if run:
    results = {}
    with st.status("Counting people...", expanded=True) as status:
        bar = st.progress(0.0)
        total_photos = sum(len(st.session_state.uploaded_images[z]) for z in segs_ready)
        done_photos, started = 0, time.time()
        st.caption("The free server takes about 30 seconds per photo. A photo you have already counted comes "
                   "back instantly.")
        tile_note = st.empty()
        for idx, seg in enumerate(segs_ready):
            img_list = st.session_state.uploaded_images[seg]
            st.write(f"{zone_label(seg)}: {len(img_list)} photo(s)")
            try:
                with on_tile_progress(lambda d, n: tile_note.caption(
                        f"Counting a large photo in {n} pieces: {d} of {n} done.")):
                    results[seg] = process_segment(
                        img_list, per_image_sources=st.session_state.image_sources.get(seg, []),
                        combine=st.session_state.get(f"combine_{seg}", "sum"))
                tile_note.empty()
            except NotEnoughMemory as exc:
                status.update(label="Not enough memory on this server", state="error", expanded=True)
                st.error(str(exc))
                st.stop()
            st.write(f"{zone_label(seg)}: **{results[seg]['count']:,}** people, counted by the "
                     f"{COUNTER_LABELS.get(results[seg].get('counter'), 'model')}")
            bar.progress((idx + 1) / len(segs_ready))
            done_photos += len(img_list)
            if done_photos < total_photos:
                left = (time.time() - started) / done_photos * (total_photos - done_photos)
                st.caption(f"About {left:.0f} s left for the other {total_photos - done_photos} photo(s).")
        status.update(label=f"Counted {len(results)} zone(s)", state="complete", expanded=False)
    st.session_state.crowd_data = results

    seg_results = {seg: {"count": r["count"], "risk": risk_level(r["count"], get_seg_thresholds(seg))}
                   for seg, r in results.items()}
    st.session_state.detection_history.insert(0, {
        "timestamp": datetime.now().strftime("%b %d, %Y  %H:%M"),
        "seg_count": len(results),
        "total":     sum(r["count"] for r in results.values()),
        "results":   seg_results,
    })
    del st.session_state.detection_history[10:]

# ── Results ────────────────────────────────────────────────────────────────
data = st.session_state.crowd_data
if data:
    section("Results", "The photo with the most people in each zone, with a dot on every head.")
    cols = st.columns(len(data))
    for col, (seg, d) in zip(cols, data.items()):
        risk = risk_level(d["count"], get_seg_thresholds(seg))
        with col:
            st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;gap:.4rem'>"
                        f"<b style='font-size:.88rem'>{zone_label(seg)}</b>{risk_pill(risk)}</div>",
                        unsafe_allow_html=True)
            st.metric(f"People in zone {seg}", f"{d['count']:,}", label_visibility="collapsed",
                      help=f"Counted by the {COUNTER_LABELS.get(d.get('counter'), 'model')} from "
                           f"{d['image_count']} photo(s)")
            for r in d.get("per_image") or []:
                check = r.get("check") or {}
                if check.get("disagree"):
                    st.warning(f"Check this count: a second model found about {check['dm_count']:,} people "
                               f"where the point model found {r['count']:,}. This usually means dots on "
                               "gravel, waves or boards. Look at the dots before acting on it.",
                               icon=":material/visibility:")
            lead = max(d.get("per_image") or [{}], key=lambda r: r.get("count", 0))
            if lead.get("overlay") is not None:
                import cv2

                st.image(cv2.cvtColor(lead["overlay"], cv2.COLOR_BGR2RGB), width="stretch")
    st.caption("A count is an estimate (about 86 to 93% accurate on test photos). Look at where the dots sit: "
               "if they land on railway gravel, tiles, rails or patterned cloth instead of heads, the count is "
               "too high. This is the model's known weak spot (see India benchmark).")
    nav_link("pages/3_📊_Analysis.py", "Next: risk levels, the evacuation plan and alerts",
             ":material/arrow_forward:", "/Analysis")
