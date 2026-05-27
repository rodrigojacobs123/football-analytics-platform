"""Game-phase classification and transition analytics — Hudl/Wyscout style.

Modern tactical analysis splits a match into 4 in-play states + 2 transitions:

    IN POSSESSION                       OUT OF POSSESSION
    ─────────────                       ─────────────────
    BUILD_UP    (own def. third)        HIGH_PRESS   (opp def. third)
    PROGRESSION (middle third)          MID_BLOCK    (middle third)
    FINAL_THIRD (opp def. third)        LOW_BLOCK    (own def. third)

    TRANSITIONS (after possession change)
    ─────────────────────────────────────
    DEF_TRANSITION_5S  : 0–5 s after losing the ball  (gegenpress window)
    DEF_TRANSITION_7S  : 0–7 s after losing the ball  (Hudl standard)
    OFF_TRANSITION_10S : 0–10 s after winning the ball (counter-attack window)

This module:
1. Walks the event stream and classifies each event into one of the phases
2. Detects every possession change → time-stamps it as a transition trigger
3. Aggregates per-team distributions and counter-press / counter-attack outcomes
"""

from __future__ import annotations
import pandas as pd
from config import (
    EVENT_PASS, EVENT_TAKE_ON, EVENT_FOUL, EVENT_TACKLE, EVENT_INTERCEPTION,
    EVENT_BALL_RECOVERY, EVENT_DISPOSSESSED, EVENT_TURNOVER, EVENT_CLEARANCE,
    EVENT_GOAL, EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED,
)


# ── Constants ───────────────────────────────────────────────────────────────
PHASES = [
    "BUILD_UP", "PROGRESSION", "FINAL_THIRD",
    "HIGH_PRESS", "MID_BLOCK", "LOW_BLOCK",
    "DEF_TRANSITION_5S", "DEF_TRANSITION_7S", "OFF_TRANSITION_10S",
]

PHASE_LABELS = {
    "BUILD_UP":           "Build-up",
    "PROGRESSION":        "Progression",
    "FINAL_THIRD":        "Final-third Attack",
    "HIGH_PRESS":         "High Press",
    "MID_BLOCK":          "Mid-block",
    "LOW_BLOCK":          "Low Block",
    "DEF_TRANSITION_5S":  "Counter-press (5s)",
    "DEF_TRANSITION_7S":  "Counter-press (7s)",
    "OFF_TRANSITION_10S": "Counter-attack (10s)",
}

PHASE_COLORS = {
    # In possession — greens (all dark enough for white text)
    "BUILD_UP":           "#1B5E20",   # very dark green – patient build from back
    "PROGRESSION":        "#2E7D32",   # dark green – moving through mid-third
    "FINAL_THIRD":        "#388E3C",   # medium green – attacking third entries
    # Out of possession — reds (all dark enough for white text)
    "HIGH_PRESS":         "#B71C1C",   # deep dark red – high-line aggressive press
    "MID_BLOCK":          "#C62828",   # dark red – medium block shape
    "LOW_BLOCK":          "#D32F2F",   # red (was near-white #FFCDD2 — fixed)
    # Transitions — ambers/oranges (all dark enough for white text)
    "DEF_TRANSITION_5S":  "#E65100",   # dark orange – gegenpress window (0–5 s)
    "DEF_TRANSITION_7S":  "#F57C00",   # orange – Hudl standard window (0–7 s)
    "OFF_TRANSITION_10S": "#F9A825",   # dark amber – counter-attack window (0–10 s)
}

# Coordinate thresholds (Opta normalised 0–100, x is attacking direction)
DEF_THIRD_MAX = 33.33    # 0–33   = defensive third
MID_THIRD_MAX = 66.66    # 33–66  = middle third
                         # 66–100 = attacking third

# Events that signal a possession change to the opposite team
TURNOVER_EVENTS = {EVENT_TACKLE, EVENT_INTERCEPTION, EVENT_BALL_RECOVERY,
                   EVENT_CLEARANCE, EVENT_DISPOSSESSED, EVENT_TURNOVER}


# ── Helpers ─────────────────────────────────────────────────────────────────
def _seconds(event: dict) -> float:
    """Match clock in seconds.

    Opta F24 ``timeMin`` is the TOTAL elapsed minute (period 2 starts at 45),
    not minute-within-period — so no extra offset is needed.
    """
    return int(event.get("timeMin", 0)) * 60 + int(event.get("timeSec", 0))


def _zone(x: float) -> str:
    """Return 'def' | 'mid' | 'att' for an attacking-direction x coord (0–100)."""
    if x <= DEF_THIRD_MAX:
        return "def"
    if x <= MID_THIRD_MAX:
        return "mid"
    return "att"


