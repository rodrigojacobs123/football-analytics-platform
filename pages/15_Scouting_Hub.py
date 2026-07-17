"""Scouting Hub — upload Wyscout search exports, rank & compare players across files."""

import io

import pandas as pd
import streamlit as st

from viz.theme import apply_theme
from viz.kpi_cards import page_header, kpi_card, ame_section
from viz.radar import radar_chart
from viz.tables import styled_dataframe
from processing.wyscout_scouting import (
    normalize_wyscout, combine_sources, score_players, add_value_index,
    assign_archetypes, archetype_breakdown, find_similar,
    top_by_file, radar_data, display_columns, dedupe_best,
    apply_league_coefficients, rank_col,
    GROUP_LABELS, DEFAULT_MIN_MINUTES, MIN_GROUP_SAMPLE,
    LEAGUE_TIERS, DEFAULT_TIER, ARCHETYPES, ROLE_METRICS,
)
from processing.wyscout_bridge import (
    opta_to_wyscout_profile, market_comparison, bridge_radar,
    OPTA_POSITION_DEFAULT_GROUP,
)
from viz.scouting_report import (
    build_scouting_report, ARCHETYPE_ES, METRIC_ES,
    _quality_issues as quality_issues, _bin_counts as bin_counts,
    _player_comment as player_comment, _scatter_axes as scatter_axes,
)
from data.loader import load_player_season_stats
from config import AME_YELLOW, AME_BLUE, AME_TEAM_NAME, AME_TEAM_FOLDER, DEFAULT_SEASON

apply_theme()

page_header("Scouting Hub", subtitle="Wyscout search exports — upload, rank, compare")

st.markdown(
    "Upload one or more Wyscout **Search results** exports (.xlsx). Each file is "
    "analysed on its own and pooled with the others, so a right-back search and a "
    "striker search can live side by side — every player is ranked **against their "
    "own position group** only. Multi-position players (e.g. `LB, LCB`) are scored "
    "in **every group they cover**, each against the right sample — check the "
    "`group_role` column to see if a row is their primary or secondary role."
)


# Parsing is cached on the raw bytes: re-runs (slider moves, tab switches) never
# re-read the Excel. This page bypasses data.loader deliberately — uploads live
# in memory, not under DATA_ROOT.
# _PARSE_VERSION is part of the cache key: st.cache_data only hashes this
# function's own body, so bump it whenever normalize_wyscout's output changes,
# or live sessions keep getting the old cached schema.
_PARSE_VERSION = 2


@st.cache_data(ttl=3600, show_spinner=False)
def _parse_upload(file_bytes: bytes, name: str, version: int) -> pd.DataFrame:
    return normalize_wyscout(pd.read_excel(io.BytesIO(file_bytes)), name)


uploads = st.file_uploader(
    "Wyscout exports", type=["xlsx"], accept_multiple_files=True,
    help="Exports from Wyscout Search (the ~115-column 'Search results' files).",
)

if not uploads:
    st.info(
        "⬆️ Drop your Wyscout files here to get started. "
        "You can upload several at once — e.g. one search per position or league."
    )
    st.stop()

frames, failed = [], []
for up in uploads:
    try:
        frames.append(_parse_upload(up.getvalue(), up.name, _PARSE_VERSION))
    except Exception as exc:  # noqa: BLE001 — surface bad files, keep the rest
        failed.append((up.name, str(exc)))

if failed:
    for name, msg in failed:
        st.warning(f"Skipped **{name}**: {msg}")
if not frames:
    st.stop()

pooled = combine_sources(frames)

