"""Gmail alerts: send an email, and build the two alert emails (crowded zone, receiving zone)."""

import base64
import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def email_configured() -> bool:
    return bool(os.environ.get("GMAIL_USER")
                and os.environ.get("GMAIL_APP_PASSWORD"))


def send_email(to_addr: str, subject: str, html_body: str,
               image_bytes: bytes | None = None) -> tuple[bool, str]:
    """Send a single email via Gmail SMTP.

    If `image_bytes` (raw JPEG/PNG bytes) is supplied it is embedded inline
    in the HTML via the CID `crowd_image`. Returns (success, message).
    """
    user = os.environ.get("GMAIL_USER")
    pwd  = os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pwd):
        return False, "Gmail credentials not configured."
    if not to_addr:
        return False, "Recipient address is empty."

    try:
        outer = MIMEMultipart("related")
        outer["Subject"] = subject
        outer["From"]    = user
        outer["To"]      = to_addr

        alt = MIMEMultipart("alternative")
        outer.attach(alt)
        alt.attach(MIMEText(html_body, "html"))

        if image_bytes:
            img_part = MIMEImage(image_bytes)
            img_part.add_header("Content-ID", "<crowd_image>")
            img_part.add_header("Content-Disposition", "inline",
                                filename="critical_zone.jpg")
            outer.attach(img_part)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.sendmail(user, [to_addr], outer.as_string())

        return True, f"Sent to {to_addr}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check GMAIL_APP_PASSWORD."
    except Exception as exc:
        return False, f"Failed: {exc}"


# ---------------------------------------------------------------------------
# Email template builders
# ---------------------------------------------------------------------------

