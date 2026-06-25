"""Home — Season KPI dashboard with player stats, multi-season trends, and performance maps."""

import streamlit as st
from viz.theme import apply_theme
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from components.sidebar import render_sidebar
from viz.kpi_cards import kpi_row, section_header, form_badges, page_header, ame_section
from viz.tables import styled_league_table
from viz.charts import line_chart, grouped_bar_chart
from viz.kpi_cards import kpi_card
from viz.xt import xt_top_contributors_bar
from data.loader import (
    load_standings, load_club_match_list, load_all_season_results,
    load_player_season_stats, list_standings_stages,
)
from processing.team_stats import compute_points_by_matchday, compute_standings_from_results
from processing.poisson import _resolve_team_in_results
from processing.xt import compute_season_xt
from data.paths import list_seasons
from config import (
    AME_TEAM_NAME, AME_TEAM_ID, AME_TEAM_FOLDER, AME_YELLOW, AME_BLUE,
    AME_DARK_BG, AME_CARD_BG, AME_WHITE,
    DEFAULT_LEAGUE, COMPETITIONS, AME_LEAGUES,
)

apply_theme()

league, season = render_sidebar()

comp_display = COMPETITIONS.get(league, league)
page_header("Season Dashboard", subtitle=f"{season} · {comp_display}")