# ── League level per file ────────────────────────────────────────────────────
# A raw percentile hides league quality; each file is tagged with a tier whose
# coefficient scales the composite score (percentiles/archetypes stay raw).
with st.expander("🌐 League level per file", expanded=False):
    st.caption(
        "Tag each upload with its league tier — a 90th-percentile passer in a "
        "development league is not one in the Bundesliga. Adds a `Score (adj)` "
        "column used for all rankings."
    )
    coeff_by_file: dict[str, float] = {}
    for fr in frames:
        fname = fr["source_file"].iloc[0]
        tier = st.selectbox(
            fname, list(LEAGUE_TIERS.keys()),
            index=list(LEAGUE_TIERS.keys()).index(DEFAULT_TIER),
            key=f"tier_{fname}",
        )
        coeff_by_file[fname] = LEAGUE_TIERS[tier]
tiers_active = any(c != 1.0 for c in coeff_by_file.values())

# ── Filters ──────────────────────────────────────────────────────────────────
with st.container():
    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.6, 1])
    max_minutes = int(pooled["Minutes played"].max())
    min_minutes = f1.slider(
        "Min. minutes played", 0, max_minutes,
        value=min(DEFAULT_MIN_MINUTES, max_minutes),
        step=90, help="Per-90 stats under ~900 minutes are mostly noise.",
    )
    age_lo, age_hi = int(pooled["Age"].min()), int(pooled["Age"].max())
    age_range = f2.slider("Age range", age_lo, age_hi, (age_lo, age_hi))
    groups_present = sorted(pooled["position_group"].dropna().unique())
    sel_groups = f3.multiselect(
        "Position groups", groups_present, default=groups_present,
        format_func=lambda g: f"{g} — {GROUP_LABELS.get(g, g)}",
    )
    top_n = f4.number_input("Top N per file", 3, 30, 10)

    g1, g2 = st.columns([2.4, 1.6])
    mv_series = pooled["Market value"].fillna(0)
    max_mv_m = max(1.0, float(mv_series.max()) / 1e6)
    mv_range = g1.slider(
        "Market value (€M)", 0.0, max_mv_m, (0.0, max_mv_m), step=0.5,
        help="Budget filter — Wyscout market value in millions of euros.",
    )
    include_no_value = g2.checkbox(
        "Include players without market value", value=True,
        help="Wyscout has no valuation (€0) for some players — usually "
             "lower-league or very young ones. Unticking hides them.",
    )

# Value/archetype filters apply AFTER scoring so percentiles stay stable:
# a budget cap shouldn't change who counts as the 90th-percentile passer.
scored = score_players(pooled, min_minutes=min_minutes)
scored = scored[
    scored["Age"].between(*age_range) & scored["position_group"].isin(sel_groups)
]
scored = add_value_index(scored)
scored = assign_archetypes(scored)
if tiers_active:
    scored = apply_league_coefficients(scored, coeff_by_file)
RANK = rank_col(scored)  # "Score (adj)" when league tiers are set, else "Score"

mv_m = scored["Market value"].fillna(0) / 1e6
in_budget = mv_m.between(*mv_range) & (scored["Market value"] > 0)
if include_no_value:
    in_budget |= scored["Market value"].fillna(0) == 0
scored = scored[in_budget]

archetypes_present = sorted(scored["Archetype"].dropna().unique())
if archetypes_present:
    sel_arch = st.multiselect(
        "Archetypes", archetypes_present, default=archetypes_present,
        help="Playing-style profiles detected per position group. "
             "'Complete' = no single dominant style.",
    )
    scored = scored[scored["Archetype"].isin(sel_arch) | scored["Archetype"].isna()]

if scored.empty:
    st.warning("No players left after filters — lower the minutes threshold or widen the age range.")
    st.stop()

# ── KPI row ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Files uploaded", len(frames))
with k2:
    kpi_card("Players (after filters)",
             len(scored[["Player", "Team"]].drop_duplicates()))
with k3:
    kpi_card("Position groups", scored["position_group"].nunique())
with k4:
    kpi_card("Avg. age", round(float(scored["Age"].mean()), 1))

