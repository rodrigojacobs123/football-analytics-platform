"""Manchester United visual theme — Plotly template, mplsoccer config, CSS."""

import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.colors import LinearSegmentedColormap

from config import MU_RED, MU_BLACK, MU_GOLD, MU_WHITE, MU_DARK_BG, MU_GRID

# ── Plotly dark template with MU colors ─────────────────────────────────────

MU_PLOTLY_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="#13131C",
        plot_bgcolor="#13131C",
        font=dict(color="#FAFAFA", family="'JetBrains Mono', monospace", size=12),
        title=dict(font=dict(size=18, color="#FAFAFA", family="Anton, sans-serif")),
        xaxis=dict(gridcolor="#1F1F2A", zerolinecolor="#1F1F2A"),
        yaxis=dict(gridcolor="#1F1F2A", zerolinecolor="#1F1F2A"),
        colorway=[MU_RED, "#42A5F5", MU_GOLD, MU_WHITE, "#3DD68C", "#FF9F1C",
                  "#FF4D6D", "#9C27B0", "#00BCD4", "#795548"],
        hoverlabel=dict(bgcolor="#13131C", font_size=12, bordercolor=MU_RED,
                        font_family="'JetBrains Mono', monospace"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        margin=dict(l=40, r=20, t=50, b=40),
    )
)
pio.templates["mu_dark"] = MU_PLOTLY_TEMPLATE
pio.templates.default = "mu_dark"

# ── mplsoccer pitch configuration ──────────────────────────────────────────

PITCH_COLOR = "#0E0E14"
PITCH_LINE_COLOR = "#2A2A38"

PITCH_KWARGS = dict(
    pitch_type="opta",
    pitch_color=PITCH_COLOR,
    line_color=PITCH_LINE_COLOR,
    linewidth=1,
    goal_type="box",
)

HALF_PITCH_KWARGS = dict(
    pitch_type="opta",
    pitch_color=PITCH_COLOR,
    line_color=PITCH_LINE_COLOR,
    linewidth=1,
    goal_type="box",
    half=True,
)

# ── Matplotlib colormaps ────────────────────────────────────────────────────

MU_CMAP = LinearSegmentedColormap.from_list(
    "mu_heat", ["#0E0E14", "#3D0A0A", MU_RED, MU_GOLD, MU_WHITE]
)

MU_CMAP_BLUE = LinearSegmentedColormap.from_list(
    "mu_blue", ["#0E0E14", "#0A1A3D", "#1565C0", "#42A5F5", MU_WHITE]
)

# ── Matplotlib figure defaults ──────────────────────────────────────────────

MPL_FIG_KWARGS = dict(facecolor="#0E0E14")

# ── Global CSS ──────────────────────────────────────────────────────────────

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=JetBrains+Mono:wght@400;600;700;800&display=swap');

