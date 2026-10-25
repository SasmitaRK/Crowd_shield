"""Crowd Shield's design system: one stylesheet and a few page building blocks.

Every page calls `GLOBAL_CSS` once, then builds its top with `page_header` and
its summary row with `kpi_cards`, so the whole app shares one look: a light
working area, a dark navigation rail, Inter type, teal for actions and the four
risk colours used only for risk.
"""

from __future__ import annotations

import html

import streamlit as st

RISK_STYLE = {  # text colour, background, border
    "Safe":      ("#047857", "#ecfdf5", "#a7f3d0"),
    "Moderate":  ("#b45309", "#fffbeb", "#fde68a"),
    "High Risk": ("#c2410c", "#fff7ed", "#fed7aa"),
    "Critical":  ("#b91c1c", "#fef2f2", "#fecaca"),
}

GLOBAL_CSS = """
<style>
  :root {
    --bg: #f5f7fa; --surface: #ffffff; --surface-2: #f8fafc; --border: #e3e8ef; --border-strong: #cfd8e3;
    --text: #0f172a; --text-2: #334155; --muted: #64748b; --faint: #94a3b8;
    --brand: #0d9488; --brand-600: #0f766e; --brand-50: #f0fdfa; --brand-100: #ccfbf1;
    --ink: #0b1220; --ink-2: #131d33;
    --safe: #10b981; --moderate: #f59e0b; --high: #f97316; --critical: #ef4444;
    --radius: 14px; --radius-sm: 10px;
    --shadow-sm: 0 1px 2px rgba(15,23,42,.05);
    --shadow: 0 1px 3px rgba(15,23,42,.06), 0 6px 16px -8px rgba(15,23,42,.10);
    --shadow-lg: 0 10px 30px -12px rgba(15,23,42,.25);
  }

  /* ── Frame ────────────────────────────────────────────── */
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stDecoration"] { display: none; }
  .main .block-container, [data-testid="stMainBlockContainer"] {
    max-width: 1320px; padding-top: 2rem; padding-left: 2.25rem; padding-right: 2.25rem;
  }
  .stApp { background: var(--bg); }
  h1, h2, h3, h4 { letter-spacing: -0.02em; color: var(--text); }
  h1 { font-size: 1.85rem !important; }
  h2 { font-size: 1.35rem !important; }
  h3 { font-size: 1.1rem !important; }
  h4 { font-size: 1rem !important; }
  code { font-size: .82em; }

  /* ── Navigation rail ──────────────────────────────────── */
  [data-testid="stSidebar"] { border-right: 1px solid #1e293b; }
  [data-testid="stSidebarNav"] a { border-radius: 9px; margin: 1px 0; }
  [data-testid="stSidebarNav"] a[aria-current="page"] {
    background: rgba(45,212,191,.12) !important; box-shadow: inset 3px 0 0 #2dd4bf;
  }
  [data-testid="stSidebarNav"] a[aria-current="page"] span { color: #ecfeff !important; font-weight: 600; }
  [data-testid="stSidebarNavSeparator"] { border-color: #1e293b; }
  [data-testid="stNavSectionHeader"] {
    font-size: .68rem !important; letter-spacing: .14em; text-transform: uppercase; color: #64748b !important;
    font-weight: 700 !important; margin-top: .6rem;
  }
  .rail-foot { font-size: .72rem; color: #64748b; line-height: 1.5; padding: .25rem .2rem; }
  .rail-foot a { color: #5eead4 !important; text-decoration: none; }
  .rail-status { display: flex; align-items: center; gap: .45rem; font-size: .74rem; color: #94a3b8; margin: .15rem 0; }
  .rail-status i { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

  /* ── Page header ──────────────────────────────────────── */
  .ph { display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; flex-wrap: wrap;
        margin: 0 0 1.4rem; padding-bottom: 1.1rem; border-bottom: 1px solid var(--border); }
  .ph .eyebrow { font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
                 color: var(--brand); display: flex; align-items: center; gap: .45rem; }
  .ph h1 { margin: .25rem 0 .3rem !important; padding: 0 !important; font-weight: 800 !important; line-height: 1.15; }
  .ph p { margin: 0; color: var(--muted); font-size: .93rem; max-width: 780px; line-height: 1.55; }
  .ph .side { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--safe); display: inline-block;
              animation: cs-live 1.8s infinite; }
  @keyframes cs-live { 0% { box-shadow: 0 0 0 0 rgba(16,185,129,.55); }
                       70% { box-shadow: 0 0 0 8px rgba(16,185,129,0); }
                       100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); } }

  /* ── Pills and chips ──────────────────────────────────── */
  .pill { display: inline-flex; align-items: center; gap: .35rem; padding: .2rem .6rem; border-radius: 999px;
          font-size: .72rem; font-weight: 700; letter-spacing: .02em; border: 1px solid transparent; white-space: nowrap; }
  .pill.neutral { background: var(--surface); color: var(--text-2); border-color: var(--border); }
  .pill.brand { background: var(--brand-50); color: var(--brand-600); border-color: var(--brand-100); }
  .pill.warn { background: #fffbeb; color: #92400e; border-color: #fde68a; }

  /* ── KPI cards ────────────────────────────────────────── */
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
         padding: .95rem 1.05rem; box-shadow: var(--shadow-sm); height: 100%; position: relative; overflow: hidden; }
  .kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent, transparent); }
  .kpi .label { font-size: .68rem; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; font-weight: 700; }
  .kpi .value { font-size: 1.6rem; font-weight: 800; color: var(--text); line-height: 1.15; margin-top: .25rem;
                font-variant-numeric: tabular-nums; white-space: nowrap; }
  .kpi .sub { font-size: .77rem; color: var(--muted); margin-top: .15rem; white-space: nowrap; overflow: hidden;
              text-overflow: ellipsis; }

  /* ── Section titles ───────────────────────────────────── */
  .section-label, .sec { font-size: .7rem; font-weight: 800; text-transform: uppercase; letter-spacing: .13em;
                         color: var(--muted); margin: 1.4rem 0 .7rem; display: flex; align-items: center; gap: .6rem; }
  .sec::after { content: ""; flex: 1; height: 1px; background: var(--border); }
  .sec-cap { color: var(--muted); font-size: .86rem; margin: -.35rem 0 .8rem; }

  /* ── Cards (new and legacy names) ─────────────────────── */
  .card, .glass-card, .metric-card { background: var(--surface); border: 1px solid var(--border);
         border-radius: var(--radius); padding: 1.1rem 1.2rem; box-shadow: var(--shadow-sm); color: var(--text); }
  .metric-card { text-align: left; }
  .feature-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                  padding: 1.35rem 1.3rem; box-shadow: var(--shadow-sm); height: 100%;
                  transition: box-shadow .2s ease, transform .2s ease, border-color .2s ease; }
  .feature-card:hover { box-shadow: var(--shadow); transform: translateY(-2px); border-color: var(--border-strong); }
  .feature-icon { width: 40px; height: 40px; background: var(--brand-50); border: 1px solid var(--brand-100);
                  border-radius: 10px; display: flex; align-items: center; justify-content: center;
                  margin-bottom: .9rem; color: var(--brand); }
  .feature-card h3 { font-size: .98rem !important; margin: 0 0 .35rem 0 !important; }
  .feature-card p { font-size: .86rem; color: var(--muted); line-height: 1.6; margin: 0; }

  /* ── Risk badges and alerts (legacy names kept) ───────── */
  .risk-badge { display: inline-block; padding: .2rem .65rem; border-radius: 999px; font-weight: 700;
                font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; border: 1px solid transparent; }
  .risk-safe     { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
  .risk-moderate { background: #fffbeb; color: #b45309; border-color: #fde68a; }
  .risk-high     { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
  .risk-critical { background: #fef2f2; color: #b91c1c; border-color: #fecaca; animation: cs-pulse 1.4s ease-in-out infinite; }
  @keyframes cs-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,.35); } 50% { box-shadow: 0 0 0 6px rgba(239,68,68,0); } }
  .alert-card { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid;
                border-radius: var(--radius-sm); padding: .9rem 1.1rem; margin-bottom: .65rem; font-size: .9rem;
                line-height: 1.6; color: var(--text); box-shadow: var(--shadow-sm); }
  .alert-safe     { border-left-color: var(--safe); }
  .alert-moderate { border-left-color: var(--moderate); }
  .alert-high     { border-left-color: var(--high); }
  .alert-critical { border-left-color: var(--critical); background: #fffafa; }

  /* ── Hero (dashboard) ─────────────────────────────────── */
  .hero { position: relative; overflow: hidden; border-radius: 18px; padding: 2.2rem 2.2rem 2rem;
          background: radial-gradient(1200px 400px at 85% -10%, rgba(45,212,191,.22), transparent 60%),
                      radial-gradient(800px 300px at 0% 120%, rgba(42,120,214,.25), transparent 60%),
                      linear-gradient(135deg, #0b1220 0%, #0f1b33 55%, #0b2a2c 100%);
          color: #e2e8f0; border: 1px solid #1e293b; box-shadow: var(--shadow-lg); margin-bottom: 1.4rem; }
  .hero h1 { color: #ffffff !important; font-size: 2.3rem !important; line-height: 1.1; margin: .5rem 0 .6rem !important;
             max-width: 720px; }
  .hero p { color: #a5b4c8; font-size: 1rem; max-width: 640px; line-height: 1.65; margin: 0 0 1.2rem; }
  .hero .eyebrow { color: #5eead4; font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
                   display: flex; align-items: center; gap: .5rem; }
  .hero .stats { display: flex; gap: 2.2rem; flex-wrap: wrap; margin-top: 1.3rem; }
  .hero .stat b { display: block; color: #fff; font-size: 1.55rem; font-weight: 800; letter-spacing: -.02em;
                  font-variant-numeric: tabular-nums; }
  .hero .stat span { color: #8ea0b8; font-size: .76rem; }
  .hero-grid { position: absolute; inset: 0; pointer-events: none; opacity: .35;
               background-image: radial-gradient(rgba(148,163,184,.35) 1px, transparent 1px);
               background-size: 22px 22px; mask-image: linear-gradient(90deg, transparent, #000 60%); }
  .hero-dots { position: absolute; right: 2.2rem; top: 50%; transform: translateY(-50%); width: 300px; height: 190px; }
  .hero-dots circle { animation: cs-float 3.6s ease-in-out infinite; }
  @keyframes cs-float { 0%,100% { opacity: .35; } 50% { opacity: 1; } }
  @media (max-width: 1100px) { .hero-dots { display: none; } }
  @media (max-width: 640px) {  /* phones: less frame, smaller type, numbers two by two */
    .main .block-container, [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; padding-top: 3rem; }
    .hero { padding: 1.4rem 1.2rem 1.3rem; border-radius: 14px; }
    .hero h1 { font-size: 1.65rem !important; }
    .hero p { font-size: .92rem; }
    .hero .stats { display: grid; grid-template-columns: 1fr 1fr; gap: .9rem 1.2rem; }
    .hero .stat b { font-size: 1.25rem; }
    .ph h1 { font-size: 1.5rem !important; }
  }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

  /* ── Loading: one look everywhere ──────────────────────── */
  /* Streamlit's corner "Running..." figure becomes a slim teal line along the top while the app works. */
  [data-testid="stStatusWidget"] { position: fixed !important; top: 0; left: 0; right: 0; height: 3px;
    z-index: 999999; overflow: hidden; background: rgba(13,148,136,.15); }
  [data-testid="stStatusWidget"] > * { display: none !important; }
  [data-testid="stStatusWidget"]::after { content: ""; position: absolute; top: 0; bottom: 0; width: 30%;
    background: linear-gradient(90deg, transparent, #14b8a6, transparent); animation: cs-sweep 1.1s ease-in-out infinite; }
  @keyframes cs-sweep { 0% { left: -30%; } 100% { left: 100%; } }
  .cs-load { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
             padding: 1rem 1.15rem; box-shadow: var(--shadow-sm); margin: .4rem 0 1rem; }
  .cs-load .t { font-weight: 700; font-size: .95rem; color: var(--text); display: flex; align-items: center; gap: .55rem; }
  .cs-load .t i { width: 9px; height: 9px; border-radius: 50%; background: var(--brand); display: inline-block;
                  animation: cs-live 1.6s infinite; }
  .cs-load .d { font-size: .82rem; color: var(--muted); margin: .25rem 0 .7rem; }
  .cs-load .track { position: relative; height: 6px; border-radius: 99px; background: var(--brand-50); overflow: hidden; }
  .cs-load .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 99px;
                   background: linear-gradient(90deg, #0d9488, #2dd4bf); transition: width .4s ease; }
  .cs-load .sweep { position: absolute; top: 0; bottom: 0; width: 35%; border-radius: 99px;
                    background: linear-gradient(90deg, transparent, #2dd4bf, transparent); animation: cs-sweep 1.3s ease-in-out infinite; }
  [data-testid="stSpinner"] i { border-top-color: var(--brand) !important; }

  /* ── Widgets ──────────────────────────────────────────── */
  .stButton > button, .stDownloadButton > button, [data-testid="stPageLink"] a {
    border-radius: 10px !important; font-weight: 600 !important;
  }
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    box-shadow: 0 1px 2px rgba(13,148,136,.25), 0 4px 12px -4px rgba(13,148,136,.45);
  }
  [data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--radius) !important; }
  div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { background: var(--surface); }
  [data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                             padding: .8rem 1rem; box-shadow: var(--shadow-sm); }
  [data-testid="stMetricLabel"] p { font-size: .72rem !important; text-transform: uppercase; letter-spacing: .08em;
                                    color: var(--muted) !important; font-weight: 700 !important; }
  [data-testid="stMetricValue"] { font-weight: 800; font-variant-numeric: tabular-nums; }
  .stTabs [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--border); }
  .stTabs [data-baseweb="tab"] { font-weight: 600; padding: .5rem .9rem; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: var(--radius-sm); overflow: hidden; }
  [data-testid="stExpander"] details { border-radius: var(--radius-sm) !important; background: var(--surface); }
  [data-testid="stFileUploaderDropzone"] { border-radius: var(--radius-sm); background: var(--surface-2); }
  [data-testid="stAlert"] { border-radius: var(--radius-sm); }
  hr { border-color: var(--border) !important; }
</style>
"""