def _html_wrap(header_color: str, header_text: str,
               body_html: str, has_image: bool = False) -> str:
    image_block = (
        '<div style="margin:1rem 0;border-radius:12px;overflow:hidden;'
        'border:2px solid rgba(0,0,0,.15)">'
        '<img src="cid:crowd_image" style="width:100%;max-width:680px;'
        'display:block" alt="Critical crowd zone" />'
        '<p style="margin:4px 8px;font-size:0.75em;color:#888">'
        'The busiest photo of this zone, with a dot on every head</p>'
        '</div>'
    ) if has_image else ""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a1a1a;
                       background:#f5f5f5;margin:0;padding:0">
      <div style="max-width:680px;margin:24px auto;background:#fff;
                  border-radius:16px;overflow:hidden;
                  box-shadow:0 4px 24px rgba(0,0,0,.12)">
        <!-- Header -->
        <div style="background:{header_color};padding:28px 32px">
          <h1 style="color:white;margin:0;font-size:1.5rem">
            {header_text}
          </h1>
        </div>
        <!-- Body -->
        <div style="padding:28px 32px">
          {image_block}
          {body_html}
          <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0">
          <p style="font-size:0.75em;color:#aaa;margin:0">
            Crowd Shield automated alert &nbsp;·&nbsp;
            Do not reply to this email.
          </p>
        </div>
      </div>
    </body></html>
    """


def _info_row(label: str, value: str) -> str:
    return (f'<tr><td style="padding:6px 12px 6px 0;color:#555;'
            f'white-space:nowrap"><b>{label}</b></td>'
            f'<td style="padding:6px 0">{value}</td></tr>')


def build_critical_email(seg: str, count: int,
                         target_seg: str | None, target_count: int,
                         move_count: int, risk_level: str,
                         thresholds: dict,
                         has_image: bool = False,
                         moves: list | None = None) -> tuple[str, str]:
    """Build alert email for a High Risk or Critical zone agent.

    `moves` lists every destination when the plan splits the people (dicts with target,
    target_count, move and path; a target of None means people nobody can take).
    """
    is_critical = risk_level == "Critical"
    color   = "#c0392b" if is_critical else "#e67e22"
    subject = (f"Crowd Shield alert: {'CRITICAL' if is_critical else 'HIGH RISK'} "
               f"— Zone {seg}")

    allowable = max(0, thresholds["critical"] - count)
    target_html = (
        f"Relocate to <b>Zone {target_seg}</b> "
        f"(current occupancy: {target_count})"
        if target_seg else "No safe destination — call for reinforcements"
    )
    if moves:
        lines = []
        for m in moves:
            if m["target"]:
                lines.append(f"<b>~{m['move']}</b> to <b>Zone {m['target']}</b> "
                             f"(current occupancy: {m['target_count']}), "
                             f"via {' → '.join(m['path'])}")
            else:
                lines.append(f"<b>~{m['move']}</b> have no safe destination: call for reinforcements")
        target_html = "<br>".join(lines)
        move_count = sum(m["move"] for m in moves)

    rows = "".join([
        _info_row("Zone", f"<b>{seg}</b>"),
        _info_row("Risk level", f"<b style='color:{color}'>{risk_level}</b>"),
        _info_row("Current count", f"<b>{count}</b> people detected"),
        _info_row("Safe capacity remaining",
                  f"<b style='color:{'#e74c3c' if allowable == 0 else '#27ae60'}'>"
                  f"{allowable} people</b> before Critical threshold"),
        _info_row("People to relocate", f"<b>~{move_count}</b>"),
        _info_row("Relocation target", target_html),
    ])

    body = f"""
    <p style="font-size:1.05rem;margin-top:0">
      Zone <b>{seg}</b> is at <b style="color:{color}">{risk_level}</b>.
      Immediate action required.
    </p>
    <table style="border-collapse:collapse;width:100%;margin-bottom:1.2rem">
      {rows}
    </table>

    <div style="background:#fff3f3;border:1px solid #f5c6cb;border-radius:10px;
         padding:14px 18px;margin-bottom:1.2rem">
      <b style="color:#c0392b">Entries and routes — Zone {seg}</b>
      <ul style="margin:.5rem 0 0;padding-left:1.4rem;color:#333">
        <li>Close <b>all main entry points</b> to this zone immediately.</li>
        <li>Block access routes leading directly to Zone {seg}.</li>
        <li>Post staff at entry barriers — allow <b>exit only</b>.</li>
        <li>Do not allow further crowds to enter until count drops below
            <b>{thresholds['high']}</b>.</li>
      </ul>
    </div>

    <div style="background:#fff8f0;border:1px solid #fde3c0;border-radius:10px;
         padding:14px 18px;margin-bottom:1.2rem">
      <b style="color:#e67e22">Moving people out</b>
      <ul style="margin:.5rem 0 0;padding-left:1.4rem;color:#333">
        <li>Open <b>all exit points</b> and guide people towards
            {"Zone " + target_seg if target_seg else "adjacent safe areas"}.</li>
        <li>Relocate approximately <b>{move_count} people</b> in an orderly manner.</li>
        <li>Use PA system / stewards to direct crowd flow away from dense spots.</li>
        <li>Prioritise exits nearest to the highest-density zones
            (see detection image above).</li>
      </ul>
    </div>

    {'<p style="color:#c0392b;font-weight:700">CRITICAL LEVEL REACHED — '
     'Activate emergency crowd management protocol immediately.</p>'
     if is_critical else ''}
    """

    html = _html_wrap(color,
                      f"{'CRITICAL' if is_critical else 'HIGH RISK'} — Zone {seg}",
                      body, has_image=has_image)
    return subject, html


def build_receiving_email(seg: str, count: int,
                           source_seg: str, source_count: int,
                           move_count: int,
                           thresholds: dict) -> tuple[str, str]:
    """Build notice email for the agent at the receiving (destination) zone."""
    subject = f"Crowd Shield notice: people coming to Zone {seg}"
    remaining_cap = max(0, thresholds["high"] - count - move_count)
    rows = "".join([
        _info_row("Your zone", f"<b>{seg}</b>"),
        _info_row("Your current count", f"{count} people"),
        _info_row("Incoming from", f"Zone {source_seg} ({source_count} people)"),
        _info_row("Expected arrivals", f"<b>~{move_count}</b> people"),
        _info_row("Projected count after arrival",
                  f"<b>{count + move_count}</b>"),
        _info_row("Remaining capacity to High threshold",
                  f"<b style='color:{'#e74c3c' if remaining_cap <= 5 else '#27ae60'}'>"
                  f"{remaining_cap} people</b>"),
    ])

    body = f"""
    <p style="font-size:1.05rem;margin-top:0">
      Your zone <b>{seg}</b> has been selected as a relocation destination.
      Please prepare to receive incoming crowd from Zone {source_seg}.
    </p>
    <table style="border-collapse:collapse;width:100%;margin-bottom:1.2rem">
      {rows}
    </table>
    <div style="background:#f0fff4;border:1px solid #b2dfdb;border-radius:10px;
         padding:14px 18px">
      <b style="color:#27ae60">Getting ready — Zone {seg}</b>
      <ul style="margin:.5rem 0 0;padding-left:1.4rem;color:#333">
        <li>Open entry points and ensure clear pathways for incoming crowd.</li>
        <li>Assign staff to guide arrivals to less congested sub-areas.</li>
        <li>Monitor count closely — alert if approaching
            <b>{thresholds['high']}</b> (your High Risk threshold).</li>
        <li>Keep exits unobstructed for continued flow.</li>
      </ul>
    </div>
    """

    html = _html_wrap("#27ae60",
                      f"Incoming Crowd Notice — Zone {seg}", body)
    return subject, html
