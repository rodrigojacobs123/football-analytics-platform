"""Player Scouting — Position-specific ratings, versatility detection, gap analysis."""

import streamlit as st
from viz.theme import apply_theme
import pandas as pd
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_card, metric_highlight, page_header, ame_section
from viz.radar import fc_radar, position_radar
from viz.pizza import pizza_chart
from viz.tables import styled_dataframe
from viz.xt import xt_top_contributors_bar
from data.loader import load_all_player_season_stats, load_player_events_season, list_standings_stages
from processing.xt import compute_season_xt
from processing.player_ratings import (
    compute_fc_ratings, POSITION_ATTR_KEYS, POSITION_CATEGORY_DISPLAY,
    get_position_attrs, get_position_display_names,
    SUB_POSITIONS,
)
from processing.play_style import classify_play_style
from processing.gap_analysis import (
    compute_team_gaps, compute_position_depth,
    find_recommendations, find_players_by_role,
)
from processing.player_profile import (
    compute_dimension_ratings, get_archetype,
    find_similar_players, load_cross_league_stats,
    DIMENSION_CONFIGS, _ARCHETYPE_MAP,
)
from viz.athletic_card import (
    style_matrix_figure, shot_map_figure, passing_rose_figure,
    chance_creation_figure, heatmap_figure,
    similar_players_figure, positions_played_figure,
)
from config import (
    AME_TEAM_NAME, AME_TEAM_ID, AME_YELLOW, AME_BLUE, AME_DARK_BG,
    POSITION_CATEGORIES, AME_LEAGUES, MIN_APPEARANCES_FOR_RATING,
)

apply_theme()

league, season = render_sidebar()

page_header("Player Scouting", subtitle=f"{season}")

# ── Tournament note for bi-annual leagues ───────────────────────────────────
_stage_names_scout = list_standings_stages(league, season)
if len(_stage_names_scout) > 1:
    st.info(
        f"📊 **{' + '.join(_stage_names_scout)} combined** — Player ratings are computed from "
        f"full-season aggregate stats (both tournaments). Event visualizations "
        f"(shot maps, heatmaps) show all-season data."
    )

# ── Compute Ratings ─────────────────────────────────────────────────────────
with st.spinner("Computing player ratings..."):
    all_stats = load_all_player_season_stats(league, season)
    ratings_df = compute_fc_ratings(all_stats)

if ratings_df.empty:
    st.warning("No player stats available for computing ratings.")
    st.stop()

# Classify play styles for all players (uses legacy PAC/SHO/PAS/DRI/DEF/PHY)
def _add_play_styles(df):
    styles = []
    for _, row in df.iterrows():
        r = {attr: int(row.get(attr, 50)) for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}
        name, desc, icon = classify_play_style(r)
        styles.append(f"{icon} {name}")
    df["play_style"] = styles
    return df

ratings_df = _add_play_styles(ratings_df)

# Get unique values for filters
all_teams = sorted(ratings_df["equipo"].dropna().unique().tolist())
all_positions = sorted(ratings_df["posicion"].dropna().unique().tolist())
all_styles = sorted(set(ratings_df["play_style"].dropna().unique().tolist()))