def page_header(title: str, subtitle: str = "", eyebrow: str = "", live: bool = False,
                pills: list[tuple[str, str]] | None = None) -> None:
    """The top of every page: a small eyebrow, the title, one line on what the page is for,
    and optional status pills on the right as (text, kind) with kind neutral/brand/warn."""
    dot = "<span class='live-dot'></span>" if live else ""
    side = "".join(f"<span class='pill {kind}'>{html.escape(text)}</span>" for text, kind in pills or [])
    st.markdown(
        f"<div class='ph'><div><div class='eyebrow'>{dot}{html.escape(eyebrow)}</div>"
        f"<h1>{html.escape(title)}</h1>"
        + (f"<p>{subtitle}</p>" if subtitle else "")
        + f"</div><div class='side'>{side}</div></div>",
        unsafe_allow_html=True)


def kpi_cards(items: list[tuple], accents: list[str] | None = None) -> None:
    """A row of summary cards; each item is (label, value, sub). `accents` colours their left edge."""
    cols = st.columns(len(items))
    for i, (col, (label, value, sub)) in enumerate(zip(cols, items)):
        accent = f"--accent:{accents[i]};" if accents and accents[i] else ""
        col.markdown(f"<div class='kpi' style='{accent}'><div class='label'>{html.escape(str(label))}</div>"
                     f"<div class='value'>{value}</div><div class='sub'>{sub}</div></div>",
                     unsafe_allow_html=True)