/* ── CSS custom properties ──────────────────────────────────────────── */
:root {
  --mu-bg:       #0E0E14;
  --mu-card:     #13131C;
  --mu-card2:    #17171F;
  --mu-border:   #1F1F2A;
  --mu-border2:  #2A2A38;
  --mu-red:      #DA291C;
  --mu-blue:     #42A5F5;
  --mu-gold:     #FBE122;
  --mu-green:    #3DD68C;
  --mu-warn:     #FF9F1C;
  --mu-danger:   #FF4D6D;
  --mu-text:     #FFFFFF;
  --mu-text2:    #CCCCCC;
  --mu-text3:    #888888;
  --mu-text4:    #555566;
  --display:     Anton, sans-serif;
  --mono:        'JetBrains Mono', 'Courier New', monospace;
  --body:        'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* ── Streamlit base overrides ───────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] {
  background-color: var(--mu-bg) !important;
}
[data-testid="stAppViewContainer"] > .main {
  background-color: var(--mu-bg) !important;
}
[data-testid="stHeader"] {
  background-color: #000 !important;
  border-bottom: 1px solid var(--mu-border) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background-color: #0B0B11 !important;
  border-right: 1px solid var(--mu-border) !important;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
  color: var(--mu-red) !important;
  font-family: var(--display) !important;
  letter-spacing: 0.06em !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stSlider { color: var(--mu-text2) !important; }

/* Sidebar nav links */
[data-testid="stSidebarNav"] a {
  color: var(--mu-text3) !important;
  font-size: 0.82rem !important;
  letter-spacing: 0.03em !important;
  padding: 0.35rem 0.8rem !important;
  border-radius: 4px !important;
  transition: color 0.15s, background 0.15s !important;
}
[data-testid="stSidebarNav"] a:hover { color: var(--mu-text) !important; background: var(--mu-border) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  color: var(--mu-red) !important;
  background: rgba(218,41,28,0.1) !important;
  border-left: 3px solid var(--mu-red) !important;
  font-weight: 700 !important;
}

/* General text */
h1 { font-family: var(--display) !important; letter-spacing: 0.05em !important; color: var(--mu-text) !important; }
h2 { font-family: var(--display) !important; letter-spacing: 0.04em !important; color: var(--mu-text) !important; }
h3 { color: var(--mu-text2) !important; font-family: var(--body) !important; }
p, li { color: var(--mu-text2) !important; }

/* Streamlit headings */
[data-testid="stMarkdownContainer"] h1 {
  font-family: var(--display) !important;
  font-size: 2rem !important;
  letter-spacing: 0.06em !important;
  color: var(--mu-text) !important;
  border-bottom: 2px solid var(--mu-border) !important;
  padding-bottom: 0.4rem !important;
  margin-bottom: 1.2rem !important;
}

/* Metrics */
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important;
  color: var(--mu-text) !important;
  font-size: 1.9rem !important;
  font-weight: 800 !important;
}
[data-testid="stMetricLabel"] {
  font-size: 0.72rem !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
  color: var(--mu-text3) !important;
}
[data-testid="stMetricDelta"] { font-family: var(--mono) !important; font-size: 0.8rem !important; }
[data-testid="stMetric"] {
  background: var(--mu-card) !important;
  border: 1px solid var(--mu-border) !important;
  border-top: 2px solid var(--mu-red) !important;
  border-radius: 4px !important;
  padding: 0.9rem 1rem !important;
}

/* DataFrames */
.stDataFrame {
  border: 1px solid var(--mu-border) !important;
  border-radius: 4px !important;
  background: var(--mu-card) !important;
}
.stDataFrame th {
  background: var(--mu-card2) !important;
  color: var(--mu-text3) !important;
  font-family: var(--mono) !important;
  font-size: 0.7rem !important;
  letter-spacing: 0.1em !important;
  text-transform: uppercase !important;
}
.stDataFrame td {
  font-family: var(--mono) !important;
  font-size: 0.82rem !important;
  color: var(--mu-text2) !important;
  border-color: var(--mu-border) !important;
}

/* Selectbox, multiselect, inputs */
.stSelectbox label, .stMultiSelect label, .stSlider label,
.stTextInput label, .stNumberInput label, .stRadio label {
  color: var(--mu-text3) !important;
  font-size: 0.72rem !important;
  letter-spacing: 0.1em !important;
  text-transform: uppercase !important;
  font-family: var(--mono) !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
  background: var(--mu-card) !important;
  border-color: var(--mu-border2) !important;
  color: var(--mu-text) !important;
}
.stSelectbox [data-baseweb="select"] > div { background: var(--mu-card) !important; border-color: var(--mu-border2) !important; }

/* Radio buttons */
.stRadio > div { gap: 0.4rem !important; }
.stRadio > div > label {
  background: var(--mu-card) !important;
  border: 1px solid var(--mu-border2) !important;
  border-radius: 3px !important;
  padding: 0.35rem 0.9rem !important;
  color: var(--mu-text3) !important;
  font-family: var(--mono) !important;
  font-size: 0.72rem !important;
  letter-spacing: 0.08em !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}
.stRadio > div > label:has(input:checked) {
  background: var(--mu-red) !important;
  border-color: var(--mu-red) !important;
  color: #fff !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: var(--mu-card) !important;
  border-bottom: 1px solid var(--mu-border) !important;
  gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--mu-text3) !important;
  font-family: var(--mono) !important;
  font-size: 0.7rem !important;
  letter-spacing: 0.1em !important;
  text-transform: uppercase !important;
  padding: 0.6rem 1.1rem !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
  color: var(--mu-red) !important;
  border-bottom-color: var(--mu-red) !important;
}

/* Expanders */
.streamlit-expanderHeader {
  background: var(--mu-card) !important;
  border: 1px solid var(--mu-border) !important;
  color: var(--mu-text2) !important;
  font-family: var(--mono) !important;
  font-size: 0.78rem !important;
  letter-spacing: 0.06em !important;
}
.streamlit-expanderContent {
  background: var(--mu-card) !important;
  border: 1px solid var(--mu-border) !important;
  border-top: none !important;
}

