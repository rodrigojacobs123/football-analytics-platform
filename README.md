# ⚽ Football Analytics Platform

> **Master's Thesis — Big Data & Sports Analytics**  
> A production-ready, 9-module Streamlit platform for in-depth football intelligence, built on Opta-format event data spanning **30+ leagues, 77 seasons, and 18 years of Premier League history**.

---

## What this is

A full end-to-end sports analytics application — from raw Opta JSON event files to interactive dashboards — covering pre-match prediction, live match reconstruction, player scouting, tactical analysis, and injury intelligence.

Built as a thesis project, designed to the standard of a professional analytics platform (think: a self-hosted version of StatsBomb IQ or Twenty3 Insight).

---

## Modules

| # | Page | What it does |
|---|------|-------------|
| 🏠 | **Home** | Season KPI dashboard · league table · 18-season cross-season trend explorer |
| 🎯 | **Pre-Match Analysis** | Recent form · Elo ratings · head-to-head history · team radar · Poisson match prediction |
| 📊 | **Post-Match Analysis** | xG timeline race · shot maps · pass network · touch heatmaps · key events timeline · formation viewer |
| ♟️ | **Tactics** | Formation display (from Opta qualifier 44) · pass network by period · defensive action map · progressive passes · ball-win height |
| 🎯 | **xG Explorer** | Interactive shot explorer with pitch viz, xG filters, and outcome breakdown |
| 🔍 | **Player Scouting** | FIFA-style attribute cards (PAC / SHO / PAS / DRI / DEF / PHY) · play-style detection · multi-season leaderboard |
| 🏥 | **Injury Tracker** | Synthetic injury intelligence · absence timeline · squad availability calendar |
| 💾 | **Data Sources** | Dataset diagnostics · file counts · schema documentation |
| 👔 | **Manager Profiles** | Manager comparison · tenure history · win-rate and style breakdown |

---

## Technical highlights

### Analytics models
- **xG model** — logistic regression trained on shot coordinates, body part, assist type, preceding sequence (qualifier 395/396)
- **Elo rating system** — dynamic team strength ratings updated match-by-match with K-factor tuning; used in form + head-to-head panels
- **Poisson prediction** — attack/defence strength computed from Elo-adjusted expected goals; 10 000 Monte Carlo simulations per fixture for scoreline probabilities
- **Match & player ratings** — composite per-player ratings from pass completion, shot volume/quality, defensive actions, progressive carries, and card penalties

### Data engineering
- Opta-format JSON parser (`data/event_parser.py`) handling 40+ event types with qualifier extraction
- Formation extraction from qualifier 44 (position rows) + qualifier 130 (formation type ID) with a fallback derivation
- **Lateral player positioning** via average touch y-position from match events — more accurate than nominal qualifiers
- `@st.cache_data(ttl=3600)` throughout — season-wide bundles load once; per-match files load on demand
- Path abstraction layer (`data/paths.py`) so no page touches the filesystem directly

### Architecture
```
app.py                          # Streamlit entry point + page registry
├── pages/                      # One file per module (9 pages)
├── data/
│   ├── paths.py                # Path builders — no I/O
│   ├── loader.py               # Cached JSON/CSV readers
│   └── event_parser.py         # Opta JSON → flat DataFrames
├── processing/                 # Pure-pandas analytics (no Streamlit)
│   ├── xg.py / xg_model.py
│   ├── elo.py
│   ├── poisson.py
│   ├── formations.py
│   ├── pass_network.py
│   ├── match_ratings.py
│   ├── player_ratings.py
│   ├── play_style.py
│   ├── set_pieces.py
│   └── ...
├── viz/
│   ├── theme.py                # Global CSS design system (dark MU palette)
│   ├── charts.py               # Plotly chart library
│   ├── pitch.py                # mplsoccer + Plotly pitch visualizations
│   ├── kpi_cards.py            # HTML KPI card components
│   └── radar.py
└── components/                 # Reusable Streamlit selectors
```

### Stack

| Layer | Technology |
|-------|-----------|
| UI framework | Streamlit ≥ 1.36 |
| Data manipulation | Pandas, NumPy |
| Interactive charts | Plotly (dark theme) |
| Pitch visualizations | mplsoccer + custom Plotly formations |
| Prediction models | SciPy (Poisson), scikit-learn (logistic regression xG) |
| Styling | Custom CSS design system via `st.markdown` — Anton + JetBrains Mono typography |

---

## Data

The platform is built for **Opta-format** JSON event data. Each league/season follows this structure:

```
<League>/<Season>/
├── jsons/
│   ├── matches.json       # season-wide match summaries + events
│   ├── standings.json
│   └── squads.json
├── partidos/<match_id>.json   # per-match Opta event files (loaded on demand)
└── equipos/<Team>/            # per-team CSVs and player stats
```

> **Note on data:** The Opta dataset used for this thesis is proprietary and not included in this repo. To run the platform locally you can substitute **StatsBomb Open Data** (freely available at [github.com/statsbomb/open-data](https://github.com/statsbomb/open-data)) by writing an adapter in `data/loader.py` that maps StatsBomb's schema to the field names expected by `data/event_parser.py`.

Key Opta conventions the parser handles:
- Shots: `typeId ∈ {13,14,15,16}` · xG in qualifier 395
- Formation rows: qualifier 44 (1=GK / 2=DEF / 3=MID / 4=FWD)
- Formation type string: qualifier 130 → mapped through `OPTA_FORMATION_MAP`
- Penalty distinction: qualifier 9 (penalty kick), **not** qualifier 22 (inside penalty area)

---

## Running locally

```bash
git clone https://github.com/<your-username>/football-analytics-platform
cd football-analytics-platform

pip install -r requirements.txt

# Point the app at your data
export MU_DATA_ROOT=/path/to/your/opta-data

streamlit run app.py
# → http://localhost:8501
```

To kill a stuck server: `lsof -ti:8501 | xargs kill -9`

---

## Selected screenshots

> *(Add screenshots here — `docs/screenshots/` folder recommended)*

---

## About

Built as the final project for a Master's in Big Data & Sports Analytics. The goal was to replicate the core analytical capabilities of professional football intelligence platforms using open-source tooling and publicly documentable methods — demonstrating that rigorous sports analytics doesn't require a £50k SaaS subscription.

**Contact:** rodrigojacobs123@gmail.com
