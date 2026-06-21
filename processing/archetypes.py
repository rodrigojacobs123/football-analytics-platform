from __future__ import annotations
"""Tactical player archetypes — behavioural classification from per-90 stats.

These archetypes are NOT the FIFA-style PAC/SHO/PAS ratings already in
`processing/player_ratings.py`.  They describe HOW a player plays, not how
good they are:

  Forward   → 5 archetypes
  Midfielder → 5 archetypes
  Defender  → 5 archetypes
  Goalkeeper → 3 archetypes

Each archetype is defined by a set of per-90 signals.  Each signal is
normalised to a 0-100 league percentile so thresholds are position-agnostic.

Architecture
------------
1.  `per90()` — normalise raw totals by minutes played.
2.  `percentile_rank()` — position-group percentile for each signal.
3.  `classify_archetype()` — match signal pattern to archetype rules.
4.  `assign_archetypes()` — apply to a whole squad DataFrame.
5.  `compute_archetype_compatibility()` — for each player, measure how
    their key metrics change across their different teammate-archetype contexts.
"""

import pandas as pd
import numpy as np


# ── Per-90 signal definitions ─────────────────────────────────────────────────
# Maps short signal name → raw column in the player stats CSV.
# Only columns that exist in jugadores_seasonstats.csv are used.

SIGNALS = {
    # Attacking
    "goals_p90":          "Goals",
    "shots_p90":          "Total Shots",
    "shots_on_p90":       "Shots On Target ( inc goals )",
    "key_passes_p90":     "Key Passes (Attempt Assists)",
    "box_touches_p90":    "Total Touches In Opposition Box",
    "final3rd_p90":       "Final Third Touches",
    "dribbles_p90":       "Successful Dribbles",
    "big_chances_p90":    "Total Big Chances Scored",
    # Pressing / defensive
    "recoveries_p90":     "Recoveries",
    "tackles_won_p90":    "Tackles Won",
    "interceptions_p90":  "Interceptions",
    "clearances_p90":     "Total Clearances",
    "fouls_p90":          "Total Fouls Conceded",
    # Passing / carrying
    "passes_p90":         "Total Passes",
    "pass_acc_p90":       "Total Successful Passes ( Excl Crosses & Corners ) ",
    "prog_carries_p90":   "Progressive Carries",
    "long_passes_p90":    "Successful Long Passes",
    "opp_half_pass_p90":  "Successful Passes Opposition Half",
    "own_half_pass_p90":  "Successful Passes Own Half",
    # Aerial
    "aerials_won_p90":    "Aerial Duels won",
    "aerials_p90":        "Aerial Duels",
    # Width
    "left_passes_p90":    "Leftside Passes",
    "right_passes_p90":   "Rightside Passes",
    "crosses_p90":        "Successful Crosses open play",
    # GK
    "saves_p90":          "Saves Made",
    "gk_dist_p90":        "GK Successful Distribution",
    "catches_p90":        "Catches",
    "punches_p90":        "Punches",
}

MIN_MINUTES = 450   # minimum minutes played to receive an archetype label


# ── Archetype catalogue ───────────────────────────────────────────────────────
# Each archetype has:
#   position_groups : which Opta position labels this applies to
#   signals         : {signal_name: (min_percentile, max_percentile | None)}
#                     ALL listed signals must be satisfied for a match.
#   priority        : lower = checked first (more specific archetypes first)
#   color           : display colour
#   icon            : emoji

