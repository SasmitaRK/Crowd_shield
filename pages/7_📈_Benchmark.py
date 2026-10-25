"""How accurate is it? The counter on standard test photos and on hand-counted Indian crowd photos."""

import html

import altair as alt
import cv2
import pandas as pd
import streamlit as st

from crowdshield.benchmark import INDIA, accuracy, by_scene, load
from shared_state import GLOBAL_CSS, init_state
from ui import kpi_cards, next_step, page_header, section

st.set_page_config(page_title="How accurate is it? • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

rows = load()
total_photos = len(list((INDIA / "images").glob("*.jpg"))) if (INDIA / "images").exists() else 0
page_header("How accurate is it?", "On standard test photos the counter gets 86.5% of packed crowds and 92.7% of "
            "street crowds right. It learned from Chinese photos, so here is how it does on Indian crowds, photo by "
            "photo, against heads counted by hand. None of these photos were used to train it.", "Proof",
            pills=[(f"{len(rows)} of {total_photos} photos hand-checked", "brand"),
                   ("Pilot: labelling in progress", "warn")])

if not rows:
    st.info("No hand-checked labels yet.")
    st.stop()

acc = accuracy(rows)
mae = sum(abs(r["error"]) for r in rows) / len(rows)
worst = max(rows, key=lambda r: abs(r["error"]))
others = [r for r in rows if r is not worst]
kpi_cards([
    ("Accuracy, all photos", f"{acc:.1%}", "1 − total error ÷ total true count"),
    ("Off by, per photo", f"{mae:,.0f}", "mean absolute error (people)"),
    ("Without the worst photo", f"{accuracy(others):.1%}", f"leaving out {worst['image']}"),
    ("Heads checked by hand", f"{sum(r['true'] for r in rows):,}", f"in {len(rows)} photos"),
], accents=["#0d9488", "#2a78d6", "#94a3b8", "#1baf7a"])

st.markdown(
    f"<div class='card' style='margin-top:1rem;font-size:.9rem'><b>Known failure:</b> on "
    f"<b>{html.escape(worst['title'])}</b> the model counted <b>{worst['model']:,.0f}</b> against "
    f"<b>{worst['true']:,}</b> real people, because the gravel between railway tracks looks like a sea of "
    f"heads from above. Fine-tuning on empty-track photos fixed that photo but made the model miss people in "
    f"smaller crowds, so the app keeps the current model and reports the failure here.</div>",
    unsafe_allow_html=True)

# ── By scene ───────────────────────────────────────────────────────────────
left, right = st.columns([5, 6], gap="large")
with left:
    section("By scene")
    scenes = pd.DataFrame(by_scene(rows))
    scenes["accuracy"] = scenes["accuracy"].clip(lower=0)
    st.dataframe(scenes, hide_index=True, width="stretch", column_config={
        "scene": "Scene", "photos": "Photos", "people": st.column_config.NumberColumn("People", format="%d"),
        "accuracy": st.column_config.ProgressColumn("Accuracy", min_value=0.0, max_value=1.0, format="percent"),
        "mae": st.column_config.NumberColumn("Off by (per photo)", format="%.0f"),
    })
    st.caption("Accuracy below zero (more error than people) is shown as 0. Scenes with one or two "
               "photos are a hint, not a result, until more photos are labelled.")

with right:
    section("Model count against the true count")
    df = pd.DataFrame([{"Photo": r["image"], "Scene": r["scene"], "True": r["true"],
                        "Model": round(r["model"]), "Error": round(r["error"])} for r in rows])
    top = max(df["True"].max(), df["Model"].max()) * 1.08
    line = alt.Chart(pd.DataFrame({"x": [1, top], "y": [1, top]})).mark_line(
        color="#94a3b8", strokeDash=[4, 4]).encode(x="x", y="y")
    dots = alt.Chart(df).mark_circle(size=110, color="#2a78d6", opacity=0.85,
                                     stroke="#ffffff", strokeWidth=1.5).encode(
        x=alt.X("True:Q", title="True count (hand-checked)", scale=alt.Scale(type="log", domain=[10, top])),
        y=alt.Y("Model:Q", title="Model count", scale=alt.Scale(type="log", domain=[10, top])),
        tooltip=["Photo", "Scene", "True", "Model", "Error"])
    st.altair_chart((line + dots).properties(height=330), width="stretch")
    st.caption("Each dot is a photo; on the dashed line the model is exactly right. Above it, the model "
               "counted too many.")

# ── Gallery ────────────────────────────────────────────────────────────────
section("Look at any photo", "Blue rings are the hand-checked heads, orange dots are the model's. "
        "Grey boxes are ignore zones, left out of both counts.")
names = [r["image"] for r in rows]
pick = st.selectbox("Photo", names, format_func=lambda n: next(
    f"{r['image']} · {r['scene']} · true {r['true']:,}, model {r['model']:,.0f}" for r in rows if r["image"] == n))
r = next(r for r in rows if r["image"] == pick)
img = cv2.imread(str(INDIA / "images" / pick))
if img is not None:
    def draw(points, colour, ring):
        out = img.copy()
        for x0, y0, x1, y1 in r["ignore"]:
            sub = out[int(y0):int(y1), int(x0):int(x1)]
            sub[:] = (0.45 * sub + 0.55 * 60).astype(sub.dtype)
        for x, y in points:
            if ring:
                cv2.circle(out, (int(x), int(y)), 7, colour, 2, cv2.LINE_AA)
            else:
                cv2.circle(out, (int(x), int(y)), 4, colour, -1, cv2.LINE_AA)
        return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)

    a, b = st.columns(2)
    a.image(draw(r["truth_points"], (214, 120, 42), True), caption=f"Hand-checked: {r['true']:,} heads",
            width="stretch")
    b.image(draw(r["model_points"], (52, 104, 235), False),
            caption=f"Model: {len(r['model_points']):,} points, {r['model']:,.0f} after count correction",
            width="stretch")
    st.caption(f"Photo: {html.escape(r['author'] or 'unknown')}, {r['license']}, via Wikimedia Commons "
               f"({r['source']}).")

with st.expander("How this is measured"):
    st.markdown("""
- **Photos:** freely licensed Wikimedia Commons photos of Indian crowds, credited in
  `data/india_test/sources.csv`. They're used only for testing, never for training.
- **Truth:** the model's points were loaded as suggestions, then a person added every missed head,
  removed wrong points and drew ignore zones over people too small or blurry to mark. A second reviewer
  audited each photo with zoomed crops.
- **Model count:** the PET point model's raw points outside the ignore zones, through the same count
  correction the app uses (fitted on held-out ShanghaiTech photos, never on these).
- **Accuracy:** 1 − total absolute error ÷ total true count, the same measure as on ShanghaiTech.
""")

next_step("Try it yourself on a photo of a crowd, or on one of these Indian samples.", "pages/2_📤_Upload.py",
          "Count people in a photo", "/Upload")
