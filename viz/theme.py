from __future__ import annotations
"""Design-token theme system with per-club palettes.

Single source of truth for all visual styling.  Every colour, radius, font,
and spacing value is defined in THEMES and injected as CSS custom properties.
Changing a token here re-styles the entire app.

Usage (top of every page or in app.py):
    from viz.theme import apply_theme
    theme = apply_theme()          # returns the active theme dict
    color = theme["colors"]["primary"]  # use in Plotly/mpl if needed
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.colors import LinearSegmentedColormap

# ═══════════════════════════════════════════════════════════════════════════
# §1  THEME DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

THEMES: dict[str, dict] = {
    "america": {
        "label": "Club América",
        "colors": {
            "bg":            "#04132E",
            "surface":       "#0A1F44",
            "surface_alt":   "#13294B",
            "border":        "#1E3461",
            "primary":       "#FFD100",
            "primary_hover": "#E6B800",
            "accent_blue":   "#2E6BD6",
            "cream":         "#F5EFD9",
            "text":          "#EAF0FA",
            "text_muted":    "#9FB0C8",
            "text_dim":      "#5C7A9B",
            "success":       "#3DD68C",
            "warning":       "#FFB020",
            "danger":        "#FF5C7A",
            "info":          "#5B9CF6",
        },
        "typo": {
            "font_display": "'Archivo', 'Inter', -apple-system, sans-serif",
            "font_body":    "'Inter', -apple-system, sans-serif",
            "font_mono":    "'JetBrains Mono', 'SF Mono', monospace",
        },
        "space": {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "40px"},
        "radius": {"sm": "6px", "md": "12px", "lg": "20px", "pill": "999px"},
        "pitch_bg": "#04132E",
        "pitch_line": "#1E3461",
    },
}

DEFAULT_CLUB = "america"


def get_active_theme() -> dict:
    """Return the theme dict for the currently selected club."""
    club = st.session_state.get("club_theme", DEFAULT_CLUB)
    return THEMES.get(club, THEMES[DEFAULT_CLUB])


# ═══════════════════════════════════════════════════════════════════════════
# §2  PLOTLY TEMPLATE (dynamic per theme)
# ═══════════════════════════════════════════════════════════════════════════

def _make_plotly_template(t: dict) -> go.layout.Template:
    c = t["colors"]
    typo = t["typo"]
    return go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=c["bg"],
            plot_bgcolor=c["bg"],
            font=dict(color=c["text_muted"], family=typo["font_body"], size=12),
            title=dict(
                font=dict(size=16, color=c["text"], family=typo["font_display"]),
                x=0.02, xanchor="left",
            ),
            xaxis=dict(
                gridcolor=c["border"], zerolinecolor=c["border"],
                tickfont=dict(size=11, color=c["text_dim"]),
            ),
            yaxis=dict(
                gridcolor=c["border"], zerolinecolor=c["border"],
                tickfont=dict(size=11, color=c["text_dim"]),
            ),
            colorway=[
                c["primary"], c["accent_blue"], c["success"], "#A78BFA",
                "#FB923C", c["danger"], "#2DD4BF", "#E879F9", c["warning"], "#94A3B8",
            ],
            hoverlabel=dict(
                bgcolor=c["surface"], font_size=12, bordercolor=c["border"],
                font_family=typo["font_body"], font_color=c["text"],
            ),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=c["text_muted"])),
            margin=dict(l=48, r=24, t=56, b=48),
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# §3  MATPLOTLIB / MPLSOCCER CONFIG (dynamic per theme)
# ═══════════════════════════════════════════════════════════════════════════

def _make_pitch_kwargs(t: dict) -> dict:
    return dict(
        pitch_type="opta",
        pitch_color=t["pitch_bg"],
        line_color=t["pitch_line"],
        linewidth=1,
        goal_type="box",
    )


def _make_half_pitch_kwargs(t: dict) -> dict:
    return dict(**_make_pitch_kwargs(t), half=True)


def _make_cmap(t: dict) -> LinearSegmentedColormap:
    c = t["colors"]
    return LinearSegmentedColormap.from_list(
        "club_heat", [c["bg"], c["surface_alt"], c["primary_hover"], c["primary"], c["cream"]]
    )


def _make_cmap_blue(t: dict) -> LinearSegmentedColormap:
    c = t["colors"]
    return LinearSegmentedColormap.from_list(
        "club_blue", [c["bg"], "#0A1A3D", c["accent_blue"], c["info"], "#B3E0FF"]
    )


# ═══════════════════════════════════════════════════════════════════════════
# §4  MODULE-LEVEL EXPORTS (backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════
# These are initialised for the default theme so existing imports don't break.
# After apply_theme() runs they're updated to match the active club.

_default = THEMES[DEFAULT_CLUB]
AME_PLOTLY_TEMPLATE = _make_plotly_template(_default)
PITCH_KWARGS = _make_pitch_kwargs(_default)
HALF_PITCH_KWARGS = _make_half_pitch_kwargs(_default)
AME_CMAP = _make_cmap(_default)
AME_CMAP_BLUE = _make_cmap_blue(_default)
MPL_FIG_KWARGS = dict(facecolor=_default["pitch_bg"])

pio.templates["ame_dark"] = AME_PLOTLY_TEMPLATE
pio.templates.default = "ame_dark"


# ═══════════════════════════════════════════════════════════════════════════
# §5  CSS GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _generate_css(t: dict) -> str:
    c = t["colors"]
    ty = t["typo"]
    sp = t["space"]
    r = t["radius"]

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {{
  --bg:           {c["bg"]};
  --surface:      {c["surface"]};
  --surface-alt:  {c["surface_alt"]};
  --border:       {c["border"]};
  --primary:      {c["primary"]};
  --primary-hover:{c["primary_hover"]};
  --accent-blue:  {c["accent_blue"]};
  --cream:        {c["cream"]};
  --text:         {c["text"]};
  --text-muted:   {c["text_muted"]};
  --text-dim:     {c["text_dim"]};
  --success:      {c["success"]};
  --warning:      {c["warning"]};
  --danger:       {c["danger"]};
  --info:         {c["info"]};
  --display:      {ty["font_display"]};
  --body:         {ty["font_body"]};
  --mono:         {ty["font_mono"]};
  --sp-xs:{sp["xs"]}; --sp-sm:{sp["sm"]}; --sp-md:{sp["md"]}; --sp-lg:{sp["lg"]}; --sp-xl:{sp["xl"]};
  --r-sm:{r["sm"]}; --r-md:{r["md"]}; --r-lg:{r["lg"]}; --r-pill:{r["pill"]};
  --shadow-sm: 0 1px 3px rgba(0,0,0,.4);
  --shadow-md: 0 4px 14px rgba(0,0,0,.45);
}}

/* ── Streamlit base ────────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--bg) !important; }}
[data-testid="stAppViewContainer"] > .main {{ background: var(--bg) !important; }}
[data-testid="stHeader"] {{
  background: color-mix(in srgb, var(--bg) 88%, transparent) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border-bottom: 1px solid var(--border) !important;
}}

/* ── Sidebar ───────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{ background: color-mix(in srgb, var(--bg) 92%, black) !important; border-right:1px solid var(--border) !important; }}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {{ color: var(--primary) !important; font-family: var(--display) !important; font-weight:700 !important; }}
[data-testid="stSidebarNav"] a {{
  color: var(--text-muted) !important; font-size:.84rem !important; font-weight:500 !important;
  padding:.45rem .9rem !important; border-radius: var(--r-sm) !important; transition: all .18s ease !important;
}}
[data-testid="stSidebarNav"] a:hover {{ color: var(--text) !important; background: var(--surface-alt) !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  color: var(--primary) !important;
  background: color-mix(in srgb, var(--primary) 10%, transparent) !important;
  border-left: 3px solid var(--primary) !important; font-weight:700 !important;
}}

/* ── Typography ────────────────────────────────────────────────── */
h1 {{ font-family: var(--display) !important; font-weight:800 !important; letter-spacing:-.02em !important; color: var(--text) !important; }}
h2 {{ font-family: var(--display) !important; font-weight:700 !important; color: var(--text) !important; }}
h3 {{ color: var(--text-muted) !important; font-family: var(--body) !important; font-weight:600 !important; }}
p, li {{ color: var(--text-muted) !important; line-height:1.6 !important; }}
[data-testid="stMarkdownContainer"] h1 {{
  font-family: var(--display) !important; font-size:1.85rem !important; font-weight:800 !important;
  color: var(--text) !important; border-bottom:1px solid var(--border) !important;
  padding-bottom:.5rem !important; margin-bottom:1.2rem !important;
}}

/* ── Metrics ───────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {{ font-family: var(--mono) !important; color: var(--text) !important; font-size:1.8rem !important; font-weight:700 !important; }}
[data-testid="stMetricLabel"] {{ font-size:.73rem !important; letter-spacing:.06em !important; text-transform:uppercase !important; color: var(--text-dim) !important; font-weight:600 !important; }}
[data-testid="stMetricDelta"] {{ font-family: var(--mono) !important; font-size:.8rem !important; font-weight:600 !important; }}
[data-testid="stMetric"] {{
  background: var(--surface) !important; border:1px solid var(--border) !important;
  border-radius: var(--r-md) !important; padding:1rem 1.1rem !important;
  position:relative !important; overflow:hidden !important;
  transition: border-color .18s, box-shadow .18s !important;
}}
[data-testid="stMetric"]:hover {{ border-color: var(--primary) !important; box-shadow: var(--shadow-sm) !important; }}
[data-testid="stMetric"]::before {{
  content:'' !important; position:absolute !important; top:0 !important; left:0 !important; right:0 !important;
  height:3px !important; background: linear-gradient(90deg, var(--primary), var(--accent-blue)) !important;
  border-radius: var(--r-md) var(--r-md) 0 0 !important;
}}

/* ── DataFrames ────────────────────────────────────────────────── */
.stDataFrame {{ border:1px solid var(--border) !important; border-radius: var(--r-md) !important; background: var(--surface) !important; overflow:hidden !important; }}
.stDataFrame th {{ background: var(--surface-alt) !important; color: var(--text-dim) !important; font-family: var(--body) !important; font-size:.72rem !important; font-weight:600 !important; text-transform:uppercase !important; }}
.stDataFrame td {{ font-family: var(--mono) !important; font-size:.82rem !important; color: var(--text-muted) !important; border-color: var(--border) !important; }}

/* ── Form controls ─────────────────────────────────────────────── */
.stSelectbox label, .stMultiSelect label, .stSlider label,
.stTextInput label, .stNumberInput label, .stRadio label {{
  color: var(--text-dim) !important; font-size:.74rem !important; letter-spacing:.04em !important;
  text-transform:uppercase !important; font-family: var(--body) !important; font-weight:600 !important;
}}
.stSelectbox > div > div, .stMultiSelect > div > div {{
  background: var(--surface) !important; border-color: var(--border) !important;
  color: var(--text) !important; border-radius: var(--r-sm) !important; transition: border-color .18s !important;
}}
.stSelectbox > div > div:hover, .stMultiSelect > div > div:hover {{ border-color: var(--primary) !important; }}
.stSelectbox [data-baseweb="select"] > div {{ background: var(--surface) !important; border-color: var(--border) !important; border-radius: var(--r-sm) !important; }}

/* ── Radio (pill) ──────────────────────────────────────────────── */
.stRadio > div {{ gap:.5rem !important; }}
.stRadio > div > label {{
  background: var(--surface) !important; border:1px solid var(--border) !important;
  border-radius: var(--r-pill) !important; padding:.4rem 1rem !important; color: var(--text-muted) !important;
  font-family: var(--body) !important; font-size:.78rem !important; font-weight:500 !important;
  cursor:pointer !important; transition: all .18s ease !important;
}}
.stRadio > div > label:hover {{ border-color: var(--primary) !important; color: var(--text) !important; background: var(--surface-alt) !important; }}
.stRadio > div > label:has(input:checked) {{
  background: var(--primary) !important; border-color: var(--primary) !important;
  color: var(--bg) !important; font-weight:700 !important;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--primary) 30%, transparent) !important;
}}

/* ── Tabs ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{ background:transparent !important; border-bottom:1px solid var(--border) !important; }}
.stTabs [data-baseweb="tab"] {{
  color: var(--text-dim) !important; font-family: var(--body) !important; font-size:.8rem !important;
  font-weight:500 !important; padding:.7rem 1.2rem !important; background:transparent !important;
  border:none !important; border-bottom:2px solid transparent !important; transition: all .18s !important;
}}
.stTabs [data-baseweb="tab"]:hover {{ color: var(--text-muted) !important; }}
.stTabs [aria-selected="true"] {{ color: var(--primary) !important; border-bottom-color: var(--primary) !important; font-weight:600 !important; }}

/* ── Expanders ─────────────────────────────────────────────────── */
.streamlit-expanderHeader {{ background: var(--surface) !important; border:1px solid var(--border) !important; border-radius: var(--r-md) !important; color: var(--text-muted) !important; font-family: var(--body) !important; font-size:.85rem !important; font-weight:500 !important; }}
.streamlit-expanderContent {{ background: var(--surface) !important; border:1px solid var(--border) !important; border-top:none !important; border-radius:0 0 var(--r-md) var(--r-md) !important; }}

/* ── Alerts ────────────────────────────────────────────────────── */
.stAlert {{ border-radius: var(--r-md) !important; border-left-width:4px !important; }}
.stSuccess {{ border-left-color: var(--success) !important; background: color-mix(in srgb, var(--success) 6%, transparent) !important; }}
.stWarning {{ border-left-color: var(--warning) !important; background: color-mix(in srgb, var(--warning) 6%, transparent) !important; }}
.stError   {{ border-left-color: var(--danger) !important; background: color-mix(in srgb, var(--danger) 6%, transparent) !important; }}
.stInfo    {{ border-left-color: var(--info) !important; background: color-mix(in srgb, var(--info) 6%, transparent) !important; }}

/* ── Buttons ───────────────────────────────────────────────────── */
.stButton > button {{
  background: var(--surface) !important; border:1px solid var(--border) !important;
  color: var(--text-muted) !important; font-family: var(--body) !important; font-size:.8rem !important;
  font-weight:600 !important; border-radius: var(--r-sm) !important; padding:.5rem 1.2rem !important;
  transition: all .18s !important;
}}
.stButton > button:hover {{ border-color: var(--primary) !important; color: var(--text) !important; background: var(--surface-alt) !important; }}
.stButton > button:active {{ transform:scale(.98) !important; }}
.stButton > button[kind="primary"] {{
  background: var(--primary) !important; border-color: var(--primary) !important;
  color: var(--bg) !important; font-weight:700 !important;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--primary) 25%, transparent) !important;
}}

/* ── Slider ────────────────────────────────────────────────────── */
.stSlider [data-testid="stSliderThumb"] {{ background: var(--primary) !important; box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 25%, transparent) !important; }}
.stSlider .rc-slider-track {{ background: var(--primary) !important; }}

/* ── Misc ──────────────────────────────────────────────────────── */
.stSpinner > div {{ border-top-color: var(--primary) !important; }}
hr {{ border-color: var(--border) !important; margin:1.8rem 0 !important; opacity:.5 !important; }}
.stCaption, [data-testid="stCaptionContainer"] {{ color: var(--text-dim) !important; font-family: var(--body) !important; font-size:.72rem !important; }}
[data-testid="column"] {{ padding:0 .4rem !important; }}

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-dim); }}
a, button, input, select, textarea {{ transition: all .18s ease !important; }}
:focus-visible {{ outline:2px solid var(--primary) !important; outline-offset:2px !important; }}

/* ══════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS (referenced by kpi_cards.py HTML generators)
   ══════════════════════════════════════════════════════════════════ */

/* ── Page header ───────────────────────────────────────────────── */
.ame-page-bar {{ display:flex; align-items:center; gap:16px; padding:14px 0 20px; margin-bottom:1.2rem; border-bottom:1px solid var(--border); }}
.ame-page-bar-accent {{ width:4px; height:32px; background:linear-gradient(180deg, var(--primary), var(--accent-blue)); border-radius:4px; flex-shrink:0; }}
.ame-page-title {{ font-family: var(--display); font-size:1.75rem; font-weight:800; letter-spacing:-.02em; color: var(--text); line-height:1; }}
.ame-page-sub {{ font-family: var(--body); font-size:.72rem; font-weight:500; letter-spacing:.08em; color: var(--text-dim); text-transform:uppercase; margin-top:4px; }}

/* ── Section headers ───────────────────────────────────────────── */
.ame-section {{ margin:2rem 0 1rem; }}
.ame-section-label {{
  font-family: var(--body); font-size:.65rem; font-weight:700; letter-spacing:.18em;
  color: var(--primary); text-transform:uppercase; margin-bottom:4px;
  display:flex; align-items:center; gap:8px;
}}
.ame-section-label::before, .ame-section-label::after {{ content:''; height:1px; width:16px; background: var(--primary); opacity:.4; }}
.ame-section-title {{ font-family: var(--display); font-size:1.5rem; font-weight:800; letter-spacing:-.015em; color: var(--text); line-height:1.1; }}
.section-header {{
  font-family: var(--display) !important; font-size:1.3rem !important; font-weight:700 !important;
  color: var(--text) !important; border-bottom:1px solid var(--border) !important;
  padding-bottom:.3rem !important; margin-bottom:.9rem !important;
}}

/* ── KPI tiles ─────────────────────────────────────────────────── */
.ame-tile-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:1px; background: var(--border); border:1px solid var(--border); border-radius: var(--r-md); overflow:hidden; margin-bottom:1.2rem; }}
.ame-tile {{ background: var(--surface); padding:.9rem 1rem; position:relative; transition:background .18s; }}
.ame-tile:hover {{ background: var(--surface-alt); }}
.ame-tile::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, var(--primary), transparent); opacity:.5; }}
.ame-tile-label {{ font-family: var(--body); font-size:.62rem; font-weight:600; letter-spacing:.12em; color: var(--text-dim); text-transform:uppercase; margin-bottom:6px; }}
.ame-tile-value {{ font-family: var(--mono); font-size:1.35rem; font-weight:700; color: var(--text); line-height:1; }}
.ame-tile-sub {{ font-family: var(--mono); font-size:.62rem; color: var(--text-dim); margin-top:4px; }}

/* ── KPI card ──────────────────────────────────────────────────── */
.kpi-card {{
  background: var(--surface); border:1px solid var(--border); border-radius: var(--r-md);
  padding:1rem 1.1rem; margin:.3rem 0; position:relative; overflow:hidden;
  transition: border-color .18s, box-shadow .18s;
}}
.kpi-card:hover {{ border-color: var(--primary); box-shadow: var(--shadow-sm); }}
.kpi-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg, var(--primary), var(--accent-blue)); }}
.kpi-card .kpi-value {{ font-family: var(--mono); font-size:1.8rem; font-weight:700; color: var(--text); margin:0; line-height:1; }}
.kpi-card .kpi-label {{ font-family: var(--body); font-size:.64rem; font-weight:600; color: var(--text-dim); text-transform:uppercase; letter-spacing:.1em; margin:0 0 6px; }}
.kpi-card .kpi-delta {{ font-family: var(--mono); font-size:.78rem; font-weight:600; margin-top:6px; }}
.kpi-card .kpi-delta.positive {{ color: var(--success); }}
.kpi-card .kpi-delta.negative {{ color: var(--danger); }}

/* ── Card container ────────────────────────────────────────────── */
.ame-card {{ background: var(--surface); border:1px solid var(--border); border-radius: var(--r-md); padding:1.1rem 1.3rem; margin-bottom:.9rem; transition: border-color .18s; }}
.ame-card:hover {{ border-color: color-mix(in srgb, var(--primary) 40%, var(--border)); }}
.ame-card-title {{ font-family: var(--body); font-size:.66rem; font-weight:600; letter-spacing:.12em; color: var(--text-dim); text-transform:uppercase; margin-bottom:.8rem; padding-bottom:.5rem; border-bottom:1px solid var(--border); }}

/* ── Form badges ───────────────────────────────────────────────── */
.form-badge {{ display:inline-flex; width:24px; height:24px; align-items:center; justify-content:center; border-radius:var(--r-sm); font-weight:700; font-size:.68rem; margin:0 2px; font-family: var(--mono); color: var(--bg); transition:transform .15s; }}
.form-badge:hover {{ transform:scale(1.15); }}
.form-badge.W {{ background: var(--success); }}
.form-badge.D {{ background: var(--text-dim); color: var(--text); }}
.form-badge.L {{ background: var(--danger); }}

/* ── Match header / V3 hero ────────────────────────────────────── */
.match-header {{ background: var(--surface); border:1px solid var(--border); border-radius: var(--r-lg); padding:1.5rem 2rem; margin-bottom:1.2rem; text-align:center; position:relative; overflow:hidden; }}
.match-header::before {{ content:''; position:absolute; inset:0; background:radial-gradient(ellipse 50% 70% at 15% 50%, color-mix(in srgb, var(--primary) 6%, transparent) 0%,transparent 70%), radial-gradient(ellipse 50% 70% at 85% 50%, color-mix(in srgb, var(--accent-blue) 5%, transparent) 0%,transparent 70%); pointer-events:none; }}
.match-header .match-meta {{ font-family: var(--body); font-size:.65rem; font-weight:500; letter-spacing:.15em; color: var(--text-dim); text-transform:uppercase; margin-bottom:.8rem; position:relative; }}
.match-header .score-row {{ display:flex; align-items:center; justify-content:center; gap:1.5rem; position:relative; }}
.match-header .team-block {{ display:flex; flex-direction:column; align-items:center; min-width:120px; flex:1; max-width:200px; }}
.match-header .team-block img {{ width:56px; height:56px; object-fit:contain; margin-bottom:.5rem; filter:drop-shadow(0 2px 8px rgba(0,0,0,.5)); }}
.match-header .team-block .team-name {{ font-family: var(--display); font-size:.95rem; font-weight:700; color: var(--text-muted); text-transform:uppercase; line-height:1.1; }}
.match-header .score-display {{ font-family: var(--display); font-size:clamp(2.8rem,6vw,4.2rem); font-weight:800; line-height:1; display:flex; align-items:center; gap:.15em; }}
.match-header .score-display .home-score {{ color: var(--primary); }}
.match-header .score-display .away-score {{ color: var(--accent-blue); }}
.match-header .score-display .score-sep {{ color: var(--text-dim); }}
.match-header .ht-score {{ font-family: var(--mono); font-size:.68rem; color: var(--text-dim); margin-top:.5rem; position:relative; }}

/* ── Stat comparison bars ──────────────────────────────────────── */
.stat-comparison {{ padding:.2rem 0; max-width:720px; margin:0 auto 1rem; }}
.stat-row {{ display:grid; grid-template-columns:52px 1fr 110px 1fr 52px; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); transition:background .15s; }}
.stat-row:hover {{ background: color-mix(in srgb, var(--surface-alt) 50%, transparent); }}
.stat-row .stat-val {{ font-family: var(--mono); font-size:.85rem; font-weight:700; }}
.stat-row .stat-val.home {{ text-align:right; color: var(--primary); }}
.stat-row .stat-val.away {{ text-align:left; color: var(--accent-blue); }}
.stat-row .stat-label {{ text-align:center; font-family: var(--body); font-size:.62rem; font-weight:600; color: var(--text-dim); text-transform:uppercase; }}
.stat-row .bar-container {{ height:5px; background: var(--surface-alt); border-radius:3px; overflow:hidden; }}
.stat-row .bar-fill-home {{ height:100%; background:linear-gradient(90deg,transparent, var(--primary)); border-radius:3px; float:right; transition:width .5s; }}
.stat-row .bar-fill-away {{ height:100%; background:linear-gradient(270deg,transparent, var(--accent-blue)); border-radius:3px; float:left; transition:width .5s; }}

/* ── Event timeline ────────────────────────────────────────────── */
.event-timeline {{ position:relative; padding:.4rem 0 .4rem 36px; }}
.event-timeline::before {{ content:''; position:absolute; left:26px; top:0; bottom:0; width:1px; background:linear-gradient(180deg, var(--border),transparent); }}
.event-item {{ display:flex; align-items:center; padding:.35rem 0; position:relative; transition:background .15s; border-radius: var(--r-sm); }}
.event-item:hover {{ background: color-mix(in srgb, var(--surface-alt) 50%, transparent); }}
.event-item .event-minute {{ position:absolute; left:-34px; width:26px; text-align:right; font-family: var(--mono); font-size:.72rem; font-weight:700; color: var(--text-dim); }}
.event-item .event-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; margin-right:10px; position:relative; left:-9px; z-index:1; box-shadow: 0 0 6px currentColor; }}
.event-item .event-icon {{ font-size:.85rem; margin-right:6px; }}
.event-item .event-detail {{ font-family: var(--body); font-size:.78rem; color: var(--text-muted); }}
.event-item .event-detail .player-name {{ font-weight:700; color: var(--text); }}

/* ── Content card ──────────────────────────────────────────────── */
.content-card {{ background: var(--surface); border:1px solid var(--border); border-radius: var(--r-md); padding:1rem 1.2rem; margin-bottom:.9rem; }}
.content-card .card-title {{ font-family: var(--body); font-size:.66rem; font-weight:600; color: var(--text-dim); text-transform:uppercase; letter-spacing:.12em; border-bottom:1px solid var(--border); padding-bottom:.5rem; margin-bottom:.8rem; }}

/* ── V3 hero (post-match) ──────────────────────────────────────── */
.v3-hero {{ position:relative; background:linear-gradient(180deg, color-mix(in srgb, var(--bg) 90%, black) 0%, var(--surface) 100%); border:1px solid var(--border); border-radius: var(--r-lg); overflow:hidden; padding:2.2rem 2rem 2rem; margin-bottom:1.5rem; text-align:center; }}
.v3-hero::before {{ content:''; position:absolute; inset:0; background:radial-gradient(ellipse 50% 40% at 20% 50%, color-mix(in srgb, var(--primary) 8%, transparent) 0%,transparent 70%), radial-gradient(ellipse 50% 40% at 80% 50%, color-mix(in srgb, var(--accent-blue) 6%, transparent) 0%,transparent 70%); pointer-events:none; }}
.v3-competition {{ font-family: var(--body); font-size:.65rem; font-weight:600; letter-spacing:.18em; color: var(--text-dim); text-transform:uppercase; margin-bottom:1.2rem; position:relative; }}
.v3-score-row {{ display:flex; align-items:center; justify-content:center; gap:1.5rem; position:relative; margin-bottom:.8rem; }}
.v3-team-block {{ display:flex; flex-direction:column; align-items:center; min-width:120px; flex:1; max-width:200px; }}
.v3-team-block img {{ width:64px; height:64px; object-fit:contain; margin-bottom:.5rem; filter:drop-shadow(0 4px 16px rgba(0,0,0,.5)); }}
.v3-team-name {{ font-family: var(--display); font-size:.95rem; font-weight:700; color: var(--text-muted); text-transform:uppercase; line-height:1.1; }}
.v3-score-center {{ display:flex; flex-direction:column; align-items:center; min-width:150px; }}
.v3-score-digits {{ font-family: var(--display); font-size:clamp(3.5rem,9vw,5.5rem); font-weight:800; line-height:1; display:flex; align-items:center; gap:.08em; }}
.v3-score-home {{ color: var(--primary); }}
.v3-score-sep {{ color: var(--text-dim); font-size:.6em; }}
.v3-score-away {{ color: var(--accent-blue); }}
.v3-ht {{ font-family: var(--mono); font-size:.68rem; color: var(--text-dim); margin-top:.3rem; }}
.v3-meta-row {{ font-family: var(--body); font-size:.65rem; font-weight:500; color: var(--text-dim); letter-spacing:.1em; text-transform:uppercase; position:relative; margin-top:.6rem; }}
.v3-xg-strip {{ display:flex; align-items:center; justify-content:center; position:relative; margin-top:1.4rem; padding-top:1.2rem; border-top:1px solid var(--border); }}
.v3-xg-block {{ flex:1; text-align:center; padding:0 1rem; }}
.v3-xg-label {{ font-family: var(--body); font-size:.6rem; font-weight:600; letter-spacing:.12em; color: var(--text-dim); text-transform:uppercase; margin-bottom:4px; }}
.v3-xg-value-home {{ font-family: var(--mono); font-size:2rem; font-weight:700; line-height:1; color: var(--primary); }}
.v3-xg-value-away {{ font-family: var(--mono); font-size:2rem; font-weight:700; line-height:1; color: var(--accent-blue); }}
.v3-xg-divider {{ font-family: var(--body); font-size:.6rem; font-weight:600; color: var(--text-dim); writing-mode:vertical-lr; padding:0 .5rem; border-left:1px solid var(--border); border-right:1px solid var(--border); }}
.v3-xg-story {{ font-family: var(--body); font-size:.68rem; color: var(--text-dim); margin-top:.6rem; font-style:italic; position:relative; }}

/* V3 section / stat bars / rating cards */
.v3-section {{ margin:2rem 0 1rem; }}
.v3-section-rule {{ font-family: var(--body); font-size:.62rem; font-weight:700; letter-spacing:.2em; color: var(--primary); margin-bottom:4px; }}
.v3-section-title {{ font-family: var(--display); font-size:1.5rem; font-weight:800; color: var(--text); line-height:1; margin:0; }}
.v3-stat-row {{ display:grid; grid-template-columns:52px 1fr 120px 1fr 52px; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); transition:background .15s; }}
.v3-stat-row:hover {{ background: color-mix(in srgb, var(--surface-alt) 50%, transparent); }}
.v3-stat-val {{ font-family: var(--mono); font-size:.85rem; font-weight:700; }}
.v3-stat-val.home {{ text-align:right; color: var(--primary); }}
.v3-stat-val.away {{ text-align:left; color: var(--accent-blue); }}
.v3-stat-label {{ width:120px; text-align:center; font-family: var(--body); font-size:.62rem; font-weight:600; color: var(--text-dim); text-transform:uppercase; }}
.v3-bar-wrap {{ height:5px; background: var(--surface-alt); border-radius:3px; overflow:hidden; }}
.v3-bar-home {{ height:100%; background:linear-gradient(90deg,transparent, var(--primary)); border-radius:3px; float:right; transition:width .5s; }}
.v3-bar-away {{ height:100%; background:linear-gradient(270deg,transparent, var(--accent-blue)); border-radius:3px; transition:width .5s; }}

.v3-rating-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(135px,1fr)); gap:.5rem; margin-top:.6rem; }}
.v3-rating-card {{ background: var(--surface); border:1px solid var(--border); border-radius: var(--r-sm); padding:.55rem .75rem; display:flex; justify-content:space-between; align-items:center; transition: border-color .18s; }}
.v3-rating-card:hover {{ border-color: color-mix(in srgb, var(--primary) 40%, var(--border)); }}
.v3-rating-name {{ font-family: var(--body); font-size:.74rem; font-weight:500; color: var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px; }}
.v3-rating-score {{ font-family: var(--mono); font-size:1.1rem; font-weight:700; }}
.v3-rating-green {{ color: var(--success); }}
.v3-rating-gold {{ color: var(--primary); }}
.v3-rating-normal {{ color: var(--text-muted); }}

/* ── League table ──────────────────────────────────────────────── */
.standings-table {{ border-collapse:collapse; width:100%; font-family: var(--body); font-size:.8rem; }}
.standings-table th {{ font-size:.64rem; font-weight:600; color: var(--text-dim); text-transform:uppercase; padding:7px 8px; border-bottom:1px solid var(--border); text-align:center; }}
.standings-table td {{ padding:6px 8px; border-bottom:1px solid var(--border); color: var(--text-muted); text-align:center; transition:background .15s; }}
.standings-table tr:hover td {{ background: var(--surface-alt); }}
.standings-table .rank-ame {{ color: var(--primary); font-weight:800; }}
</style>"""