ARCHETYPES: list[dict] = [

    # ── FORWARDS ─────────────────────────────────────────────────────────────
    {
        "name": "Clinical Finisher",
        "position_groups": ["Forward", "Attacker"],
        "priority": 1,
        "icon": "🎯",
        "color": "#DA291C",
        "description": "Penalty-box predator. High shots, high conversion, stays central.",
        "signals": {
            "shots_p90":     (60, None),
            "big_chances_p90": (50, None),
            "box_touches_p90": (55, None),
        },
    },
    {
        "name": "Press Machine",
        "position_groups": ["Forward", "Attacker"],
        "priority": 2,
        "icon": "⚡",
        "color": "#FF6B35",
        "description": "High-energy forward who presses relentlessly and wins the ball high up.",
        "signals": {
            "recoveries_p90":    (65, None),
            "fouls_p90":         (55, None),
        },
    },
    {
        "name": "Target Man",
        "position_groups": ["Forward", "Attacker"],
        "priority": 3,
        "icon": "🏋️",
        "color": "#8B4513",
        "description": "Aerial focal point. Wins headers, holds up play, creates for others.",
        "signals": {
            "aerials_won_p90":   (65, None),
            "box_touches_p90":   (45, None),
        },
    },
    {
        "name": "Wide Dribbler",
        "position_groups": ["Forward", "Attacker"],
        "priority": 4,
        "icon": "🏃",
        "color": "#9C27B0",
        "description": "Takes players on from wide positions, cuts inside or crosses.",
        "signals": {
            "dribbles_p90":  (65, None),
            "crosses_p90":   (40, None),
        },
    },
    {
        "name": "Shadow Striker",
        "position_groups": ["Forward", "Attacker"],
        "priority": 5,
        "icon": "👻",
        "color": "#3F51B5",
        "description": "Drops deep, links play, creates more than he scores. Second striker.",
        "signals": {
            "key_passes_p90":  (55, None),
            "final3rd_p90":    (55, None),
            "shots_p90":       (None, 55),   # relatively fewer shots
        },
    },

    # ── MIDFIELDERS ──────────────────────────────────────────────────────────
    {
        "name": "Deep Playmaker",
        "position_groups": ["Midfielder"],
        "priority": 1,
        "icon": "🧠",
        "color": "#1565C0",
        "description": "Dictates tempo from deep. High pass volume, high accuracy, rarely loses ball.",
        "signals": {
            "passes_p90":       (65, None),
            "own_half_pass_p90":(60, None),
            "pass_acc_p90":     (60, None),
        },
    },
    {
        "name": "Box-to-Box Engine",
        "position_groups": ["Midfielder"],
        "priority": 2,
        "icon": "⚙️",
        "color": "#00838F",
        "description": "Covers ground in both directions. Tackles, carries, and arrives in box.",
        "signals": {
            "tackles_won_p90":  (55, None),
            "prog_carries_p90": (55, None),
            "recoveries_p90":   (50, None),
        },
    },
    {
        "name": "Press Trigger",
        "position_groups": ["Midfielder"],
        "priority": 3,
        "icon": "🔥",
        "color": "#E65100",
        "description": "High-intensity presser who wins the ball in the opponent's half.",
        "signals": {
            "recoveries_p90":     (65, None),
            "interceptions_p90":  (55, None),
            "opp_half_pass_p90":  (50, None),
        },
    },
    {
        "name": "Half-Space Connector",
        "position_groups": ["Midfielder"],
        "priority": 4,
        "icon": "🔗",
        "color": "#558B2F",
        "description": "Operates in half-spaces between lines. Progressive carrier and creator.",
        "signals": {
            "key_passes_p90":   (55, None),
            "prog_carries_p90": (60, None),
            "final3rd_p90":     (50, None),
        },
    },
    {
        "name": "Recycler",
        "position_groups": ["Midfielder"],
        "priority": 5,
        "icon": "🔄",
        "color": "#78909C",
        "description": "Keeps possession moving. High pass volume, mostly sideways or backwards.",
        "signals": {
            "passes_p90":       (60, None),
            "own_half_pass_p90":(65, None),
            "prog_carries_p90": (None, 45),
        },
    },

    # ── DEFENDERS ────────────────────────────────────────────────────────────
    {
        "name": "Ball-Playing CB",
        "position_groups": ["Defender"],
        "priority": 1,
        "icon": "🎭",
        "color": "#1976D2",
        "description": "Builds from the back. Comfortable in possession, picks long passes.",
        "signals": {
            "passes_p90":       (55, None),
            "long_passes_p90":  (55, None),
            "prog_carries_p90": (45, None),
        },
    },
    {
        "name": "Aerial Colossus",
        "position_groups": ["Defender"],
        "priority": 2,
        "icon": "🦅",
        "color": "#4A148C",
        "description": "Dominates in the air at both ends. Wins headers and clears danger.",
        "signals": {
            "aerials_won_p90":  (65, None),
            "clearances_p90":   (55, None),
        },
    },
    {
        "name": "Aggressive Marker",
        "position_groups": ["Defender"],
        "priority": 3,
        "icon": "🛡️",
        "color": "#BF360C",
        "description": "Man-marker who wins duels aggressively. High tackle rate, physical.",
        "signals": {
            "tackles_won_p90":  (60, None),
            "fouls_p90":        (55, None),
        },
    },
    {
        "name": "Carrying Fullback",
        "position_groups": ["Defender"],
        "priority": 4,
        "icon": "🚀",
        "color": "#00695C",
        "description": "Attacks down the flank. Progressive carries, overlapping runs, crosses.",
        "signals": {
            "prog_carries_p90": (60, None),
            "crosses_p90":      (50, None),
            "opp_half_pass_p90":(50, None),
        },
    },
    {
        "name": "Press-Resistant CB",
        "position_groups": ["Defender"],
        "priority": 5,
        "icon": "🧱",
        "color": "#37474F",
        "description": "Stays calm under pressure. Rarely loses the ball, high duel win rate.",
        "signals": {
            "dribbles_p90":     (40, None),
            "pass_acc_p90":     (60, None),
            "clearances_p90":   (45, None),
        },
    },

    # ── GOALKEEPERS ──────────────────────────────────────────────────────────
    {
        "name": "Sweeper Keeper",
        "position_groups": ["Goalkeeper"],
        "priority": 1,
        "icon": "🧤",
        "color": "#00ACC1",
        "description": "Comes off line to claim crosses and sweep loose balls behind defence.",
        "signals": {
            "catches_p90":   (55, None),
            "gk_dist_p90":   (50, None),
        },
    },
    {
        "name": "Pure Shot Stopper",
        "position_groups": ["Goalkeeper"],
        "priority": 2,
        "icon": "🚫",
        "color": "#F57F17",
        "description": "Exceptional reflexes. Saves the unsaveable, limited with feet.",
        "signals": {
            "saves_p90":     (55, None),
            "catches_p90":   (None, 50),  # fewer claims = stays on line
        },
    },
    {
        "name": "Distribution GK",
        "position_groups": ["Goalkeeper"],
        "priority": 3,
        "icon": "📡",
        "color": "#4CAF50",
        "description": "Plays out from the back. Key to build-up, accurate with both feet.",
        "signals": {
            "gk_dist_p90":   (60, None),
            "punches_p90":   (None, 50),  # fewer punches = prefers distribution
        },
    },
]


