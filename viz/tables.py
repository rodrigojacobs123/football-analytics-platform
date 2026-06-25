from __future__ import annotations
"""Styled DataFrame renderers for league tables and data displays."""

import pandas as pd
import streamlit as st
from config import AME_YELLOW, AME_TEAM_NAME, AME_DARK_BG


def styled_league_table(
    df: pd.DataFrame,
    highlight_team: str = AME_TEAM_NAME,
    league: str = "",
) -> None:
    """Render a league table with the specified team highlighted.

    Qualification zones are drawn based on competition format:
    - Liga MX: top 8 = Liguilla (green), 9-12 = Repechaje (amber)
    - Other leagues: top 4 = Champions League (blue), 5-6 = Europa (orange), 18 = relegation (red)
    """
    if df.empty:
        st.warning("No standings data available.")
        return

    display_cols = ["rank", "team_name", "played", "won", "drawn", "lost",
                    "gf", "ga", "gd", "points"]
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df[available_cols].copy()

    col_names = {
        "rank": "Pos", "team_name": "Team", "played": "P", "won": "W",
        "drawn": "D", "lost": "L", "gf": "GF", "ga": "GA",
        "gd": "GD", "points": "Pts",
    }
    display_df = display_df.rename(columns=col_names)

    is_liga_mx = "liga_mx" in league.lower() or "mexico_liga" in league.lower()
    total_teams = len(display_df)

    def highlight_row(row):
        styles = []
        pos = row.get("Pos", 999)
        team = row.get("Team", "")
        is_highlighted = team == highlight_team

        base_bg = ""
        if is_liga_mx:
            if pos <= 8:
                base_bg = "background-color: #00441B22;"   # dark green — Liguilla direct
            elif pos <= 12:
                base_bg = "background-color: #F57F1722;"   # amber — Repechaje
        else:
            if pos <= 4:
                base_bg = "background-color: #1A3A6B33;"   # blue — Champions League
            elif pos <= 6:
                base_bg = "background-color: #FF6B3533;"   # orange — Europa League
            elif pos >= total_teams - 2 and total_teams > 10:
                base_bg = "background-color: #B7000022;"   # red — Relegation

        if is_highlighted:
            return [f"background-color: {AME_YELLOW}44; font-weight: bold"] * len(row)

        return [base_bg] * len(row)

    styled = display_df.style.apply(highlight_row, axis=1)
    styled = styled.set_properties(**{"text-align": "center"})
    if "Team" in display_df.columns:
        styled = styled.set_properties(subset=["Team"], **{"text-align": "left"})

    # Legend below table
    st.dataframe(styled, width="stretch", hide_index=True, height=740)

    if is_liga_mx:
        st.markdown(
            "<span style='font-size:0.72rem;color:#888;'>"
            "🟩 Liguilla (direct) — Top 8 &nbsp;|&nbsp; "
            "🟧 Repechaje — 9th–12th &nbsp;|&nbsp; "
            "⬛ Eliminated — 13th+"
            "</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span style='font-size:0.72rem;color:#888;'>"
            "🟦 Champions League &nbsp;|&nbsp; "
            "🟧 Europa League &nbsp;|&nbsp; "
            "🟥 Relegation"
            "</span>",
            unsafe_allow_html=True,
        )


def game_state_table(df: pd.DataFrame, team_name: str = "",
                     min_matches: int = 3) -> None:
    """Render a Losing / Level / Winning attacking-output split.

    ``df`` is the output of ``processing.game_state.compute_season_game_state``
    (columns ``label, matches, minutes, shots, xg, xt, xg_per90, xt_per90``).
    States observed in fewer than ``min_matches`` matches are dimmed and tagged
    "low n" — early-season game-state buckets are thin and shouldn't be read as
    signal (respects ``MIN_MATCHES_FOR_PREDICTION``).
    """
    if df is None or df.empty:
        st.info(f"No game-state data for {team_name}." if team_name
                else "No game-state data.")
        return

    has_n = "matches" in df.columns
    disp = pd.DataFrame({
        "State": df["label"],
        "Matches": df["matches"] if has_n else "—",
        "Min": df["minutes"].round(0).astype(int),
        "Shots": df["shots"],
        "xG": df["xg"].round(2),
        "xG/90": df["xg_per90"].round(2),
        "xT": df["xt"].round(2),
        "xT/90": df["xt_per90"].round(2),
    })

    low = df["matches"] < min_matches if has_n else pd.Series(False, index=df.index)
    if low.any():
        disp.loc[low.values, "State"] = disp.loc[low.values, "State"] + " ⚠︎"

    def _dim_low(row):
        is_low = low.iloc[row.name] if has_n else False
        return ["color:#666" if is_low else ""] * len(row)

    styler = disp.style.apply(_dim_low, axis=1).format(precision=2)
    if team_name:
        st.markdown(f"**{team_name}**")
    st.dataframe(styler, width="stretch", hide_index=True)
    if has_n and low.any():
        st.caption(f"⚠︎ = fewer than {min_matches} matches in this state — "
                   "treat as low-sample, not signal.")


