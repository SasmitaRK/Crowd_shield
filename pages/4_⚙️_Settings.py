"""Settings: each zone's risk limits, where alerts go, what this server can do, and resets."""

import os

import streamlit as st

from crowdshield import config, notify
from crowdshield.risk import thresholds_from_area
from crowdshield.session import BadSession, export_session, import_session
from emailer import email_configured, send_email
from shared_state import DEFAULT_THRESHOLDS, FRUIN_PRESETS, GLOBAL_CSS, SEGMENTS, init_state, zone_label
from ui import page_header, section

st.set_page_config(page_title="Settings • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Settings", "Each zone's risk limits, where alerts go, and what this server can do.", "Configure")

LEVELS = (("moderate", "Moderate from"), ("high", "High Risk from"), ("critical", "Critical from"))


def show_limits(limits: dict) -> None:
    """Put limits into the table's boxes. Runs in callbacks, before the boxes are drawn."""
    for seg, t in limits.items():
        for key, _ in LEVELS:
            st.session_state[f"lim_{key}_{seg}"] = int(t[key])


# ── Risk limits ────────────────────────────────────────────────────────────
section("Risk limits", "A zone's risk comes from how many people are in it. These are the counts at which each "
        "zone turns Moderate, High Risk and Critical. The quickest way to set them is <b>Apply map areas</b> on "
        "the Site map; you can also work them out from areas below, or type them in.")

with st.expander("Work out limits from each zone's area"):
    st.caption("Limit = area (m²) × the density standard's people per m² × camera coverage.")
    a, b = st.columns(2)
    preset_name = a.selectbox("Density standard", list(FRUIN_PRESETS), index=1,
                              help="People per m² at which each risk level starts (after Fruin's Level of Service).")
    coverage = b.slider("Share of each zone the cameras see", 0.50, 1.00, 0.75, 0.05,
                        help="Photos that show only part of a zone count fewer people than are there, so the "
                             "limits are lowered by the same share to stay on the safe side.")
    preset = FRUIN_PRESETS[preset_name]
    st.caption(f"{preset_name}: Moderate from {preset['moderate']}, High Risk from {preset['high']} and Critical "
               f"from {preset['critical']} people per m².")
    areas = {}
    for col, seg in zip(st.columns(5), SEGMENTS):
        areas[seg] = col.number_input(f"{zone_label(seg)} (m²)", 0, 1_000_000,
                                      int(st.session_state.seg_areas.get(seg, 0)), 10, key=f"area_{seg}")

    def apply_areas():
        new = {s: thresholds_from_area(v, preset, coverage) for s, v in areas.items() if v > 0}
        st.session_state.seg_areas.update(areas)
        st.session_state.thresholds.update(new)
        show_limits(new)
        st.session_state.limits_note = (f"Worked out limits for zone(s) {', '.join(new)}." if new else
                                        "Enter an area for at least one zone.")

    st.button("Work out and apply", on_click=apply_areas, disabled=not any(areas.values()))

for seg in SEGMENTS:  # first visit: fill the boxes from the saved limits
    if f"lim_moderate_{seg}" not in st.session_state:
        show_limits({seg: st.session_state.thresholds.get(seg, DEFAULT_THRESHOLDS)})

with st.container(border=True):
    widths = [3, 2, 2, 2]
    for col, title in zip(st.columns(widths), ["Zone"] + [label for _, label in LEVELS]):
        col.markdown(f"<div class='sec' style='margin:.1rem 0'>{title}</div>", unsafe_allow_html=True)
    for seg in SEGMENTS:
        cols = st.columns(widths, vertical_alignment="center")
        cols[0].markdown(f"**{zone_label(seg)}**")
        for col, (key, label) in zip(cols[1:], LEVELS):
            col.number_input(f"{label}, zone {seg}", 1, 1_000_000, step=5, key=f"lim_{key}_{seg}",
                             label_visibility="collapsed")


def save_limits():
    new = {seg: {key: st.session_state[f"lim_{key}_{seg}"] for key, _ in LEVELS} for seg in SEGMENTS}
    bad = [seg for seg, t in new.items() if not t["moderate"] < t["high"] < t["critical"]]
    if bad:
        st.session_state.limits_note = (f"Not saved: in zone(s) {', '.join(bad)} each limit must be higher than "
                                        "the one before it.")
    else:
        st.session_state.thresholds = new
        st.session_state.limits_note = "Saved."


st.button("Save limits", type="primary", on_click=save_limits)
note = st.session_state.pop("limits_note", None)
if note:
    (st.error if note.startswith("Not saved") else st.success)(note)

# ── Alert channels ─────────────────────────────────────────────────────────
section("Alert channels", "Where Crowd Shield sends alerts. Nothing is sent unless you press Send alerts on Alerts "
        "and plans, switch alerts on in Live feed, or press a test button here.")
tg, mail = st.columns(2)
with tg:
    st.markdown("**Telegram** (free, works on a phone)")
    if notify.telegram_configured():
        st.success("Telegram is set up.")
        if st.button("Send a test message", key="tg_test"):
            ok, message = notify.send_telegram("Crowd Shield test: alerts from this app reach this chat.")
            (st.success if ok else st.error)(message)
    else:
        st.warning("Telegram is not set up.")
    with st.expander("How to set up Telegram alerts (2 minutes)", expanded=not notify.telegram_configured()):
        st.markdown("""
1. In Telegram, open **@BotFather**, send `/newbot`, pick a name, and copy the **token** it gives you.
2. Open your new bot and press **Start** (a bot can only message people who started it).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser (put your token in) and copy the
   number after `"chat":{"id":`. For a group, add the bot to it first; its id starts with `-`.
4. Add two secrets: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. On Streamlit Community Cloud this is
   **App settings → Secrets**: `TELEGRAM_BOT_TOKEN = "123:abc"` and `TELEGRAM_CHAT_ID = "123456789"`.
        """)
