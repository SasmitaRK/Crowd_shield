"""Team and alerts: where alerts go (Telegram, email) and who looks after each zone."""

import os
import re

import streamlit as st

from crowdshield import notify
from emailer import email_configured, send_email
from shared_state import GLOBAL_CSS, SEGMENTS, init_state, zone_label
from ui import kpi_cards, next_step, page_header, section

st.set_page_config(page_title="Team and alerts • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Team and alerts", "Choose who hears about danger. A Telegram chat gets one message for the whole team; "
            "each zone's contact gets an email with their own orders.", "Set up")

channels = notify.ready_channels()
assigned = sum(1 for v in st.session_state.agents.values() if v)
kpi_cards([
    ("Alerts", "Ready" if channels else "Off", " and ".join(channels) if channels else "set up below"),
    ("Zones with a contact", f"{assigned} / 5", "for email alerts"),
    ("Alerts sent", f"{st.session_state.alert_count}", "this session"),
], accents=["#10b981" if channels else "#94a3b8", "#10b981" if assigned == 5 else "#f59e0b", "#2a78d6"])

section("1. Where alerts go", "Nothing is ever sent on its own: only when you press Send alerts on the evacuation "
        "plan, switch alerts on while watching a live camera, or press a test button here.")
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
    with st.expander("How to set up Telegram alerts (2 minutes)"):
        st.markdown("""
1. In Telegram, open **@BotFather**, send `/newbot`, pick a name, and copy the **token** it gives you.
2. Open your new bot and press **Start** (a bot can only message people who started it).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser (put your token in) and copy the
   number after `"chat":{"id":`. For a group, add the bot to it first; its id starts with `-`.
4. Add two secrets: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. On Streamlit Community Cloud this is
   **App settings → Secrets**: `TELEGRAM_BOT_TOKEN = "123:abc"` and `TELEGRAM_CHAT_ID = "123456789"`.
        """)
with mail:
    st.markdown("**Email** (Gmail), to each zone's contact below")
    if email_configured():
        st.success("Gmail is set up.")
        if st.button("Email a test to myself", key="mail_test"):
            ok, message = send_email(os.environ["GMAIL_USER"], "Crowd Shield test",
                                     "<p>Alerts from Crowd Shield reach this inbox.</p>")
            (st.success if ok else st.error)(message)
    else:
        st.warning("Gmail is not set up.")
    with st.expander("How to set up email alerts"):
        st.markdown("""
| Secret name | Value |
|---|---|
| `GMAIL_USER` | Gmail address that sends alerts |
| `GMAIL_APP_PASSWORD` | 16-character app password from Google |

1. Turn on 2-Step Verification in your [Google account security settings](https://myaccount.google.com/security).
2. Make an [app password](https://myaccount.google.com/apppasswords) and name it Crowd Shield.
3. Add both as secrets (on Streamlit Community Cloud: **App settings → Secrets**).
        """)


# ── Contacts ───────────────────────────────────────────────────────────────
section("2. Who looks after each zone", "The email address that gets a zone's orders. Zone names come from the "
        "site map once you apply one there.")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
for seg in SEGMENTS:  # fill the boxes from the saved contacts on first load
    st.session_state.setdefault(f"agent_input_{seg}", st.session_state.agents.get(seg, ""))

new_vals = {}
with st.container(border=True):
    for seg in SEGMENTS:
        saved = st.session_state.agents.get(seg, "")
        c1, c2, c3 = st.columns([3, 4, 2], vertical_alignment="center")
        c1.markdown(f"**{zone_label(seg)}**")
        new_vals[seg] = c2.text_input(f"Contact email for zone {seg}", placeholder="name@example.com",
                                      label_visibility="collapsed", key=f"agent_input_{seg}")
        c3.markdown("<span class='pill brand'>Has a contact</span>" if saved
                    else "<span class='pill neutral'>No contact yet</span>", unsafe_allow_html=True)

if st.button("Save contacts", type="primary", icon=":material/save:"):
    invalid = [s for s, v in new_vals.items() if v and not EMAIL_RE.match(v.strip())]
    if invalid:
        st.error(f"Check the email address for zone(s): {', '.join(invalid)}")
    else:
        st.session_state.agents = {s: v.strip() for s, v in new_vals.items()}
        st.success(f"Saved: {sum(1 for v in new_vals.values() if v)} of 5 zones have a contact. Contacts last for "
                   "this browser session; save your session in Settings to keep them.")
        st.rerun()

next_step("Count some people, then send the plan to your team.", "pages/3_Analysis.py",
          "Go to the evacuation plan and alerts", "/Analysis")