# ═══════════════════════════════════════════════════════════════════════════
# §6  APPLY THEME (the only public API most pages need)
# ═══════════════════════════════════════════════════════════════════════════

def apply_theme() -> dict:
    """Inject CSS, configure Plotly/mpl, and return the active theme dict.

    Call once at the top of every page (after st.set_page_config in app.py).
    """
    global AME_PLOTLY_TEMPLATE, PITCH_KWARGS, HALF_PITCH_KWARGS
    global AME_CMAP, AME_CMAP_BLUE, MPL_FIG_KWARGS

    t = get_active_theme()

    # Inject CSS custom properties
    st.markdown(_generate_css(t), unsafe_allow_html=True)

    # Update Plotly template
    AME_PLOTLY_TEMPLATE = _make_plotly_template(t)
    pio.templates["ame_dark"] = AME_PLOTLY_TEMPLATE
    pio.templates.default = "ame_dark"

    # Update mpl config
    PITCH_KWARGS = _make_pitch_kwargs(t)
    HALF_PITCH_KWARGS = _make_half_pitch_kwargs(t)
    AME_CMAP = _make_cmap(t)
    AME_CMAP_BLUE = _make_cmap_blue(t)
    MPL_FIG_KWARGS = dict(facecolor=t["pitch_bg"])

    return t