# ── Liga MX tournament selector (Apertura / Clausura) ──────────────────────
_stage_names = list_standings_stages(league, season)
_selected_stage = ""
if len(_stage_names) > 1:
    _selected_stage = st.radio(
        "Tournament",
        options=_stage_names,
        index=len(_stage_names) - 1,   # default to last (Clausura)
        horizontal=True,
        key="liga_mx_stage_selector",
    )
    st.markdown(
        f"<p style='font-size:0.78rem;color:#888;margin-top:-0.5rem;'>"
        f"Liga MX uses two separate tournaments per year — "
        f"<b>Apertura</b> (Jul–Nov) and <b>Clausura</b> (Jan–May). "
        f"Standings reset each tournament.</p>",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════
# § 0  KPI HEADER — Position, Points, Record, Goal Difference
# ═══════════════════════════════════════════════════════════════════════════
# Load standings — prefer computed table when the static JSON is stale
_json_standings = load_standings(league, season, stage_name=_selected_stage)
_computed_standings = compute_standings_from_results(league, season)

# Prefer computed standings ONLY if they have marginally more matches than the JSON
# (i.e., data is fresh/newer). For bi-annual leagues (Liga MX), the computed table
# combines Apertura+Clausura which inflates played counts — always prefer the JSON there.
_has_stages = len(_stage_names) > 1
if (not _has_stages
        and not _computed_standings.empty
        and (_json_standings.empty
             or _computed_standings["played"].max() > _json_standings["played"].max())):
    standings = _computed_standings
else:
    standings = _json_standings

is_ame_league = league in AME_LEAGUES
# For bi-annual leagues pass the selected tournament as a stage filter so
# W/D/L, GF/GA and rank all reflect the correct Apertura or Clausura only.
club_matches = (
    load_club_match_list(league, season, stage_filter=_selected_stage)
    if is_ame_league else pd.DataFrame()
)

if not club_matches.empty:
    wins = int((club_matches["result"] == "W").sum())
    draws = int((club_matches["result"] == "D").sum())
    losses = int((club_matches["result"] == "L").sum())
    gf = int(club_matches["club_score"].sum())
    ga = int(club_matches["opp_score"].sum())
    gd = gf - ga
    played = len(club_matches)
    points = wins * 3 + draws

    # Compute rank from all match results — same stage filter as club_matches
    rank = "–"
    all_results = load_all_season_results(league, season, stage_filter=_selected_stage)
    if not all_results.empty:
        team_points = {}
        for _, r in all_results.iterrows():
            hs, as_ = r["home_score"], r["away_score"]
            ht, at = r["home_team"], r["away_team"]
            if hs > as_:
                team_points[ht] = team_points.get(ht, 0) + 3
                team_points[at] = team_points.get(at, 0)
            elif hs == as_:
                team_points[ht] = team_points.get(ht, 0) + 1
                team_points[at] = team_points.get(at, 0) + 1
            else:
                team_points[at] = team_points.get(at, 0) + 3
                team_points[ht] = team_points.get(ht, 0)
        ame_resolved = _resolve_team_in_results(all_results, AME_TEAM_NAME, AME_TEAM_ID)
        sorted_teams = sorted(team_points.items(), key=lambda x: -x[1])
        for i, (t, _) in enumerate(sorted_teams, 1):
            if t == ame_resolved:
                rank = f"#{i}"
                break

    kpi_row([
        {"label": "League Position", "value": rank},
        {"label": "Points", "value": points},
        {"label": "Record (W-D-L)", "value": f"{wins}-{draws}-{losses}"},
        {"label": "Goal Difference", "value": f"{gd:+d}", "delta": gd},
    ])

    st.markdown("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matches", played)
    col2.metric("Goals For", gf)
    col3.metric("Goals Against", ga)
    col4.metric("Points/Match", round(points / max(played, 1), 2))

    form_list = list(club_matches["result"].tail(6))
    if form_list:
        st.markdown("**Recent Form:** " + form_badges(form_list), unsafe_allow_html=True)

elif not standings.empty and AME_TEAM_NAME in standings["team_name"].values:
    ame_row = standings[standings["team_name"] == AME_TEAM_NAME].iloc[0]
    kpi_row([
        {"label": "League Position", "value": f"#{int(ame_row['rank'])}"},
        {"label": "Points", "value": int(ame_row["points"])},
        {"label": "Record (W-D-L)", "value": f"{int(ame_row['won'])}-{int(ame_row['drawn'])}-{int(ame_row['lost'])}"},
        {"label": "Goal Difference", "value": f"{int(ame_row['gd']):+d}", "delta": int(ame_row["gd"])},
    ])
    st.markdown("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matches", int(ame_row["played"]))
    col2.metric("Goals For", int(ame_row["gf"]))
    col3.metric("Goals Against", int(ame_row["ga"]))
    col4.metric("Points/Match", round(ame_row["points"] / max(ame_row["played"], 1), 2))
    last_six = ame_row.get("last_six", "")
    if last_six:
        form_list = list(last_six.replace(",", ""))
        st.markdown("**Recent Form:** " + form_badges(form_list), unsafe_allow_html=True)
else:
    st.warning("CF América not found in standings for this season.")


# ═══════════════════════════════════════════════════════════════════════════
# § 1  MULTI-SEASON DATA COLLECTION
# ═══════════════════════════════════════════════════════════════════════════
# Collect historical data across all available seasons
all_seasons = list_seasons(league)

season_history = []  # W/D/L, GF/GA, rank per season
for s in all_seasons:
    st_df = load_standings(league, s)  # default = last stage (Clausura) — consistent for trends
    # Upgrade to computed standings ONLY when JSON is stale and not bi-annual league
    if not _has_stages:
        comp_df = compute_standings_from_results(league, s)
        if (not comp_df.empty
                and (st_df.empty or comp_df["played"].max() > st_df["played"].max())):
            st_df = comp_df
    if st_df.empty or AME_TEAM_NAME not in st_df["team_name"].values:
        continue
    row = st_df[st_df["team_name"] == AME_TEAM_NAME].iloc[0]
    # Also try to get aggregated player stats for assists & saves
    pstats = load_player_season_stats(league, s, AME_TEAM_FOLDER)
    total_assists = 0
    total_saves = 0
    if not pstats.empty:
        total_assists = int(pstats["Goal Assists"].sum()) if "Goal Assists" in pstats.columns else 0
        total_saves = int(pstats["Saves Made"].sum()) if "Saves Made" in pstats.columns else 0
    season_history.append({
        "season": s[:4][-2:] + "/" + s[-4:][-2:],  # "2025-2026" → "25/26"
        "season_full": s,
        "wins": int(row["won"]),
        "draws": int(row["drawn"]),
        "losses": int(row["lost"]),
        "gf": int(row["gf"]),
        "ga": int(row["ga"]),
        "gd": int(row["gd"]),
        "points": int(row["points"]),
        "rank": int(row["rank"]),
        "played": int(row["played"]),
        "assists": total_assists,
        "saves": total_saves,
    })

hist_df = pd.DataFrame(season_history) if season_history else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# § 2  MATCH RESULTS BREAKDOWN + PLAYER STATS TABLE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")

col_results, col_player = st.columns([1, 2])

# ── Left: Match Results Breakdown (multi-season) ────────────────────────
with col_results:
    section_header("Match Results Breakdown")
    if not hist_df.empty:
        # Show last 7 seasons, chronological order (oldest → newest)
        plot_df = hist_df.head(7).iloc[::-1].copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["wins"],
            name="Wins", marker_color="#4CAF50",
        ))
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["draws"],
            name="Draws", marker_color=AME_BLUE,
        ))
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["losses"],
            name="Losses", marker_color=AME_YELLOW,
        ))
        fig.update_layout(
            barmode="group",
            xaxis_title="", yaxis_title="",
            height=350,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=40, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No historical data available.")

    # ── Offensive & Defensive Performance ────────────────────────────────
    section_header("Offensive & Defensive Performance")
    if not hist_df.empty:
        plot_df = hist_df.head(7).iloc[::-1].copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["saves"],
            name="Saves", marker_color="#666666",
        ))
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["gf"],
            name="Goals", marker_color="#4CAF50",
        ))
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["assists"],
            name="Assists", marker_color=AME_BLUE,
        ))
        fig.add_trace(go.Bar(
            x=plot_df["season"], y=plot_df["ga"],
            name="Goals Against", marker_color="#FF6B35",
        ))
        fig.update_layout(
            barmode="group",
            xaxis_title="", yaxis_title="",
            height=350,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=40, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Right: Player Stats Table ────────────────────────────────────────────
with col_player:
    section_header("Player Statistics")
    pstats = load_player_season_stats(league, season, AME_TEAM_FOLDER)
    if not pstats.empty:
        # Build display table with key metrics
        cols_map = {
            "dorsal": "Shirt",
            "nombre": "Player",
            "Goals": "Goals",
            "Goal Assists": "Assists",
            "Shots On Target ( inc goals )": "Shots on Target",
            "Total Fouls Conceded": "Fouls",
            "Yellow Cards": "Yellow Cards",
            "Total Red Cards": "Red Cards",
            "Time Played": "Minutes Played",
        }
        available = {k: v for k, v in cols_map.items() if k in pstats.columns}
        display = pstats[list(available.keys())].copy()
        display.columns = list(available.values())

        # Compute Pass Accuracy %
        succ_col = "Total Successful Passes ( Excl Crosses & Corners ) "
        fail_col = "Total Unsuccessful Passes ( Excl Crosses & Corners )"
        if succ_col in pstats.columns and fail_col in pstats.columns:
            succ = pstats[succ_col].fillna(0)
            fail = pstats[fail_col].fillna(0)
            total = succ + fail
            display["Pass Acc."] = (succ / total.replace(0, float("nan")) * 100).fillna(0).round(0).astype(int)
            display["Pass Acc."] = display["Pass Acc."].astype(str) + "%"

        # Compute Shot Accuracy %
        if "Total Shots" in pstats.columns and "Shots On Target ( inc goals )" in pstats.columns:
            total_shots = pstats["Total Shots"].fillna(0)
            on_target = pstats["Shots On Target ( inc goals )"].fillna(0)
            display["Shot Acc."] = (on_target / total_shots.replace(0, float("nan")) * 100).fillna(0).round(0).astype(int)
            display["Shot Acc."] = display["Shot Acc."].astype(str) + "%"

        # Fill NaN with 0 and convert to int where possible
        for col in ["Goals", "Assists", "Shots on Target", "Fouls", "Yellow Cards", "Red Cards", "Minutes Played"]:
            if col in display.columns:
                display[col] = display[col].fillna(0).astype(int)

        if "Shirt" in display.columns:
            display["Shirt"] = display["Shirt"].fillna(0).astype(int)

        # Sort by Goals descending, then by Minutes Played
        display = display.sort_values(
            by=["Goals", "Minutes Played"],
            ascending=[False, False],
        ).reset_index(drop=True)

        # Filter out players with 0 minutes
        display = display[display["Minutes Played"] > 0]

        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            height=620,
            column_config={
                "Shirt": st.column_config.NumberColumn("🔢", width="small"),
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Goals": st.column_config.NumberColumn("⚽ Goals", width="small"),
                "Assists": st.column_config.NumberColumn("🅰️ Assists", width="small"),
                "Shots on Target": st.column_config.NumberColumn("🎯 SOT", width="small"),
                "Pass Acc.": st.column_config.TextColumn("Pass %", width="small"),
                "Shot Acc.": st.column_config.TextColumn("Shot %", width="small"),
                "Fouls": st.column_config.NumberColumn("Fouls", width="small"),
                "Yellow Cards": st.column_config.NumberColumn("🟨", width="small"),
                "Red Cards": st.column_config.NumberColumn("🟥", width="small"),
                "Minutes Played": st.column_config.NumberColumn("⏱️ Mins", width="small"),
            },
        )
        st.caption(f"{len(display)} players")
    else:
        st.info("No player statistics available for this season.")


