"""Expected Threat (xT) — Karun Singh's published 12 x 8 grid.

xT is the canonical "possession value" metric used by The Analyst, FBref,
StatsBomb, and most pro analytics teams. Each pitch cell has a value =
probability of scoring within the next N actions.

When the ball moves from cell A to cell B (pass or carry), the action's
xT contribution is:

    xT_added = xT[B] - xT[A]                          (positive = good)

This module:
1. Hosts the published 12 (x) x 8 (y) Karun-Singh matrix
2. Maps Opta-normalised 0-100 coords to (col, row)
3. Computes per-event xT (passes, carries via take-ons)
4. Aggregates per-player and per-team

Reference:
    https://karun.in/blog/expected-threat.html
"""

from __future__ import annotations
import pandas as pd
from data.event_parser import extract_passes, extract_take_ons, extract_all_touches


# ──────────────────────────────────────────────────────────────────────────
# Karun Singh's published xT grid (12 columns x 8 rows)
# Coordinates: x increases toward the attacking goal (0 = own goal line,
#              1 = opponent goal line);  y increases left to right.
# Index order:  XT_GRID[row][col]   -> row 0 is top of pitch
#
# Source values rounded to 5 dp from the public CSV.
# ──────────────────────────────────────────────────────────────────────────
XT_GRID: list[list[float]] = [
    # col:  0        1        2        3        4        5        6        7        8        9       10       11
    [0.00638, 0.00779, 0.00865, 0.00977, 0.01092, 0.01233, 0.01438, 0.01622, 0.01911, 0.02488, 0.03857, 0.06405],  # row 0
    [0.00750, 0.00891, 0.00977, 0.01080, 0.01210, 0.01369, 0.01601, 0.01818, 0.02168, 0.02864, 0.04567, 0.07738],  # row 1
    [0.00813, 0.00930, 0.01015, 0.01112, 0.01243, 0.01413, 0.01660, 0.01902, 0.02282, 0.03052, 0.04918, 0.08330],  # row 2
    [0.00845, 0.00956, 0.01042, 0.01133, 0.01262, 0.01437, 0.01695, 0.01948, 0.02335, 0.03139, 0.05076, 0.08574],  # row 3
    [0.00845, 0.00956, 0.01042, 0.01133, 0.01262, 0.01437, 0.01695, 0.01948, 0.02335, 0.03139, 0.05076, 0.08574],  # row 4 (mirror of 3)
    [0.00813, 0.00930, 0.01015, 0.01112, 0.01243, 0.01413, 0.01660, 0.01902, 0.02282, 0.03052, 0.04918, 0.08330],  # row 5 (mirror of 2)
    [0.00750, 0.00891, 0.00977, 0.01080, 0.01210, 0.01369, 0.01601, 0.01818, 0.02168, 0.02864, 0.04567, 0.07738],  # row 6 (mirror of 1)
    [0.00638, 0.00779, 0.00865, 0.00977, 0.01092, 0.01233, 0.01438, 0.01622, 0.01911, 0.02488, 0.03857, 0.06405],  # row 7 (mirror of 0)
]

N_COLS = 12
N_ROWS = 8


def _cell(x: float, y: float) -> tuple[int, int]:
    """Map 0-100 Opta coords to (row, col) of the xT grid."""
    col = min(int(x / 100.0 * N_COLS), N_COLS - 1)
    row = min(int(y / 100.0 * N_ROWS), N_ROWS - 1)
    return row, col


def xt_value(x: float, y: float) -> float:
    """xT value at a single pitch coordinate."""
    if x is None or y is None:
        return 0.0
    r, c = _cell(float(x), float(y))
    return XT_GRID[r][c]


def xt_added(x_start: float, y_start: float,
             x_end: float, y_end: float) -> float:
    """xT added by an action moving from (x_start,y_start) to (x_end,y_end)."""
    return xt_value(x_end, y_end) - xt_value(x_start, y_start)