/* Alerts */
.stAlert { border-radius: 3px !important; border-left-width: 3px !important; }
.stSuccess { border-left-color: var(--mu-green) !important; background: rgba(61,214,140,0.08) !important; }
.stWarning { border-left-color: var(--mu-warn) !important; background: rgba(255,159,28,0.08) !important; }
.stError   { border-left-color: var(--mu-danger) !important; background: rgba(255,77,109,0.08) !important; }
.stInfo    { border-left-color: var(--mu-blue) !important; background: rgba(66,165,245,0.08) !important; }

/* Spinner */
.stSpinner > div { border-top-color: var(--mu-red) !important; }

/* Divider */
hr { border-color: var(--mu-border) !important; margin: 1.5rem 0 !important; }

/* Buttons */
.stButton > button {
  background: var(--mu-card) !important;
  border: 1px solid var(--mu-border2) !important;
  color: var(--mu-text2) !important;
  font-family: var(--mono) !important;
  font-size: 0.72rem !important;
  letter-spacing: 0.1em !important;
  text-transform: uppercase !important;
  border-radius: 3px !important;
  transition: all 0.15s !important;
}
.stButton > button:hover {
  border-color: var(--mu-red) !important;
  color: var(--mu-text) !important;
}
.stButton > button[kind="primary"] {
  background: var(--mu-red) !important;
  border-color: var(--mu-red) !important;
  color: #fff !important;
}

/* Slider */
.stSlider [data-testid="stSliderThumb"] { background: var(--mu-red) !important; }
.stSlider .rc-slider-track { background: var(--mu-red) !important; }

/* Caption */
.stCaption, [data-testid="stCaptionContainer"] {
  color: var(--mu-text4) !important;
  font-family: var(--mono) !important;
  font-size: 0.68rem !important;
  letter-spacing: 0.08em !important;
}

/* Columns gap */
[data-testid="column"] { padding: 0 0.4rem !important; }

/* ── MU Custom Components ─────────────────────────────────────────── */

/* Page header bar */
.mu-page-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 0 18px 0;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--mu-border);
}
.mu-page-bar-accent {
  width: 4px;
  height: 28px;
  background: var(--mu-red);
  border-radius: 2px;
  flex-shrink: 0;
}
.mu-page-bar-brand {
  font-family: var(--display);
  font-size: 1.05rem;
  letter-spacing: 0.15em;
  color: var(--mu-red);
  text-transform: uppercase;
}
.mu-page-bar-sep {
  color: var(--mu-border2);
  font-size: 1.2rem;
  line-height: 1;
}
.mu-page-title {
  font-family: var(--display);
  font-size: 1.8rem;
  letter-spacing: 0.06em;
  color: var(--mu-text);
  text-transform: uppercase;
  line-height: 1;
}
.mu-page-sub {
  font-family: var(--mono);
  font-size: 0.65rem;
  letter-spacing: 0.15em;
  color: var(--mu-text4);
  text-transform: uppercase;
  margin-top: 2px;
}

/* Section headers */
.mu-section {
  margin: 1.8rem 0 0.8rem;
}
.mu-section-label {
  font-family: var(--mono);
  font-size: 0.62rem;
  letter-spacing: 0.28em;
  color: var(--mu-red);
  text-transform: uppercase;
  margin-bottom: 3px;
}
.mu-section-title {
  font-family: var(--display);
  font-size: 1.6rem;
  letter-spacing: 0.06em;
  color: var(--mu-text);
  text-transform: uppercase;
  line-height: 1.05;
}

/* Old section-header class — update to new style */
.section-header {
  font-family: var(--display) !important;
  font-size: 1.4rem !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: var(--mu-text) !important;
  border-bottom: 1px solid var(--mu-border) !important;
  padding-bottom: 0.25rem !important;
  margin-bottom: 0.8rem !important;
}

/* KPI tiles — compact stat strip */
.mu-tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1px;
  background: var(--mu-border);
  border: 1px solid var(--mu-border);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 1.2rem;
}
.mu-tile {
  background: var(--mu-card);
  padding: 0.8rem 1rem;
  border-top: 2px solid rgba(218,41,28,0.35);
}
.mu-tile-label {
  font-family: var(--mono);
  font-size: 0.58rem;
  letter-spacing: 0.18em;
  color: var(--mu-text3);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.mu-tile-value {
  font-family: var(--mono);
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--mu-text);
  line-height: 1;
}
.mu-tile-sub {
  font-family: var(--mono);
  font-size: 0.6rem;
  color: var(--mu-text4);
  margin-top: 3px;
}

