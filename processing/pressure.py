from __future__ import annotations
"""Pressure-style defensive metrics (StatsBomb / The Analyst conventions).

Opta F24 doesn't carry a 'pressure' event natively (it's a StatsBomb-specific
event). We approximate the same insights using events we DO have:

- "Pressure regains"     ~  ball recoveries / tackles in the opposition half
                            within 5 s of an opponent ball-receiving event.
- "Defensive line height" ~ avg x of own back-line defensive actions
                            (tackles + interceptions + clearances) when
                            the opponent has the ball.
- "Ball recovery height"  ~  mean x of the team's ball recoveries.
- "High turnovers"        ~  recoveries in the opp's defensive 1/3 (x>66).
- "Shot-ending HTOs"      ~  high turnovers that lead to a shot within 10 s.
"""

import pandas as pd
from data.event_parser import (
    extract_ball_recoveries, extract_tackles, extract_interceptions,
    extract_clearances, extract_shots,
)
from config import EVENT_GOAL, EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED


SHOT_TYPES = {EVENT_GOAL, EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED}


def _seconds(ev: dict) -> float:
    return int(ev.get("timeMin", 0)) * 60 + int(ev.get("timeSec", 0))


def compute_pressure_metrics(events: list[dict], team_id: str,
                             opp_id: str) -> dict:
    """Compute the pressure-style metric bundle for one team."""
    recoveries  = extract_ball_recoveries(events, team_id)
    tackles     = extract_tackles(events, team_id)
    intercepts  = extract_interceptions(events, team_id)
    clearances  = extract_clearances(events, team_id)

    # ── Ball recovery height ─────────────────────────────────────────────
    ball_recovery_height = (
        round(recoveries["x"].mean(), 1) if not recoveries.empty else 0.0
    )

    # ── Defensive line height ────────────────────────────────────────────
    # Use defensive ACTIONS from the team while opponent had the ball as a
    # proxy for "where was our defensive line standing".  We pool tackles +
    # interceptions + clearances (all classic backline events).
    def_actions = pd.concat(
        [df[["x", "y"]] for df in (tackles, intercepts, clearances) if not df.empty],
        ignore_index=True,
    )
    def_line_height = (
        round(def_actions["x"].mean(), 1) if not def_actions.empty else 0.0
    )

    # ── High turnovers (recoveries in opp's defensive 1/3) ───────────────
    if not recoveries.empty:
        high_turnovers = int((recoveries["x"] >= 66).sum())
    else:
        high_turnovers = 0

    # ── Shot-ending high turnovers ───────────────────────────────────────
    # For each high-recovery, check if the team had a shot within 10 s.
    shot_ending_htos = 0
    if high_turnovers > 0:
        shots = extract_shots(events, team_id=team_id)
        if not shots.empty:
            shot_times = []
            for _, s in shots.iterrows():
                # 'minute' is timeMin, 'second' is from extractor (defaults to 0)
                shot_times.append(int(s["minute"]) * 60)
            shot_times.sort()
            for _, r in recoveries[recoveries["x"] >= 66].iterrows():
                t = int(r["minute"]) * 60
                # binary search-ish lookahead
                for st in shot_times:
                    if st < t:
                        continue
                    if st - t <= 10:
                        shot_ending_htos += 1
                    break

    # ── Pressure regains (recoveries within 5 s of opp ball-event) ───────
    # We approximate "opp ball-event" with the opp's previous PASS — if our
    # next event after the opp pass is a recovery within 5 s, it's a regain.
    chronological = sorted(events, key=lambda e: (
        int(e.get("timeMin", 0)), int(e.get("timeSec", 0)),
        int(e.get("eventId", 0))))
    pressure_regains = 0
    last_opp_pass_t = None
    for ev in chronological:
        type_id = ev.get("typeId")
        team = ev.get("contestantId")
        if team == opp_id and type_id == 1:
            last_opp_pass_t = _seconds(ev)
        elif team == team_id and type_id == 49 and last_opp_pass_t is not None:
            if _seconds(ev) - last_opp_pass_t <= 5:
                pressure_regains += 1
            last_opp_pass_t = None

    return {
        "ball_recovery_height":     ball_recovery_height,
        "def_line_height":          def_line_height,
        "high_turnovers":           high_turnovers,
        "shot_ending_high_turnovers": shot_ending_htos,
        "pressure_regains_5s":      pressure_regains,
        "total_recoveries":         len(recoveries),
        "recoveries_df":            recoveries,
        "def_actions_df":           def_actions,
    }


# ──────────────────────────────────────────────────────────────────────────
# Season aggregation (cached "deep tier")
#
# compute_pressure_metrics() above is pure (events -> dict).  The function
# below adds the Streamlit-cached scan over partidos/ so the pressing bundle
# can be surfaced at season level on the Tactics page.  Same pattern as
# processing/season_tactics.py.
# ──────────────────────────────────────────────────────────────────────────
import json
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Computing pressing metrics…")
def compute_season_pressure(league: str, season: str, team_id: str,
                            stage_filter: str = "") -> dict:
    """Season-aggregated pressing / transition metrics for one team.

    Scans every match the team played in partidos/ and averages the
    Opta-approximated pressure bundle (these are NOT native StatsBomb pressure
    events — see module docstring).  Returns {} when no matches found, else a
    dict of season averages/totals plus a ``per_match`` DataFrame for trends.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    rows: list[dict] = []
    match_num = 0

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

        is_home = team_id == home_id
        opp_id = away_id if is_home else home_id
        events = raw.get("liveData", {}).get("event", [])
        m = compute_pressure_metrics(events, team_id, opp_id)
        match_num += 1
        rows.append({
            "match_num": match_num,
            "opponent": info["away_team"] if is_home else info["home_team"],
            "venue": "H" if is_home else "A",
            "ball_recovery_height": m["ball_recovery_height"],
            "def_line_height": m["def_line_height"],
            "high_turnovers": m["high_turnovers"],
            "shot_ending_high_turnovers": m["shot_ending_high_turnovers"],
            "pressure_regains_5s": m["pressure_regains_5s"],
        })

    if match_num == 0:
        return {}

    df = pd.DataFrame(rows)
    return {
        "matches": match_num,
        "avg_recovery_height": round(df["ball_recovery_height"].mean(), 1),
        "avg_def_line_height": round(df["def_line_height"].mean(), 1),
        "high_turnovers_per_match": round(df["high_turnovers"].mean(), 1),
        "shot_ending_htos_total": int(df["shot_ending_high_turnovers"].sum()),
        "pressure_regains_per_match": round(df["pressure_regains_5s"].mean(), 1),
        "per_match": df,
    }
