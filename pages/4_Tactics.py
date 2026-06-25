"""Season Tactics — Deep tactical profile for any team over the season."""

import json
import streamlit as st
from viz.theme import apply_theme
import pandas as pd
from components.sidebar import render_sidebar
from components.team_selector import team_selector
from viz.kpi_cards import section_header, kpi_card, kpi_row, page_header, ame_section
from viz.charts import (
    tactical_progression_chart, formation_donut, multi_line_chart,
    grouped_bar_chart, bar_chart,
    ppda_trend_chart, dual_axis_trend_chart,
    donut_chart, histogram, style_quadrant_chart, cross_channel_chart,
    discipline_scatter_chart, pass_risk_reward_scatter,
)
from viz.radar import team_radar
from viz.pitch import plot_shot_map, plot_formation_shape, plot_team_shape, plot_heatmap
from viz.tables import styled_dataframe
from viz.xt import xt_pitch_heatmap, xt_top_contributors_bar
from data.loader import load_standings, load_team_season_stats, build_player_name_map, list_standings_stages
from data.event_parser import extract_shots, parse_match_info
from data.paths import list_team_folders, partidos_dir
from processing.season_tactics import (
    compute_season_tactical_progression, load_team_season_agg,
    compute_rolling_averages, compute_season_xt,
)
from processing.team_stats import (
    compute_team_radar_data, RADAR_CATEGORIES, get_team_folder_map,
    build_team_name_lookup,
)
from processing.manager_stats import (
    compute_formation_usage, compute_home_away_split,
    compute_goals_timeline, compute_recent_form,
)
from processing.pressure import compute_season_pressure
from processing.sequences import compute_season_sequences
from processing.wide_play import compute_season_cross_value, compute_season_throwin_value
from processing.set_pieces import compute_season_set_piece_phases
from processing.team_shape import compute_season_team_shape
from processing.discipline import compute_league_discipline, load_team_foul_locations
from processing.carries import compute_season_carries
from processing.expected_pass import compute_season_xp
from processing.transitions import compute_season_transitions
from config import AME_TEAM_NAME, AME_YELLOW, AME_BLUE, AME_DARK_BG

apply_theme()

league, season = render_sidebar()

page_header("Season Tactics", subtitle=f"{season}")

# ── Tournament Stage Selector (Liga MX / bi-annual leagues) ────────────────
_stage_names = list_standings_stages(league, season)
_stage_filter = ""
if len(_stage_names) > 1:
    _stage_filter = st.radio(
        "Tournament",
        options=_stage_names,
        index=len(_stage_names) - 1,
        horizontal=True,
        key="tactics_stage",
    )

# ── Team Selector ──────────────────────────────────────────────────────────
selected = team_selector(league, season, key="season_tactics_sel",
                         multi=False, label="Select Team")
team_name = selected[0] if selected else AME_TEAM_NAME

# Resolve team_id and folder
standings = load_standings(league, season)
team_row = standings[standings["team_name"] == team_name]
team_id = team_row.iloc[0]["team_id"] if not team_row.empty else ""

# folder mapping
folder_map = get_team_folder_map(league, season)
team_folder = folder_map.get(team_name, "")

if not team_id:
    st.warning(f"Could not find team ID for {team_name}.")
    st.stop()

# ── Load data tiers ────────────────────────────────────────────────────────
# Fast tier: aggregate season stats
agg = load_team_season_agg(league, season, team_folder) if team_folder else {}

# Deep tier: per-match progression (cached, stage-filtered)
progression = compute_season_tactical_progression(league, season, team_id,
                                                  stage_filter=_stage_filter)
has_progression = not progression.empty


# ═══════════════════════════════════════════════════════════════════════════
# § 1  TACTICAL IDENTITY
# ═══════════════════════════════════════════════════════════════════════════
section_header("Tactical Identity")

# Season KPI cards (from aggregate stats)
if agg:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Possession", f"{agg.get('possession_pct', '–')}%")
    with k2:
        kpi_card("Pass Accuracy", f"{agg.get('pass_accuracy', '–')}%")
    with k3:
        kpi_card("Goals/Match", f"{agg.get('goals_per_match', '–')}")
    with k4:
        kpi_card("Clean Sheets", agg.get("clean_sheets", "–"))

    k5, k6, k7, k8 = st.columns(4)
    with k5:
        kpi_card("Shots/Match", agg.get("shots_per_match", "–"))
    with k6:
        kpi_card("Tackles Won", agg.get("tackles_won", "–"))
    with k7:
        kpi_card("Interceptions", agg.get("interceptions", "–"))
    with k8:
        kpi_card("Set-Piece Goals", agg.get("set_piece_goals", "–"))