def _is_shot(type_id: int) -> bool:
    return type_id in (EVENT_GOAL, EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED)


# ── Possession parsing ──────────────────────────────────────────────────────
def parse_possession_chains(events: list[dict],
                            home_id: str, away_id: str) -> pd.DataFrame:
    """Return a DataFrame, one row per event, with possession bookkeeping.

    Columns:
        idx, t (seconds), team_id, type_id, x, y, period, possession_team,
        is_change (True on first event of a new possession),
        prev_team (team that just LOST the ball — only set when is_change).
    """
    rows: list[dict] = []
    poss_team: str | None = None
    prev_team: str | None = None

    for i, ev in enumerate(events):
        type_id = ev.get("typeId")
        team = ev.get("contestantId")
        if team not in (home_id, away_id):
            continue   # ignore neutral/system events

        # Decide whether possession has changed. A turnover by team B clearly
        # gives possession to team B; a successful pass by team A keeps it.
        change = False
        if poss_team is None:
            # First valid event of the match
            poss_team = team
            change = True
        elif type_id in TURNOVER_EVENTS and team != poss_team:
            prev_team = poss_team
            poss_team = team
            change = True
        elif type_id == EVENT_PASS and team != poss_team:
            # Defensive deflection that becomes the other team's pass — rare.
            prev_team = poss_team
            poss_team = team
            change = True

        rows.append({
            "idx": i,
            "t": _seconds(ev),
            "team_id": team,
            "type_id": type_id,
            "x": float(ev.get("x", 0) or 0),
            "y": float(ev.get("y", 0) or 0),
            "period": int(ev.get("periodId", 1) or 1),
            "possession_team": poss_team,
            "is_change": change,
            "prev_team": prev_team if change else None,
        })

    return pd.DataFrame(rows)


# ── Phase classification ────────────────────────────────────────────────────
def classify_phases(chain: pd.DataFrame, team_id: str, opp_id: str,
                    counter_press_windows: tuple[int, ...] = (5, 7),
                    counter_attack_window: int = 10) -> pd.DataFrame:
    """Annotate each row with the team's tactical phase at that moment.

    Rules — applied in order, first match wins:

    1.  If we're inside a counter-attack window after team_id won the ball
        → OFF_TRANSITION_10S.
    2.  If we're inside a counter-press window after team_id lost the ball
        → DEF_TRANSITION_5S (and 7S if applicable — they overlap by design).
    3.  Otherwise classify by possession + ball x-zone (in team_id's frame):
            in possession  → BUILD_UP / PROGRESSION / FINAL_THIRD
            out of poss.   → HIGH_PRESS / MID_BLOCK / LOW_BLOCK
    """
    if chain.empty:
        return chain.assign(phase=[])

    # Find every possession change time-stamp by team and direction
    changes = chain[chain["is_change"]].copy()
    won_by_team = changes[changes["possession_team"] == team_id]["t"].tolist()
    lost_by_team = changes[changes["prev_team"] == team_id]["t"].tolist()

    cp_windows_sorted = tuple(sorted(counter_press_windows))   # e.g. (5, 7)

    def _classify(row: pd.Series) -> str:
        t = row["t"]
        x = row["x"]
        if row["team_id"] != team_id:
            x = 100.0 - x   # mirror to team_id's attacking frame

        is_team_event = row["team_id"] == team_id
        in_possession = row["possession_team"] == team_id

        # 1) Transitions only apply to team_id's OWN events — otherwise an
        #    opponent's pass during our 10s counter-attack window gets
        #    mis-classified as our counter-attack.
        if is_team_event:
            # Offensive transition: we just won the ball, within the window
            for win_t in reversed(won_by_team):
                if win_t > t:
                    continue
                if t - win_t <= counter_attack_window:
                    return "OFF_TRANSITION_10S"
                break
            # Defensive transition: we just lost the ball, within the window
            for lost_t in reversed(lost_by_team):
                if lost_t > t:
                    continue
                dt = t - lost_t
                for w in cp_windows_sorted:
                    if dt <= w:
                        return f"DEF_TRANSITION_{w}S"
                break

        # 2) Settled phase based on possession + zone
        zone = _zone(x)
        if in_possession:
            return {"def": "BUILD_UP", "mid": "PROGRESSION", "att": "FINAL_THIRD"}[zone]
        else:
            # When defending, x is mirrored to OUR attacking direction:
            #   x>66 = opponent deep in our attacking half = pressing high
            #   x in 33–66 = opponent in middle third
            #   x<33 = opponent deep in our defensive third = low block
            return {"att": "HIGH_PRESS", "mid": "MID_BLOCK", "def": "LOW_BLOCK"}[zone]

    chain = chain.copy()
    chain["phase"] = chain.apply(_classify, axis=1)
    return chain