def section(title: str, caption: str = "") -> None:
    """A quiet section title with a rule, and an optional one-line caption."""
    st.markdown(f"<div class='sec'>{html.escape(title)}</div>"
                + (f"<div class='sec-cap'>{caption}</div>" if caption else ""), unsafe_allow_html=True)


def risk_pill(risk: str | None, text: str | None = None) -> str:
    """HTML for a small label in a risk level's colours (showing `text`, or the level itself),
    or a dash when a zone hasn't been counted."""
    if not risk:
        return f"<span class='pill neutral'>{html.escape(text or '–')}</span>"
    fg, bg, border = RISK_STYLE[risk]
    return (f"<span class='pill' style='color:{fg};background:{bg};border-color:{border}'>"
            f"{html.escape(text or risk)}</span>")


def nav_link(page: str, label: str, icon: str | None = None, url: str = "") -> None:
    """A link to another page of the app. Outside the app's navigation (a page run on its own,
    as the tests do) it falls back to a plain link instead of failing."""
    try:
        st.page_link(page, label=label, icon=icon)
    except st.errors.StreamlitAPIException:
        st.markdown(f"[{label}]({url or '/'})")


class Working:
    """A loading card: what is happening, in plain words, with real progress when it is known.

    with working("Counting people", "Zone A, 1 of 3") as job:
        job.update("Zone B, 2 of 3", fraction=0.5)
    The card disappears when the block ends. Without a fraction it shows a moving bar instead.
    """

    def __init__(self, title: str, detail: str = "", fraction: float | None = None):
        self.title, self.detail, self.fraction = title, detail, fraction
        self.slot = st.empty()

    def update(self, detail: str | None = None, fraction: float | None = None, title: str | None = None):
        self.title = title or self.title
        self.detail = self.detail if detail is None else detail
        self.fraction = fraction if fraction is not None else self.fraction
        bar = ("<div class='sweep'></div>" if self.fraction is None else
               f"<div class='fill' style='width:{max(2.0, min(1.0, self.fraction) * 100):.1f}%'></div>")
        self.slot.markdown(f"<div class='cs-load'><div class='t'><i></i>{html.escape(self.title)}</div>"
                           f"<div class='d'>{html.escape(self.detail) or '&nbsp;'}</div>"
                           f"<div class='track'>{bar}</div></div>", unsafe_allow_html=True)

    def __enter__(self):
        return self

    def done(self):
        self.slot.empty()

    def __exit__(self, *exc):
        self.done()
        return False


def working(title: str, detail: str = "", fraction: float | None = None) -> Working:
    """A loading card, shown straight away. Use it as a `with` block, or call .done() to remove it."""
    job = Working(title, detail, fraction)
    job.update()
    return job


def next_step(text: str, page: str, label: str, url: str, icon: str = ":material/arrow_forward:") -> None:
    """The end of a page: one line on what to do next, and the link that does it, so nobody gets stuck."""
    st.markdown(f"<div class='sec' style='margin-top:2rem'>Next</div><div class='sec-cap'>{html.escape(text)}</div>",
                unsafe_allow_html=True)
    nav_link(page, label, icon, url)


def compact(n: float) -> str:
    """547408 -> 547.4K: big counts the way dashboards show them."""
    for size, suffix in ((1e6, "M"), (1e3, "K")):
        if abs(n) >= size:
            return f"{n / size:.1f}{suffix}"
    return f"{n:,.0f}"