# ═══════════════════════════════════════════════════════════════════════════
# § 2b  BALL PROGRESSION — EXPECTED THREAT (xT)
# ═══════════════════════════════════════════════════════════════════════════
# América only plays AME_LEAGUES (Liga MX + CONCACAF), so the season xT scan
# is only meaningful there.
if league in AME_LEAGUES:
    st.markdown("---")
    section_header("Ball Progression — Expected Threat (xT)")
    st.caption(
        "Season-aggregated xT: the threat each player *adds* by moving the ball "
        "into more dangerous zones (passes + carries). Karun-Singh 12×8 grid."
    )
    _xt = compute_season_xt(league, season, AME_TEAM_ID)
    if _xt and _xt.get("matches", 0) > 0:
        xc1, xc2, xc3 = st.columns(3)
        with xc1:
            kpi_card("Season xT", f"+{_xt['total_xt']:.1f}")
        with xc2:
            kpi_card("xT / Match", f"+{_xt['xt_per_match']:.2f}")
        with xc3:
            kpi_card("Matches", _xt["matches"])
        lb = _xt["leaderboard"]
        if not lb.empty:
            st.plotly_chart(
                xt_top_contributors_bar(
                    lb.head(8), title=f"{AME_TEAM_NAME} — Top xT Contributors",
                    color=AME_YELLOW),
                use_container_width=True,
            )
    else:
        st.info("Season xT requires per-match files in partidos/.")

    # ── Attacking output by game state ────────────────────────────────────
    st.markdown("---")
    section_header("Attacking Output by Game State")
    st.caption(
        "xG and xT re-cut by scoreline state. A leading team cedes possession; "
        "a chasing team inflates xG against an open defence — so the *Level* row "
        "is the cleanest read of true attacking level. Normalised per-90 by "
        "minutes actually spent in each state."
    )
    from processing.game_state import compute_season_game_state
    from viz.tables import game_state_table
    from config import MIN_MATCHES_FOR_PREDICTION
    _gs = compute_season_game_state(league, season, AME_TEAM_ID)
    if _gs is not None and not _gs.empty:
        game_state_table(_gs, AME_TEAM_NAME, min_matches=MIN_MATCHES_FOR_PREDICTION)
    else:
        st.info("Game-state split requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3  HISTORICAL POSITION TABLE + SCATTER PLOTS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")