small = scored[scored.get("small_sample", False) == True]  # noqa: E712
if not small.empty:
    st.caption(
        f"⚠️ Groups with fewer than {MIN_GROUP_SAMPLE} players "
        f"({', '.join(sorted(small['position_group'].unique()))}) — percentiles "
        "there are unstable, read the scores with care."
    )

# ── Shortlist infrastructure ─────────────────────────────────────────────────
# The deliverable of a scouting screening is a LIST that travels to the
# committee, not a dashboard. Rows picked anywhere land here and export to
# Excel from the ⭐ tab. Keyed by (Player, Team) so re-adding is idempotent.
if "shortlist" not in st.session_state:
    st.session_state.shortlist = {}


def _clean_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """List columns break st.dataframe selection + Excel export."""
    out = df.drop(columns=["position_groups"], errors="ignore").copy()
    if "found_in" in out.columns:
        out["found_in"] = out["found_in"].map(
            lambda v: ", ".join(v) if isinstance(v, list) else v)
    return out


def _add_to_shortlist(rows: list[dict]) -> None:
    # on_click callback: runs BEFORE the rerun, so the tab label's count is
    # already fresh when st.tabs() re-executes.
    for r in rows:
        st.session_state.shortlist[f"{r['Player']}|{r['Team']}"] = r
    st.toast(f"Shortlist: {len(st.session_state.shortlist)} players")


def selectable_table(df: pd.DataFrame, key: str, height: int = 400) -> None:
    """Ranking table whose rows can be sent to the shortlist."""
    disp = _clean_for_display(df).reset_index(drop=True)
    event = st.dataframe(
        disp, width="stretch", hide_index=True, height=height,
        on_select="rerun", selection_mode="multi-row", key=key,
    )
    rows = event.selection.rows if event and event.selection else []
    if rows:
        st.button(
            f"⭐ Add {len(rows)} selected to shortlist", key=f"{key}_add",
            on_click=_add_to_shortlist,
            args=([disp.iloc[i].to_dict() for i in rows],),
        )


(tab_files, tab_global, tab_compare, tab_similar, tab_replace, tab_market,
 tab_analysis, tab_short) = st.tabs(
    ["🏆 Best per file", "🌍 Global ranking", "🎯 Compare players",
     "🧬 Similar players", "🦅 Replace from squad", "💎 Market opportunities",
     "📊 Market analysis",
     f"⭐ Shortlist ({len(st.session_state.shortlist)})"]
)

# ── Tab 1: best per file ─────────────────────────────────────────────────────
with tab_files:
    ame_section("PER FILE", "Top players in each upload")
    for fname, fdf in top_by_file(scored, n=int(top_n)).items():
        with st.expander(f"📄 {fname} — {len(fdf)} shown", expanded=len(uploads) == 1):
            styled_dataframe(
                fdf[display_columns(fdf)].drop(columns=["found_in"], errors="ignore"),
                height=min(420, 40 + 36 * len(fdf)),
            )

# ── Tab 2: global ranking ────────────────────────────────────────────────────
with tab_global:
    ame_section("POOLED", "Ranking across all files")
    g = st.selectbox(
        "Position group", sorted(scored["position_group"].unique()),
        format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
        key="global_group",
    )
    gdf = scored[scored["position_group"] == g].sort_values(RANK, ascending=False)

    import plotly.graph_objects as go
    top15 = gdf.head(15).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top15[RANK], y=top15["Player"] + "  (" + top15["Team"].fillna("?") + ")",
        orientation="h", marker_color=AME_YELLOW,
        text=top15[RANK], textposition="outside",
    ))
    fig.update_layout(
        height=max(300, 32 * len(top15)), margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(range=[0, 105],
                   title="Composite score" + (" (league-adjusted)" if tiers_active else "")),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF0FA"),
    )
    st.plotly_chart(fig, width="stretch")
    selectable_table(gdf[display_columns(gdf)], key=f"table_global_{g}", height=440)