/* KPI card — existing class updated */
.kpi-card {
  background: var(--mu-card);
  border: 1px solid var(--mu-border);
  border-top: 2px solid rgba(218,41,28,0.5);
  border-radius: 3px;
  padding: 0.9rem 1rem;
  margin: 0.3rem 0;
}
.kpi-card .kpi-value {
  font-family: var(--mono);
  font-size: 1.9rem;
  font-weight: 800;
  color: var(--mu-text);
  margin: 0;
  line-height: 1;
}
.kpi-card .kpi-label {
  font-family: var(--mono);
  font-size: 0.6rem;
  color: var(--mu-text3);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  margin: 0 0 4px 0;
}
.kpi-card .kpi-delta { font-family: var(--mono); font-size: 0.75rem; margin-top: 4px; }
.kpi-card .kpi-delta.positive { color: var(--mu-green); }
.kpi-card .kpi-delta.negative { color: var(--mu-danger); }

/* Card container */
.mu-card {
  background: var(--mu-card);
  border: 1px solid var(--mu-border);
  border-radius: 4px;
  padding: 1rem 1.2rem;
  margin-bottom: 0.8rem;
}
.mu-card-title {
  font-family: var(--mono);
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  color: var(--mu-text3);
  text-transform: uppercase;
  margin-bottom: 0.8rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--mu-border);
}

/* Form badges */
.form-badge {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  font-weight: 800;
  font-size: 0.68rem;
  margin: 0 2px;
  font-family: var(--mono);
  color: #0E0E14;
}
.form-badge.W { background-color: var(--mu-green); }
.form-badge.D { background-color: var(--mu-gold); }
.form-badge.L { background-color: var(--mu-danger); }

/* ── Match Header (V2/V3 style) ──────────────────────────────────── */
.match-header {
  background: var(--mu-card);
  border: 1px solid var(--mu-border);
  border-radius: 4px;
  padding: 1.2rem 1.8rem;
  margin-bottom: 1rem;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.match-header::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 55% 80% at 15% 50%, rgba(218,41,28,0.07) 0%, transparent 70%),
    radial-gradient(ellipse 55% 80% at 85% 50%, rgba(66,165,245,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.match-header .match-meta {
  font-family: var(--mono);
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  color: var(--mu-text4);
  text-transform: uppercase;
  margin-bottom: 0.8rem;
  position: relative;
}
.match-header .score-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  position: relative;
}
.match-header .team-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 120px;
  flex: 1;
  max-width: 200px;
}
.match-header .team-block img {
  width: 56px;
  height: 56px;
  object-fit: contain;
  margin-bottom: 0.4rem;
  filter: drop-shadow(0 2px 8px rgba(0,0,0,0.5));
}
.match-header .team-block .team-name {
  font-family: var(--display);
  font-size: 1rem;
  letter-spacing: 0.06em;
  color: var(--mu-text2);
  text-transform: uppercase;
  line-height: 1.1;
}
.match-header .score-display {
  font-family: var(--display);
  font-size: clamp(2.8rem, 6vw, 4.5rem);
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1;
  display: flex;
  align-items: center;
  gap: 0.15em;
}
.match-header .score-display .home-score { color: var(--mu-red); }
.match-header .score-display .away-score { color: var(--mu-blue); }
.match-header .score-display .score-sep { color: var(--mu-border2); }
.match-header .ht-score {
  font-family: var(--mono);
  font-size: 0.65rem;
  color: var(--mu-text4);
  letter-spacing: 0.12em;
  margin-top: 0.4rem;
  position: relative;
}