col_hist, col_scatter1, col_scatter2 = st.columns([1, 1, 1])

# ── Historical Position per Season ──────────────────────────────────────
with col_hist:
    section_header("Season-by-Season Record")
    if not hist_df.empty:
        pos_df = hist_df[["season_full", "rank", "points", "played", "wins", "draws", "losses", "gf", "ga", "gd"]].copy()
        pos_df.columns = ["Season", "Rank", "Pts", "P", "W", "D", "L", "GF", "GA", "GD"]
        pos_df = pos_df.sort_values("Season", ascending=False)
        st.dataframe(
            pos_df,
            hide_index=True,
            use_container_width=True,
            height=420,
            column_config={
                "Season": st.column_config.TextColumn("Season", width="small"),
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "Pts": st.column_config.NumberColumn("Pts", width="small"),
                "GD": st.column_config.NumberColumn("GD", width="small"),
            },
        )
    else:
        st.info("No historical data.")

# ── Minutes vs Production (scatter) ─────────────────────────────────────
with col_scatter1:
    section_header("Minutes vs Production")
    if not pstats.empty:
        scatter_df = pstats.copy()
        scatter_df["Goal Contributions"] = (
            scatter_df["Goals"].fillna(0) + scatter_df["Goal Assists"].fillna(0)
        )
        scatter_df["Minutes"] = scatter_df["Time Played"].fillna(0)
        scatter_df["Player"] = scatter_df["nombre"]

        # Map position to display labels
        pos_map = {"Goalkeeper": "GK", "Defender": "DF", "Midfielder": "MF", "Forward": "FW"}
        scatter_df["Position"] = scatter_df["posicion"].map(pos_map).fillna("?")

        # Filter to players with at least some minutes
        scatter_df = scatter_df[scatter_df["Minutes"] > 0]

        pos_colors = {"GK": "#888888", "DF": "#42A5F5", "MF": AME_YELLOW, "FW": AME_BLUE}

        fig = px.scatter(
            scatter_df,
            x="Minutes",
            y="Goal Contributions",
            color="Position",
            size="Goal Contributions",
            size_max=25,
            hover_name="Player",
            color_discrete_map=pos_colors,
            template="ame_dark",
        )
        # Add average reference lines
        avg_mins = scatter_df["Minutes"].mean()
        avg_gc = scatter_df["Goal Contributions"].mean()
        fig.add_hline(y=avg_gc, line_dash="dash", line_color="#555", opacity=0.5,
                      annotation_text="Avg Contributions", annotation_font_color="#888")
        fig.add_vline(x=avg_mins, line_dash="dash", line_color="#555", opacity=0.5,
                      annotation_text="Avg Minutes", annotation_font_color="#888")
        fig.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            xaxis_title="Minutes Played",
            yaxis_title="Goal Contributions",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No player data.")