# ── Tab 3: radar comparison ──────────────────────────────────────────────────
with tab_compare:
    ame_section("HEAD TO HEAD", "Percentile radar (within position group)")
    cg = st.selectbox(
        "Position group", sorted(scored["position_group"].unique()),
        format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
        key="compare_group",
    )
    cdf = scored[scored["position_group"] == cg].sort_values(RANK, ascending=False)
    options = cdf["Player"].tolist()
    sel_players = st.multiselect(
        "Players (2–5)", options, default=options[:2], max_selections=5,
    )
    if len(sel_players) >= 2:
        categories, values = radar_data(scored, cg, sel_players)
        st.plotly_chart(
            radar_chart(categories, values, title=GROUP_LABELS.get(cg, cg)),
            width="stretch",
        )
        side = cdf[cdf["Player"].isin(sel_players)]
        styled_dataframe(
            side[display_columns(side)], height=40 + 36 * len(side),
        )
    else:
        st.info("Pick at least two players to compare.")

# ── Tab 4: similar players ───────────────────────────────────────────────────
with tab_similar:
    ame_section("ALTERNATIVES", "Find stylistic replacements")
    st.caption(
        "Pick a target and get the closest profiles in his position group — "
        "similarity is how closely their percentile profiles match, so a 92% "
        "match plays like him, whatever the price."
    )
    ranked = scored.sort_values(RANK, ascending=False)
    labels = {
        idx: (f"{r['Player']} ({r['Team']}) — {r['position_group']}"
              + (" · secondary role" if r.get("group_role") == "secondary" else ""))
        for idx, r in ranked.iterrows()
    }
    target_idx = st.selectbox(
        "Target player", list(labels.keys()), format_func=labels.get,
    )
    target = scored.loc[target_idx]

    import plotly.graph_objects as go  # noqa: F811 — same module as tab 2
    c_info, c_arch = st.columns([1, 1.4])
    with c_info:
        kpi_card("Score", target["Score"])
        kpi_card("Archetype", target["Archetype"] if pd.notna(target["Archetype"]) else "—")
        mv = target["Market value"]
        kpi_card("Market value", f"€{mv/1e6:.1f}M" if mv and mv > 0 else "unknown")
    with c_arch:
        breakdown = archetype_breakdown(scored, target_idx)
        if breakdown:
            items = sorted(breakdown.items(), key=lambda kv: kv[1])
            afig = go.Figure(go.Bar(
                x=[v for _, v in items], y=[k for k, _ in items],
                orientation="h", marker_color=AME_YELLOW,
                text=[f"{v:.0f}" for _, v in items], textposition="outside",
            ))
            afig.update_layout(
                height=60 + 44 * len(items), margin=dict(l=10, r=40, t=24, b=10),
                title="Style profile (bundle percentiles)",
                xaxis=dict(range=[0, 108]),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#EAF0FA"),
            )
            st.plotly_chart(afig, width="stretch")

    similar = find_similar(scored, target_idx, k=10)
    if similar.empty:
        st.info("Not enough players in this position group to compare against.")
    else:
        show = similar[["similarity"] + [c for c in display_columns(similar)
                                         if c != "found_in"]]
        selectable_table(show, key=f"table_similar_{target_idx}",
                         height=40 + 36 * len(show))

        rivals = similar.head(2)["Player"].tolist()
        categories, values = radar_data(
            scored, target["position_group"], [target["Player"], *rivals],
        )
        if len(values) >= 2:
            st.plotly_chart(
                radar_chart(categories, values,
                            title=f"{target['Player']} vs closest matches"),
                width="stretch",
            )