/* ── Stats Comparison (V2 style) ─────────────────────────────────── */
.stat-comparison { padding: 0.2rem 0; max-width: 720px; margin: 0 auto 1rem; }
.stat-row {
  display: grid;
  grid-template-columns: 52px 1fr 110px 1fr 52px;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid #1A1A22;
}
.stat-row .stat-val {
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 800;
  color: var(--mu-text2);
}
.stat-row .stat-val.home { text-align: right; color: var(--mu-red); }
.stat-row .stat-val.away { text-align: left; color: var(--mu-blue); }
.stat-row .stat-label {
  text-align: center;
  font-family: var(--mono);
  font-size: 0.58rem;
  color: var(--mu-text4);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.stat-row .bar-container {
  height: 4px;
  background: #0E0E14;
  border-radius: 2px;
  overflow: hidden;
}
.stat-row .bar-fill-home { height: 100%; background: var(--mu-red); border-radius: 2px 0 0 2px; float: right; }
.stat-row .bar-fill-away { height: 100%; background: var(--mu-blue); border-radius: 0 2px 2px 0; float: left; }

/* ── Event Timeline ───────────────────────────────────────────────── */
.event-timeline { position: relative; padding: 0.4rem 0 0.4rem 36px; }
.event-timeline::before {
  content: '';
  position: absolute;
  left: 26px; top: 0; bottom: 0;
  width: 1px;
  background: var(--mu-border);
}
.event-item { display: flex; align-items: center; padding: 0.3rem 0; position: relative; }
.event-item .event-minute {
  position: absolute; left: -34px; width: 26px; text-align: right;
  font-family: var(--mono); font-size: 0.7rem; font-weight: 700; color: var(--mu-text4);
}
.event-item .event-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  margin-right: 10px; position: relative; left: -9px; z-index: 1;
}
.event-item .event-icon { font-size: 0.85rem; margin-right: 6px; }
.event-item .event-detail { font-family: var(--mono); font-size: 0.75rem; color: var(--mu-text3); }
.event-item .event-detail .player-name { font-weight: 700; color: var(--mu-text2); }

/* Content card */
.content-card {
  background: var(--mu-card);
  border: 1px solid var(--mu-border);
  border-radius: 4px;
  padding: 0.9rem 1.1rem;
  margin-bottom: 0.8rem;
}
.content-card .card-title {
  font-family: var(--mono);
  font-size: 0.62rem;
  color: var(--mu-text3);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  border-bottom: 1px solid var(--mu-border);
  padding-bottom: 0.4rem;
  margin-bottom: 0.8rem;
}

