"""Alert channels: Telegram (free, works on a phone) and, if set up, email.

Telegram needs two settings, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, as environment variables or
Streamlit secrets. Nothing here is sent unless something calls it: the live monitor on a new alert, the
"Send alerts" button on the evacuation plan, or a test button in Team and alerts. The token is never put in a message or an error.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org"
TIMEOUT_S = 10


def _setting(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def telegram_configured() -> bool:
    return bool(_setting("TELEGRAM_BOT_TOKEN") and _setting("TELEGRAM_CHAT_ID"))


def ready_channels() -> list[str]:
    """The alert channels that are set up, as the app names them: "Telegram" and/or "email"."""
    from emailer import email_configured

    return [name for name, ready in (("Telegram", telegram_configured()), ("email", email_configured())) if ready]


def _post(method: str, fields: dict, files: dict | None = None) -> dict:
    token = _setting("TELEGRAM_BOT_TOKEN")
    url = f"{API}/bot{token}/{method}"
    if files:
        boundary = "----crowdshield" + os.urandom(8).hex()
        body = b""
        for key, value in fields.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n").encode()
        for key, (filename, data) in files.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{filename}\"\r\n"
                     "Content-Type: image/jpeg\r\n\r\n").encode() + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        request = urllib.request.Request(url, data=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        request = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode())
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode())


def send_telegram(text: str, image_bytes: bytes | None = None) -> tuple[bool, str]:
    """Send a message (and optionally a photo) to the configured chat. Returns (ok, message)."""
    if not telegram_configured():
        return False, "Telegram is not set up (needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)."
    chat = _setting("TELEGRAM_CHAT_ID")
    try:
        if image_bytes:
            reply = _post("sendPhoto", {"chat_id": chat, "caption": text[:1024]},
                          {"photo": ("zone.jpg", image_bytes)})
        else:
            reply = _post("sendMessage", {"chat_id": chat, "text": text[:4096]})
    except urllib.error.HTTPError as exc:
        reason = {401: "the bot token is wrong", 400: "the chat id is wrong, or the bot was never started "
                  "(open the bot in Telegram and press Start)", 403: "the bot was blocked or removed from the chat",
                  404: "the bot token is wrong"}.get(exc.code, f"Telegram answered {exc.code}")
        return False, f"Telegram refused the message: {reason}."
    except Exception as exc:  # network down, timeout, bad reply
        return False, f"Could not reach Telegram ({type(exc).__name__})."
    return (True, "Sent to Telegram.") if reply.get("ok") else (False, "Telegram did not accept the message.")


def alert_text(zone: str, name: str, risk: str, count: float, per_m2: float | None = None,
               minutes_to_danger: float | None = None) -> str:
    """The text of a crowd alert: short enough to read on a lock screen."""
    head = {"Critical": "CRITICAL", "High Risk": "HIGH RISK"}.get(risk, risk.upper())
    lines = [f"Crowd Shield: {head} in zone {zone} ({name})",
             f"About {count:,.0f} people" + (f", {per_m2:.1f} per m2" if per_m2 else "") + "."]
    if minutes_to_danger is not None and minutes_to_danger > 0:
        lines.append(f"At this pace it reaches 5 per m2 in about {minutes_to_danger:.0f} min.")
    lines.append("Close entries to this zone and open its exits.")
    return "\n".join(lines)


def broadcast(text: str, image_bytes: bytes | None = None, email_to: list[str] | None = None) -> list[str]:
    """Send an alert on every channel that is set up. Returns one status line per attempt."""
    results = []
    if telegram_configured():
        ok, message = send_telegram(text, image_bytes)
        results.append(f"Telegram: {message}")
    if email_to:
        from emailer import email_configured, send_email

        if email_configured():
            for address in email_to:
                ok, message = send_email(address, "Crowd Shield alert", f"<pre>{text}</pre>", image_bytes)
                results.append(f"Email {address}: {message}")
    if not results:
        results.append("No alert channel is set up (add Telegram or Gmail in Team and alerts).")
    return results