def styled_dataframe(df: pd.DataFrame, height: int = 400, **kwargs) -> None:
    """Render a generic styled DataFrame."""
    if df.empty:
        st.info("No data available.")
        return
    st.dataframe(df, width="stretch", hide_index=True, height=height, **kwargs)


def _danger_card(role_icon: str, role_label: str, row: dict | None,
                 accent: str) -> str:
    """HTML for a single danger-man card (offensive or defensive)."""
    if not row:
        return (
            f'<div style="flex:1;background:#1A1A2E;border-radius:8px;'
            f'padding:0.7rem 0.9rem;opacity:0.6;">'
            f'<span style="color:#888;font-size:0.8rem;">{role_icon} {role_label}'
            f'</span><br><span style="color:#666;">No data</span></div>'
        )
    return (
        f'<div style="flex:1;background:#1A1A2E;border-radius:8px;'
        f'padding:0.7rem 0.9rem;border-left:3px solid {accent};">'
        f'<span style="color:#888;font-size:0.72rem;text-transform:uppercase;'
        f'letter-spacing:0.5px;">{role_icon} {role_label}</span><br>'
        f'<span style="color:#FFF;font-size:1.05rem;font-weight:700;">'
        f'{row["player"]}</span>'
        f'<span style="color:{accent};font-size:1.05rem;font-weight:700;'
        f'float:right;">{row["threat"]:.0f}</span><br>'
        f'<span style="color:#aaa;font-size:0.78rem;">'
        f'top signal: {row.get("_why", "")}</span></div>'
    )


def player_threats_panel(threats: dict, team_name: str = "",
                         accent: str = AME_YELLOW) -> None:
    """Render a team's danger-men + full ranked threat tables.

    ``threats`` is the output of ``processing.player_threats.compute_player_threats``
    — keys ``offensive``, ``defensive`` (DataFrames) and ``top_offensive`` /
    ``top_defensive`` (single rows). Shows the standout attacker and ball-winner
    as cards, with the full squad-relative ranking behind an expander. The
    ``threat`` index is squad-relative (0–100), not an absolute league rating.
    """
    if not threats or (threats.get("offensive", pd.DataFrame()).empty
                       and threats.get("defensive", pd.DataFrame()).empty):
        st.info(f"No threat data for {team_name}." if team_name
                else "No threat data.")
        return

    if team_name:
        st.markdown(f"**{team_name}**")

    st.markdown(
        '<div style="display:flex;gap:0.6rem;margin-bottom:0.4rem;">'
        + _danger_card("⚔️", "Most dangerous offensively",
                       threats.get("top_offensive"), accent)
        + _danger_card("🛡️", "Most dangerous defensively",
                       threats.get("top_defensive"), accent)
        + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Full threat ranking"):
        off = threats.get("offensive", pd.DataFrame())
        if not off.empty:
            st.markdown("**Offensive threat** · index relative to teammates (0–100)")
            disp = off.drop(columns=["_why"]).rename(columns={
                "player": "Player", "threat": "Threat", "xg": "xG",
                "xgchain": "xGChain", "shots": "Shots/g",
                "key_passes": "KeyP/g", "take_ons_won": "Drb/g"})
            st.dataframe(disp, width="stretch", hide_index=True)
        deff = threats.get("defensive", pd.DataFrame())
        if not deff.empty:
            st.markdown("**Defensive threat** · index relative to teammates (0–100)")
            disp = deff.drop(columns=["_why"]).rename(columns={
                "player": "Player", "threat": "Threat",
                "tackles_won": "Tkl/g", "interceptions": "Int/g",
                "recoveries": "Rec/g", "clearances": "Clr/g",
                "aerials_won": "Aer/g"})
            st.dataframe(disp, width="stretch", hide_index=True)


def player_stats_table(df: pd.DataFrame, stat_columns: list[str] | None = None,
                       sort_by: str | None = None) -> None:
    """Render a player statistics table with key columns."""
    if df.empty:
        st.info("No player data available.")
        return

    if stat_columns is None:
        stat_columns = ["nombre", "posicion", "Games Played", "Goals", "Goal Assists",
                        "Total Passes", "Tackles Won", "Interceptions"]
    available = [c for c in stat_columns if c in df.columns]
    display = df[available].copy()

    if sort_by and sort_by in display.columns:
        display = display.sort_values(sort_by, ascending=False)

    st.dataframe(display, width="stretch", hide_index=True, height=500)