/* ── V3 Hero Components (Post Match Analysis) ────────────────────── */
.v3-hero {
  position: relative;
  background: #08080C;
  border: 1px solid var(--mu-border);
  border-radius: 6px;
  overflow: hidden;
  padding: 2rem 2rem 1.8rem;
  margin-bottom: 1.5rem;
  text-align: center;
}
.v3-hero::before {
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 55% 45% at 20% 50%, rgba(218,41,28,0.11) 0%, transparent 70%),
    radial-gradient(ellipse 55% 45% at 80% 50%, rgba(66,165,245,0.09) 0%, transparent 70%),
    repeating-linear-gradient(-45deg, transparent, transparent 28px, rgba(255,255,255,0.01) 28px, rgba(255,255,255,0.01) 29px);
  pointer-events: none;
}
.v3-competition {
  font-family: var(--mono); font-size: 0.62rem; letter-spacing: 0.22em;
  color: var(--mu-text4); text-transform: uppercase; margin-bottom: 1rem; position: relative;
}
.v3-score-row { display: flex; align-items: center; justify-content: center; gap: 1.5rem; position: relative; margin-bottom: 0.8rem; }
.v3-team-block { display: flex; flex-direction: column; align-items: center; min-width: 120px; flex: 1; max-width: 200px; }
.v3-team-block img { width: 60px; height: 60px; object-fit: contain; margin-bottom: 0.4rem; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.6)); }
.v3-team-name { font-family: var(--display); font-size: 1rem; letter-spacing: 0.07em; color: var(--mu-text2); text-transform: uppercase; line-height: 1.1; }
.v3-score-center { display: flex; flex-direction: column; align-items: center; min-width: 150px; }
.v3-score-digits { font-family: var(--display); font-size: clamp(3.5rem, 9vw, 6rem); line-height: 1; letter-spacing: -0.02em; display: flex; align-items: center; gap: 0.1em; }
.v3-score-home { background: linear-gradient(160deg, #FF5555 0%, #DA291C 60%, #8B0000 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.v3-score-sep { color: #1E1E2A; font-size: 0.7em; padding: 0 0.05em; -webkit-text-fill-color: #1E1E2A; }
.v3-score-away { background: linear-gradient(160deg, #90CAF9 0%, #42A5F5 60%, #1565C0 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.v3-ht { font-family: var(--mono); font-size: 0.65rem; color: var(--mu-text4); letter-spacing: 0.1em; margin-top: 0.25rem; }
.v3-meta-row { font-family: var(--mono); font-size: 0.62rem; color: var(--mu-text4); letter-spacing: 0.12em; text-transform: uppercase; position: relative; margin-top: 0.6rem; }
.v3-xg-strip { display: flex; align-items: center; justify-content: center; position: relative; margin-top: 1.2rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.04); }
.v3-xg-block { flex: 1; text-align: center; padding: 0 1rem; }
.v3-xg-label { font-family: var(--mono); font-size: 0.58rem; letter-spacing: 0.18em; color: var(--mu-text4); text-transform: uppercase; margin-bottom: 2px; }
.v3-xg-value-home { font-family: var(--display); font-size: 2.2rem; line-height: 1; color: var(--mu-red); letter-spacing: 0.02em; }
.v3-xg-value-away { font-family: var(--display); font-size: 2.2rem; line-height: 1; color: var(--mu-blue); letter-spacing: 0.02em; }
.v3-xg-divider { font-family: var(--mono); font-size: 0.58rem; color: var(--mu-border2); letter-spacing: 0.15em; writing-mode: vertical-lr; padding: 0 0.4rem; border-left: 1px solid var(--mu-border); border-right: 1px solid var(--mu-border); }
.v3-xg-story { font-family: var(--mono); font-size: 0.62rem; color: var(--mu-text4); letter-spacing: 0.08em; margin-top: 0.5rem; font-style: italic; position: relative; }

/* V3 Section Headers */
.v3-section { margin: 1.8rem 0 0.8rem; }
.v3-section-rule { font-family: var(--mono); font-size: 0.58rem; letter-spacing: 0.28em; color: var(--mu-red); margin-bottom: 2px; }
.v3-section-title { font-family: var(--display); font-size: 1.6rem; letter-spacing: 0.06em; color: var(--mu-text); text-transform: uppercase; line-height: 1; margin: 0; }

/* V3 Stat bars */
.v3-stat-row { display: grid; grid-template-columns: 52px 1fr 120px 1fr 52px; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid #1A1A22; }
.v3-stat-val { font-family: var(--mono); font-size: 0.85rem; font-weight: 800; }
.v3-stat-val.home { text-align: right; color: var(--mu-red); }
.v3-stat-val.away { text-align: left; color: var(--mu-blue); }
.v3-stat-label { width: 120px; text-align: center; font-family: var(--mono); font-size: 0.58rem; color: var(--mu-text4); text-transform: uppercase; letter-spacing: 0.1em; }
.v3-bar-wrap { height: 4px; background: #0E0E14; border-radius: 2px; overflow: hidden; }
.v3-bar-home { height: 100%; background: var(--mu-red); border-radius: 2px; float: right; }
.v3-bar-away { height: 100%; background: var(--mu-blue); border-radius: 2px; }

/* V3 Rating cards */
.v3-rating-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 0.5rem; margin-top: 0.6rem; }
.v3-rating-card { background: var(--mu-card); border: 1px solid var(--mu-border); border-radius: 3px; padding: 0.5rem 0.7rem; display: flex; justify-content: space-between; align-items: center; }
.v3-rating-name { font-family: var(--mono); font-size: 0.72rem; color: var(--mu-text3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80px; }
.v3-rating-score { font-family: var(--display); font-size: 1.1rem; letter-spacing: 0.05em; }
.v3-rating-green { color: var(--mu-green); }
.v3-rating-gold  { color: var(--mu-gold); }
.v3-rating-normal { color: var(--mu-text3); }

/* League table rows */
.standings-table { border-collapse: collapse; width: 100%; font-family: var(--mono); font-size: 0.78rem; }
.standings-table th { font-size: 0.6rem; letter-spacing: 0.1em; color: var(--mu-text4); text-transform: uppercase; padding: 6px 8px; border-bottom: 1px solid var(--mu-border); text-align: center; }
.standings-table td { padding: 5px 8px; border-bottom: 1px solid #1A1A22; color: var(--mu-text2); text-align: center; }
.standings-table tr:hover td { background: var(--mu-card2); }
.standings-table .rank-mu { color: var(--mu-red); font-weight: 800; }
</style>
"""


def apply_theme():
    """Inject global CSS into the Streamlit app."""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