# ── Per-90 normalisation ──────────────────────────────────────────────────────

def compute_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-90 signal columns to a player stats DataFrame.

    Requires 'Time Played' (minutes) column.
    """
    out = df.copy()
    minutes = out.get("Time Played", pd.Series(dtype=float)).fillna(0).clip(lower=1)

    for signal, col in SIGNALS.items():
        if col in out.columns:
            out[signal] = (out[col].fillna(0) / minutes * 90).round(3)
        else:
            out[signal] = 0.0

    return out


def compute_percentiles(df: pd.DataFrame, position: str) -> pd.DataFrame:
    """Return percentile ranks (0–100) for each signal within a position group.

    Percentile is computed across ALL players of the same position group so
    thresholds in ARCHETYPES are position-independent.
    """
    group = df[df["posicion"] == position].copy()
    for signal in SIGNALS:
        if signal in group.columns:
            group[f"{signal}_pct"] = (
                group[signal].rank(pct=True, na_option="bottom") * 100
            ).round(1)
        else:
            group[f"{signal}_pct"] = 50.0
    return group


# ── Archetype classification ──────────────────────────────────────────────────

def _matches_archetype(row: pd.Series, archetype: dict) -> bool:
    """Return True if a player row satisfies ALL signal thresholds."""
    for signal, (lo, hi) in archetype["signals"].items():
        pct_col = f"{signal}_pct"
        val = row.get(pct_col, 50)
        if lo is not None and val < lo:
            return False
        if hi is not None and val > hi:
            return False
    return True


def classify_player(row: pd.Series) -> dict | None:
    """Return the best-matching archetype dict for a player row, or None."""
    pos = row.get("posicion", "")
    minutes = row.get("Time Played", 0)
    if minutes < MIN_MINUTES:
        return None

    # Try archetypes in priority order, filtered to this position
    candidates = [a for a in ARCHETYPES if pos in a["position_groups"]]
    candidates.sort(key=lambda a: a["priority"])

    for arch in candidates:
        if _matches_archetype(row, arch):
            return arch
    return None


def assign_archetypes(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'archetype', 'arch_icon', 'arch_color', 'arch_desc' columns.

    Input df must already have per-90 and percentile columns
    (from compute_per90 + compute_percentiles).
    """
    positions = df["posicion"].dropna().unique()
    frames = []

    for pos in positions:
        sub = compute_percentiles(df, pos)
        rows = []
        for _, row in sub.iterrows():
            arch = classify_player(row)
            row = row.copy()
            if arch:
                row["archetype"]  = arch["name"]
                row["arch_icon"]  = arch["icon"]
                row["arch_color"] = arch["color"]
                row["arch_desc"]  = arch["description"]
            else:
                row["archetype"]  = "Undefined"
                row["arch_icon"]  = "❓"
                row["arch_color"] = "#555"
                row["arch_desc"]  = "Insufficient data or mixed profile."
            rows.append(row)
        frames.append(pd.DataFrame(rows))

    if not frames:
        return df

    result = pd.concat(frames, ignore_index=True)
    return result