with mail:
    st.markdown("**Email** (Gmail), one contact per zone on Response team")
    if email_configured():
        st.success("Gmail is set up.")
        if st.button("Email a test to myself", key="mail_test"):
            ok, message = send_email(os.environ["GMAIL_USER"], "Crowd Shield test",
                                     "<p>Alerts from Crowd Shield reach this inbox.</p>")
            (st.success if ok else st.error)(message)
    else:
        st.warning("Gmail is not set up.")
    with st.expander("How to set up email alerts", expanded=not email_configured()):
        st.markdown("""
| Secret name | Value |
|---|---|
| `GMAIL_USER` | Gmail address that sends alerts |
| `GMAIL_APP_PASSWORD` | 16-character app password from Google |

1. Turn on 2-Step Verification at <https://myaccount.google.com/security>.
2. Make an app password at <https://myaccount.google.com/apppasswords> (name it Crowd Shield).
3. Add both as secrets (on Streamlit Community Cloud: **App settings → Secrets**).
        """)

# ── Server ─────────────────────────────────────────────────────────────────
section("Server", "What this server can hold, and how it will count a photo right now. A server too small to run "
        "a photo in one pass counts it in tiles, which keeps the detail. If even a tile would not fit, the app "
        "says so instead of crashing.")
limit, used, own = config.memory_limit_bytes(), config.memory_in_use_bytes(), config.own_rss_bytes()
gb = lambda b: "unknown" if b is None else f"{b / 1e9:.1f} GB"  # noqa: E731
work = config.default_work_side()
try:
    fit = config.fit_max_side(ceiling=work)
    how = "one pass" if fit >= work else f"tiles of {fit} px"
except config.NotEnoughMemory:
    how = "none fits"
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Memory limit", gb(limit))
c2.metric("In use", gb(used), help="Memory used by everything running on this server.")
c3.metric("This app", gb(own))
c4.metric("Photo detail", f"{work} px", help="Photos are shrunk to this size (longer side) before counting.")
c5.metric("Counted in", how, help="One pass if it fits in memory, otherwise tiles with a little overlap.")
st.caption(f"Running from `{config.REPO_ROOT}`"
           f"{' (Streamlit Community Cloud)' if config.on_streamlit_cloud() else ''}.")

# ── Save and load ──────────────────────────────────────────────────────────
section("Save and load your work", "Nothing is stored on the server, so closing the tab clears your counts, limits, "
        "contacts and drawn site. Save them to a file on your computer and load them next time. Photos are not "
        "saved, only the numbers.")
s1, s2 = st.columns(2)
with s1:
    st.download_button("Save my session (JSON file)", export_session(st.session_state),
                       file_name="crowd_shield_session.json", mime="application/json", width="stretch",
                       icon=":material/download:")
with s2:
    saved = st.file_uploader("Load a saved session", type=["json"], label_visibility="collapsed",
                             key="session_file")
    if saved is not None and st.button("Load it", width="stretch", icon=":material/upload:"):
        try:
            loaded = import_session(saved.getvalue().decode("utf-8", errors="replace"))
        except BadSession as exc:
            st.error(str(exc))
        else:
            for key, value in loaded.items():
                st.session_state[key] = value
            for seg in SEGMENTS:  # the boxes on this and other pages read these keys first
                st.session_state.pop(f"agent_input_{seg}", None)
                st.session_state.pop(f"area_{seg}", None)
            show_limits(st.session_state.thresholds)
            st.success("Loaded: " + ", ".join({"crowd_data": "counts", "thresholds": "risk limits",
                                              "agents": "contacts", "custom_site": "drawn site",
                                              "zone_names": "zone names"}.get(k, k) for k in loaded) + ".")

# ── Reset ──────────────────────────────────────────────────────────────────
section("Reset", "Everything here lasts for this browser session only; these clear it sooner.")


def clear_photos():
    for key in ("uploaded_images", "image_names", "image_sources"):
        st.session_state[key] = {s: [] for s in SEGMENTS}
    st.session_state.crowd_data = {}


def clear_contacts():
    st.session_state.agents = {s: "" for s in SEGMENTS}
    for seg in SEGMENTS:
        st.session_state.pop(f"agent_input_{seg}", None)


def reset_limits():
    st.session_state.thresholds = {s: dict(DEFAULT_THRESHOLDS) for s in SEGMENTS}
    show_limits(st.session_state.thresholds)


r1, r2, r3 = st.columns(3)
r1.button("Clear photos and counts", width="stretch", on_click=clear_photos)
r2.button("Clear contacts", width="stretch", on_click=clear_contacts)
r3.button(f"Reset limits to {DEFAULT_THRESHOLDS['moderate']} / {DEFAULT_THRESHOLDS['high']} / "
          f"{DEFAULT_THRESHOLDS['critical']}", width="stretch", on_click=reset_limits)