# ── Tab 5: replace from squad (Opta ↔ Wyscout bridge) ────────────────────────
with tab_replace:
    ame_section("SQUAD → MARKET", f"Replace a {AME_TEAM_NAME} player")
    st.caption(
        "Pick a current squad player (Opta season stats) and find his closest "
        "profiles in the uploaded market. Only the metrics both data sources "
        "share are compared — the caption under the results says exactly which."
    )
    squad = load_player_season_stats("Mexico_Liga_MX", DEFAULT_SEASON, AME_TEAM_FOLDER)
    squad = squad[pd.to_numeric(squad["Time Played"], errors="coerce").fillna(0) > 0]
    if squad.empty:
        st.warning(f"No Opta season stats found for {AME_TEAM_NAME} in {DEFAULT_SEASON}.")
    else:
        squad = squad.sort_values("Time Played", ascending=False).reset_index(drop=True)
        r1, r2 = st.columns([2, 1.4])
        sq_idx = r1.selectbox(
            "Squad player", squad.index,
            format_func=lambda i: (f"{squad.loc[i, 'nombre']} — "
                                   f"{squad.loc[i, 'posicion']} "
                                   f"({int(squad.loc[i, 'Time Played'])}′)"),
        )
        sq_row = squad.loc[sq_idx]
        default_group = OPTA_POSITION_DEFAULT_GROUP.get(sq_row["posicion"], "CM")
        groups_avail = sorted(scored["position_group"].unique())
        rep_group = r2.selectbox(
            "Shop in position group", groups_avail,
            index=groups_avail.index(default_group) if default_group in groups_avail else 0,
            format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
            help="Opta only says GK/Defender/Midfielder/Forward — override to shop "
                 "a Defender as a full-back, a Midfielder as a DM, etc.",
        )
        minutes_played = int(sq_row["Time Played"])
        if minutes_played < DEFAULT_MIN_MINUTES:
            st.warning(
                f"⚠️ {sq_row['nombre']} has only {minutes_played}′ this season — "
                "his per-90 profile is noisy; treat this comparison as indicative."
            )

        profile = opta_to_wyscout_profile(sq_row)
        matches, pseudo_pct, pseudo_score, shared = market_comparison(
            scored, profile, rep_group, k=10,
        )
        if matches.empty or pseudo_score is None:
            st.info("No comparable metrics between this player and the uploaded "
                    "market sample for that position group.")
        else:
            b1, b2, b3 = st.columns(3)
            with b1:
                kpi_card("Score in this market", pseudo_score)
            with b2:
                kpi_card("Upgrades found", int(matches["upgrade"].sum()))
            with b3:
                kpi_card("Metrics compared", len(shared))
            st.caption("Compared on: " + ", ".join(shared))

            show = matches[["similarity", "upgrade"]
                           + [c for c in display_columns(matches) if c != "found_in"]]
            selectable_table(show, key=f"table_replace_{sq_idx}_{rep_group}",
                             height=40 + 36 * len(show))

            rivals = matches.head(2)["Player"].tolist()
            categories, values = bridge_radar(
                scored, rep_group, f"{sq_row['nombre']} ({AME_TEAM_NAME})",
                pseudo_pct, rivals,
            )
            if len(categories) >= 3:
                st.plotly_chart(
                    radar_chart(categories, values,
                                title=f"{sq_row['nombre']} vs market (shared metrics only)"),
                    width="stretch",
                )

# ── Tab 6: market opportunities ──────────────────────────────────────────────
with tab_market:
    ame_section("RECRUITMENT", "Where the market is beatable")
    # One row per player here — multi-position players count once, at their
    # best-scoring role.
    market_pool = dedupe_best(scored)
    m1, m2 = st.columns(2)

    with m1:
        st.markdown("**💎 Undervalued** — outperform their price bracket")
        under = (
            market_pool[market_pool["value_index"].notna()]
            .sort_values("value_index", ascending=False).head(15)
        )
        styled_dataframe(
            under[["Player", "Team", "position_group", "Archetype", "Age", "Score",
                   "value_index", "Market value"]],
            height=420,
        )

    with m2:
        st.markdown("**⏳ Contract leverage** — deals expiring within 12 months")
        horizon = pd.Timestamp.now() + pd.DateOffset(months=12)
        expiring = (
            market_pool[market_pool["Contract expires"].notna()
                        & (market_pool["Contract expires"] <= horizon)]
            .sort_values(RANK, ascending=False).head(15)
        )
        styled_dataframe(
            expiring[["Player", "Team", "position_group", "Archetype", "Age", "Score",
                      "Contract expires", "Market value"]],
            height=420,
        )

    st.markdown("**🌱 U23 high performers** — top score among players 23 or younger")
    young = market_pool[market_pool["Age"] <= 23].sort_values(RANK, ascending=False).head(15)
    styled_dataframe(
        young[["Player", "Team", "position_group", "Archetype", "Age", "Score",
               "Minutes played", "Market value", "Contract expires"]],
        height=420,
    )