# Style label (derived from progression averages if available)
if has_progression:
    avg_ppda = progression["ppda"].mean()
    avg_poss = progression["possession"].mean()
    if avg_ppda < 9 and avg_poss > 55:
        style = "High Press / Possession"
        style_icon = "🔥"
    elif avg_ppda < 9:
        style = "Aggressive Press"
        style_icon = "⚡"
    elif avg_poss > 55:
        style = "Possession-Based"
        style_icon = "🎯"
    elif avg_ppda > 13:
        style = "Low Block / Counter"
        style_icon = "🛡️"
    else:
        style = "Balanced / Transitional"
        style_icon = "⚖️"

    st.markdown(f"""
    <div style="text-align:center;padding:0.6rem;margin:0.5rem 0 1rem;
         background:#1A1A2E;border-radius:8px;border-left:4px solid {AME_YELLOW};">
        <span style="font-size:1.6rem;">{style_icon}</span>
        <span style="color:#ccc;font-size:1.1rem;font-weight:600;margin-left:0.5rem;">
            Tactical Style: {style}
        </span>
        <span style="color:#888;font-size:0.8rem;margin-left:1rem;">
            (Avg PPDA: {avg_ppda:.1f} | Avg Possession: {avg_poss:.1f}%)
        </span>
    </div>
    """, unsafe_allow_html=True)

# Radar: team vs league average
st.markdown("#### Team Radar vs League")
all_folders = list_team_folders(league, season)
all_radar = compute_team_radar_data(league, season, all_folders)

if all_radar and team_name in all_radar:
    # Compute league average
    all_values = list(all_radar.values())
    n_cats = len(RADAR_CATEGORIES)
    league_avg = [
        round(sum(v[i] for v in all_values) / len(all_values), 1)
        for i in range(n_cats)
    ]
    radar_data = {
        team_name: all_radar[team_name],
        "League Average": league_avg,
    }
    fig = team_radar(radar_data, RADAR_CATEGORIES, title=f"{team_name} vs League")
    st.plotly_chart(fig, width="stretch")
else:
    st.info("Radar data not available for this team.")


# Recent form
form = compute_recent_form(league, season, team_id, n=5,
                           stage_filter=_stage_filter)
