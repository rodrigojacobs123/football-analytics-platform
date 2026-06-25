from __future__ import annotations
"""Team shape — Stretch Index & last-line compactness from average positions.

`processing/formations.py` already gives a defensive *line height* (a single
x-value), but nothing about the *shape* of the block — and shape is what
distinguishes a genuinely compact line from one that is merely deep.  This
module adds two literature-backed, event-tractable numbers:

  • **Stretch Index** = area of the convex hull of the four deepest outfielders
    (the back line).  Small = compact last line; large = stretched / exposed.
  • **Last-line exposure** = mean distance from the three most advanced
    attackers to their nearest of those four defenders — how much space the
    forwards are leaving in front of the back line.

Both are built from each player's *average position* over a match
(`tactical_positions.average_player_positions`), so they are an **event-data
approximation** of the true (tracking) compactness: they capture structural
tendency, not instantaneous shape.  Coordinates are the usual normalised 0-100
(x = depth, own goal 0 → opponent goal 100; y = width).

Pure pandas/Python + scipy; no Streamlit in the core functions.
"""

from statistics import mean

from processing.tactical_positions import average_player_positions


def _hull_area(points: list[tuple[float, float]]) -> float:
    """Convex-hull area of 2-D points in normalised 0-100² units.

    Falls back to the shoelace area of the raw points if scipy is unavailable
    or the points are degenerate (collinear / < 3 distinct).
    """
    if len(points) < 3:
        return 0.0
    try:
        import numpy as np
        from scipy.spatial import ConvexHull
        arr = np.array(points, dtype=float)
        # ConvexHull throws on collinear/degenerate input — guard it.
        return float(ConvexHull(arr).volume)   # 2-D "volume" == area
    except Exception:
        # Shoelace on the points as given (lower bound on the true hull area).
        n = len(points)
        s = 0.0
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0


def _nearest_dist(p: tuple[float, float],
                  others: list[tuple[float, float]]) -> float:
    return min(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for q in others)


def shape_from_positions(positions: dict[str, tuple[float, float]]) -> dict:
    """Compute team-shape metrics from a {player_id: (x, y)} average-position map.

    The deepest player (lowest x) is treated as the goalkeeper and dropped; the
    next four deepest outfielders form the back line, the three highest-x the
    attackers.  Returns ``{}`` if fewer than 6 positioned players are available.
    """
    if not positions or len(positions) < 6:
        return {}

    # Sort outfielders by depth; drop the GK (single deepest player).
    ordered = sorted(positions.items(), key=lambda kv: kv[1][0])
    gk_id = ordered[0][0]
    outfield = ordered[1:]

    back4 = outfield[:4]
    back4_pts = [xy for _, xy in back4]
    attackers = outfield[-3:]
    att_pts = [xy for _, xy in attackers]

    stretch = _hull_area(back4_pts)
    exposure = mean(_nearest_dist(a, back4_pts) for a in att_pts) if back4_pts else 0.0
    line_height = mean(p[0] for p in back4_pts)
    block_width = (max(p[1] for p in back4_pts) - min(p[1] for p in back4_pts))

    back4_ids = {pid for pid, _ in back4}
    att_ids = {pid for pid, _ in attackers}
    players = []
    for pid, (x, y) in positions.items():
        if pid == gk_id:
            role = "GK"
        elif pid in back4_ids:
            role = "DEF"
        elif pid in att_ids:
            role = "ATT"
        else:
            role = "MID"
        players.append({"player_id": pid, "x": round(x, 2),
                        "y": round(y, 2), "role": role})

    return {
        "stretch_index": round(stretch, 1),
        "exposure": round(exposure, 1),
        "line_height": round(line_height, 1),
        "block_width": round(block_width, 1),
        "players": players,
        "n_players": len(positions),
    }


def compute_team_shape(events: list[dict], team_id: str) -> dict:
    """Single-match team shape from a team's average positions (pre-first-sub)."""
    if not events or not team_id:
        return {}
    return shape_from_positions(average_player_positions(events, team_id))


# ── Season aggregation (cached deep tier) ────────────────────────────────────
import json

import streamlit as st

from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Computing team shape & Stretch Index…")
def compute_season_team_shape(league: str, season: str, team_id: str,
                              stage_filter: str = "") -> dict:
    """Season team shape: average each player's position across matches, then
    derive the Stretch Index / exposure once from the averaged positions.

    Accumulating per-player positions (rather than averaging the scalar metrics)
    keeps the returned ``players`` list, the hull drawn in the viz, and the
    headline numbers mutually consistent.  Returns ``{}`` if no matches found.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    acc: dict[str, list[tuple[float, float]]] = {}
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
        if team_id not in (info["home_id"], info["away_id"]):
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue
        events = raw.get("liveData", {}).get("event", [])
        pos = average_player_positions(events, team_id)
        matches += 1
        for pid, xy in pos.items():
            acc.setdefault(pid, []).append(xy)

    if matches == 0:
        return {}

    # Keep players who appeared in a meaningful share of matches; average them.
    min_apps = max(2, matches // 3)
    avg_pos = {
        pid: (mean(p[0] for p in locs), mean(p[1] for p in locs))
        for pid, locs in acc.items() if len(locs) >= min_apps
    }
    shape = shape_from_positions(avg_pos)
    if shape:
        shape["matches"] = matches
    return shape