# ── Tab 7: market analysis (report sections, interactive) ────────────────────
with tab_analysis:
    import plotly.graph_objects as go  # noqa: F811 — also imported in tab 2

    _PLOT_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#EAF0FA"))

    def _dist_fig(labels, counts, title):
        fig = go.Figure(go.Bar(x=labels, y=counts, marker_color=AME_YELLOW,
                               text=counts, textposition="outside"))
        fig.update_layout(title=title, height=280,
                          margin=dict(l=10, r=10, t=40, b=10),
                          yaxis_title="Players", **_PLOT_LAYOUT)
        return fig

    def _highlight_scatter(df_all, top, xcol, ycol, title):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_all[xcol], y=df_all[ycol], mode="markers", name="Sample",
            marker=dict(size=6, color=AME_BLUE, opacity=0.45),
            text=df_all["Player"] + " (" + df_all["Team"].fillna("?") + ")",
            hoverinfo="text+x+y",
        ))
        fig.add_trace(go.Scatter(
            x=top[xcol], y=top[ycol], mode="markers+text", name="Highlighted",
            marker=dict(size=11, color=AME_YELLOW),
            text=top["Player"], textposition="top center",
            textfont=dict(size=9, color="#EAF0FA"),
        ))
        fig.update_layout(
            title=title, height=460, showlegend=False,
            xaxis_title=METRIC_ES.get(xcol, xcol),
            yaxis_title=METRIC_ES.get(ycol, ycol),
            margin=dict(l=10, r=10, t=40, b=10), **_PLOT_LAYOUT)
        return fig

    ame_section("REPORT VIEW", "Market analysis")
    ag = st.selectbox(
        "Position group", sorted(scored["position_group"].unique()),
        format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
        key="analysis_group",
    )
    agdf = scored[scored["position_group"] == ag]
    universe = pooled[pooled["position_groups"].map(
        lambda gs: ag in gs if isinstance(gs, list) else False)]

    # 1 — Universe & data quality
    u1, u2, u3, u4 = st.columns(4)
    with u1:
        kpi_card(f"{ag} in universe", len(universe))
    with u2:
        kpi_card("In rankings (≥ min. minutes)",
                 len(agdf[["Player", "Team"]].drop_duplicates()))
    with u3:
        kpi_card("≥1,500 minutes", int((universe["Minutes played"] >= 1500).sum()))
    with u4:
        kpi_card("Secondary role", int((agdf["group_role"] == "secondary").sum()))

    issues = {k: v for k, v in quality_issues(pooled).items() if v > 0}
    if issues:
        items = sorted(issues.items(), key=lambda kv: kv[1])
        qfig = go.Figure(go.Bar(
            x=[v for _, v in items], y=[k for k, _ in items], orientation="h",
            marker_color=AME_BLUE, text=[v for _, v in items],
            textposition="outside"))
        qfig.update_layout(title="Data quality issues (whole upload)",
                           height=90 + 34 * len(items),
                           margin=dict(l=10, r=30, t=40, b=10), **_PLOT_LAYOUT)
        st.plotly_chart(qfig, width="stretch")
        st.caption(
            "Market value €0 = missing, not a cheap deal. Players failing these "
            "checks need a manual look before any shortlist decision."
        )

    # 2 — Distributions
    d1, d2, d3 = st.columns(3)
    age_l, age_c = bin_counts(universe["Age"].dropna(), [0, 21, 24, 28, 32, 99],
                              ["≤21", "22-24", "25-28", "29-32", "33+"])
    d1.plotly_chart(_dist_fig(age_l, age_c, "Age distribution"), width="stretch")
    min_l, min_c = bin_counts(universe["Minutes played"].fillna(0),
                              [-1, 449, 899, 1499, 2499, 99999],
                              ["<450", "450-899", "900-1499", "1500-2499", "2500+"])
    d2.plotly_chart(_dist_fig(min_l, min_c, "Minutes distribution"), width="stretch")
    mv_l, mv_c = bin_counts(universe["Market value"].fillna(0),
                            [-1, 0, 1e6 - 1, 5e6, 15e6, 30e6, 9e9],
                            ["0/n.d.", "<€1m", "€1-5m", "€5-15m", "€15-30m", "€30m+"])
    d3.plotly_chart(_dist_fig(mv_l, mv_c, "Market value distribution"), width="stretch")

    # 3 — Benchmarks
    st.markdown("**Benchmarks (ranked sample)** — P75 as a positive-alert "
                "threshold, median as the baseline.")
    bench = []
    for col, _w, _inv in ROLE_METRICS.get(ag, []):
        if col in agdf.columns and agdf[col].notna().any():
            s = agdf[col].dropna()
            bench.append({"Métrica": METRIC_ES.get(col, col),
                          "P25": round(s.quantile(0.25), 2),
                          "Mediana": round(s.median(), 2),
                          "P75": round(s.quantile(0.75), 2)})
    styled_dataframe(pd.DataFrame(bench), height=40 + 36 * len(bench))

    # 4 — Profile scatter + ranking with auto-comments
    prof_options = [a for a, _cols in ARCHETYPES.get(ag, [])
                    if f"arch: {a}" in agdf.columns]
    if prof_options:
        sel_prof = st.selectbox(
            "Style profile", prof_options,
            format_func=lambda a: ARCHETYPE_ES.get(a, a), key="analysis_prof")
        arch_col = f"arch: {sel_prof}"
        bundle_cols = [c for c in dict(ARCHETYPES[ag])[sel_prof]
                       if c in agdf.columns]
        if len(bundle_cols) >= 2:
            top8 = agdf.sort_values(arch_col, ascending=False).head(8)
            st.plotly_chart(
                _highlight_scatter(
                    agdf, top8, bundle_cols[0], bundle_cols[1],
                    f"Perfil {ARCHETYPE_ES.get(sel_prof, sel_prof)} — destacados"),
                width="stretch")
            gdf_cols = list(agdf.columns)
            top6 = agdf.sort_values(arch_col, ascending=False).head(6)
            rows = [{"Player": r["Player"], "Team": r["Team"],
                     "Age": int(r["Age"]) if pd.notna(r["Age"]) else None,
                     "Min.": int(r["Minutes played"]),
                     "Market value": r["Market value"],
                     "Profile score": round(r[arch_col], 1),
                     "Lectura": player_comment(r, gdf_cols)}
                    for _, r in top6.iterrows()]
            styled_dataframe(pd.DataFrame(rows), height=40 + 40 * len(rows))

    # 5 — Shortlist scatters
    s1, s2 = st.columns(2)
    axes = scatter_axes(ag, list(agdf.columns))
    young_all = agdf[agdf["Age"] <= 23]
    if axes and len(young_all) >= 5:
        xcol, ycol = axes
        topy = young_all.sort_values(RANK, ascending=False).head(10)
        s1.plotly_chart(
            _highlight_scatter(agdf, topy, xcol, ycol, "Shortlist U23"),
            width="stretch")
    with_value = agdf[agdf["Market value"] > 0].copy()
    if len(with_value) >= 5:
        with_value["Valor €m"] = with_value["Market value"] / 1e6
        topv = (with_value[with_value["Age"] <= 25]
                .sort_values("value_index", ascending=False).head(10))
        vfig = go.Figure()
        vfig.add_trace(go.Scatter(
            x=with_value["Valor €m"], y=with_value[RANK], mode="markers",
            marker=dict(size=6, color=AME_BLUE, opacity=0.45),
            text=with_value["Player"], hoverinfo="text+x+y", name="Sample"))
        vfig.add_trace(go.Scatter(
            x=topv["Market value"] / 1e6, y=topv[RANK], mode="markers+text",
            marker=dict(size=11, color=AME_YELLOW), text=topv["Player"],
            textposition="top center", textfont=dict(size=9, color="#EAF0FA"),
            name="Value picks"))
        vfig.update_layout(title="U25 value — score vs price", height=460,
                           showlegend=False, xaxis_title="Market value (€m)",
                           yaxis_title="Composite score",
                           margin=dict(l=10, r=10, t=40, b=10), **_PLOT_LAYOUT)
        s2.plotly_chart(vfig, width="stretch")