if form:
    form_colors = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}
    chips = ""
    for res in form:
        c = form_colors.get(res, "#888")
        chips += (
            f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;'
            f'text-align:center;border-radius:6px;background:{c};color:white;'
            f'font-weight:700;margin:0 3px;">{res}</span>'
        )
    st.markdown(
        f'<div style="margin:0.5rem 0;"><span style="color:#888;font-size:0.85rem;'
        f'margin-right:0.5rem;">Last 5:</span>{chips}</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# § 2  FORMATION PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Formation Profile")

formations = compute_formation_usage(league, season, team_id,
                                     stage_filter=_stage_filter)

if formations:
    # Show up to 3 most-used formations as pitch shapes
    top_formations = formations[:3]
    n_forms = len(top_formations)
    form_cols = st.columns(n_forms)
    form_colors = [AME_YELLOW, "#42A5F5", "#4CAF50"]
    for i, f_data in enumerate(top_formations):
        with form_cols[i]:
            plot_formation_shape(
                f_data["formation"],
                primary_color=form_colors[i],
                pct=f_data["pct"],
            )
            st.markdown(
                f'<div style="text-align:center;color:#aaa;font-size:0.85rem;">'
                f'{f_data["count"]} matches</div>',
                unsafe_allow_html=True,
            )

    # Formation results table below
    if has_progression:
        form_results = progression[["match_num", "opponent", "venue", "formation",
                                     "result", "score"]].copy()
        form_results.columns = ["#", "Opponent", "H/A", "Formation", "Result", "Score"]
        st.dataframe(
            form_results.style.applymap(
                lambda v: (
                    "color: #4CAF50; font-weight: bold" if v == "W"
                    else ("color: #FFC107" if v == "D"
                          else ("color: #F44336" if v == "L" else ""))
                ),
                subset=["Result"],
            ),
            use_container_width=True,
            height=350,
        )
else:
    st.info("No formation data found. Ensure match files exist in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 2b  TEAM SHAPE & COMPACTNESS (Stretch Index)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Team Shape & Compactness")
st.caption(
    "Built from season-average positions (an **event-data approximation** of "
    "true tracking compactness). **Stretch Index** = convex-hull area of the four "
    "deepest outfielders — small = compact last line, large = stretched. "
    "**Exposure** = how much space the front three leave in front of the back line."
)

shape = compute_season_team_shape(league, season, team_id, stage_filter=_stage_filter)
if shape and shape.get("players"):
    ts1, ts2 = st.columns([1, 1])
    with ts1:
        plot_team_shape(shape, title=f"{team_name} — Average Shape")
    with ts2:
        sh1, sh2 = st.columns(2)
        with sh1:
            kpi_card("Stretch Index", f"{shape['stretch_index']:.0f}")
            kpi_card("Line Height", f"{shape['line_height']:.0f}")
        with sh2:
            kpi_card("Last-line Exposure", f"{shape['exposure']:.1f}")
            kpi_card("Block Width", f"{shape['block_width']:.0f}")
        st.caption(
            "Stretch Index is in normalised 0-100² pitch units (the back-four "
            "hull area). A lower number with a high line height = a compact, "
            "high-pressing block; a high number = a spread-out last line easier "
            "to play through."
        )
else:
    st.info("Team shape requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3  TACTICAL PROGRESSION
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Tactical Progression")

if has_progression:
    st.caption("5-match rolling averages. Bottom markers: 🟩 Win  🟨 Draw  🟥 Loss")

    # Compute rolling averages for all metrics
    all_metrics = ["possession", "ppda", "field_tilt", "pass_accuracy", "progressive_passes"]
    prog_with_rolling = compute_rolling_averages(progression, all_metrics, window=5)

    # ── Chart 1: Pressing Intensity (PPDA with tactical bands) ────────────
    fig_ppda = ppda_trend_chart(
        prog_with_rolling,
        title=f"{team_name} — Pressing Intensity",
    )
    st.plotly_chart(fig_ppda, use_container_width=True)

    # ── Chart 2: Possession & Territory (single % axis, both comparable) ─────
    st.caption(
        "**Possession %** = ball control share. "
        "**Field Tilt %** = share of both teams' attacking-third touches. "
        "Both >50% means territorial dominance."
    )
    fig_poss = tactical_progression_chart(
        prog_with_rolling,
        metrics=["possession", "field_tilt"],
        rolling_cols=["possession_rolling", "field_tilt_rolling"],
        colors=[AME_YELLOW, "#42A5F5"],
        title=f"{team_name} — Possession & Territory (%)",
        y_label="% (both on same scale)",
    )
    # 50% reference line — above = dominant
    fig_poss.add_hline(y=50, line_dash="dash", line_color="#555", opacity=0.6,
                       annotation_text="50% (equal)", annotation_position="top right",
                       annotation=dict(font_size=10, font_color="#888"))
    # Rename legend labels
    for trace in fig_poss.data:
        if trace.name == "Possession":
            trace.name = "Possession %"
        elif trace.name == "Field Tilt":
            trace.name = "Field Tilt %"
    st.plotly_chart(fig_poss, use_container_width=True)

    # ── Chart 3: Passing Quality (dual axis — % vs count) ────────────────
    fig_pass = dual_axis_trend_chart(
        prog_with_rolling,
        left_metric="pass_accuracy",
        right_metric="progressive_passes",
        left_rolling="pass_accuracy_rolling",
        right_rolling="progressive_passes_rolling",
        left_color=AME_BLUE,
        right_color="#42A5F5",
        left_label="Pass Accuracy %",
        right_label="Progressive Passes",
        title=f"{team_name} — Passing Quality",
    )
    st.plotly_chart(fig_pass, use_container_width=True)

    # Insight callout
    if len(progression) >= 10:
        first5 = progression.head(5)
        last5 = progression.tail(5)
        ppda_start = first5["ppda"].mean()
        ppda_end = last5["ppda"].mean()
        poss_start = first5["possession"].mean()
        poss_end = last5["possession"].mean()
        prog_start = first5["progressive_passes"].mean()
        prog_end = last5["progressive_passes"].mean()

        press_desc = "pressing more intensely" if ppda_end < ppda_start else "pressing less"
        prog_dir = "increasing" if prog_end > prog_start else "decreasing"

        st.markdown(f"""
        <div style="padding:0.8rem;background:#1A1A2E;border-radius:8px;border-left:4px solid {AME_BLUE};
             margin:0.5rem 0;">
            <span style="color:#ccc;font-size:0.9rem;">
                <b>📊 Trend Analysis:</b><br>
                • <b>Pressing:</b> PPDA {ppda_start:.1f} → {ppda_end:.1f} — {press_desc}<br>
                • <b>Possession:</b> {poss_start:.1f}% → {poss_end:.1f}%<br>
                • <b>Progressive Passes:</b> {prog_start:.0f} → {prog_end:.0f}/game — {prog_dir}
            </span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("Per-match tactical progression requires match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3b  EXPECTED THREAT (xT)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Expected Threat (xT)")
st.caption(
    "**xT** measures *possession value* — the probability of scoring within the "
    "next few actions from each pitch zone. A pass's xT-added is the value it "
    "gains by moving the ball into a more dangerous zone. "
    "Grid: [Karun Singh's published 12×8 model](https://karun.in/blog/expected-threat.html). "
    "Open-play passes only; ranked by total xT added across the season."
)

season_xt = compute_season_xt(league, season, team_id, stage_filter=_stage_filter)

if not season_xt["leaders"].empty:
    n_matches = season_xt["matches"]
    if n_matches < 5:
        st.caption(
            f"⚠️ Low sample — only {n_matches} match(es) aggregated. "
            "Early-season xT totals are volatile."
        )

    xk1, xk2, xk3 = st.columns(3)
    with xk1:
        kpi_card("Season xT (passes)", f"+{season_xt['total_xt']:.2f}")
    with xk2:
        kpi_card("Matches", n_matches)
    with xk3:
        per_match = season_xt["total_xt"] / n_matches if n_matches else 0
        kpi_card("xT / Match", f"+{per_match:.2f}")

    xc1, xc2 = st.columns(2)
    with xc1:
        st.plotly_chart(
            xt_pitch_heatmap(season_xt["all_passes"],
                             title="Where Threat Is Created"),
            use_container_width=True,
        )
    with xc2:
        st.plotly_chart(
            xt_top_contributors_bar(season_xt["leaders"],
                                    title="Top xT Contributors", color=AME_YELLOW),
            use_container_width=True,
        )
else:
    st.info("Season xT requires match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3e  BALL CARRIES — PROGRESSION BY DRIVING
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Ball Carries")
st.caption(
    "Carrying — driving the ball with the feet — is ~25-30% of open-play "
    "progression and was previously invisible here (we only valued passes and "
    "shots). Each carry is priced with the same xT grid; **line-breaks** count "
    "carries crossing a vertical third boundary (an *event-data proxy* for "
    "bypassing an opponent line — true packing needs tracking data)."
)
season_car = compute_season_carries(league, season, team_id, stage_filter=_stage_filter)
if season_car:
    ck1, ck2, ck3, ck4 = st.columns(4)
    with ck1:
        kpi_card("Carries / season", f"{season_car['carries']:,}")
    with ck2:
        kpi_card("Progressive", f"{season_car['progressive']:,}")
    with ck3:
        kpi_card("Line-breaks", f"{season_car['line_breaks']:,}")
    with ck4:
        kpi_card("Carry xT", f"+{season_car['total_carry_xt']:.2f}")
    lb = season_car["leaderboard"]
    if not lb.empty:
        show = lb[["player_name", "carries", "prog", "line_breaks",
                   "box_entries", "carry_xt", "distance"]].head(12)
        styled_dataframe(show.rename(columns={
            "player_name": "Player", "carries": "Carries", "prog": "Progressive",
            "line_breaks": "Line-breaks", "box_entries": "Box entries",
            "carry_xt": "Carry xT", "distance": "Dist (m)"}))
else:
    st.info("Carry analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3f  PASSING RISK / REWARD — EXPECTED PASS COMPLETION (xP)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Passing Risk / Reward (xP)")
st.caption(
    "**xP** models how hard each pass was to complete, separating *ambition* "
    "from *execution*. **Pass rating** = actual − expected completion (passing "
    "over expectation). The scatter places each player by difficulty (1 − xP) "
    "vs reward (xT gained); bubble = volume, colour = net decision value."
)
season_xp = compute_season_xp(league, season, team_id, stage_filter=_stage_filter)
if season_xp:
    pk1, pk2, pk3, pk4 = st.columns(4)
    with pk1:
        kpi_card("Completion", f"{season_xp['completion_pct']:.1f}%")
    with pk2:
        kpi_card("Expected (xP)", f"{season_xp['exp_completion_pct']:.1f}%")
    with pk3:
        sign = "+" if season_xp["pass_rating"] >= 0 else ""
        kpi_card("Pass rating", f"{sign}{season_xp['pass_rating']:.1f}")
    with pk4:
        kpi_card("Pass value", f"{season_xp['total_pass_value']:.1f}")
    lb = season_xp["leaderboard"]
    if not lb.empty:
        top_names = lb.head(5)["player_name"].tolist()
        st.plotly_chart(
            pass_risk_reward_scatter(
                lb, title=f"{team_name} — Passing Risk vs Reward",
                highlight=top_names),
            use_container_width=True,
        )
        show = lb[["player_name", "passes", "completion", "xp", "over_exp",
                   "avg_reward", "avg_risk", "pass_value"]].head(12)
        styled_dataframe(show.rename(columns={
            "player_name": "Player", "passes": "Passes", "completion": "Comp%",
            "xp": "xP", "over_exp": "Over-exp", "avg_reward": "Reward",
            "avg_risk": "Risk", "pass_value": "Pass value"}))
else:
    st.info("xP analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3g  TRANSITION CONVERSION — COUNTER-ATTACK LETHALITY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Transition Conversion")
st.caption(
    "How lethal is the team *in transition*? For every open-play regain we check "
    "whether a shot followed within 10s and how good a chance it was, then split "
    "all shooting into **transition** vs **settled**. A high transition share + "
    "fast time-to-shot = a counter-attacking identity."
)
season_tr = compute_season_transitions(league, season, team_id, stage_filter=_stage_filter)
if season_tr:
    tk1, tk2, tk3, tk4 = st.columns(4)
    with tk1:
        kpi_card("Transition xG", f"{season_tr['transition_xg']:.2f}")
    with tk2:
        kpi_card("% of xG from transition", f"{season_tr['pct_xg_from_transition']:.0f}%")
    with tk3:
        kpi_card("Transition shots", f"{season_tr['transition_shots']}")
    with tk4:
        tts = season_tr["avg_time_to_shot"]
        kpi_card("Avg time to shot", f"{tts:.1f}s" if tts is not None else "—")
else:
    st.info("Transition analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3c  PRESSING & TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Pressing & Transitions")
st.caption(
    "Opta F24 has no native 'pressure' event, so these are **approximations** "
    "of StatsBomb/The-Analyst pressing metrics derived from recoveries, tackles, "
    "interceptions & clearances. *Pitch height is on the 0–100 scale (higher = "
    "further upfield = more aggressive).*"
)

press = compute_season_pressure(league, season, team_id, stage_filter=_stage_filter)

if press and press.get("matches", 0) > 0:
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        kpi_card("Ball-Recovery Height", f"{press['avg_recovery_height']:.1f}")
    with pc2:
        kpi_card("Defensive-Line Height", f"{press['avg_def_line_height']:.1f}")
    with pc3:
        kpi_card("High Turnovers / Match", f"{press['high_turnovers_per_match']:.1f}")
    with pc4:
        kpi_card("Shot-Ending HTOs", press["shot_ending_htos_total"])

    pc5, pc6, pc7, pc8 = st.columns(4)
    with pc5:
        kpi_card("Pressure Regains / Match", f"{press['pressure_regains_per_match']:.1f}")
    with pc6:
        kpi_card("Avg Possession", f"{press.get('avg_possession_pct', 0):.0f}%")
    with pc7:
        kpi_card("Def. Actions / Match", f"{press.get('def_actions_per_match', 0):.0f}")
    with pc8:
        kpi_card("PAdj Def. Actions / Match",
                 f"{press.get('padj_def_actions_per_match', 0):.0f}")
    st.caption(
        "**PAdj** = possession-adjusted — defensive actions rescaled to a neutral "
        "50%-possession baseline so high-possession sides aren't undercounted for "
        "having fewer defensive opportunities."
    )

    # 5-match rolling averages so the chart draws bold trend lines
    per_match = compute_rolling_averages(
        press["per_match"],
        ["ball_recovery_height", "def_line_height"], window=5,
    )
    if len(per_match) >= 2:
        fig_press = tactical_progression_chart(
            per_match,
            metrics=["ball_recovery_height", "def_line_height"],
            colors=[AME_YELLOW, AME_BLUE],
            title=f"{team_name} — Recovery & Defensive-Line Height Over Season",
            y_label="Pitch x (0–100)",
        )
        # Rename legend labels for clarity
        for trace in fig_press.data:
            if trace.name == "Ball Recovery Height":
                trace.name = "Ball-Recovery Height"
            elif trace.name == "Def Line Height":
                trace.name = "Defensive-Line Height"
        st.plotly_chart(fig_press, use_container_width=True)
else:
    st.info("Pressing metrics require per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3b  PLAYING STYLE — possession sequences
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Playing Style — Possession Sequences")
st.caption(
    "Sequences are passages of play ending in a turnover, stoppage or shot. "
    "**Directness** = upfield progress ÷ ball-path length; **direct speed** = "
    "m/s toward goal. The quadrant splits the league at its medians."
)

style_df = compute_season_sequences(league, season, stage_filter=_stage_filter)
if not style_df.empty and team_id in set(style_df["team_id"]):
    me = style_df[style_df["team_id"] == team_id].iloc[0]
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        kpi_card("Passes / Sequence", f"{me['avg_passes_per_seq']:.1f}")
    with sc2:
        kpi_card("Directness", f"{me['avg_directness']:.2f}")
    with sc3:
        kpi_card("Direct Speed", f"{me['avg_direct_speed']:.2f} m/s")
    with sc4:
        sps = me["sequences_per_shot"]
        kpi_card("Sequences / Shot", f"{sps:.1f}" if sps else "—")

    fig_style = style_quadrant_chart(
        style_df, highlight_id=team_id,
        title=f"{league.replace('_', ' ')} — Playing-Style Quadrant",
    )
    st.plotly_chart(fig_style, use_container_width=True)
else:
    st.info("Playing-style sequences require per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3b  WIDE PLAY — CROSSING & CUTBACKS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Wide Play — Crossing & Cutbacks")
st.caption(
    "Each cross is priced by the **xG it creates** — the first shot the team "
    "takes within ~6s, attributed back to the delivery. **Cutbacks** (pulled "
    "back from the byline) convert far better than floated crosses, so they are "
    "flagged separately. xG is linked per match, so a cross never claims another "
    "game's shot."
)

cross = compute_season_cross_value(league, season, team_id, stage_filter=_stage_filter)
if cross and cross.get("crosses", 0) > 0:
    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        kpi_card("Crosses / Match", cross["per_match"]["crosses"])
    with wc2:
        kpi_card("Completion", f"{cross['completion_pct']:.0f}%")
    with wc3:
        kpi_card("Cutbacks", cross["cutbacks"])
    with wc4:
        kpi_card("xG / Cross", f"{cross['xg_per_cross']:.3f}")

    st.markdown(
        f"Cutbacks generate **{cross['xg_per_cutback']:.3f} xG each** vs "
        f"**{cross['xg_per_cross']:.3f}** for an average cross — "
        f"{cross['xg_generated']:.1f} total xG created from wide deliveries."
    )

    cw1, cw2 = st.columns([1, 1])
    with cw1:
        st.plotly_chart(cross_channel_chart(cross["by_channel"]),
                        use_container_width=True)
    with cw2:
        st.markdown("**Top cross deliverers**")
        lb = cross["leaderboard"]
        if not lb.empty:
            show = lb.head(8)[["player_name", "crosses", "completed",
                               "cutbacks", "xg_generated"]].rename(columns={
                "player_name": "Player", "crosses": "Crosses",
                "completed": "Cmp", "cutbacks": "Cutbacks", "xg_generated": "xG",
            })
            st.dataframe(show, hide_index=True, use_container_width=True)
else:
    st.info("Crossing analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3d  THROW-INS & LONG THROWS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Throw-Ins & Long Throws")
st.caption(
    "The breakout 2025-26 trend. A **long throw** is a throw-in delivered into "
    "the penalty area; each is priced by the **xG it creates** (first shot within "
    "~6s, linked per match). Long throws convert far better than ordinary throws "
    "— a near-free set-piece weapon."
)

throws = compute_season_throwin_value(league, season, team_id, stage_filter=_stage_filter)
if throws and throws.get("throwins", 0) > 0:
    tw1, tw2, tw3, tw4 = st.columns(4)
    with tw1:
        kpi_card("Throw-ins / Match", throws["per_match"]["throwins"])
    with tw2:
        kpi_card("Long Throws", throws["long_throws"])
    with tw3:
        kpi_card("xG / Long Throw", f"{throws['xg_per_long_throw']:.3f}")
    with tw4:
        kpi_card("xG from Throws", f"{throws['xg_generated']:.2f}")

    if throws["long_throws"] > 0:
        st.markdown(
            f"**{throws['long_throws']}** long throws into the box generated "
            f"**{throws['xg_per_long_throw']:.3f} xG each** — "
            f"{throws['shots_created']} shots created from throw-ins this season."
        )
    lb = throws.get("leaderboard", pd.DataFrame())
    if not lb.empty:
        st.markdown("**Top throw-in deliverers**")
        show = lb.head(6)[["player_name", "throwins", "long_throws",
                           "xg_generated"]].rename(columns={
            "player_name": "Player", "throwins": "Throw-ins",
            "long_throws": "Long", "xg_generated": "xG",
        })
        st.dataframe(show, hide_index=True, use_container_width=True)
else:
    st.info("Throw-in analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 4  ATTACKING & DEFENSIVE PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Attacking & Defensive Profile")

if agg:
    # Attacking stats
    st.markdown("#### Attacking")
    ac1, ac2, ac3, ac4 = st.columns(4)
    games = agg.get("games_played", 38)
    with ac1:
        kpi_card("Goals", int(agg.get("goals", 0)))
    with ac2:
        kpi_card("Shots/Match", agg.get("shots_per_match", "–"))
    with ac3:
        sot = agg.get("shots_on_target", 0)
        ts = agg.get("total_shots", 1) or 1
        kpi_card("SOT %", f"{round(sot / ts * 100, 1)}%")
    with ac4:
        kpi_card("Key Passes", int(agg.get("key_passes", 0)))

    # Defensive stats
    st.markdown("#### Defending")
    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        kpi_card("Goals Conceded", int(agg.get("goals_conceded", 0)))
    with dc2:
        kpi_card("Tackles Won", int(agg.get("tackles_won", 0)))
    with dc3:
        kpi_card("Tackle Success", f"{agg.get('tackle_success', 0)}%")
    with dc4:
        kpi_card("Clearances", int(agg.get("total_clearances", 0)))

# Home vs Away split
st.markdown("#### Home vs Away Performance")
ha_split = compute_home_away_split(league, season, team_id,
                                   stage_filter=_stage_filter)

ha_df = pd.DataFrame({
    "Metric": ["Wins", "Draws", "Losses", "Goals For", "Goals Against"],
    "Home": [
        ha_split["home_w"], ha_split["home_d"], ha_split["home_l"],
        ha_split["home_gf"], ha_split["home_ga"],
    ],
    "Away": [
        ha_split["away_w"], ha_split["away_d"], ha_split["away_l"],
        ha_split["away_gf"], ha_split["away_ga"],
    ],
})

fig = grouped_bar_chart(ha_df, x="Metric", y_cols=["Home", "Away"],
                        colors=[AME_YELLOW, "#42A5F5"],
                        title=f"{team_name} — Home vs Away",
                        bar_names=["Home", "Away"])
st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# § 5  SET-PIECE SEASON SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Set-Piece Season Summary")

if agg:
    sp1, sp2, sp3, sp4 = st.columns(4)
    with sp1:
        kpi_card("Corners Taken", int(agg.get("corners_taken", 0)))
    with sp2:
        ca = agg.get("corners_accurate", 0)
        ct = agg.get("corners_taken", 1) or 1
        kpi_card("Corner Accuracy", f"{round(ca / ct * 100, 1)}%")
    with sp3:
        kpi_card("Set-Piece Goals", int(agg.get("set_piece_goals", 0)))
    with sp4:
        kpi_card("Penalty Goals", int(agg.get("penalty_goals", 0)))

# Per-match SP trend from progression data
if has_progression and "sp_shots" in progression.columns:
    sp_trend = compute_rolling_averages(progression, ["sp_shots", "corners_won"], window=5)

    fig = tactical_progression_chart(
        sp_trend,
        metrics=["sp_shots", "corners_won"],
        title=f"{team_name} — Set-Piece Threat Over Season",
        colors=["#4CAF50", AME_BLUE],
        y_label="Count",
    )
    st.plotly_chart(fig, width="stretch")

# ── Corner first- vs second-phase value (HOPS-style) ────────────────────────
st.markdown("#### Corner Phases — First Contact vs Second Ball")
st.caption(
    "Splits corner xG into the **first phase** (initial delivery, ≤6s) and the "
    "**second phase** (recycled / second-ball attack, 6-45s). The modern edge "
    "is the second phase. **Shot Ratio** = % of corners producing a shot."
)
phases = compute_season_set_piece_phases(league, season, team_id,
                                         stage_filter=_stage_filter)
if phases and phases.get("n_set_pieces", 0) > 0:
    ph1, ph2, ph3, ph4 = st.columns(4)
    with ph1:
        kpi_card("Corners", phases["n_set_pieces"])
    with ph2:
        kpi_card("Shot Ratio", f"{phases['shot_ratio']:.0f}%")
    with ph3:
        kpi_card("First / Second xG",
                 f"{phases['first_xg']:.2f} / {phases['second_xg']:.2f}")
    with ph4:
        kpi_card("Second-phase Share", f"{phases['second_phase_share']:.0f}%")

    by_r = phases.get("by_routine", pd.DataFrame())
    if not by_r.empty:
        fig_ph = grouped_bar_chart(
            by_r, x="delivery_label", y_cols=["first_xg", "second_xg"],
            colors=[AME_YELLOW, AME_BLUE],
            title=f"{team_name} — Corner xG by Phase & Routine",
            bar_names=["First phase", "Second phase"],
        )
        st.plotly_chart(fig_ph, width="stretch")
else:
    st.info("Corner-phase analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 6  PASSING PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Passing Profile")

if agg:
    games = agg.get("games_played", 38) or 38

    pp1, pp2, pp3, pp4 = st.columns(4)
    with pp1:
        kpi_card("Total Passes", int(agg.get("total_passes", 0)))
    with pp2:
        kpi_card("Pass Accuracy", f"{agg.get('pass_accuracy', 0)}%")
    with pp3:
        kpi_card("Crossing Accuracy", f"{agg.get('crossing_accuracy', 0)}%")
    with pp4:
        kpi_card("Passes/Match", round(agg.get("total_passes", 0) / games, 0))

    # Pass type distribution
    short = agg.get("successful_short_passes", 0)
    long = agg.get("successful_long_passes", 0)
    crosses = agg.get("successful_crosses", 0)

    if short + long + crosses > 0:
        pass_dist = pd.DataFrame({
            "Type": ["Short Passes", "Long Passes", "Crosses"],
            "Count": [short, long, crosses],
        })
        fig = bar_chart(pass_dist, x="Type", y="Count",
                        title=f"{team_name} — Pass Type Distribution",
                        color=AME_YELLOW)
        st.plotly_chart(fig, width="stretch")

    # Possession stats
    pp5, pp6, pp7, pp8 = st.columns(4)
    with pp5:
        kpi_card("Recoveries", int(agg.get("recoveries", 0)))
    with pp6:
        kpi_card("Successful Dribbles", int(agg.get("successful_dribbles", 0)))
    with pp7:
        kpi_card("Losses of Possession", int(agg.get("total_losses", 0)))
    with pp8:
        kpi_card("Fouls Won", int(agg.get("fouls_won", 0)))
else:
    st.info("Aggregate season stats not available for this team.")


# ═══════════════════════════════════════════════════════════════════════════
# § 6b  DISCIPLINE & FOULING EFFICIENCY (Expected Booking, xB)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Discipline & Fouling Efficiency")
st.caption(
    "**Expected Booking (xB)** = the chance a foul earns a card, learned "
    "empirically from where fouls are committed across the league. A team **above** "
    "the break-even line is booked more than its foul locations warrant; **below** "
    "= 'smart foulers'. **Fouls/card** is the efficiency headline."
)

disc = compute_league_discipline(league, season, stage_filter=_stage_filter)
disc_team = pd.DataFrame()
if disc and not disc.get("per_team", pd.DataFrame()).empty:
    pt = disc["per_team"]
    disc_team = pt[pt["team_id"] == team_id]

if not disc_team.empty:
    row = disc_team.iloc[0]
    dk1, dk2, dk3, dk4 = st.columns(4)
    with dk1:
        kpi_card("Fouls / Card", f"{row['fouls_per_card']:.1f}")
    with dk2:
        kpi_card("Cards vs Expected", f"{row['cards_vs_expected']:+.1f}")
    with dk3:
        kpi_card("Reds", int(row["reds"]))
    with dk4:
        kpi_card("Dangerous Fouls Won", int(row["dangerous_fouls_won"]))

    eff = ("more disciplined than their foul locations imply"
           if row["cards_vs_expected"] < -0.5 else
           ("booked more than expected — reckless or referee-prone"
            if row["cards_vs_expected"] > 0.5 else "booked about as expected"))
    st.markdown(
        f"{team_name} draw **{int(row['dangerous_fouls_won'])}** fouls in the "
        f"final third (set-piece value won) and are **{eff}**."
    )

    dc1, dc2 = st.columns([3, 2])
    with dc1:
        st.plotly_chart(
            discipline_scatter_chart(disc["per_team"], highlight_id=team_id,
                                     title=f"{league.replace('_', ' ')} — Fouling Efficiency"),
            use_container_width=True,
        )
    with dc2:
        foul_locs = load_team_foul_locations(league, season, team_id,
                                             stage_filter=_stage_filter)
        if not foul_locs.empty:
            plot_heatmap(foul_locs, title=f"{team_name} — Where They Foul")
        else:
            st.info("No foul-location data.")
else:
    st.info("Discipline analysis requires per-match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 7  GOALS TIMELINE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Goal Difference Trend")

goals_df = compute_goals_timeline(league, season, team_id,
                                  stage_filter=_stage_filter)
if not goals_df.empty:
    fig = multi_line_chart(
        goals_df, x="match_num",
        y_cols=["gd_cumulative"],
        colors=[AME_YELLOW],
        title=f"{team_name} — Cumulative Goal Difference",
        y_label="Goal Difference",
    )
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="#555", opacity=0.5)
    st.plotly_chart(fig, width="stretch")

