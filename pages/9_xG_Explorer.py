"""xG Explorer — Interactive shot explorer with filters, pitch visualization."""

import streamlit as st
from viz.theme import apply_theme
import pandas as pd
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_row, page_header, ame_section
from viz.pitch import plot_shot_map
from viz.charts import bar_chart, donut_chart, histogram, goalmouth_shot_map
from viz.tables import styled_dataframe
from data.loader import load_club_match_list, load_match_raw, build_player_name_map
from data.event_parser import extract_shots, parse_match_info
from processing.xgot import (
    add_xgot, player_finishing, keeper_shot_stopping, XGOT_DISCLAIMER,
)
from config import AME_TEAM_ID, AME_TEAM_NAME, AME_YELLOW, AME_BLUE

apply_theme()

league, season = render_sidebar()

page_header("xG Explorer", subtitle="Interactive shot analysis across the season")

# ── Load all club shots for the season ────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_season_shots(_league: str, _season: str) -> pd.DataFrame:
    """Load all shots from club matches for the season."""
    matches = load_club_match_list(_league, _season)
    if matches.empty:
        return pd.DataFrame()

    all_shots = []
    for _, match in matches.iterrows():
        mid = match.get("match_id", "")
        if not mid:
            continue
        raw = load_match_raw(_league, _season, mid)
        if not raw:
            continue
        info = parse_match_info(raw)
        events = raw.get("liveData", {}).get("event", [])
        shots = extract_shots(events)
        if not shots.empty:
            shots["match_id"] = mid
            shots["matchday"] = info["matchday"]
            shots["home_team"] = info["home_team"]
            shots["away_team"] = info["away_team"]
            shots["date"] = info["date"]
            all_shots.append(shots)

    if not all_shots:
        return pd.DataFrame()
    return add_xgot(pd.concat(all_shots, ignore_index=True))


with st.spinner("Loading season shot data..."):
    season_shots = load_season_shots(league, season)

if season_shots.empty:
    st.warning("No shot data available for this season.")
    st.stop()

name_map = build_player_name_map(league, season)
season_shots["player_display"] = season_shots.apply(
    lambda r: name_map.get(r["player_id"], r["player_name"]), axis=1
)

# ── Filters ─────────────────────────────────────────────────────────────────
section_header("Filters")
col1, col2, col3, col4 = st.columns(4)

with col1:
    team_filter = st.selectbox("Team", ["All", AME_TEAM_NAME, "Opponents"], key="xg_team")
with col2:
    outcomes = season_shots["outcome"].unique().tolist()
    outcome_filter = st.multiselect("Outcome", outcomes, default=outcomes, key="xg_outcome")
with col3:
    body_parts = season_shots["body_part"].dropna().unique().tolist()
    body_filter = st.multiselect("Body Part", body_parts, default=body_parts, key="xg_body")
with col4:
    min_range = st.slider("Minute Range", 0, 95,
                          (0, 95), key="xg_minute")

# Apply filters
filtered = season_shots.copy()
if team_filter == AME_TEAM_NAME:
    filtered = filtered[filtered["team_id"] == AME_TEAM_ID]
elif team_filter == "Opponents":
    filtered = filtered[filtered["team_id"] != AME_TEAM_ID]
filtered = filtered[filtered["outcome"].isin(outcome_filter)]
filtered = filtered[filtered["body_part"].isin(body_filter)]
filtered = filtered[(filtered["minute"] >= min_range[0]) & (filtered["minute"] <= min_range[1])]

# ── KPIs ────────────────────────────────────────────────────────────────────
goals = filtered[filtered["outcome"] == "Goal"]
total_xg = filtered["xg"].sum()
conversion = (len(goals) / len(filtered) * 100) if len(filtered) > 0 else 0
xg_diff = len(goals) - total_xg

kpi_row([
    {"label": "Total Shots", "value": len(filtered)},
    {"label": "Goals", "value": len(goals)},
    {"label": "Total xG", "value": f"{total_xg:.2f}"},
    {"label": "Conversion %", "value": f"{conversion:.1f}%"},
])
st.markdown("")
on_target = filtered[filtered.get("on_target", False) & filtered["xgot"].notna()] \
    if "xgot" in filtered.columns else filtered.iloc[0:0]
total_xgot = on_target["xgot"].sum()
col1, col2, col3 = st.columns(3)
col1.metric("Goals - xG", f"{xg_diff:+.2f}")
col2.metric("Avg xG/Shot", f"{(total_xg / len(filtered)):.3f}" if len(filtered) > 0 else "0")
col3.metric("Total xGOT (on-target)", f"{total_xgot:.2f}",
            help="Post-shot xG — chance quality combined with shot placement.")

# ── Shot Map ────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Shot Map")
plot_shot_map(filtered, title=f"Shots ({team_filter})")