# ── Tab 8: shortlist + export ────────────────────────────────────────────────
with tab_short:
    ame_section("DELIVERABLE", "Shortlist for the committee")
    if not st.session_state.shortlist:
        st.info(
            "Empty for now — select rows in the **Global ranking**, **Similar "
            "players** or **Replace from squad** tables and hit "
            "'⭐ Add selected to shortlist'."
        )
    else:
        short_df = pd.DataFrame(list(st.session_state.shortlist.values()))
        styled_dataframe(short_df, height=40 + 36 * len(short_df))

        rm = st.multiselect(
            "Remove from shortlist", list(st.session_state.shortlist.keys()),
            format_func=lambda k: k.replace("|", " — "),
        )
        c1, c2, c3 = st.columns([1, 1, 2])
        if rm and c1.button("Remove selected"):
            for k in rm:
                st.session_state.shortlist.pop(k, None)
            st.rerun()
        if c2.button("Clear all"):
            st.session_state.shortlist = {}
            st.rerun()

        # Excel is the format that actually travels to a recruitment committee.
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            short_df.to_excel(xw, sheet_name="Shortlist", index=False)
            _clean_for_display(
                scored[display_columns(scored)]
            ).to_excel(xw, sheet_name="Full filtered pool", index=False)
        c3.download_button(
            "📥 Download Excel (shortlist + full pool)",
            data=buf.getvalue(),
            file_name="scouting_shortlist.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── PDF scouting report ──────────────────────────────────────────────
    st.markdown("---")
    ame_section("REPORT", "PDF scouting report")
    st.caption(
        "Committee-format PDF for one position group: universe & data quality, "
        "benchmarks, rankings per profile, young-talent shortlists and "
        "highlighted scatters. Shortlisted players are marked with ★."
    )
    rep_group = st.selectbox(
        "Report position group", sorted(scored["position_group"].unique()),
        format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
        key="report_group",
    )
    if st.button("📄 Generate PDF report"):
        with st.spinner("Building report (charts + tables)…"):
            try:
                pdf_bytes = build_scouting_report(
                    pooled, scored, rep_group, min_minutes,
                    starred=set(st.session_state.shortlist.keys()),
                )
                st.session_state["scouting_report"] = (rep_group, pdf_bytes)
            except ValueError as exc:
                st.warning(str(exc))
    if "scouting_report" in st.session_state:
        saved_group, pdf_bytes = st.session_state["scouting_report"]
        st.download_button(
            f"📥 Download report — {saved_group} ({len(pdf_bytes) / 1e6:.1f} MB)",
            data=pdf_bytes,
            file_name=f"Reporte_Scouting_{saved_group}.pdf",
            mime="application/pdf",
        )
