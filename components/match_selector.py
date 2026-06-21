from __future__ import annotations
"""Match dropdown selector showing matchday, opponent, score, date."""

import streamlit as st
import pandas as pd
from config import AME_TEAM_ID
from data.loader import load_club_match_list, load_all_season_results


def match_selector(league: str, season: str, key: str = "match_sel",
                   label: str = "Select Match", stage_filter: str = "") -> dict | None:
    """Render a match selector dropdown.

    If club has matches in this competition/season, shows club matches.
    Otherwise shows all matches in the competition.
    Returns dict with match details or None if no selection.
    """
    club_matches = load_club_match_list(league, season, stage_filter=stage_filter)
    if not club_matches.empty:
        return _club_match_selector(club_matches, key, label)

    # Fallback: show all matches in the competition
    return all_match_selector(league, season, key=key, label=label, stage_filter=stage_filter)


def _club_match_selector(matches: pd.DataFrame, key: str, label: str) -> dict | None:
    """Club-specific match selector with opponent/result view."""
    matches["label"] = matches.apply(
        lambda r: (
            f"MD {r['matchday']} · "
            f"{'vs' if r['is_home'] else '@'} {r['opponent']} "
            f"({r['club_score']}-{r['opp_score']}) · "
            f"{r['result']} · {str(r['date'])[:10]}"
        ),
        axis=1,
    )

    labels = matches["label"].tolist()
    selected_label = st.selectbox(label, options=labels, key=key)

    if selected_label:
        idx = labels.index(selected_label)
        row = matches.iloc[idx]
        return row.to_dict()
    return None


def all_match_selector(league: str, season: str, team_id: str = None,
                       key: str = "all_match_sel",
                       label: str = "Select Match",
                       stage_filter: str = "") -> dict | None:
    """Generic match selector for any team (or all matches in the competition)."""
    results = load_all_season_results(league, season, stage_filter=stage_filter)
    if results.empty:
        st.warning("No results available.")
        return None

    if team_id:
        results = results[
            (results["home_id"] == team_id) | (results["away_id"] == team_id)
        ]

    results["label"] = results.apply(
        lambda r: (
            f"MD {r['matchday']} · "
            f"{r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']} · "
            f"{str(r['date'])[:10]}"
        ),
        axis=1,
    )

    labels = results["label"].tolist()
    selected = st.selectbox(label, options=labels, key=key)
    if selected:
        idx = labels.index(selected)
        return results.iloc[idx].to_dict()
    return None


def team_match_selector(league: str, season: str, team_id: str = None,
                        key: str = "team_match_sel") -> dict | None:
    """Alias for all_match_selector for backward compatibility."""
    return all_match_selector(league, season, team_id=team_id, key=key)