# ── Situation Breakdown ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    section_header("Outcome Distribution")
    outcome_counts = filtered["outcome"].value_counts()
    fig = donut_chart(
        outcome_counts.index.tolist(), outcome_counts.values.tolist(),
        title="Shot Outcomes",
        colors=[AME_YELLOW, AME_BLUE, "#888888", "#FF9800", "#42A5F5"],
    )
    st.plotly_chart(fig, width="stretch")

with col2:
    section_header("Body Part Distribution")
    body_counts = filtered["body_part"].value_counts()
    fig = donut_chart(
        body_counts.index.tolist(), body_counts.values.tolist(),
        title="Shot Type",
    )
    st.plotly_chart(fig, width="stretch")

# ── xG Distribution ────────────────────────────────────────────────────────
section_header("xG Distribution")
fig = histogram(filtered["xg"], title="Distribution of xG Values",
                x_label="xG", nbins=25)
st.plotly_chart(fig, width="stretch")

# ── Finishing Quality (xGOT / Post-Shot xG) ─────────────────────────────────
st.markdown("---")
section_header("Finishing Quality — xGOT (Post-Shot xG)")
st.caption(XGOT_DISCLAIMER)

gm_col, fin_col = st.columns([1, 1])
with gm_col:
    fig = goalmouth_shot_map(on_target, title="Where on-target shots were placed")
    st.plotly_chart(fig, width="stretch")
with fin_col:
    finishing = player_finishing(filtered)
    if not finishing.empty:
        finishing["player_display"] = finishing["player_id"].map(name_map).fillna(
            finishing["player_name"])
        fin_tbl = finishing[finishing["shots_on_target"] >= 3][[
            "player_display", "shots_on_target", "goals", "xgot", "finishing"
        ]].copy()
        fin_tbl.columns = ["Player", "On-Target", "Goals", "xGOT", "Finishing (xGOT-xG)"]
        fin_tbl["xGOT"] = fin_tbl["xGOT"].round(2)
        fin_tbl["Finishing (xGOT-xG)"] = fin_tbl["Finishing (xGOT-xG)"].round(2)
        st.markdown("**Finishing leaderboard** (min 3 on-target shots)")
        styled_dataframe(fin_tbl.head(15), height=460)
    else:
        st.info("No on-target shots with goal-mouth data in the current filter.")

# ── Goalkeeper Shot-Stopping ─────────────────────────────────────────────────
section_header("Goalkeeper Shot-Stopping")
ks = keeper_shot_stopping(season_shots, AME_TEAM_ID)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Shots on Target Faced", ks["shots_faced"])
k2.metric("Goals Conceded", ks["goals_conceded"])
k3.metric("PSxG Faced", f"{ks['psxg_faced']:.2f}",
          help="Post-shot xG of shots faced — goals an average keeper would concede.")
k4.metric("Shot-Stopping +/-", f"{ks['shot_stopping']:+.2f}",
          help="PSxG faced minus goals conceded. Positive = saved more than expected.")
st.caption(f"{AME_TEAM_NAME} goalkeeping over the season "
           "(open-play on-target shots; penalties excluded).")

# ── Player xG Leaderboard ──────────────────────────────────────────────────
st.markdown("---")
section_header("Player xG Leaderboard")
player_xg = filtered.groupby("player_display").agg(
    shots=("xg", "count"),
    total_xg=("xg", "sum"),
    goals=("outcome", lambda x: (x == "Goal").sum()),
).reset_index()
player_xg["xg_diff"] = player_xg["goals"] - player_xg["total_xg"]
player_xg = player_xg.sort_values("total_xg", ascending=False)
player_xg.columns = ["Player", "Shots", "Total xG", "Goals", "Goals - xG"]
player_xg["Total xG"] = player_xg["Total xG"].round(2)
player_xg["Goals - xG"] = player_xg["Goals - xG"].round(2)
styled_dataframe(player_xg.head(20), height=500)

# ── Player Drill-Down ───────────────────────────────────────────────────────
st.markdown("---")
section_header("Player Drill-Down")
players = filtered["player_display"].dropna().unique().tolist()
if players:
    selected_player = st.selectbox("Select Player", sorted(players), key="xg_player")
    player_shots = filtered[filtered["player_display"] == selected_player]

    col1, col2 = st.columns([2, 1])
    with col1:
        plot_shot_map(player_shots, title=f"{selected_player} Shot Map")
    with col2:
        st.metric("Shots", len(player_shots))
        st.metric("Goals", len(player_shots[player_shots["outcome"] == "Goal"]))
        st.metric("xG", f"{player_shots['xg'].sum():.2f}")

    # Shot log
    log = player_shots[["minute", "outcome", "xg", "body_part", "matchday"]].copy()
    log.columns = ["Minute", "Outcome", "xG", "Body Part", "Matchday"]
    log["xG"] = log["xG"].round(3)
    styled_dataframe(log.sort_values("Minute"), height=300)
