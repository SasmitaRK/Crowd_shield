"""Team and alerts: where alerts go (Telegram, email) and who looks after each zone."""

import os
import re

import streamlit as st

from crowdshield import notify
from emailer import email_configured, send_email
from shared_state import GLOBAL_CSS, SEGMENTS, init_state, telegram_chat, zone_label
from ui import kpi_cards, next_step, page_header, section

st.set_page_config(page_title="Team and alerts • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Team and alerts", "Choose who hears about danger. A Telegram chat gets one message for the whole team; "
            "each zone's contact gets an email with their own orders.", "Set up")

channels = notify.ready_channels(telegram_chat())
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
    st.markdown("**Telegram** (free, on your phone)")
    linked = st.session_state.get("telegram_chat")
    if linked:
        who = f" ({linked['name']})" if linked.get("name") else ""
        st.success(f"Alerts go to Telegram{who}.")
        b1, b2 = st.columns(2)
        if b1.button("Send a test message", key="tg_test", width="stretch"):
            ok, message = notify.send_telegram("Crowd Shield test: alerts from this app reach this chat.",
                                               chat_id=linked["id"])
            (st.success if ok else st.error)(message)
        if b2.button("Disconnect", key="tg_off", width="stretch"):
            st.session_state.pop("telegram_chat", None)
            st.rerun()
    elif notify.telegram_configured():
        st.success("Alerts go to this app's team chat.")
        if st.button("Send a test message", key="tg_test"):
            ok, message = notify.send_telegram("Crowd Shield test: alerts from this app reach this chat.")
            (st.success if ok else st.error)(message)
    elif notify.bot_ready():
        code = st.session_state.setdefault("telegram_code", notify.new_link_code())
        link, group_link = notify.connect_link(code), notify.connect_link(code, group=True)
        if not link:
            st.warning("Telegram can't be reached right now. Try again in a minute.")
        else:
            st.markdown("Get this session's alerts in Telegram. No sign-up, nothing to type.")
            st.markdown(f"1. Choose where alerts go: [just me]({link}), then press **Start**; or "
                        f"[a team group]({group_link}), such as your police or volunteer group, then pick the "
                        "group (you need to be its admin).\n"
                        "2. Come back here and press **Done**.")
            if st.button("Done", key="tg_check", type="primary", icon=":material/link:"):
                found = notify.find_chat(code)
                if found:
                    chat_id, name = found
                    st.session_state.telegram_chat = {"id": chat_id, "name": name}
                    st.session_state.pop("telegram_code", None)
                    notify.send_telegram("Crowd Shield is connected. Alerts from your session will arrive here.",
                                         chat_id=chat_id)
                    st.rerun()
                st.warning("Not found yet: open one of the links above in Telegram and finish there, then press "
                           "Done again.")
            st.caption("Your chat is linked to this browser session only and forgotten when you close it.")
    else:
        st.warning("Telegram is not set up on this server.")
    with st.expander("Running your own copy? Set up the Telegram bot"):
        st.markdown("""
1. In Telegram, open **@BotFather**, send `/newbot`, pick a name, and copy the **token** it gives you.
2. Add it as a secret: `TELEGRAM_BOT_TOKEN = "123:abc"` (on Streamlit Community Cloud: **App settings →
   Secrets**; on a laptop: an environment variable). Each user can then connect their own Telegram here.
3. Optional, for one fixed team chat (also used by the command-line monitor): open your bot, press
   **Start**, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the number after
   `"chat":{"id":`, then add it as `TELEGRAM_CHAT_ID`. For a group, add the bot first; its id starts with `-`.
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
