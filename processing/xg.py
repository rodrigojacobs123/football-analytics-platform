from __future__ import annotations
"""xG extraction, timelines, and season aggregation.

Methodology
-----------
xG values consumed by this module are NOT computed here — they are sourced
from the Opta F24 event feed:

1. **Primary source (preferred)** — Opta qualifier ``395`` on each shot event.
   Opta's xG is a logistic regression over shot location, body part, assist
   type, distance/angle, attack pattern (open play / set piece / penalty)
   and one-on-one flags. Values are 0–100 in the feed and divided by 100
   to yield 0–1 probabilities. Penalties are forced to ``PENALTY_XG``
   (≈ 0.79) regardless of qualifier — see ``processing/xg_model.py``.

2. **Fallback model** — when qualifier 395 is missing on a shot (some older
   feeds only attach it to goals), ``xg_model.estimate_xg()`` substitutes a
   small distance-and-angle logistic that mirrors the published Opta model's
   shape on open-play shots.

This module then aggregates those per-shot xG values into:
   * match totals (home / away)
   * minute-by-minute cumulative timelines for the xG race chart
   * season-level per-match xG vs goals series
"""

import pandas as pd
import numpy as np
import streamlit as st
from data.event_parser import extract_shots, extract_goals
from data.loader import load_match_events, load_match_raw
from data.event_parser import parse_match_info


def compute_match_xg(events: list[dict], team_id: str) -> float:
    """Sum xG for all shots by a team in a match."""
    shots = extract_shots(events, team_id)
    return shots["xg"].sum() if not shots.empty else 0.0


def compute_xg_timeline(events: list[dict], home_id: str, away_id: str) -> pd.DataFrame:
    """Build cumulative xG by minute for both teams.

    Returns DataFrame: minute, home_xg, away_xg (cumulative).
    """
    shots = extract_shots(events)
    if shots.empty:
        return pd.DataFrame({"minute": [0, 90], "home_xg": [0, 0], "away_xg": [0, 0]})

    # Build minute-by-minute cumulative xG
    max_min = max(90, int(shots["minute"].max()) + 1)
    timeline = []
    home_cum = 0.0
    away_cum = 0.0

    for m in range(0, max_min + 1):
        min_shots = shots[shots["minute"] == m]
        home_cum += min_shots[min_shots["team_id"] == home_id]["xg"].sum()
        away_cum += min_shots[min_shots["team_id"] == away_id]["xg"].sum()
        timeline.append({"minute": m, "home_xg": round(home_cum, 2), "away_xg": round(away_cum, 2)})

    df = pd.DataFrame(timeline)
    df.attrs["home_id"] = home_id
    df.attrs["away_id"] = away_id
    return df


def compute_shot_map_data(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract all shots with x, y, xG, player, outcome, body_part."""
    return extract_shots(events, team_id)


@st.cache_data(ttl=3600)
def compute_club_season_xg(league: str, season: str, club_team_id: str) -> pd.DataFrame:
    """Compute xG for all Club América matches in a season.

    Iterates through club match files, extracting shot data.
    Returns DataFrame: matchday, date, opponent, is_home, club_xg, opp_xg, club_goals, opp_goals.
    """
    from data.loader import load_club_match_list, load_match_raw
    from data.event_parser import parse_match_info

    matches = load_club_match_list(league, season)
    if matches.empty:
        return pd.DataFrame()

    rows = []
    for _, match in matches.iterrows():
        match_id = match.get("match_id", "")
        if not match_id:
            continue

        raw = load_match_raw(league, season, match_id)
        if not raw:
            continue

        info = parse_match_info(raw)
        events = raw.get("liveData", {}).get("event", [])
        if not events:
            continue

        home_id = info["home_id"]
        away_id = info["away_id"]
        is_home = home_id == club_team_id
        opp_id = away_id if is_home else home_id

        club_xg = compute_match_xg(events, club_team_id)
        opp_xg = compute_match_xg(events, opp_id)

        rows.append({
            "matchday": info["matchday"],
            "date": info["date"],
            "opponent": info["away_team"] if is_home else info["home_team"],
            "is_home": is_home,
            "club_xg": round(club_xg, 2),
            "opp_xg": round(opp_xg, 2),
            "club_goals": match["club_score"],
            "opp_goals": match["opp_score"],
        })

    return pd.DataFrame(rows)