# ── Player Performance Map (scatter) ─────────────────────────────────────
with col_scatter2:
    section_header("Player Performance Map")
    if not pstats.empty:
        perf_df = pstats.copy()
        perf_df["Minutes"] = perf_df["Time Played"].fillna(0)
        perf_df = perf_df[perf_df["Minutes"] >= 90].copy()  # At least 1 full match

        # Compute per-90 metrics for position score
        perf_df["per90"] = 90.0 / perf_df["Minutes"]

        # Position score: weighted combination of key actions per 90
        perf_df["goals_p90"] = perf_df["Goals"].fillna(0) * perf_df["per90"]
        perf_df["assists_p90"] = perf_df["Goal Assists"].fillna(0) * perf_df["per90"]
        perf_df["tackles_p90"] = perf_df["Tackles Won"].fillna(0) * perf_df["per90"] if "Tackles Won" in perf_df.columns else 0
        perf_df["interceptions_p90"] = perf_df["Interceptions"].fillna(0) * perf_df["per90"] if "Interceptions" in perf_df.columns else 0
        perf_df["keypasses_p90"] = perf_df["Key Passes (Attempt Assists)"].fillna(0) * perf_df["per90"] if "Key Passes (Attempt Assists)" in perf_df.columns else 0

        # Normalize each metric 0-1 within squad
        for col in ["goals_p90", "assists_p90", "tackles_p90", "interceptions_p90", "keypasses_p90"]:
            if col in perf_df.columns:
                cmax = perf_df[col].max()
                if cmax > 0:
                    perf_df[col] = perf_df[col] / cmax

        # Position Score = weighted average of normalized per-90 metrics
        perf_df["Position Score"] = (
            perf_df["goals_p90"] * 0.30 +
            perf_df["assists_p90"] * 0.20 +
            perf_df.get("tackles_p90", 0) * 0.20 +
            perf_df.get("interceptions_p90", 0) * 0.15 +
            perf_df.get("keypasses_p90", 0) * 0.15
        )

        perf_df["Goal Contributions"] = (
            perf_df["Goals"].fillna(0) + perf_df["Goal Assists"].fillna(0)
        )
        perf_df["Contributions p90"] = perf_df["Goal Contributions"] * perf_df["per90"]
        perf_df["Player"] = perf_df["nombre"]

        pos_map = {"Goalkeeper": "GK", "Defender": "DF", "Midfielder": "MF", "Forward": "FW"}
        perf_df["Position"] = perf_df["posicion"].map(pos_map).fillna("?")
        perf_df = perf_df[perf_df["Position"] != "GK"]  # Exclude GKs from performance map

        pos_colors = {"DF": "#42A5F5", "MF": AME_YELLOW, "FW": AME_BLUE}

        fig = px.scatter(
            perf_df,
            x="Position Score",
            y="Contributions p90",
            color="Position",
            size="Minutes",
            size_max=30,
            hover_name="Player",
            color_discrete_map=pos_colors,
            template="ame_dark",
        )
        fig.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            xaxis_title="Overall Position Score",
            yaxis_title="Goal Contributions / 90",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No player data.")