# ═══════════════════════════════════════════════════════════════════════════
# § 1  ADVANCED FILTERS
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("**Advanced Filters**", expanded=True):
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        scope = st.radio("Scope", ["CF América", "Custom Team", "Entire League"],
                         horizontal=False, key="scouting_scope")
    with fcol2:
        if scope == "Custom Team":
            selected_teams = st.multiselect("Select Team(s)", all_teams, key="team_filter")
        else:
            selected_teams = []
        pos_filter = st.multiselect("Position", all_positions, key="pos_filter")
    with fcol3:
        style_filter = st.multiselect("Play Style", all_styles, key="style_filter")
    with fcol4:
        ovr_range = st.slider("OVR Range", 40, 99, (40, 99), key="ovr_filter")
        # Dynamic sort options: position-specific if single position selected
        if len(pos_filter) == 1:
            pos_attrs = get_position_display_names(pos_filter[0])
            sort_options = ["OVR"] + pos_attrs
        else:
            sort_options = ["OVR", "PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
        attr_sort = st.selectbox("Sort by", sort_options, key="sort_ratings")

# Apply filters
if scope == "CF América":
    display_df = ratings_df[ratings_df["equipo"] == AME_TEAM_NAME].copy()
    if display_df.empty:
        display_df = ratings_df[ratings_df["equipo"].str.contains("CF América", na=False)]
    focus_team = AME_TEAM_NAME
elif scope == "Custom Team":
    if selected_teams:
        display_df = ratings_df[ratings_df["equipo"].isin(selected_teams)].copy()
        focus_team = selected_teams[0] if len(selected_teams) == 1 else None
    else:
        display_df = ratings_df.copy()
        focus_team = None
else:
    display_df = ratings_df.copy()
    focus_team = None

if pos_filter:
    display_df = display_df[display_df["posicion"].isin(pos_filter)]
if style_filter:
    display_df = display_df[display_df["play_style"].isin(style_filter)]
display_df = display_df[
    (display_df["OVR"] >= ovr_range[0]) & (display_df["OVR"] <= ovr_range[1])
]


# ═══════════════════════════════════════════════════════════════════════════
# § 2  PLAYER LEADERBOARD (position-aware columns)
# ═══════════════════════════════════════════════════════════════════════════
section_header(f"Player Leaderboard ({len(display_df)} players)")

# Show position-specific columns when filtering by one position
if len(pos_filter) == 1:
    pos_keys = get_position_attrs(pos_filter[0])
    pos_display = get_position_display_names(pos_filter[0])
    show_cols = ["nombre", "posicion", "equipo", "play_style"] + pos_keys + ["OVR"]
    # Map sort display name → column key
    display_to_key = {v: k for k, v in POSITION_CATEGORY_DISPLAY.items()}
    sort_col = display_to_key.get(attr_sort, attr_sort)
else:
    show_cols = ["nombre", "posicion", "equipo", "play_style",
                 "PAC", "SHO", "PAS", "DRI", "DEF", "PHY", "OVR"]
    sort_col = attr_sort

available = [c for c in show_cols if c in display_df.columns]
if sort_col in display_df.columns:
    sorted_df = display_df[available].sort_values(sort_col, ascending=False).head(50)
else:
    sorted_df = display_df[available].sort_values("OVR", ascending=False).head(50)

# Rename position-specific columns to display names for the table
rename_map = {k: v for k, v in POSITION_CATEGORY_DISPLAY.items() if k in sorted_df.columns}
styled_dataframe(sorted_df.rename(columns=rename_map), height=420)


# ═══════════════════════════════════════════════════════════════════════════
# § 2b  EXPECTED THREAT (xT) — SEASON BALL-PROGRESSION LEADERS
# ═══════════════════════════════════════════════════════════════════════════
# Scoped to Club América: an entire-league xT scan would load every team's
# per-match files (too heavy). America only plays AME_LEAGUES.
st.markdown("---")
section_header("Expected Threat (xT) — Ball Progression Leaders")
if league in AME_LEAGUES:
    st.caption(
        f"Season xT-added per player ({AME_TEAM_NAME}) — threat generated by "
        f"progressing the ball via passes & carries (Karun-Singh 12×8 grid). "
        f"Minimum {MIN_APPEARANCES_FOR_RATING} appearances to filter cameo noise."
    )
    _xt_scout = compute_season_xt(
        league, season, AME_TEAM_ID,
        min_appearances=MIN_APPEARANCES_FOR_RATING,
    )
    _lb = _xt_scout.get("leaderboard", pd.DataFrame()) if _xt_scout else pd.DataFrame()
    if not _lb.empty:
        xcol1, xcol2 = st.columns([3, 2])
        with xcol1:
            st.plotly_chart(
                xt_top_contributors_bar(
                    _lb.head(10),
                    title=f"{AME_TEAM_NAME} — Top xT Contributors",
                    color=AME_YELLOW),
                use_container_width=True,
            )
        with xcol2:
            _table = _lb.rename(columns={
                "player_name": "Player", "xt_added": "xT Added",
                "xt_per_match": "xT/Match", "passes": "Prog. Passes",
                "apps": "Apps",
            })
            styled_dataframe(_table, height=380)
    else:
        st.info(
            f"Season xT requires per-match files in partidos/ for {AME_TEAM_NAME}."
        )
else:
    st.info(
        f"Season xT leaderboard is computed for {AME_TEAM_NAME} only "
        f"(in its competitions: {', '.join(AME_LEAGUES)})."
    )


# ═══════════════════════════════════════════════════════════════════════════
# § 3  INDIVIDUAL PLAYER CARD (position-specific radar + versatility)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Player Card")

player_options = display_df[display_df["nombre"].notna()]["nombre"].tolist()
if not player_options:
    st.info("No rated players match your filters.")
    st.stop()

selected_name = st.selectbox("Select Player", player_options, key="player_card_sel")
player_row = display_df[display_df["nombre"] == selected_name].iloc[0]

# Get player's position and corresponding attributes
ovr = int(player_row.get("OVR", 50))
pos = player_row.get("posicion", "Midfielder")
team = player_row.get("equipo", "Unknown")
pos_keys = get_position_attrs(pos)
pos_display_names = get_position_display_names(pos)

# Build position-specific ratings dict
pos_ratings = {k: int(player_row.get(k, 50)) if pd.notna(player_row.get(k)) else 50
               for k in pos_keys}

# Legacy ratings for play-style
legacy_ratings = {attr: int(player_row.get(attr, 50))
                  for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}

# Player card layout
col1, col2, col3 = st.columns([1.2, 2, 1])

with col1:
    metric_highlight("OVR", ovr, AME_YELLOW)
    st.markdown(f"**Position:** {pos}")
    st.markdown(f"**Team:** {team}")

    # Play-style badge
    style_name, style_desc, style_icon = classify_play_style(legacy_ratings)
    st.markdown(f"""
    <div style="background:#1A1A2E;border-left:3px solid {AME_BLUE};padding:0.8rem;
                border-radius:5px;margin-top:1rem;">
        <p style="margin:0;color:{AME_BLUE};font-weight:bold;font-size:1.1rem;">
            {style_icon} {style_name}
        </p>
        <p style="margin:0.3rem 0 0;color:#999;font-size:0.85rem;">{style_desc}</p>
    </div>
    """, unsafe_allow_html=True)

    # Versatility badge
    v_tags = player_row.get("versatility_tags", [])
    if isinstance(v_tags, list) and v_tags:
        for tag in v_tags:
            st.markdown(f"""
            <div style="background:#1A1A2E;border-left:3px solid #42A5F5;padding:0.6rem;
                        border-radius:5px;margin-top:0.5rem;">
                <p style="margin:0;color:#42A5F5;font-weight:bold;font-size:0.9rem;">
                    {tag}
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Percentile ranking
    all_pos_players = ratings_df[ratings_df["posicion"] == pos]
    if not all_pos_players.empty:
        rank = (all_pos_players["OVR"] <= ovr).sum()
        pctile = int(rank / len(all_pos_players) * 100)
        st.markdown(f"""
        <div style="margin-top:0.8rem;padding:0.5rem;background:#1A1A2E;border-radius:5px;">
            <span style="color:#888;font-size:0.75rem;">LEAGUE PERCENTILE</span><br>
            <span style="color:{'#4CAF50' if pctile >= 75 else (AME_BLUE if pctile >= 50 else '#FF5252')};
                   font-size:1.5rem;font-weight:700;">{pctile}th</span>
            <span style="color:#666;font-size:0.75rem;"> among {len(all_pos_players)} {pos}s</span>
        </div>
        """, unsafe_allow_html=True)

with col2:
    # Tabs: classic radar OR scouted.football-style pizza percentile chart
    tab_radar, tab_pizza = st.tabs(["📊 Radar", "🍕 Pizza (percentiles)"])

    with tab_radar:
        fig = position_radar(selected_name, pos, pos_ratings)
        st.plotly_chart(fig, use_container_width=True)

    with tab_pizza:
        # Build category-grouped pizza metrics from squad-percentiles.
        # Map each position-specific attribute key to its tactical category
        # (matches POSITION_ATTR_KEYS in processing/player_ratings.py).
        ATTR_CATEGORY = {
            # Forward
            "FWD_Finish":       "Attack",
            "FWD_Move":         "Attack",
            "FWD_Chance":       "Attack",
            "FWD_Dribble":      "Possess",
            "FWD_AerialThreat": "Defend",   # aerial = duels = defensive trait colour
            # Midfielder
            "MID_Pass":         "Possess",
            "MID_Create":       "Attack",
            "MID_Carry":        "Possess",
            "MID_DefWork":      "Defend",
            "MID_Press":        "Defend",
            # Defender
            "DEF_Tackle":       "Defend",
            "DEF_Aerial":       "Defend",
            "DEF_Position":     "Defend",
            "DEF_BallPlay":     "Possess",
            "DEF_Physical":     "Defend",
            # Goalkeeper
            "GK_ShotStop":      "Defend",
            "GK_Dist":          "Possess",
            "GK_Command":       "Defend",
            "GK_Reflex":        "Defend",
            "GK_CleanSheet":    "Defend",
        }

        pizza_metrics = []
        for key, display_name in zip(pos_keys, pos_display_names):
            val = pos_ratings.get(key, 50)
            # Compute squad percentile for this attribute
            if not all_pos_players.empty and key in all_pos_players.columns:
                valid = all_pos_players[key].dropna()
                pctile = int((valid <= val).sum() / len(valid) * 100) if len(valid) > 0 else 50
            else:
                pctile = 50
            pizza_metrics.append({
                "label": display_name,
                "value": pctile,
                "category": ATTR_CATEGORY.get(key, "Possess"),
            })

        # Sort: Attack → Possess → Defend so the pizza visually groups
        cat_order = {"Attack": 0, "Possess": 1, "Defend": 2}
        pizza_metrics.sort(key=lambda m: cat_order.get(m["category"], 1))

        st.plotly_chart(
            pizza_chart(selected_name, pizza_metrics,
                        title_suffix=f"vs {len(all_pos_players)} {pos}s · league percentile"),
            use_container_width=True)

with col3:
    # Position-specific attribute bars with league percentile context
    for key, display_name in zip(pos_keys, pos_display_names):
        val = pos_ratings.get(key, 50)
        # League percentile for this attribute
        if not all_pos_players.empty and key in all_pos_players.columns:
            valid = all_pos_players[key].dropna()
            attr_pctile = int((valid <= val).sum() / len(valid) * 100) if len(valid) > 0 else 50
        else:
            attr_pctile = 50
        bar_color = AME_YELLOW if val >= 75 else (AME_BLUE if val >= 60 else "#666")
        pctile_color = "#4CAF50" if attr_pctile >= 75 else (AME_BLUE if attr_pctile >= 50 else "#888")
        st.markdown(f"""
        <div style="margin:0.35rem 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#999;font-size:0.72rem;width:80px;">{display_name}</span>
                <span style="color:white;font-weight:bold;font-size:1rem;">{val}</span>
                <span style="color:{pctile_color};font-size:0.7rem;">{attr_pctile}%ile</span>
            </div>
            <div style="background:#333;border-radius:3px;height:8px;width:100%;">
                <div style="background:{bar_color};border-radius:3px;height:8px;width:{val}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# § 3b  ATHLETIC-STYLE PROFILE CARD
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")

with st.expander("**⚡ Player Intelligence Card** (Opta-style deep profile)", expanded=True):
    player_id_val = str(player_row.get("id", ""))

    # ── Archetype detection ──────────────────────────────────────────────
    peers_for_dims = ratings_df[ratings_df["posicion"] == pos].copy()
    # Join back the raw stats for dimension computation
    raw_stats = load_all_player_season_stats(league, season)
    if not raw_stats.empty and "id" in raw_stats.columns:
        peer_raw = raw_stats[raw_stats["posicion"] == pos]
        target_raw_rows = raw_stats[raw_stats["id"] == player_id_val]
        target_raw = target_raw_rows.iloc[0] if not target_raw_rows.empty else player_row
    else:
        peer_raw = pd.DataFrame()
        target_raw = player_row

    if not peer_raw.empty:
        dim_ratings = compute_dimension_ratings(target_raw, pos, peer_raw)
    else:
        dim_ratings = {d: 3 for d in list(DIMENSION_CONFIGS.get(pos, DIMENSION_CONFIGS["Midfielder"]))}

    archetype_name, archetype_desc = get_archetype(pos, dim_ratings)

    # ── Minutes + team percentage ─────────────────────────────────────────
    minutes_played = int(target_raw.get("Time Played", 0) or 0) if not peer_raw.empty else 0
    team_total_min = int(peer_raw[peer_raw["equipo"] == team]["Time Played"].sum()) if not peer_raw.empty else 0
    team_pct = f"{minutes_played / team_total_min * 100:.1f}%" if team_total_min > 0 else "—"

    # ── Header ────────────────────────────────────────────────────────────
    from config import AME_BLUE, AME_YELLOW, AME_DARK_BG
    st.markdown(f"""
    <div style="background:#1A1A2E;border-radius:8px;padding:1rem 1.2rem;margin-bottom:0.8rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
                <h2 style="margin:0;color:white;font-size:1.5rem;font-weight:700;">{selected_name}</h2>
                <p style="margin:0.2rem 0 0;color:#888;font-size:0.85rem;">
                    {pos} · {team} · {minutes_played:,} min played ({team_pct} of team total)
                </p>
                <div style="margin-top:0.6rem;">
                    <span style="color:{AME_YELLOW};font-weight:700;font-size:1rem;">'{archetype_name}'</span>
                    <span style="color:#aaa;font-size:0.85rem;margin-left:0.4rem;">→ {archetype_desc}</span>
                </div>
            </div>
            <div style="text-align:right;">
                <span style="color:{AME_BLUE};font-size:2rem;font-weight:700;">{ovr}</span>
                <br><span style="color:#666;font-size:0.7rem;">OVR</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Row 1: Style Matrix | Position-specific viz ───────────────────────
    card_col1, card_col2 = st.columns([1, 1.4])

    with card_col1:
        st.caption("Playing style (vs. peers in league)")
        pos_color = AME_YELLOW if team == "CF América" else "#4A90D9"
        st.plotly_chart(
            style_matrix_figure(dim_ratings, position_color=pos_color),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with card_col2:
        # Load player events from partidos
        with st.spinner("Loading event data..."):
            # Shots for forwards, passes for midfielders/defenders, all events for heatmap
            if pos in ("Forward", "Attacker"):
                events_df = load_player_events_season(
                    league, season, player_id_val, type_ids=(13, 14, 15, 16)
                )
                if not events_df.empty:
                    st.caption("Shot map (size = xG, red = goal)")
                    xg_sum = events_df["xg"].dropna().sum()
                    goals_count = int((events_df["outcome"] == 1).sum())
                    fig = shot_map_figure(events_df, xg_total=xg_sum, goals_total=goals_count)
                    st.pyplot(fig, use_container_width=True)
                    plt = __import__("matplotlib.pyplot", fromlist=["close"])
                    plt.close("all")
                else:
                    st.info("No shot event data found for this player.")

            elif pos == "Midfielder":
                pass_events = load_player_events_season(
                    league, season, player_id_val, type_ids=(1,)
                )
                if not pass_events.empty:
                    sub = player_row.get("sub_posicion", "Central Midfielder")
                    if sub in ("Attacking Midfielder",):
                        st.caption("Chance creation map")
                        key_passes = pass_events[pass_events["outcome"] == 1]
                        fig = chance_creation_figure(key_passes)
                        st.pyplot(fig, use_container_width=True)
                    else:
                        st.caption("Passing direction rose")
                        fig = passing_rose_figure(pass_events)
                        st.plotly_chart(fig, use_container_width=True,
                                        config={"displayModeBar": False})
                    import matplotlib.pyplot as _plt
                    _plt.close("all")
                else:
                    st.info("No pass event data found for this player.")

            elif pos == "Defender":
                pass_events = load_player_events_season(
                    league, season, player_id_val, type_ids=(1,)
                )
                if not pass_events.empty:
                    st.caption("Progressive pass zones")
                    fig = passing_rose_figure(pass_events)
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})
                    import matplotlib.pyplot as _plt
                    _plt.close("all")
                else:
                    st.info("No pass event data found for this player.")
            else:
                st.info("Event visualization not configured for this position.")

    # ── Row 2: Similar players | Positions played | Heatmap ──────────────
    st.markdown("---")
    sim_col, heat_col = st.columns([1.2, 1])

    with sim_col:
        st.caption("Similar players in Europe (cosine similarity on per-90 profile)")
        with st.spinner("Searching across European leagues..."):
            cross_df = load_cross_league_stats(season)
            similar_df = find_similar_players(
                player_id_val, pos, raw_stats, cross_df, top_n=10
            )
        st.plotly_chart(
            similar_players_figure(similar_df, position_color=pos_color),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with heat_col:
        st.caption("Open-play season heatmap")
        with st.spinner("Building heatmap..."):
            all_events = load_player_events_season(league, season, player_id_val)
            open_play = all_events[~all_events["is_penalty"]] if not all_events.empty else all_events
        fig = heatmap_figure(open_play, team_color=pos_color)
        st.pyplot(fig, use_container_width=True)
        import matplotlib.pyplot as _plt2
        _plt2.close("all")


# ═══════════════════════════════════════════════════════════════════════════
# § 4  PLAYER COMPARISON
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Player Comparison")

all_player_names = ratings_df[ratings_df["nombre"].notna()]["nombre"].tolist()
compare_names = st.multiselect(
    "Compare with (any league player)",
    [n for n in all_player_names if n != selected_name],
    max_selections=2,
    key="player_compare"
)

if compare_names:
    # Check if all compared players share the same position
    compare_rows = [ratings_df[ratings_df["nombre"] == n].iloc[0] for n in compare_names]
    all_same_pos = all(r.get("posicion") == pos for r in compare_rows)

    if all_same_pos:
        # Position-specific radar comparison
        compare_pos_ratings = {}
        for name, row in zip(compare_names, compare_rows):
            compare_pos_ratings[name] = {
                k: int(row.get(k, 50)) if pd.notna(row.get(k)) else 50
                for k in pos_keys
            }
        fig = position_radar(selected_name, pos, pos_ratings,
                             compare_to=compare_pos_ratings)
        st.plotly_chart(fig, use_container_width=True)

        # Comparison table with position attributes
        comp_data = {"Attribute": pos_display_names + ["OVR"]}
        comp_data[selected_name] = [pos_ratings.get(k, 0) for k in pos_keys] + [ovr]
        for name, row in zip(compare_names, compare_rows):
            comp_data[name] = ([int(row.get(k, 0)) if pd.notna(row.get(k)) else 0
                                for k in pos_keys]
                               + [int(row.get("OVR", 0))])
    else:
        # Mixed positions — use legacy PAC/SHO/PAS/DRI/DEF/PHY radar
        compare_legacy = {}
        for name, row in zip(compare_names, compare_rows):
            compare_legacy[name] = {attr: int(row.get(attr, 50))
                                    for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}
        fig = fc_radar(selected_name, legacy_ratings, compare_to=compare_legacy)
        st.plotly_chart(fig, use_container_width=True)

        # Comparison table with legacy attributes
        attrs = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
        comp_data = {"Attribute": attrs + ["OVR"]}
        comp_data[selected_name] = [legacy_ratings.get(a, 0) for a in attrs] + [ovr]
        for name, row in zip(compare_names, compare_rows):
            comp_data[name] = [int(row.get(a, 0)) for a in attrs] + [int(row.get("OVR", 0))]

    comp_df = pd.DataFrame(comp_data)
    styled_dataframe(comp_df, height=300)


# ═══════════════════════════════════════════════════════════════════════════
# § 5  SQUAD DEPTH ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Squad Depth Analysis")

depth_team = st.selectbox(
    "Analyze Team Depth",
    all_teams,
    index=all_teams.index(AME_TEAM_NAME) if AME_TEAM_NAME in all_teams else 0,
    key="depth_team"
)

depth_df = compute_position_depth(ratings_df, depth_team)
if not depth_df.empty:
    for _, row in depth_df.iterrows():
        depth_color = {
            "Strong": "#4CAF50", "Adequate": AME_BLUE,
            "Thin": "#FF9800", "Empty": "#FF5252"
        }.get(row["depth_rating"], "#666")

        depth_icon = {
            "Strong": "++", "Adequate": "+", "Thin": "-", "Empty": "--"
        }.get(row["depth_rating"], "?")

        bar_width = min(row["count"] * 15, 100)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:0.3rem 0;padding:0.5rem;
                    background:#1A1A2E;border-radius:6px;border-left:3px solid {depth_color};">
            <span style="width:100px;color:#ccc;font-size:0.85rem;font-weight:600;">{row['position']}</span>
            <div style="flex:1;">
                <div style="background:#333;border-radius:3px;height:20px;width:100%;position:relative;">
                    <div style="background:{depth_color};border-radius:3px;height:20px;width:{bar_width}%;
                         display:flex;align-items:center;padding-left:8px;">
                        <span style="color:white;font-size:0.75rem;font-weight:700;">{row['count']} players</span>
                    </div>
                </div>
            </div>
            <span style="width:60px;text-align:center;color:white;font-weight:700;font-size:0.9rem;">
                {row['avg_ovr']}
            </span>
            <span style="width:30px;text-align:center;color:{depth_color};font-weight:bold;">{depth_icon}</span>
            <span style="width:80px;color:{depth_color};font-size:0.75rem;font-weight:600;">
                {row['depth_rating']}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Bar = player count | Number = avg OVR | Rating = depth assessment")
else:
    st.info("No depth data available for this team.")


# ═══════════════════════════════════════════════════════════════════════════
# § 6  TEAM GAP ANALYSIS (position-specific attributes)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Gap Analysis vs League Average")

gap_team = depth_team  # Use same team selection

gaps_df = compute_team_gaps(ratings_df, gap_team)
if not gaps_df.empty:
    # Show OVR gaps by position
    ovr_gaps = gaps_df[gaps_df["attribute"] == "OVR"].copy()
    ovr_gaps = ovr_gaps.sort_values("gap")

    st.markdown(f"#### {gap_team} — Position OVR vs League Average")

    for _, row in ovr_gaps.iterrows():
        gap = row["gap"]
        gap_color = "#4CAF50" if gap >= 2 else (AME_BLUE if gap >= -2 else "#FF5252")
        gap_icon = "+" if gap > 0 else ("-" if gap < 0 else "=")
        bar_pos = min(max((row["team_avg"] - 40) / 60 * 100, 0), 100)

        st.markdown(f"""
        <div style="margin:0.35rem 0;padding:0.5rem 0.8rem;background:#1A1A2E;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#ccc;font-size:0.85rem;font-weight:600;width:100px;">
                    {row['position']}
                </span>
                <span style="color:white;font-size:0.9rem;">
                    Team: <b>{row['team_avg']}</b>
                </span>
                <span style="color:#888;font-size:0.9rem;">
                    League: <b>{row['league_avg']}</b>
                </span>
                <span style="color:{gap_color};font-size:0.9rem;font-weight:700;">
                    {gap_icon} {abs(gap):.1f}
                </span>
            </div>
            <div style="position:relative;background:#333;border-radius:3px;height:8px;margin-top:6px;">
                <div style="background:{gap_color};border-radius:3px;height:8px;width:{bar_pos}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Detailed attribute gaps (expandable, now position-specific)
    with st.expander("Detailed Attribute Breakdown"):
        detail = gaps_df[gaps_df["attribute"] != "OVR"].copy()
        if not detail.empty:
            # Show display_name instead of raw attribute key
            show = detail[["position", "display_name", "team_avg", "league_avg", "gap"]].copy()
            show.columns = ["Position", "Attribute", "Team Avg", "League Avg", "Gap"]
            styled_dataframe(show, height=350)
else:
    st.info("No gap data available.")


# ═══════════════════════════════════════════════════════════════════════════
# § 7  SCOUTING RECOMMENDATIONS (position-specific attributes)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Scouting Recommendations")

rec_team = depth_team

# ── Mode selector: auto gap analysis vs manual role browsing ──
rec_mode_col, rec_filter_col = st.columns([1, 2])
with rec_mode_col:
    rec_mode = st.radio(
        "Search mode",
        ["Auto (Gap Analysis)", "Browse by Role"],
        horizontal=True,
        key="rec_mode",
    )

recs_df = pd.DataFrame()
role_label = ""

if rec_mode == "Browse by Role":
    with rec_filter_col:
        chosen_role = st.selectbox(
            "Select a role",
            SUB_POSITIONS,
            key="rec_role",
        )
    role_label = chosen_role
    recs_df = find_players_by_role(ratings_df, rec_team, chosen_role, top_n=5)
else:
    recs_df = find_recommendations(ratings_df, rec_team, top_n=3)


def _render_rec_card(rec: pd.Series) -> None:
    """Render a single recommendation card with position-specific attribute chips."""
    rec_pos = rec["posicion"]
    rec_pos_keys = get_position_attrs(rec_pos)
    rec_pos_names = get_position_display_names(rec_pos)

    attr_chips = ""
    for key, display in zip(rec_pos_keys, rec_pos_names):
        val = rec.get(display, rec.get(key, 40))
        if pd.isna(val):
            val = 40
        val = int(val)
        attr_chips += (
            f'<div style="text-align:center;padding:4px 6px;background:#222;border-radius:4px;">'
            f'<span style="color:#888;font-size:0.6rem;">{display[:8]}</span><br>'
            f'<span style="color:white;font-size:0.8rem;font-weight:600;">{val}</span>'
            f'</div>'
        )

    key_display = rec.get("key_display", rec.get("key_attribute", ""))
    key_val = int(rec.get("key_value", 0))
    sub_pos = rec.get("sub_posicion", "")
    role_tag = f' · <span style="color:{AME_BLUE};font-size:0.7rem;">{sub_pos}</span>' if sub_pos else ""

    card_html = (
        f'<div style="display:flex;align-items:center;gap:10px;margin:0.4rem 0;padding:0.7rem 1rem;'
        f'background:#1A1A2E;border-radius:8px;border-left:3px solid {AME_YELLOW};">'
        f'<div style="text-align:center;min-width:50px;">'
        f'<span style="color:{AME_YELLOW};font-size:1.6rem;font-weight:700;">{rec["OVR"]}</span>'
        f'<br><span style="color:#666;font-size:0.65rem;">OVR</span></div>'
        f'<div style="flex:1;min-width:120px;">'
        f'<span style="color:white;font-size:1rem;font-weight:600;">{rec["nombre"]}</span>'
        f'<br><span style="color:#888;font-size:0.8rem;">{rec["equipo"]} | {rec_pos}{role_tag}</span></div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;">{attr_chips}</div>'
        f'<div style="text-align:center;padding:4px 8px;background:{AME_BLUE}22;border-radius:4px;'
        f'border:1px solid {AME_BLUE}44;min-width:70px;">'
        f'<span style="color:{AME_BLUE};font-size:0.6rem;">KEY</span><br>'
        f'<span style="color:{AME_BLUE};font-size:0.8rem;font-weight:700;">{key_display} {key_val}</span>'
        f'</div></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


if not recs_df.empty:
    if rec_mode == "Browse by Role":
        st.markdown(f"**Top {role_label} players from other teams (excluding {rec_team}):**")
        for _, rec in recs_df.iterrows():
            _render_rec_card(rec)
        st.caption(f"Showing top players classified as **{role_label}** by attribute profile.")
    else:
        st.markdown(f"**Players from other teams who could strengthen {rec_team}:**")
        for gap_label in recs_df["fills_gap"].unique():
            gap_recs = recs_df[recs_df["fills_gap"] == gap_label]
            st.markdown(f"#### {gap_label}")
            for _, rec in gap_recs.iterrows():
                _render_rec_card(rec)
        st.caption("Recommendations based on positions where the team rates below league average.")
else:
    if rec_mode == "Browse by Role":
        st.info(f"No **{role_label}** players found in other teams.")
    else:
        st.success(f"{rec_team} is above league average in all positions! No urgent gaps detected.")

# ── Archetype & Dimension Guide (contextual to current recommendations) ───
_POS_ORDER = ["Forward", "Midfielder", "Defender", "Goalkeeper"]
_POS_ICONS = {"Forward": "⚽", "Midfielder": "🔄", "Defender": "🛡️", "Goalkeeper": "🧤"}

# Colour-coded dimension pill
def _dim_pill(dim_name: str, pos_key: str) -> str:
    accent = AME_YELLOW if pos_key == "Forward" else (
        "#4A90D9" if pos_key == "Midfielder" else (
        AME_BLUE if pos_key == "Defender" else "#5FBF7A"
    ))
    return (
        f'<span style="display:inline-block;padding:2px 8px;margin:2px;'
        f'background:{accent}22;border:1px solid {accent}55;border-radius:12px;'
        f'color:{accent};font-size:0.72rem;font-weight:600;">{dim_name}</span>'
    )

with st.expander("**Scouting Archetype Guide** — what each profile means on the pitch"):
    pos_tabs = st.tabs([f"{_POS_ICONS[p]} {p}s" for p in _POS_ORDER])

    for tab, pos_key in zip(pos_tabs, _POS_ORDER):
        with tab:
            archetypes = _ARCHETYPE_MAP.get(pos_key, [])
            dims_for_pos = list(DIMENSION_CONFIGS.get(pos_key, {}).keys())

            # Dimension legend at the top of each tab
            legend_pills = " ".join(_dim_pill(d, pos_key) for d in dims_for_pos)
            st.markdown(
                f'<div style="margin-bottom:0.8rem;">'
                f'<span style="color:#666;font-size:0.75rem;margin-right:6px;">Dimensions rated:</span>'
                f'{legend_pills}</div>',
                unsafe_allow_html=True,
            )

            cols = st.columns(2)
            for i, (rule, (arch_name, arch_desc)) in enumerate(archetypes):
                # Build threshold chips for non-empty rules
                threshold_html = ""
                if rule:
                    for dim, thresh in rule.items():
                        squares = "■" * thresh + "□" * (5 - thresh)
                        threshold_html += (
                            f'<div style="font-size:0.68rem;color:#888;margin-top:2px;">'
                            f'<span style="color:#bbb;">{dim}</span>'
                            f' <span style="color:{AME_YELLOW};letter-spacing:1px;">'
                            f'{squares}</span></div>'
                        )
                else:
                    threshold_html = (
                        '<div style="font-size:0.68rem;color:#555;margin-top:2px;">'
                        'Balanced across all dimensions</div>'
                    )

                card = (
                    f'<div style="padding:0.6rem 0.8rem;margin:0.3rem 0;'
                    f'background:#1A1A2E;border-radius:6px;'
                    f'border-left:3px solid {AME_BLUE};">'
                    f'<span style="color:{AME_BLUE};font-weight:700;font-size:0.95rem;">'
                    f'{arch_name}</span>'
                    f'<br><span style="color:#aaa;font-size:0.8rem;">{arch_desc}</span>'
                    f'{threshold_html}'
                    f'</div>'
                )
                with cols[i % 2]:
                    st.markdown(card, unsafe_allow_html=True)

            # Dimension definitions table for this position
            with st.expander(f"What each {pos_key} dimension measures", expanded=False):
                dim_cfg = DIMENSION_CONFIGS.get(pos_key, {})
                for dim_name, cfg in dim_cfg.items():
                    stat_list = ", ".join(
                        f"{s} (×{w:.2f})" for s, w in cfg["stats"].items()
                    )
                    st.markdown(
                        f"**{dim_name}** — {stat_list}",
                        help="Computed as a per-90 weighted sum across the stats listed."
                    )
