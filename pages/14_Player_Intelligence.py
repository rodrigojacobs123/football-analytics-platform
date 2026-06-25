"""Player Intelligence — tactical archetypes, play-style profiles,
and archetype-compatibility analysis for every player in the league.

New archetype system (from processing/archetypes.py):
  • 5 Forward archetypes  (Clinical Finisher, Press Machine, Target Man,
                           Wide Dribbler, Shadow Striker)
  • 5 Midfielder archetypes (Deep Playmaker, Box-to-Box Engine, Press Trigger,
                              Half-Space Connector, Recycler)
  • 5 Defender archetypes  (Ball-Playing CB, Aerial Colossus, Aggressive Marker,
                             Carrying Fullback, Press-Resistant CB)
  • 3 GK archetypes        (Sweeper Keeper, Pure Shot Stopper, Distribution GK)

Each player also gets a season-long stat timeline and an archetype-
compatibility score showing how they perform alongside each squad archetype.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.sidebar import render_sidebar
from data.loader import load_all_player_season_stats
from processing.archetypes import (
    compute_per90, assign_archetypes, compute_archetype_compatibility,
    ARCHETYPES, archetypes_for_position, MIN_MINUTES,
)
from viz.kpi_cards import page_header, section_header, kpi_row
from viz.theme import apply_theme
from config import AME_YELLOW, AME_BLUE, AME_DARK_BG, AME_TEAM_NAME

apply_theme()


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R,G,B' string for rgba() CSS."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _html(block: str) -> str:
    """Flatten a multi-line HTML f-string for ``st.markdown(unsafe_allow_html=True)``.

    Streamlit renders markdown, and markdown treats any line indented by ≥ 4
    spaces as a *code block* — so HTML written with Python indentation inside a
    triple-quoted string leaks to the page as literal ``<div>`` text. Stripping
    the leading whitespace from every line removes that trigger while leaving the
    HTML semantically identical (inter-tag whitespace is insignificant).
    """
    return "".join(line.strip() for line in block.splitlines())


league, season = render_sidebar()
page_header("Player Intelligence", subtitle=f"Tactical Archetypes · {season}")

# NOTE: a per-tournament (Apertura/Clausura) selector used to live here, but
# `load_all_player_season_stats` only exposes *season-aggregate* player stats —
# there is no stage-level split in the team CSVs — so the control filtered
# nothing. It was removed rather than left as a dead widget. If stage-level
# player stats are added to the loader later, reinstate the radio and pass the
# chosen stage through to the load call.

# ── Load & classify ───────────────────────────────────────────────────────────
with st.spinner("Computing per-90 stats and classifying archetypes…"):
    raw_df = load_all_player_season_stats(league, season)
    if raw_df.empty:
        st.error("No player stats available.")
        st.stop()

    # Compute per-90 signals
    p90_df = compute_per90(raw_df)

    # Assign archetypes across all positions
    arch_df = assign_archetypes(p90_df)

arch_known = arch_df[arch_df["archetype"] != "Undefined"]


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_league, tab_player, tab_compat = st.tabs([
    "🗺️ League Archetype Map",
    "🧬 Player Profile",
    "🤝 Archetype Compatibility",
])


# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — League-wide archetype distribution
# ═══════════════════════════════════════════════════════════════════════════
with tab_league:
    section_header("League Archetype Distribution")
    st.caption(
        "Every player classified by **how they play**, not how good they are. "
        f"Only players with ≥ {MIN_MINUTES} minutes are shown."
    )

    # ── Filters ──────────────────────────────────────────────────────────
    col_pos, col_team, col_arch = st.columns(3)
    with col_pos:
        pos_filter = st.multiselect(
            "Position", arch_known["posicion"].dropna().unique().tolist(),
            key="intel_pos_filter"
        )
    with col_team:
        team_filter = st.multiselect(
            "Team", sorted(arch_known["equipo"].dropna().unique().tolist()),
            key="intel_team_filter"
        )
    with col_arch:
        arch_filter = st.multiselect(
            "Archetype", sorted(arch_known["archetype"].unique().tolist()),
            key="intel_arch_filter"
        )

    disp = arch_known.copy()
    if pos_filter:
        disp = disp[disp["posicion"].isin(pos_filter)]
    if team_filter:
        disp = disp[disp["equipo"].isin(team_filter)]
    if arch_filter:
        disp = disp[disp["archetype"].isin(arch_filter)]

    st.markdown(f"**{len(disp)} players** match current filters")

    # ── Archetype frequency chart ─────────────────────────────────────────
    arch_counts = (
        arch_known.groupby(["archetype", "arch_color", "arch_icon"])
        .size().reset_index(name="count")
        .sort_values("count", ascending=True)
    )
    fig_freq = go.Figure(go.Bar(
        y=[f"{r['arch_icon']} {r['archetype']}" for _, r in arch_counts.iterrows()],
        x=arch_counts["count"],
        orientation="h",
        marker=dict(color=arch_counts["arch_color"].tolist()),
        text=arch_counts["count"],
        textposition="outside",
        textfont=dict(color="#FAFAFA"),
    ))
    fig_freq.update_layout(
        template="ame_dark",
        title="Players per Archetype (league-wide)",
        height=max(300, len(arch_counts) * 30 + 60),
        margin=dict(l=10, r=50, t=40, b=20),
        xaxis_title="Player Count",
    )
    st.plotly_chart(fig_freq, width="stretch")

    # ── Scatter: two key per-90 metrics coloured by archetype ────────────
    st.markdown("#### Archetype Scatter — Pressing vs Creation")
    if "recoveries_p90" in disp.columns and "key_passes_p90" in disp.columns:
        fig_sc = go.Figure()
        for arch_name in disp["archetype"].unique():
            sub = disp[disp["archetype"] == arch_name]
            color = sub["arch_color"].iloc[0] if "arch_color" in sub else "#888"
            icon  = sub["arch_icon"].iloc[0]  if "arch_icon"  in sub else "❓"
            fig_sc.add_trace(go.Scatter(
                x=sub["recoveries_p90"],
                y=sub["key_passes_p90"],
                mode="markers",
                marker=dict(color=color, size=9,
                            line=dict(color="#111", width=0.5)),
                name=f"{icon} {arch_name}",
                text=sub.apply(
                    lambda r: f"{r.get('nombre','?')}<br>{r.get('equipo','')}"
                              f"<br>Recoveries: {r['recoveries_p90']:.2f}"
                              f"<br>Key passes: {r['key_passes_p90']:.2f}",
                    axis=1
                ),
                hovertemplate="%{text}<extra></extra>",
            ))
        fig_sc.update_layout(
            template="ame_dark",
            title="Pressing (Recoveries/90) vs Creation (Key Passes/90)",
            xaxis_title="Ball Recoveries per 90",
            yaxis_title="Key Passes per 90",
            height=480,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(size=10)),
        )
        st.plotly_chart(fig_sc, width="stretch")

    # ── Player table ──────────────────────────────────────────────────────
    show_cols = ["nombre", "posicion", "equipo", "arch_icon", "archetype",
                 "arch_desc", "goals_p90", "recoveries_p90",
                 "key_passes_p90", "tackles_won_p90", "aerials_won_p90"]
    show_cols = [c for c in show_cols if c in disp.columns]
    rename = {
        "nombre": "Player", "posicion": "Pos", "equipo": "Team",
        "arch_icon": "", "archetype": "Archetype", "arch_desc": "Description",
        "goals_p90": "Goals/90", "recoveries_p90": "Rec/90",
        "key_passes_p90": "KP/90", "tackles_won_p90": "Tkl/90",
        "aerials_won_p90": "Aer/90",
    }
    table = disp[show_cols].rename(columns=rename).sort_values("Player")
    st.dataframe(table, width="stretch", hide_index=True, height=400)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — Individual player profile
# ═══════════════════════════════════════════════════════════════════════════
with tab_player:
    section_header("Player Profile")

    # ── Player picker ─────────────────────────────────────────────────────
    # Order players by minutes played (desc) so the default landing player is a
    # *regular* with a real archetype, not the alphabetically-first squad member
    # (who is often a sub below MIN_MINUTES and shows "Undefined" — the original
    # "broken first impression" bug). Each option is labelled with its archetype
    # icon + minutes so the user can see at a glance who is actually classified.
    _mins_col = "Time Played" if "Time Played" in arch_df.columns else None

    def _ordered_names(frame: pd.DataFrame) -> list[str]:
        f = frame.dropna(subset=["nombre"]).copy()
        if _mins_col:
            f = f.sort_values(_mins_col, ascending=False)
        # de-dupe preserving the minutes order
        return list(dict.fromkeys(f["nombre"].tolist()))

    # name -> "icon Archetype · 1,350′" label for the dropdown
    _label_lookup: dict[str, str] = {}
    for _, _r in arch_df.dropna(subset=["nombre"]).iterrows():
        if _r["nombre"] in _label_lookup:
            continue
        _icon = _r.get("arch_icon", "❓")
        _arch = _r.get("archetype", "Undefined")
        _raw_mins = _r.get(_mins_col, 0) if _mins_col else 0
        _mins = int(_raw_mins) if pd.notna(_raw_mins) else 0
        _tag = f"{_icon} {_arch}" if _arch != "Undefined" else "❓ Unclassified"
        _label_lookup[_r["nombre"]] = (
            f"{_r['nombre']}  —  {_tag}" + (f" · {_mins:,}′" if _mins else "")
        )

    def _fmt_player(name: str) -> str:
        return _label_lookup.get(name, name)

    cf_players = arch_df[arch_df["equipo"].str.contains("América", na=False)]
    all_players = _ordered_names(arch_df)
    cf_names = _ordered_names(cf_players)

    scope_col, player_col = st.columns([1, 2])
    with scope_col:
        # Only offer the "CF América" scope when this competition actually has
        # América players. Most leagues (MLS, USL, most CONCACAF seasons) don't,
        # and defaulting to an empty CF list left the picker empty — which then
        # tripped st.stop() below and blanked the whole page, including the
        # Compatibility tab. Fall back to the full league when there's no squad.
        scope_options = ["CF América", "All League"] if cf_names else ["All League"]
        scope = st.radio("Show", scope_options, horizontal=True,
                         key="intel_player_scope")
        classified_only = st.checkbox(
            f"Classified only (≥ {MIN_MINUTES} min)", value=True,
            key="intel_classified_only",
            help="Hide players below the minutes threshold who have no archetype.",
        )
    with player_col:
        player_list = cf_names if (scope == "CF América" and cf_names) else all_players
        if classified_only:
            _classified = set(
                arch_df.loc[arch_df["archetype"] != "Undefined", "nombre"]
            )
            _filtered = [n for n in player_list if n in _classified]
            player_list = _filtered or player_list  # never blank the picker
        selected_player = st.selectbox("Select Player", player_list,
                                       format_func=_fmt_player,
                                       key="intel_player_sel")

    # With the scope/player_list fix above, player_list is never empty when the
    # competition has data, so selected_player is always a real player and this
    # guard no longer fires for non-América leagues (the original bug). It stays
    # only as a backstop for a genuinely empty competition.
    player_rows = arch_df[arch_df["nombre"] == selected_player]
    if selected_player is None or player_rows.empty:
        st.info("No players available to profile for this competition.")
        st.stop()

    p = player_rows.iloc[0]
    pos = p.get("posicion", "")
    team = p.get("equipo", "")
    arch = p.get("archetype", "Undefined")
    arch_icon = p.get("arch_icon", "❓")
    arch_color = p.get("arch_color", "#555")
    arch_desc = p.get("arch_desc", "")
    _raw_minutes = p.get("Time Played", 0)
    minutes = float(_raw_minutes) if pd.notna(_raw_minutes) else 0.0

    # ── Profile header ────────────────────────────────────────────────────
    st.markdown(_html(f"""
    <div style="background:#1A1A2E;border-radius:10px;padding:1.2rem 1.5rem;
                margin-bottom:1rem;border-left:5px solid {arch_color};">
        <div style="display:flex;align-items:center;gap:1rem;">
            <span style="font-size:3rem;">{arch_icon}</span>
            <div>
                <h2 style="margin:0;color:white;font-size:1.6rem;">{selected_player}</h2>
                <p style="margin:0.2rem 0 0;color:#aaa;">
                    {pos} · {team} · {int(minutes):,} min played
                </p>
                <div style="margin-top:0.5rem;">
                    <span style="color:{arch_color};font-weight:700;font-size:1.1rem;">
                        {arch_icon} {arch}
                    </span>
                    <span style="color:#888;font-size:0.85rem;margin-left:0.8rem;">
                        — {arch_desc}
                    </span>
                </div>
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    # Low-sample / unclassified caveat — shown instead of letting the radar and
    # signal chips render as confident-looking noise for a player who hasn't met
    # the minutes threshold (the case that made the page look "broken").
    if arch == "Undefined" or minutes < MIN_MINUTES:
        st.warning(
            f"**{selected_player}** has **{int(minutes):,} min** — below the "
            f"**{MIN_MINUTES} min** threshold needed for a reliable archetype. "
            "The profile below is shown for reference only and is statistically "
            "noisy at this sample size. Pick a higher-minutes player (or untick "
            "*Classified only*) to compare like-for-like.",
            icon="⚠️",
        )

    # ── Key per-90 radar (position-specific signals) ──────────────────────
    pos_arch_defs = archetypes_for_position(pos)
    all_signals_for_pos = set()
    for a in pos_arch_defs:
        all_signals_for_pos.update(a["signals"].keys())

    radar_signals = sorted(all_signals_for_pos)[:8]  # cap at 8 axes

    if radar_signals:
        # Compute league percentile context
        pos_group = arch_df[arch_df["posicion"] == pos]

        radar_vals = []
        radar_labels = []
        for sig in radar_signals:
            # Prefer the percentile already computed at classification time
            # (`{sig}_pct`, ranked within position) so the radar agrees with the
            # signal-breakdown chips below. Fall back to an inline rank only if
            # the precomputed column is missing.
            pct_col = f"{sig}_pct"
            if pct_col in p.index and pd.notna(p.get(pct_col)):
                pct = float(p.get(pct_col, 50))
            elif sig in pos_group.columns:
                val = float(p.get(sig, 0))
                league_vals = pos_group[sig].dropna()
                pct = ((league_vals <= val).sum() / len(league_vals) * 100
                       if len(league_vals) > 0 else 50)
            else:
                continue
            radar_vals.append(round(pct, 1))
            radar_labels.append(sig.replace("_p90", "").replace("_", " ").title())

        if radar_vals:
            fig_radar = go.Figure(go.Scatterpolar(
                r=radar_vals + [radar_vals[0]],
                theta=radar_labels + [radar_labels[0]],
                fill="toself",
                fillcolor=f"rgba({_hex_to_rgb(arch_color)},0.2)",
                line=dict(color=arch_color, width=2),
                name=arch,
            ))

            # Add league average (50th percentile reference)
            fig_radar.add_trace(go.Scatterpolar(
                r=[50] * (len(radar_labels) + 1),
                theta=radar_labels + [radar_labels[0]],
                mode="lines",
                line=dict(color="#555", width=1, dash="dash"),
                name="League avg",
            ))

            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(range=[0, 100], showticklabels=False,
                                    gridcolor="#2A2A38"),
                    angularaxis=dict(gridcolor="#2A2A38"),
                    bgcolor=AME_DARK_BG,
                ),
                paper_bgcolor=AME_DARK_BG,
                template="ame_dark",
                showlegend=True,
                height=400,
                title=f"{selected_player} — Percentile Profile vs {pos}s",
                legend=dict(orientation="h", yanchor="bottom", y=1.05),
            )
            st.plotly_chart(fig_radar, width="stretch")

    # ── Archetype signal breakdown ─────────────────────────────────────────
    st.markdown("#### Signal Breakdown — which archetype thresholds you meet")

    pos_archetypes = archetypes_for_position(pos)
    pos_group = arch_df[arch_df["posicion"] == pos]

    for a in sorted(pos_archetypes, key=lambda x: x["priority"]):
        is_match = a["name"] == arch
        border = f"3px solid {a['color']}" if is_match else "1px solid #333"
        bg = "#1A1A2E" if is_match else "#111118"

        chips_html = ""
        for sig, (lo, hi) in a["signals"].items():
            pct_col = f"{sig}_pct"
            sig_val = float(p.get(pct_col, 50))
            meets = (lo is None or sig_val >= lo) and (hi is None or sig_val <= hi)
            chip_color = a["color"] if meets else "#555"
            lo_label = f"≥{lo}th" if lo else ""
            hi_label = f"≤{hi}th" if hi else ""
            threshold = lo_label + hi_label
            chips_html += (
                f'<span style="display:inline-block;padding:2px 8px;margin:2px;'
                f'background:{chip_color}33;border:1px solid {chip_color};'
                f'border-radius:12px;color:{"white" if meets else "#666"};'
                f'font-size:0.72rem;">'
                f'{sig.replace("_p90","").replace("_"," ").title()} '
                f'<b>{sig_val:.0f}th</b> {threshold}</span>'
            )

        match_badge = (
            f'<span style="background:{a["color"]};color:white;padding:2px 8px;'
            f'border-radius:4px;font-size:0.75rem;font-weight:700;">✓ MATCH</span>'
            if is_match else ""
        )

        st.markdown(_html(f"""
        <div style="background:{bg};border:{border};border-radius:8px;
                    padding:0.7rem 1rem;margin:0.4rem 0;">
            <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:0.4rem;">
                <span style="font-size:1.2rem;">{a['icon']}</span>
                <span style="color:{a['color']};font-weight:700;">{a['name']}</span>
                {match_badge}
            </div>
            <div style="color:#888;font-size:0.8rem;margin-bottom:0.4rem;">
                {a['description']}
            </div>
            <div>{chips_html}</div>
        </div>
        """), unsafe_allow_html=True)

    # ── Raw stat snapshot ──────────────────────────────────────────────────
    with st.expander("Raw per-90 stats"):
        stat_rows = []
        for sig, col in [
            ("Goals", "goals_p90"), ("Shots", "shots_p90"),
            ("Key Passes", "key_passes_p90"), ("Dribbles", "dribbles_p90"),
            ("Recoveries", "recoveries_p90"), ("Tackles Won", "tackles_won_p90"),
            ("Interceptions", "interceptions_p90"), ("Clearances", "clearances_p90"),
            ("Aerials Won", "aerials_won_p90"), ("Prog. Carries", "prog_carries_p90"),
            ("Total Passes", "passes_p90"), ("Long Passes", "long_passes_p90"),
            ("Box Touches", "box_touches_p90"),
        ]:
            if col in p.index:
                stat_rows.append({"Stat": sig, "Per 90": round(float(p.get(col, 0)), 2)})
        st.dataframe(pd.DataFrame(stat_rows), width="stretch", hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — Archetype compatibility
# ═══════════════════════════════════════════════════════════════════════════
with tab_compat:
    section_header("Archetype Compatibility")
    st.caption(
        "For the selected player, see the archetype makeup of their squad "
        "and how their key metric compares to the league average in that context. "
        "A future version will use per-match lineup data for exact context analysis."
    )

    # Re-use player selection from tab 2
    p2_rows = arch_df[arch_df["nombre"] == selected_player]
    if p2_rows.empty:
        st.info("Select a player in the Player Profile tab first.")
    else:
        p2 = p2_rows.iloc[0]
        player_id = str(p2.get("id", ""))
        p2_team = p2.get("equipo", "")

        squad = arch_df[arch_df["equipo"] == p2_team].copy()

        compat_df = compute_archetype_compatibility(player_id, squad, arch_df)

        if not compat_df.empty:
            st.markdown(f"#### {selected_player}'s team archetype mix")

            # Show archetype makeup of squad
            fig_squad = go.Figure()
            for _, row in compat_df.iterrows():
                fig_squad.add_trace(go.Bar(
                    x=[f"{row['arch_icon']} {row['archetype']}"],
                    y=[row["teammate_count"]],
                    marker_color=row["arch_color"],
                    text=[str(row["teammate_count"])],
                    textposition="auto",
                    name=row["archetype"],
                    showlegend=False,
                    hovertext=f"{row['archetype']}: {row['teammate_count']} teammates",
                    hovertemplate="%{hovertext}<extra></extra>",
                ))
            fig_squad.update_layout(
                template="ame_dark",
                title=f"{p2_team} — Teammate Archetype Distribution",
                yaxis_title="Players",
                height=320,
                bargap=0.3,
            )
            st.plotly_chart(fig_squad, width="stretch")

            # Player's metric vs league baseline
            metric_label = compat_df["metric_label"].iloc[0]
            player_val = compat_df["player_metric"].iloc[0]
            league_val = compat_df["league_avg"].iloc[0]
            delta = player_val - league_val
            delta_color = "#4CAF50" if delta >= 0 else AME_YELLOW
            delta_arrow = "↑" if delta >= 0 else "↓"

            st.markdown(_html(f"""
            <div style="background:#1A1A2E;border-radius:8px;padding:1rem 1.2rem;
                        margin:0.8rem 0;border-left:4px solid {delta_color};">
                <div style="color:#aaa;font-size:0.8rem;text-transform:uppercase;
                            letter-spacing:0.1em;">{metric_label} per 90</div>
                <div style="display:flex;gap:2rem;margin-top:0.4rem;align-items:center;">
                    <div>
                        <span style="color:white;font-size:2rem;font-weight:700;">
                            {player_val:.2f}
                        </span>
                        <span style="color:#aaa;font-size:0.9rem;margin-left:4px;">
                            {selected_player}
                        </span>
                    </div>
                    <div style="color:#555;font-size:1.5rem;">vs</div>
                    <div>
                        <span style="color:#888;font-size:1.4rem;">{league_val:.2f}</span>
                        <span style="color:#666;font-size:0.85rem;margin-left:4px;">
                            league avg ({pos})
                        </span>
                    </div>
                    <div style="color:{delta_color};font-size:1.6rem;font-weight:700;">
                        {delta_arrow} {abs(delta):.2f}
                    </div>
                </div>
            </div>
            """), unsafe_allow_html=True)

            # Full compatibility table
            st.markdown("#### Full squad archetype breakdown")
            show_compat = compat_df[[
                "arch_icon", "archetype", "teammate_count",
                "player_metric", "league_avg", "delta_vs_league"
            ]].rename(columns={
                "arch_icon": "", "archetype": "Archetype",
                "teammate_count": "# Teammates",
                "player_metric": f"{metric_label}/90",
                "league_avg": "League Avg",
                "delta_vs_league": "Δ vs League",
            })
            st.dataframe(show_compat, width="stretch", hide_index=True)

            # Archetype catalogue for this position
            st.markdown(f"---")
            st.markdown(f"#### All {pos} Archetypes — What they mean on the pitch")
            arch_list = archetypes_for_position(pos)
            cols = st.columns(2)
            for i, a in enumerate(arch_list):
                with cols[i % 2]:
                    st.markdown(_html(f"""
                    <div style="background:#1A1A2E;border-left:4px solid {a['color']};
                                border-radius:6px;padding:0.7rem 1rem;margin:0.3rem 0;">
                        <span style="font-size:1.2rem;">{a['icon']}</span>
                        <span style="color:{a['color']};font-weight:700;margin-left:0.4rem;">
                            {a['name']}
                        </span>
                        <br>
                        <span style="color:#888;font-size:0.82rem;">{a['description']}</span>
                    </div>
                    """), unsafe_allow_html=True)
        else:
            st.info("Compatibility data not available for this player.")