# ── Aggregations ────────────────────────────────────────────────────────────
def phase_distribution(chain_with_phases: pd.DataFrame) -> dict[str, dict]:
    """Return {phase: {events: int, share_pct: float}}.

    Share is over total classified events (rounded to 1 dp).
    """
    if chain_with_phases.empty:
        return {p: {"events": 0, "share_pct": 0.0} for p in PHASES}

    counts = chain_with_phases["phase"].value_counts().to_dict()
    total = sum(counts.values()) or 1
    return {
        p: {"events": int(counts.get(p, 0)),
            "share_pct": round(counts.get(p, 0) / total * 100, 1)}
        for p in PHASES
    }


def transition_metrics(chain: pd.DataFrame, team_id: str,
                       counter_press_windows: tuple[int, ...] = (5, 7),
                       counter_attack_window: int = 10) -> dict:
    """Counter-press success rates + counter-attack productivity.

    Counter-press success
      For each turnover where team_id LOST possession, did team_id win it
      back within the window?  Reported as % of all losses.

    Counter-attack productivity
      For each turnover where team_id WON possession, did team_id reach the
      attacking third / get a shot within the counter-attack window?
    """
    out = {
        "losses": 0, "wins": 0,
        "counter_press_5s_pct": 0.0, "counter_press_7s_pct": 0.0,
        "counter_attack_shots": 0, "counter_attack_final_third_pct": 0.0,
        "avg_recovery_time_s": None,
    }
    if chain.empty:
        return out

    changes = chain[chain["is_change"]].copy().reset_index(drop=True)
    if changes.empty:
        return out

    # All times where team_id lost / won possession
    losses_t = changes.loc[changes["prev_team"] == team_id, "t"].tolist()
    wins_t = changes.loc[changes["possession_team"] == team_id, "t"].tolist()
    out["losses"] = len(losses_t)
    out["wins"] = len(wins_t)

    # ── Counter-press: did we re-win within window? ─────────────────────────
    next_wins_after_loss: list[float] = []     # time-to-recover per loss
    cp_hits = {w: 0 for w in counter_press_windows}

    j = 0   # pointer into wins_t (sorted)
    for L in losses_t:
        while j < len(wins_t) and wins_t[j] <= L:
            j += 1
        if j >= len(wins_t):
            next_wins_after_loss.append(None)
            continue
        recovery_dt = wins_t[j] - L
        next_wins_after_loss.append(recovery_dt)
        for w in counter_press_windows:
            if recovery_dt <= w:
                cp_hits[w] += 1

    if losses_t:
        for w in counter_press_windows:
            out[f"counter_press_{w}s_pct"] = round(cp_hits[w] / len(losses_t) * 100, 1)
        recovery_times = [t for t in next_wins_after_loss if t is not None]
        if recovery_times:
            out["avg_recovery_time_s"] = round(sum(recovery_times) / len(recovery_times), 1)

    # ── Counter-attack productivity: shots / reach final third in 10s ──────
    ca_shots = 0
    ca_final_third = 0
    chain_sorted = chain.sort_values("t")
    for W in wins_t:
        window_events = chain_sorted[
            (chain_sorted["t"] >= W) & (chain_sorted["t"] <= W + counter_attack_window)
        ]
        # Shot by team_id?
        team_window = window_events[window_events["team_id"] == team_id]
        if not team_window.empty:
            if team_window["type_id"].apply(_is_shot).any():
                ca_shots += 1
            # Reached final third (x>66 in own attacking direction)
            if (team_window["x"] > MID_THIRD_MAX).any():
                ca_final_third += 1

    out["counter_attack_shots"] = ca_shots
    if wins_t:
        out["counter_attack_final_third_pct"] = round(ca_final_third / len(wins_t) * 100, 1)
    return out


# ── Top-level convenience ───────────────────────────────────────────────────
def compute_team_phase_report(events: list[dict], team_id: str, opp_id: str,
                              counter_press_windows: tuple[int, ...] = (5, 7),
                              counter_attack_window: int = 10) -> dict:
    """One-call API: returns everything Pre/Post-Match pages need.

    Returns:
        {
          "distribution": {phase: {events, share_pct}, ...},
          "transitions":  {losses, wins, counter_press_*_pct, ...},
          "chain":        the annotated DataFrame (for charts that want raw),
        }
    """
    chain = parse_possession_chains(events, team_id, opp_id)
    chain = classify_phases(chain, team_id, opp_id,
                            counter_press_windows, counter_attack_window)
    return {
        "distribution": phase_distribution(chain),
        "transitions": transition_metrics(chain, team_id,
                                          counter_press_windows,
                                          counter_attack_window),
        "chain": chain,
    }
