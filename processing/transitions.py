from __future__ import annotations
"""Transition / counter-attack CONVERSION profile — a value layer on game_phases.

``processing/game_phases.py`` already *detects* transitions (it tells you a team
won the ball and whether they got a shot within the counter-attack window).  What
it does not do is say how **lethal** those transitions are — and counter-attacking
identity is a core Liga MX scouting question (América breaking on a deep-block
opponent vs. grinding them down in settled possession).

This module attaches xG to the detection: for every open-play regain it asks
"did a shot follow within the window, and how good a chance was it?", then splits
the team's whole shooting output into **transition** vs **settled** and reports
the conversion economy:

    xg_per_regain          = transition xG ÷ regains      (how dangerous each turnover win is)
    pct_xg_from_transition = transition xG ÷ total xG      (how transition-reliant the attack is)
    avg_time_to_shot       = mean seconds regain → shot    (directness)

Pure functions first; cached season aggregation at the bottom (xt/xdef pattern).
"""

import json

import pandas as pd
import streamlit as st

from data.paths import partidos_dir
from data.event_parser import extract_shots, parse_match_info
from processing.game_phases import parse_possession_chains

COUNTER_WINDOW_S = 10      # seconds after a regain that a shot counts as "transition"


def transition_profile(events: list[dict], team_id: str, opp_id: str,
                       window: int = COUNTER_WINDOW_S) -> dict:
    """Transition vs settled shooting economy for one team in one match.

    Returns {
        regains, shots, xg, transition_shots, transition_xg, settled_shots,
        settled_xg, xg_per_regain, pct_shots_from_transition,
        pct_xg_from_transition, avg_time_to_shot,
    }.
    """
    out = {"regains": 0, "shots": 0, "xg": 0.0, "transition_shots": 0,
           "transition_xg": 0.0, "settled_shots": 0, "settled_xg": 0.0,
           "xg_per_regain": 0.0, "pct_shots_from_transition": 0.0,
           "pct_xg_from_transition": 0.0, "avg_time_to_shot": None}

    chain = parse_possession_chains(events, team_id, opp_id)
    if chain.empty:
        return out

    # Open-play regains = moments team_id took over possession.
    regains = sorted(chain.loc[(chain["is_change"]) &
                               (chain["possession_team"] == team_id), "t"].tolist())
    out["regains"] = len(regains)

    shots = extract_shots(events, team_id=team_id)
    if shots.empty:
        return out

    shots = shots.copy()
    shots["t"] = shots["minute"] * 60 + shots["second"]
    out["shots"] = len(shots)
    out["xg"] = round(float(shots["xg"].sum()), 3)

    # For each shot, find the most recent regain within the window → transition.
    times_to_shot = []
    import bisect
    for s in shots.itertuples():
        i = bisect.bisect_right(regains, s.t) - 1
        if i >= 0 and 0 <= s.t - regains[i] <= window:
            out["transition_shots"] += 1
            out["transition_xg"] += float(s.xg)
            times_to_shot.append(s.t - regains[i])
        else:
            out["settled_shots"] += 1
            out["settled_xg"] += float(s.xg)

    out["transition_xg"] = round(out["transition_xg"], 3)
    out["settled_xg"] = round(out["settled_xg"], 3)
    if out["regains"]:
        out["xg_per_regain"] = round(out["transition_xg"] / out["regains"], 4)
    if out["shots"]:
        out["pct_shots_from_transition"] = round(out["transition_shots"] / out["shots"] * 100, 1)
    if out["xg"] > 0:
        out["pct_xg_from_transition"] = round(out["transition_xg"] / out["xg"] * 100, 1)
    if times_to_shot:
        out["avg_time_to_shot"] = round(sum(times_to_shot) / len(times_to_shot), 1)
    return out


@st.cache_data(ttl=3600, show_spinner="Computing transition conversion profile…")
def compute_season_transitions(league: str, season: str, team_id: str,
                               stage_filter: str = "",
                               window: int = COUNTER_WINDOW_S) -> dict:
    """Season transition-conversion profile for one team.

    Returns {} if no matches, else {
        matches, regains, shots, xg, transition_shots, transition_xg,
        settled_shots, settled_xg, xg_per_regain, pct_shots_from_transition,
        pct_xg_from_transition, avg_time_to_shot, per_match (DataFrame)
    }.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    agg = {"regains": 0, "shots": 0, "xg": 0.0, "transition_shots": 0,
           "transition_xg": 0.0, "settled_shots": 0, "settled_xg": 0.0}
    times = []
    rows = []
    matches = 0

    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        info = parse_match_info(raw)
        home_id, away_id = info["home_id"], info["away_id"]
        if team_id not in (home_id, away_id):
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue
        opp_id = away_id if team_id == home_id else home_id
        prof = transition_profile(raw.get("liveData", {}).get("event", []),
                                  team_id, opp_id, window=window)
        matches += 1
        for k in agg:
            agg[k] += prof[k]
        if prof["avg_time_to_shot"] is not None and prof["transition_shots"]:
            times.append((prof["avg_time_to_shot"], prof["transition_shots"]))
        rows.append({
            "match_num": matches,
            "opponent": info["away_team"] if team_id == home_id else info["home_team"],
            "venue": "H" if team_id == home_id else "A",
            "regains": prof["regains"],
            "transition_xg": prof["transition_xg"],
            "xg_per_regain": prof["xg_per_regain"],
        })

    if matches == 0:
        return {}

    # Weighted mean time-to-shot (weight by number of transition shots).
    avg_tts = None
    if times:
        num = sum(t * n for t, n in times)
        den = sum(n for _, n in times)
        avg_tts = round(num / den, 1) if den else None

    return {
        "matches": matches,
        **{k: round(v, 3) if isinstance(v, float) else v for k, v in agg.items()},
        "xg_per_regain": round(agg["transition_xg"] / agg["regains"], 4) if agg["regains"] else 0.0,
        "pct_shots_from_transition": round(agg["transition_shots"] / agg["shots"] * 100, 1) if agg["shots"] else 0.0,
        "pct_xg_from_transition": round(agg["transition_xg"] / agg["xg"] * 100, 1) if agg["xg"] > 0 else 0.0,
        "avg_time_to_shot": avg_tts,
        "per_match": pd.DataFrame(rows),
    }
