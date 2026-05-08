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

from __future__ import annotations
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