# ── Archetype compatibility (how a player performs with each archetype) ────────

def compute_archetype_compatibility(
    target_player_id: str,
    squad_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
) -> pd.DataFrame:
    """For a target player, measure their key per-90 stats broken down by
    the archetypes of teammates who play in the same squad.

    Since we only have season-level stats (not per-match lineups), we
    approximate by comparing the target player's stats against squads that
    have different archetype distributions — cross-team comparison.

    Returns a DataFrame with columns:
        archetype, count_teammates, target_key_metric_avg,
        vs_league_delta, trend ('↑' / '↓' / '=')
    """
    target_rows = all_players_df[all_players_df["id"] == target_player_id]
    if target_rows.empty:
        return pd.DataFrame()

    target = target_rows.iloc[0]
    target_pos = target.get("posicion", "")
    target_team = target.get("equipo", "")

    # Key metric for the target player (based on position)
    key_metric_map = {
        "Forward":    "goals_p90",
        "Attacker":   "goals_p90",
        "Midfielder":  "key_passes_p90",
        "Defender":   "tackles_won_p90",
        "Goalkeeper": "saves_p90",
    }
    key_metric = key_metric_map.get(target_pos, "passes_p90")

    # Teammates: same team, different players
    teammates = squad_df[squad_df["equipo"] == target_team].copy()
    if "archetype" not in teammates.columns:
        return pd.DataFrame()

    target_metric_val = float(target.get(key_metric, 0))
    league_avg = all_players_df[
        all_players_df["posicion"] == target_pos
    ][key_metric].mean() if key_metric in all_players_df.columns else 0

    # Group teammates by archetype and see the player's metric context
    records = []
    for arch_name, group in teammates.groupby("archetype"):
        n = len(group)
        # For now: just report presence and the player's baseline
        # (True per-match context requires lineup data from partidos/)
        records.append({
            "archetype": arch_name,
            "arch_icon": group["arch_icon"].iloc[0] if "arch_icon" in group else "❓",
            "arch_color": group["arch_color"].iloc[0] if "arch_color" in group else "#555",
            "teammate_count": n,
            "player_metric": round(target_metric_val, 2),
            "league_avg": round(league_avg, 2),
            "delta_vs_league": round(target_metric_val - league_avg, 2),
            "metric_label": key_metric.replace("_p90", "").replace("_", " ").title(),
        })

    return pd.DataFrame(records).sort_values("teammate_count", ascending=False)


# ── Quick lookup helpers ──────────────────────────────────────────────────────

def archetype_by_name(name: str) -> dict | None:
    for a in ARCHETYPES:
        if a["name"] == name:
            return a
    return None


def archetypes_for_position(pos: str) -> list[dict]:
    return [a for a in ARCHETYPES if pos in a["position_groups"]]
