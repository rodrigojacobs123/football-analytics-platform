from __future__ import annotations
"""Corner Defense Intelligence — three analytical models.

Model 1 — First Contact Control Index
    Who wins the first contact after each opponent corner?

Model 2 — Delivery Hotspot Suppression
    Which zones do opponent corners land in, weighted by danger?

Model 3 — Second Ball Control
    After a clearance, who wins the loose ball?

All models share a common foundation: `extract_corner_sequences()`, which
scans a match event list and groups the 12-second event window after every
opponent corner into a 'sequence' dict.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    EVENT_CORNER, EVENT_CLEARANCE, EVENT_AERIAL,
    EVENT_BALL_RECOVERY, EVENT_PASS, EVENT_GOAL,
    EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED,
    EVENT_TACKLE, EVENT_INTERCEPTION, EVENT_SAVE,
    EVENT_KEEPER_PICKUP, EVENT_CLAIM,
    SHOT_TYPE_IDS,
)
from data.event_parser import parse_match_info
from data.paths import partidos_dir


# ── Time helpers ──────────────────────────────────────────────────────────────

def _secs(minute: int, second: int) -> float:
    return minute * 60.0 + second


# ── Event sequence extraction ─────────────────────────────────────────────────

SEQUENCE_WINDOW = 20   # seconds after corner kick to collect events
CLEARANCE_WINDOW = 12  # seconds after a clearance to find second ball

# Hard enders: goal scored or new corner TAKEN BY THE OPPONENT (retains set-piece).
# We do NOT end on a corner won by the defending team — we still want the events
# leading up to it (the clearance is what caused that corner win).
_HARD_ENDERS = {EVENT_GOAL, 5}   # goal or ball out = end of danger phase


def extract_corner_sequences(
    events: list[dict],
    team_id: str,
    opponent_id: str,
    window: float = SEQUENCE_WINDOW,
    mode: str = "defend",
) -> list[dict]:
    """Extract corner sequences for analysis.

    Parameters
    ----------
    team_id     : the primary team we are analysing.
    opponent_id : the opposing team in this match.
    mode        : "defend" → analyse opponent corners (team_id defends).
                  "attack" → analyse team_id's own corners (team_id attacks).

    Returns a list of sequence dicts:
    {
        corner_event   : the raw corner event dict (the kick itself),
        minute         : match minute,
        corner_x/y     : position of the corner kick,
        events         : [event, ...] within `window` seconds after the kick,
        defending_team_id : team that is DEFENDING in this sequence,
        opponent_id    : team that is ATTACKING in this sequence,
        led_to_shot    : bool — a shot happened within the sequence,
        led_to_goal    : bool — a goal was scored within the sequence,
        mode           : "defend" | "attack",
    }
    """
    if mode == "attack":
        corner_taker_id = team_id        # team takes the corner
        defending_id    = opponent_id    # opponent defends
    else:
        corner_taker_id = opponent_id    # opponent takes corner
        defending_id    = team_id        # team defends

    sorted_events = sorted(
        events,
        key=lambda e: _secs(int(e.get("timeMin", 0)), int(e.get("timeSec", 0))),
    )
    n = len(sorted_events)
    sequences = []

    for i, e in enumerate(sorted_events):
        if e.get("typeId") != EVENT_CORNER:
            continue
        if e.get("contestantId") != corner_taker_id:
            continue

        t0 = _secs(int(e.get("timeMin", 0)), int(e.get("timeSec", 0)))
        seq_events = []

        for j in range(i + 1, n):
            ne = sorted_events[j]
            t = _secs(int(ne.get("timeMin", 0)), int(ne.get("timeSec", 0)))
            if t - t0 > window:
                break

            # Corner RETAINED by the attacking team = still dangerous, keep going
            # Corner REGAINED by defending team after losing it = end of phase
            if ne.get("typeId") == EVENT_CORNER:
                seq_events.append(ne)
                break

            if ne.get("typeId") in _HARD_ENDERS:
                seq_events.append(ne)
                break

            seq_events.append(ne)

        led_to_shot = any(e2.get("typeId") in SHOT_TYPE_IDS for e2 in seq_events)
        led_to_goal = any(e2.get("typeId") == EVENT_GOAL for e2 in seq_events)

        sequences.append({
            "corner_event":    e,
            "minute":          int(e.get("timeMin", 0)),
            "corner_x":        float(e.get("x", 0)),
            "corner_y":        float(e.get("y", 0)),
            "events":          seq_events,
            "defending_team_id": defending_id,
            "opponent_id":     corner_taker_id,
            "led_to_shot":     led_to_shot,
            "led_to_goal":     led_to_goal,
            "mode":            mode,
        })

    return sequences


# ── Coordinate normalisation ─────────────────────────────────────────────────
# In Opta's shared coordinate system corners can be at x≈0 OR x≈100 depending
# on which end the opponent is attacking.  For ALL aggregate analysis we flip
# sequences where corner_x < 50 so the defended goal is always at x=100.
# The raw (un-flipped) sequence is preserved for the per-sequence explorer.

def _flip_event(e: dict) -> dict:
    """Return a copy of event e with x/y flipped (100-x, 100-y)."""
    ne = e.copy()
    ne["x"] = round(100.0 - float(e.get("x", 50)), 2)
    ne["y"] = round(100.0 - float(e.get("y", 50)), 2)
    return ne


def normalise_sequence(seq: dict) -> dict:
    """Return sequence with all coords rotated so the defended goal is at x=100.

    If corner_x > 50 the opponent is already attacking toward x=100 → no-op.
    If corner_x < 50 the opponent is attacking toward x=0 → flip everything.
    """
    if seq["corner_x"] > 50:
        return seq          # already the right orientation

    flipped = seq.copy()
    flipped["corner_x"] = round(100.0 - seq["corner_x"], 2)
    flipped["corner_y"] = round(100.0 - seq["corner_y"], 2)
    flipped["events"]   = [_flip_event(e) for e in seq["events"]]
    return flipped


def normalise_sequences(seqs: list[dict]) -> list[dict]:
    return [normalise_sequence(s) for s in seqs]


# ── Event type label map (used by both backend and page table) ────────────────

EVENT_TYPE_LABELS: dict[int, str] = {
    1:  "Pass",
    2:  "Offside Pass",
    3:  "Take-On",
    4:  "Foul",
    5:  "Ball Out",
    6:  "Corner",
    7:  "Tackle",
    8:  "Interception",
    9:  "Turnover",
    10: "Save",
    11: "Claim",
    12: "Clearance",
    13: "Shot (Miss)",
    14: "Shot (Post)",
    15: "Shot (Saved)",
    16: "GOAL ⚽",
    17: "Card",
    44: "Aerial Duel",
    49: "Ball Recovery",
    50: "Dispossessed",
    52: "Keeper Pick-Up",
    60: "Chance Missed",
    61: "Ball Touch",
}


# ── First-contact classification ──────────────────────────────────────────────

# Map event typeId → outcome label from the DEFENDING team's perspective.
# A "won" first contact = defending team made the first touch.
_FIRST_CONTACT_MAP: dict[int, str] = {
    EVENT_CLEARANCE:    "Clearance",
    EVENT_AERIAL:       "Aerial Duel",
    EVENT_TACKLE:       "Tackle",
    EVENT_INTERCEPTION: "Interception",
    EVENT_SAVE:         "Save",
    EVENT_KEEPER_PICKUP:"Keeper Claim",
    EVENT_CLAIM:        "Keeper Claim",
    EVENT_BALL_RECOVERY:"Recovery",
    EVENT_GOAL:         "Goal Conceded",
    EVENT_PASS:         "Recycled / Flick-on",
    EVENT_CORNER:       "Corner Won / Conceded",  # handled by team check below
    5:                  "Ball Out",               # out of play after corner
}
for tid in SHOT_TYPE_IDS:
    _FIRST_CONTACT_MAP[tid] = "Shot Conceded"


def classify_first_contact(event: dict, defending_team_id: str) -> tuple[str, bool]:
    """Return (contact_type, defending_team_won_first_contact).

    Special case: TypeId 6 (corner) — if the defending team wins it, label
    it 'Corner Won (Def)'; if the attacker retains it, 'Corner Retained (Att)'.
    """
    tid = event.get("typeId")
    team = event.get("contestantId", "")
    is_defending = team == defending_team_id

    if tid == EVENT_CORNER:
        label = "Corner Won (Def)" if is_defending else "Corner Retained (Att)"
        return label, is_defending

    label = _FIRST_CONTACT_MAP.get(tid, f"Other (id={tid})")
    return label, is_defending


# ── Model 1: First Contact Control Index ──────────────────────────────────────

def compute_first_contact_index(sequences: list[dict]) -> dict:
    """Aggregate first-contact stats across all opponent corners.

    Returns
    -------
    {
        total_corners   : int,
        won             : int,         # defending team wins first contact
        lost            : int,
        win_rate        : float (0–1),
        by_type         : {type_label: count},
        dangerous_rate  : float,       # % first contacts that were shots/goals
        records         : [per-corner dicts for a table]
    }
    """
    total = 0
    won = 0
    by_type: dict[str, int] = {}
    dangerous = 0
    records = []

    for seq in sequences:
        if not seq["events"]:
            continue
        total += 1
        first = seq["events"][0]
        label, defended = classify_first_contact(first, seq["defending_team_id"])

        by_type[label] = by_type.get(label, 0) + 1
        if defended:
            won += 1
        if label in ("Shot Conceded", "Goal Conceded"):
            dangerous += 1

        records.append({
            "minute": seq["minute"],
            "corner_side": "Left" if seq["corner_y"] < 50 else "Right",
            "first_contact": label,
            "defended": defended,
            "dangerous": label in ("Shot Conceded", "Goal Conceded"),
        })

    return {
        "total_corners": total,
        "won": won,
        "lost": total - won,
        "win_rate": round(won / total, 3) if total else 0,
        "by_type": by_type,
        "dangerous_rate": round(dangerous / total, 3) if total else 0,
        "records": records,
    }


# ── Model 2: Delivery Hotspot Suppression ─────────────────────────────────────

# Zone danger weights — based on empirical xG literature.
# 6-yard box corners of the pitch are most dangerous delivery targets.
ZONE_DANGER_WEIGHTS = {
    "six_yard":    1.00,   # highest danger
    "penalty_spot": 0.75,
    "penalty_area": 0.50,
    "edge_box":    0.25,
    "outside":     0.05,
}


def _classify_landing_zone(lx: float, ly: float, defending_right: bool) -> str:
    """Classify where a corner lands based on the first event coordinates.

    defending_right=True means the defended goal is on the right (x≈100).
    """
    if defending_right:
        in_six   = lx >= 94.2 and 36.8 <= ly <= 63.2
        in_pen   = lx >= 83.0 and 21.1 <= ly <= 78.9
        near_pen = lx >= 83.0 and (ly < 21.1 or ly > 78.9)
        edge     = 66.0 <= lx < 83.0
    else:
        in_six   = lx <= 5.8  and 36.8 <= ly <= 63.2
        in_pen   = lx <= 17.0 and 21.1 <= ly <= 78.9
        near_pen = lx <= 17.0 and (ly < 21.1 or ly > 78.9)
        edge     = 17.0 < lx <= 34.0

    if in_six:
        return "six_yard"
    if in_pen:
        return "penalty_area"
    if near_pen:
        return "penalty_spot"
    if edge:
        return "edge_box"
    return "outside"


def compute_delivery_zones(sequences: list[dict]) -> dict:
    """Map each corner to where it lands and compute a danger score.

    All sequences are normalised first so the defended goal is always at x=100.
    The landing zone is taken from the FIRST EVENT in the sequence (the event
    that made contact with the delivery), not the corner kick origin.

    Returns
    -------
    {
        landing_points : [(x, y, zone, danger_weight)] for heatmap,
        zone_counts    : {zone: count},
        danger_score   : float (0–100, weighted average),
        by_side        : {'Left': {...}, 'Right': {...}}
                         — side refers to which side of the goal the corner
                           is delivered FROM (normalised corner_y).
    }
    """
    normed = normalise_sequences(sequences)
    points = []
    zone_counts: dict[str, int] = {}
    total_danger = 0.0
    by_side: dict[str, dict[str, int]] = {"Left": {}, "Centre": {}, "Right": {}}

    for seq in normed:
        if not seq["events"]:
            lx, ly = seq["corner_x"], seq["corner_y"]
        else:
            first = seq["events"][0]
            lx = float(first.get("x", seq["corner_x"]))
            ly = float(first.get("y", seq["corner_y"]))

        # After normalisation defended goal is always at x=100
        zone = _classify_landing_zone(lx, ly, defending_right=True)
        weight = ZONE_DANGER_WEIGHTS.get(zone, 0.05)

        # Corner side: which side of the defended goal the corner comes from
        # (normalised y: low y = near bottom touchline, high y = top touchline)
        corner_side = "Left" if seq["corner_y"] < 40 else (
            "Right" if seq["corner_y"] > 60 else "Centre")

        led_to_goal = seq.get("led_to_goal", False)
        led_to_shot = seq.get("led_to_shot", False)
        points.append((lx, ly, zone, weight, led_to_goal, led_to_shot))
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
        total_danger += weight
        by_side[corner_side][zone] = by_side[corner_side].get(zone, 0) + 1

    n = len(normed)
    danger_score = round((total_danger / n) * 100, 1) if n else 0

    return {
        "landing_points": points,   # (x, y, zone, weight, led_to_goal, led_to_shot)
        "zone_counts": zone_counts,
        "danger_score": danger_score,
        "by_side": by_side,
        "total_corners": n,
    }


# ── Model 3: Second Ball Control ──────────────────────────────────────────────

def compute_second_ball_control(
    sequences: list[dict],
    window: float = CLEARANCE_WINDOW,
    _normed: bool = False,
) -> dict:
    """Find clearances within each corner sequence, then determine who wins
    the subsequent loose ball within `window` seconds.

    Returns
    -------
    {
        clearances_tracked : int,
        won_second_ball    : int,
        lost_second_ball   : int,
        second_ball_rate   : float,
        avg_recovery_dist  : float   (Opta units from goal),
        danger_resets      : int,    (loose ball won near box by attacker)
        records            : [per-clearance dicts]
    }
    """
    work = sequences if _normed else normalise_sequences(sequences)
    clearances_tracked = 0
    won = 0
    danger_resets = 0
    recovery_distances = []
    records = []

    for seq in work:
        defending_id = seq["defending_team_id"]
        events = seq["events"]
        if not events:
            continue

        # Find first clearance by defending team within the sequence
        clearance_idx = None
        clearance_t = None
        for idx, e in enumerate(events):
            if (e.get("typeId") == EVENT_CLEARANCE
                    and e.get("contestantId") == defending_id):
                clearance_idx = idx
                clearance_t = _secs(
                    int(e.get("timeMin", 0)), int(e.get("timeSec", 0))
                )
                break

        if clearance_idx is None:
            continue

        clearances_tracked += 1
        clr_x = float(events[clearance_idx].get("x", 50))
        clr_y = float(events[clearance_idx].get("y", 50))

        # Find next possession event after clearance within window
        second_ball_winner = None
        second_event = None
        for e in events[clearance_idx + 1:]:
            et = _secs(int(e.get("timeMin", 0)), int(e.get("timeSec", 0)))
            if et - clearance_t > window:
                break
            tid = e.get("typeId")
            if tid in {EVENT_PASS, EVENT_BALL_RECOVERY, EVENT_TACKLE,
                       EVENT_CLEARANCE, EVENT_INTERCEPTION} | set(SHOT_TYPE_IDS):
                second_ball_winner = e.get("contestantId")
                second_event = e
                break

        if second_ball_winner is None:
            # No clear second-ball winner in window
            continue

        won_it = (second_ball_winner == defending_id)
        if won_it:
            won += 1

        # Recovery distance from goal (defending goal at x≈100)
        rec_x = float(second_event.get("x", clr_x)) if second_event else clr_x
        dist_from_goal = abs(100 - rec_x)   # lower = more dangerous
        recovery_distances.append(dist_from_goal)

        # Danger reset: opponent wins second ball within 30m of goal
        if not won_it and dist_from_goal < 30:
            danger_resets += 1

        records.append({
            "minute": seq["minute"],
            "clearance_x": clr_x,
            "clearance_y": clr_y,
            "won_second_ball": won_it,
            "recovery_dist_from_goal": round(dist_from_goal, 1),
            "danger_reset": not won_it and dist_from_goal < 30,
        })

    n = clearances_tracked
    avg_dist = round(sum(recovery_distances) / len(recovery_distances), 1) \
        if recovery_distances else 0.0

    return {
        "clearances_tracked": n,
        "won_second_ball": won,
        "lost_second_ball": n - won,
        "second_ball_rate": round(won / n, 3) if n else 0,
        "avg_recovery_dist": avg_dist,
        "danger_resets": danger_resets,
        "records": records,
    }


# ── Side-of-field danger analysis ────────────────────────────────────────────

def compute_side_danger(sequences: list[dict]) -> dict:
    """Compute danger metrics broken down by which side the corner came from.

    Sequences are normalised first so the defended goal is always at x=100.
    'Left' / 'Right' refers to which side of the defended goal the corner
    is delivered from (corner_y in normalised coords).

    Returns per-side stats: shots, goals, clearances, dangerous contacts.
    """
    normed = normalise_sequences(sequences)
    sides = {
        "Left":   {"corners": 0, "shots": 0, "goals": 0, "clearances": 0, "danger": 0},
        "Right":  {"corners": 0, "shots": 0, "goals": 0, "clearances": 0, "danger": 0},
        "Centre": {"corners": 0, "shots": 0, "goals": 0, "clearances": 0, "danger": 0},
    }

    for seq in normed:
        cy = seq["corner_y"]
        side = "Left" if cy < 40 else ("Right" if cy > 60 else "Centre")
        sides[side]["corners"] += 1

        for e in seq["events"]:
            tid = e.get("typeId")
            if tid in SHOT_TYPE_IDS:
                sides[side]["shots"] += 1
                sides[side]["danger"] += 1
            if tid == EVENT_GOAL:
                sides[side]["goals"] += 1
                sides[side]["danger"] += 1
            if tid == EVENT_CLEARANCE and e.get("contestantId") == seq["defending_team_id"]:
                sides[side]["clearances"] += 1

    # Compute shot rate per side
    for s in sides.values():
        n = s["corners"]
        s["shot_rate"] = round(s["shots"] / n, 3) if n else 0
        s["danger_rate"] = round(s["danger"] / n, 3) if n else 0

    return sides


# ── Player touch network after corners ────────────────────────────────────────

def build_touch_network(sequences: list[dict], name_map: dict[str, str]) -> dict:
    """Build a player-to-player interaction graph from corner sequences.

    Sequences are normalised first so all positions are shown with the
    defended goal at x=100 (consistent orientation across all matches).

    An edge A→B means A's event was immediately followed by B's event.

    Returns
    -------
    {
        nodes : {player_id: {name, x, y, touches, team_id}},
        edges : [(from_id, to_id, weight)],
    }
    """
    normed = normalise_sequences(sequences)
    nodes: dict[str, dict] = {}
    edge_counts: dict[tuple, int] = {}

    for seq in normed:
        events = seq["events"]
        prev_pid = seq["opponent_id"]   # start from "the corner taker"

        for e in events:
            pid = e.get("playerId", "")
            if not pid:
                continue
            tid = e.get("contestantId", "")

            if pid not in nodes:
                nodes[pid] = {
                    "name": name_map.get(pid, e.get("playerName", pid)),
                    "x": float(e.get("x", 50)),
                    "y": float(e.get("y", 50)),
                    "touches": 0,
                    "team_id": tid,
                    "x_sum": 0.0,
                    "y_sum": 0.0,
                }
            nodes[pid]["touches"] += 1
            nodes[pid]["x_sum"] += float(e.get("x", 50))
            nodes[pid]["y_sum"] += float(e.get("y", 50))

            if prev_pid and prev_pid != pid:
                key = (prev_pid, pid)
                edge_counts[key] = edge_counts.get(key, 0) + 1

            prev_pid = pid

    # Average positions
    for pid, node in nodes.items():
        t = node["touches"]
        node["x"] = round(node["x_sum"] / t, 1) if t else 50
        node["y"] = round(node["y_sum"] / t, 1) if t else 50

    edges = [
        (from_id, to_id, count)
        for (from_id, to_id), count in edge_counts.items()
        if count >= 1
    ]

    return {"nodes": nodes, "edges": edges}


# ── Season-level aggregation (scans partidos/) ───────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Analysing corner sequences…")
def load_season_corner_defense(
    league: str,
    season: str,
    team_id: str,
    stage_filter: str = "",
    mode: str = "defend",
) -> dict:
    """Scan all season match files and aggregate corner data.

    Parameters
    ----------
    mode : "defend" → analyse opponent corners (team defends)
           "attack" → analyse team's own corners (team attacks)

    Returns
    -------
    {
        first_contact  : dict from compute_first_contact_index(),
        delivery       : dict from compute_delivery_zones(),
        second_ball    : dict from compute_second_ball_control(),
        side_danger    : dict from compute_side_danger(),
        touch_network  : dict from build_touch_network(),
        all_sequences  : list[dict],  raw sequences for per-match drill-down
        match_index    : [(match_id, label, n_corners)],
        mode           : str  — "defend" | "attack"
    }
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return _empty_result()

    all_seqs: list[dict] = []
    match_index: list[tuple] = []
    name_map: dict[str, str] = {}

    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        home_id = info["home_id"]
        away_id = info["away_id"]

        if team_id not in (home_id, away_id):
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue

        is_home = team_id == home_id
        opponent_id = away_id if is_home else home_id
        events = raw.get("liveData", {}).get("event", [])

        # Build player name map from this match
        for e in events:
            pid = e.get("playerId", "")
            pname = e.get("playerName", "")
            if pid and pname:
                name_map[pid] = pname

        seqs = extract_corner_sequences(events, team_id, opponent_id, mode=mode)

        label = (f"MD {info['matchday']} — "
                 f"{info['home_team']} {info['home_score']}-{info['away_score']} "
                 f"{info['away_team']}")
        match_index.append((info["match_id"], label, len(seqs)))

        for s in seqs:
            s["match_label"] = label
            s["match_id"] = info["match_id"]

        all_seqs.extend(seqs)

    if not all_seqs:
        return _empty_result()

    return {
        "first_contact":  compute_first_contact_index(all_seqs),
        "delivery":       compute_delivery_zones(all_seqs),
        "second_ball":    compute_second_ball_control(all_seqs),
        "side_danger":    compute_side_danger(all_seqs),
        "touch_network":  build_touch_network(all_seqs, name_map),
        "all_sequences":  all_seqs,
        "match_index":    match_index,
        "name_map":       name_map,
        "mode":           mode,
        "goals":          sum(1 for s in all_seqs if s.get("led_to_goal")),
        "shots":          sum(1 for s in all_seqs if s.get("led_to_shot")),
    }


def _empty_result() -> dict:
    return {
        "first_contact": {}, "delivery": {}, "second_ball": {},
        "side_danger": {}, "touch_network": {}, "all_sequences": [],
        "match_index": [], "name_map": {}, "mode": "defend",
        "goals": 0, "shots": 0,
    }