# ═══════════════════════════════════════════════════════════════════════════
# § 4  SEASON RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Season Results")

results = load_all_season_results(league, season, stage_filter=_selected_stage)

if is_ame_league and not results.empty:
    if not club_matches.empty:
        display_df = club_matches[["matchday", "date", "opponent", "is_home",
                                  "club_score", "opp_score", "result"]].copy()
        display_df["date"] = pd.to_datetime(display_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        display_df["Venue"] = display_df["is_home"].map({True: "Home", False: "Away"})
        display_df["Score"] = display_df.apply(
            lambda r: f"{int(r['club_score'])}-{int(r['opp_score'])}", axis=1
        )
        display_df["Result"] = display_df["result"]
        display_df = display_df.rename(columns={
            "matchday": "MD", "date": "Date", "opponent": "Opponent",
        })
        st.dataframe(
            display_df[["MD", "Date", "Venue", "Opponent", "Score", "Result"]],
            hide_index=True, use_container_width=True,
            column_config={
                "MD": st.column_config.NumberColumn("MD", width="small"),
                "Result": st.column_config.TextColumn("Result", width="small"),
            },
        )
        st.caption(f"{len(club_matches)} matches played")
    else:
        st.info("No match results available for CF América in this competition.")
elif not results.empty:
    display_df = results[["matchday", "date", "home_team", "away_team",
                           "home_score", "away_score"]].copy()
    display_df["date"] = pd.to_datetime(display_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    display_df["Score"] = display_df.apply(
        lambda r: f"{int(r['home_score'])}-{int(r['away_score'])}", axis=1
    )
    display_df = display_df.rename(columns={
        "matchday": "MD", "date": "Date",
        "home_team": "Home", "away_team": "Away",
    })
    st.dataframe(
        display_df[["MD", "Date", "Home", "Score", "Away"]],
        hide_index=True, use_container_width=True,
    )
    st.caption(f"{len(display_df)} matches played")
else:
    st.info("No results available for this season.")


# ═══════════════════════════════════════════════════════════════════════════
# § 5  LEAGUE TABLE + POINTS PROGRESSION
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
col_table, col_chart = st.columns([1, 1])

with col_table:
    section_header("League Table")
    styled_league_table(standings, league=league)

with col_chart:
    section_header("Points Progression")
    pts_df = compute_points_by_matchday(league, season, AME_TEAM_NAME, team_id=AME_TEAM_ID)
    if not pts_df.empty:
        fig = line_chart(pts_df, x="matchday", y="cumulative_points",
                         title="Cumulative Points", y_label="Points",
                         markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No matchday data available.")

    section_header("Historical Points by Season")
    if not hist_df.empty:
        fig = line_chart(hist_df, x="season", y="points",
                         title="CF América Points by Season", y_label="Total Points",
                         markers=True)
        st.plotly_chart(fig, use_container_width=True)