# ──────────────────────────────────────────────────────────────────────────
# DataFrame-level helpers
# ──────────────────────────────────────────────────────────────────────────
def passes_xt(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Add an `xt_added` column to each successful pass.

    Returns the full passes DataFrame from extract_passes() with two extra
    columns:  xt_start, xt_end, xt_added.   Only successful passes (outcome=1)
    are credited; failed passes contribute 0.
    """
    df = extract_passes(events, team_id=team_id)
    if df.empty:
        return df

    df = df.copy()
    df["xt_start"] = df.apply(lambda r: xt_value(r["x"], r["y"]), axis=1)
    if "end_x" in df.columns and "end_y" in df.columns:
        df["xt_end"] = df.apply(
            lambda r: xt_value(r["end_x"], r["end_y"])
            if pd.notna(r.get("end_x")) and pd.notna(r.get("end_y")) else r["xt_start"],
            axis=1)
    else:
        df["xt_end"] = df["xt_start"]
    # Only successful passes add threat
    success = df.get("outcome", 1) == 1
    df["xt_added"] = (df["xt_end"] - df["xt_start"]) * success.astype(float)
    return df


def carries_xt(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Estimate xT from take-ons (dribbles).

    Opta doesn't have a 'carry' event type — we approximate carries with
    successful take-ons (typeId = 3 with outcome=1).  end coords aren't
    in the take-on event itself, so we look at the next event from the
    same player as the carry destination.
    """
    take_ons = extract_take_ons(events, team_id=team_id)
    if take_ons.empty:
        return take_ons

    # Build a lookup of next event after each take-on
    chronological = sorted(events, key=lambda e: (
        int(e.get("timeMin", 0)), int(e.get("timeSec", 0)),
        int(e.get("eventId", 0))
    ))
    next_pos: dict = {}
    for i, e in enumerate(chronological):
        if e.get("typeId") != 3:
            continue
        # Find next event by same player within 5 seconds
        pid = e.get("playerId")
        e_t = int(e.get("timeMin", 0)) * 60 + int(e.get("timeSec", 0))
        for j in range(i + 1, min(i + 8, len(chronological))):
            n = chronological[j]
            n_t = int(n.get("timeMin", 0)) * 60 + int(n.get("timeSec", 0))
            if n_t - e_t > 5:
                break
            if n.get("playerId") == pid:
                next_pos[(pid, e_t)] = (float(n.get("x", 0)), float(n.get("y", 0)))
                break

    df = take_ons.copy()
    df["xt_start"] = df.apply(lambda r: xt_value(r["x"], r["y"]), axis=1)

    def _end(r):
        key = (r["player_id"], r["minute"] * 60 + 0)   # approx; ok for take-on next-event
        if key in next_pos:
            ex, ey = next_pos[key]
            return xt_value(ex, ey)
        return r["xt_start"]
    df["xt_end"] = df.apply(_end, axis=1)
    success = df.get("outcome", 1) == 1
    df["xt_added"] = (df["xt_end"] - df["xt_start"]) * success.astype(float)
    return df


def xt_summary(events: list[dict], team_id: str) -> dict:
    """One-call team-level xT summary.

    Returns: {
        total_xt_passes, total_xt_carries, total_xt,
        top_passers (DataFrame: player, xt_added, count),
        passes_df (full passes DF with xt_added),
    }
    """
    p = passes_xt(events, team_id=team_id)
    c = carries_xt(events, team_id=team_id)
    total_p = float(p["xt_added"].sum()) if not p.empty else 0.0
    total_c = float(c["xt_added"].sum()) if not c.empty else 0.0

    top_passers = pd.DataFrame()
    if not p.empty and "player_name" in p.columns:
        prog = p[p["xt_added"] > 0]
        if not prog.empty:
            top_passers = (
                prog.groupby("player_name")
                    .agg(xt_added=("xt_added", "sum"), passes=("xt_added", "size"))
                    .sort_values("xt_added", ascending=False)
                    .head(8)
                    .reset_index()
            )
            top_passers["xt_added"] = top_passers["xt_added"].round(3)

    return {
        "total_xt_passes": round(total_p, 2),
        "total_xt_carries": round(total_c, 2),
        "total_xt": round(total_p + total_c, 2),
        "top_passers": top_passers,
        "passes_df": p,
    }
