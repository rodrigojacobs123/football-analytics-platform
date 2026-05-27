"""Styled DataFrame renderers for league tables and data displays."""

import pandas as pd
import streamlit as st
from config import MU_RED, MU_TEAM_NAME, MU_DARK_BG


def styled_league_table(
    df: pd.DataFrame,
    highlight_team: str = MU_TEAM_NAME,
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
            return [f"background-color: {MU_RED}44; font-weight: bold"] * len(row)

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


def styled_dataframe(df: pd.DataFrame, height: int = 400, **kwargs) -> None:
    """Render a generic styled DataFrame."""
    if df.empty:
        st.info("No data available.")
        return
    st.dataframe(df, width="stretch", hide_index=True, height=height, **kwargs)


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
