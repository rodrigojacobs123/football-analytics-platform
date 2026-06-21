from __future__ import annotations
"""Tactical positioning engine — canonical coordinates for every formation role.

Maps Opta's (position_row, order_in_row, formation_str) to precise pitch
coordinates using a 25-position canonical system and per-formation overrides.

Coordinate system (normalised):
  x = depth:  0 (own goal) → 100 (opponent goal)
  y = width:  0 (right touchline) → 100 (left touchline)

On a vertical pitch panel: x maps to the vertical axis (GK at bottom,
forwards at top), y maps to the horizontal axis.
"""

import warnings
from collections import defaultdict
from statistics import median

# ═══════════════════════════════════════════════════════════════════════════
# § 1  CANONICAL POSITION COORDINATES (25 StatsBomb-equivalent positions)
# ═══════════════════════════════════════════════════════════════════════════
# Editable source of truth.  Adjust any value to tune the visual layout.
# y=0 is RIGHT touchline, y=100 is LEFT touchline (Opta convention).

POSITION_COORDS: dict[int, tuple[float, float]] = {
    1:  (6,  50),   # Goalkeeper
    2:  (28, 15),   # Right Back              (right side = low y)
    3:  (22, 35),   # Right Center Back
    4:  (20, 50),   # Center Back
    5:  (22, 65),   # Left Center Back
    6:  (28, 85),   # Left Back               (left side = high y)
    7:  (45, 10),   # Right Wing Back
    8:  (45, 90),   # Left Wing Back
    9:  (42, 35),   # Right Defensive Midfield
    10: (40, 50),   # Center Defensive Midfield
    11: (42, 65),   # Left Defensive Midfield
    12: (60, 15),   # Right Midfield
    13: (58, 35),   # Right Center Midfield
    14: (56, 50),   # Center Midfield
    15: (58, 65),   # Left Center Midfield
    16: (60, 85),   # Left Midfield
    17: (78, 12),   # Right Wing
    18: (74, 35),   # Right Attacking Midfield
    19: (72, 50),   # Center Attacking Midfield
    20: (74, 65),   # Left Attacking Midfield
    21: (78, 88),   # Left Wing
    22: (88, 35),   # Right Center Forward
    23: (90, 50),   # Striker / Center Forward
    24: (88, 65),   # Left Center Forward
    25: (80, 50),   # Secondary Striker
}

POSITION_NAMES: dict[int, str] = {
    1: "GK", 2: "RB", 3: "RCB", 4: "CB", 5: "LCB", 6: "LB",
    7: "RWB", 8: "LWB",
    9: "RDM", 10: "CDM", 11: "LDM",
    12: "RM", 13: "RCM", 14: "CM", 15: "LCM", 16: "LM",
    17: "RW", 18: "RAM", 19: "CAM", 20: "LAM", 21: "LW",
    22: "RCF", 23: "ST", 24: "LCF", 25: "SS",
}


# ═══════════════════════════════════════════════════════════════════════════
# § 2  FORMATION → POSITION-ID MAPPING
# ═══════════════════════════════════════════════════════════════════════════
# For each formation string, list the canonical position IDs in Opta
# order: GK first, then outfield rows top-to-bottom, RIGHT-to-LEFT
# within each row (matching Opta's qualifier 44 order_in_row convention).
#
# Example: "4-3-3" → [1, 2,3,5,6, 9,14,11, 17,23,21]
#   Row 1 (GK):  [1]              → GK
#   Row 2 (DEF): [2, 3, 5, 6]     → RB, RCB, LCB, LB
#   Row 3 (MID): [9, 14, 11]      → RDM, CM, LDM  (or RCM, CM, LCM)
#   Row 4 (FWD): [17, 23, 21]     → RW, ST, LW

FORMATION_POSITION_IDS: dict[str, list[int]] = {
    # ── Back 4 systems ────────────────────────────────────────────────
    "4-4-2": [
        1,                  # GK
        2, 3, 5, 6,         # RB, RCB, LCB, LB
        12, 13, 15, 16,     # RM, RCM, LCM, LM
        22, 24,             # RCF, LCF
    ],
    "4-4-1-1": [
        1,
        2, 3, 5, 6,
        12, 13, 15, 16,
        25,                 # SS (behind striker)
        23,                 # ST
    ],
    "4-3-3": [
        1,
        2, 3, 5, 6,
        13, 14, 15,         # RCM, CM, LCM
        17, 23, 21,         # RW, ST, LW
    ],
    "4-2-3-1": [
        1,
        2, 3, 5, 6,
        9, 11,              # RDM, LDM
        18, 19, 20,         # RAM, CAM, LAM
        23,                 # ST
    ],
    "4-1-4-1": [
        1,
        2, 3, 5, 6,
        10,                 # CDM
        12, 13, 15, 16,     # RM, RCM, LCM, LM
        23,                 # ST
    ],
    "4-1-2-1-2": [
        1,
        2, 3, 5, 6,
        10,                 # CDM
        13, 15,             # RCM, LCM
        19,                 # CAM
        22, 24,             # RCF, LCF
    ],
    "4-5-1": [
        1,
        2, 3, 5, 6,
        12, 13, 14, 15, 16, # RM, RCM, CM, LCM, LM
        23,                 # ST
    ],
    "4-3-2-1": [
        1,
        2, 3, 5, 6,
        13, 14, 15,         # RCM, CM, LCM
        18, 20,             # RAM, LAM
        23,                 # ST
    ],
    "4-2-2-2": [
        1,
        2, 3, 5, 6,
        9, 11,              # RDM, LDM
        18, 20,             # RAM, LAM
        22, 24,             # RCF, LCF
    ],
    "4-2-4-0": [
        1,
        2, 3, 5, 6,
        9, 11,              # RDM, LDM
        17, 18, 20, 21,     # RW, RAM, LAM, LW
    ],
    "4-1-3-2": [
        1,
        2, 3, 5, 6,
        10,                 # CDM
        13, 14, 15,         # RCM, CM, LCM
        22, 24,             # RCF, LCF
    ],

    # ── Back 3 / 5 systems ────────────────────────────────────────────
    "3-4-3": [
        1,
        3, 4, 5,            # RCB, CB, LCB
        7, 13, 15, 8,       # RWB, RCM, LCM, LWB
        17, 23, 21,         # RW, ST, LW
    ],
    "3-5-2": [
        1,
        3, 4, 5,            # RCB, CB, LCB
        7, 13, 14, 15, 8,   # RWB, RCM, CM, LCM, LWB
        22, 24,             # RCF, LCF
    ],
    "3-4-2-1": [
        1,
        3, 4, 5,            # RCB, CB, LCB
        7, 13, 15, 8,       # RWB, RCM, LCM, LWB
        18, 20,             # RAM, LAM
        23,                 # ST
    ],
    "3-5-1-1": [
        1,
        3, 4, 5,
        7, 13, 14, 15, 8,
        25,                 # SS
        23,                 # ST
    ],
    "3-1-4-2": [
        1,
        3, 4, 5,
        10,                 # CDM
        12, 13, 15, 16,     # RM, RCM, LCM, LM
        22, 24,             # RCF, LCF
    ],
    "3-4-1-2": [
        1,
        3, 4, 5,
        7, 13, 15, 8,
        19,                 # CAM
        22, 24,             # RCF, LCF
    ],

    # ── Back 5 explicit ──────────────────────────────────────────────
    "5-3-2": [
        1,
        7, 3, 4, 5, 8,      # RWB, RCB, CB, LCB, LWB
        13, 14, 15,          # RCM, CM, LCM
        22, 24,              # RCF, LCF
    ],
    "5-4-1": [
        1,
        7, 3, 4, 5, 8,
        12, 13, 15, 16,
        23,
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# § 3  PER-FORMATION COORDINATE OVERRIDES
# ═══════════════════════════════════════════════════════════════════════════
# Fine-tune individual positions within a specific formation.
# Example: push wing-backs higher in 3-5-2 than the default WB depth.

FORMATION_OVERRIDES: dict[str, dict[int, tuple[float, float]]] = {
    "3-5-2": {
        7:  (50, 10),   # RWB pushed higher in 3-5-2
        8:  (50, 90),   # LWB pushed higher in 3-5-2
    },
    "5-3-2": {
        7:  (32, 10),   # RWB deeper in 5-3-2 (defensive)
        8:  (32, 90),   # LWB deeper in 5-3-2
    },
    "5-4-1": {
        7:  (32, 10),
        8:  (32, 90),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# § 4  PURE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def resolve_player_xy(position_id: int, formation: str = "") -> tuple[float, float]:
    """Return (x, y) for a canonical position ID, checking formation overrides first."""
    if formation and formation in FORMATION_OVERRIDES:
        overrides = FORMATION_OVERRIDES[formation]
        if position_id in overrides:
            return overrides[position_id]

    if position_id in POSITION_COORDS:
        return POSITION_COORDS[position_id]

    warnings.warn(f"Unknown position_id {position_id}, defaulting to center")
    return (50.0, 50.0)


def _formation_total(formation_str: str) -> int:
    """Sum of digits in a formation string like '4-3-3' → 10."""
    try:
        return sum(int(x) for x in formation_str.split("-"))
    except (ValueError, AttributeError):
        return 0


def get_formation_positions(
    formation: dict,
    player_names: dict[str, str] | None = None,
) -> list[dict]:
    """Map an Opta formation dict to positioned players using POSITION_COORDS.

    Parameters
    ----------
    formation : dict from extract_formation() with keys:
        formation_str, starters [{player_id, shirt, position_row, order_in_row}]
    player_names : {player_id: display_name}

    Returns
    -------
    List of dicts: [{player_id, player_name, jersey_number, position_id,
                     position_name, x, y}]
    """
    if not formation:
        return []

    player_names = player_names or {}
    form_str = formation.get("formation_str", "")
    starters = formation.get("starters", [])

    if not starters:
        return []

    # Try to use the formation-specific position ID mapping
    position_ids = FORMATION_POSITION_IDS.get(form_str)

    if position_ids and len(position_ids) == len(starters):
        return _map_with_position_ids(starters, position_ids, form_str, player_names)

    # Fallback: derive positions from formation string + row structure
    return _map_from_rows(starters, form_str, player_names)


def _map_with_position_ids(
    starters: list[dict],
    position_ids: list[int],
    formation_str: str,
    player_names: dict[str, str],
) -> list[dict]:
    """Map starters to position IDs using the FORMATION_POSITION_IDS table."""
    # Sort starters by (position_row, order_in_row) to match the canonical order
    sorted_starters = sorted(starters, key=lambda p: (p["position_row"], p["order_in_row"]))

    result = []
    for player, pos_id in zip(sorted_starters, position_ids):
        x, y = resolve_player_xy(pos_id, formation_str)
        pid = player["player_id"]
        name = player_names.get(pid, "")
        result.append({
            "player_id": pid,
            "player_name": name,
            "jersey_number": player.get("shirt", ""),
            "position_id": pos_id,
            "position_name": POSITION_NAMES.get(pos_id, "?"),
            "x": x,
            "y": y,
        })
    return result


def _map_from_rows(
    starters: list[dict],
    formation_str: str,
    player_names: dict[str, str],
) -> list[dict]:
    """Fallback: derive positions from row structure when formation isn't in the table."""
    try:
        row_sizes = [int(x) for x in formation_str.split("-")]
    except (ValueError, AttributeError):
        row_sizes = []

    gk = [s for s in starters if s["position_row"] == 1]
    field = sorted(
        [s for s in starters if s["position_row"] >= 2],
        key=lambda p: (p["position_row"], p["order_in_row"]),
    )

    # Build rows: [GK] + split field players by formation string
    rows: list[list[dict]] = []
    if gk:
        rows.append(gk)

    if row_sizes and sum(row_sizes) == len(field):
        idx = 0
        for size in row_sizes:
            rows.append(field[idx:idx + size])
            idx += size
    else:
        for rv in sorted(set(p["position_row"] for p in field)):
            rows.append([p for p in field if p["position_row"] == rv])

    # Assign coordinates by even spacing
    n_rows = len(rows)
    result = []
    for row_idx, players in enumerate(rows):
        x = 6.0 + row_idx * 84.0 / max(n_rows - 1, 1)
        n = len(players)
        for i, p in enumerate(players):
            y = 50.0 if n == 1 else 15.0 + i * 70.0 / (n - 1)
            pid = p["player_id"]
            result.append({
                "player_id": pid,
                "player_name": player_names.get(pid, ""),
                "jersey_number": p.get("shirt", ""),
                "position_id": 0,
                "position_name": "",
                "x": x,
                "y": y,
            })
    return result


# ═══════════════════════════════════════════════════════════════════════════
# § 5  AVERAGE POSITION MODE (from match events)
# ═══════════════════════════════════════════════════════════════════════════

# Opta event types to exclude from positional averages (set pieces bias location)
_SET_PIECE_TYPES = {
    6,   # Corner
    61,  # Ball touch (often set-piece related)
}
_SET_PIECE_QUALIFIERS = {
    6,   # Corner-related
    22,  # Inside penalty area (often set piece context)
    24,  # Free kick
    107, # Throw-in
    124, # Goal kick
}


def average_player_positions(
    events: list[dict],
    team_id: str,
    until_first_sub: bool = True,
) -> dict[str, tuple[float, float]]:
    """Compute median positions from events, rescaled to 0-100 normalised frame.

    Parameters
    ----------
    events : raw Opta event list from a match
    team_id : filter to this team's events
    until_first_sub : if True, only use events before the first substitution
        for a more stable formation snapshot

    Returns
    -------
    {player_id: (x_norm, y_norm)} where x=depth 0→100, y=width 0→100
    """
    # Find first sub minute if requested
    max_minute = 999
    if until_first_sub:
        for ev in events:
            if ev.get("typeId") in (18, 19) and ev.get("contestantId") == team_id:
                t = ev.get("timeMin", 999)
                if t < max_minute:
                    max_minute = t

    # Collect positions, filtering set pieces
    positions: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for ev in events:
        if ev.get("contestantId") != team_id:
            continue
        if ev.get("timeMin", 0) >= max_minute:
            continue

        pid = ev.get("playerId", "")
        x_raw = ev.get("x")
        y_raw = ev.get("y")
        if not pid or x_raw is None or y_raw is None:
            continue

        # Skip set-piece event types
        type_id = ev.get("typeId", 0)
        if type_id in _SET_PIECE_TYPES:
            continue

        # Skip events with set-piece qualifiers
        quals = {q.get("qualifierId") for q in ev.get("qualifier", [])}
        if quals & _SET_PIECE_QUALIFIERS:
            continue

        try:
            positions[pid].append((float(x_raw), float(y_raw)))
        except (ValueError, TypeError):
            continue

    if not positions:
        return {}

    # Compute medians — Opta coords are already 0-100 normalised
    result: dict[str, tuple[float, float]] = {}
    for pid, locs in positions.items():
        if len(locs) < 3:
            continue
        xs = [loc[0] for loc in locs]
        ys = [loc[1] for loc in locs]
        result[pid] = (median(xs), median(ys))

    # Nudge overlapping positions
    _nudge_overlaps(result, min_dist=4.0)

    return result


def _nudge_overlaps(
    positions: dict[str, tuple[float, float]],
    min_dist: float = 4.0,
) -> None:
    """Push apart any two players whose centroids are closer than min_dist."""
    pids = list(positions.keys())
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            ax, ay = positions[pids[i]]
            bx, by = positions[pids[j]]
            dx, dy = bx - ax, by - ay
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < min_dist and dist > 0:
                push = (min_dist - dist) / 2.0
                nx = dx / dist * push
                ny = dy / dist * push
                positions[pids[i]] = (ax - nx, ay - ny)
                positions[pids[j]] = (bx + nx, by + ny)


def merge_canonical_with_averages(
    canonical: list[dict],
    avg_positions: dict[str, tuple[float, float]],
    blend: float = 1.0,
) -> list[dict]:
    """Replace canonical coords with average positions where available.

    blend: 0.0 = fully canonical, 1.0 = fully average. Default fully average.
    """
    result = []
    for p in canonical:
        pid = p["player_id"]
        if pid in avg_positions:
            ax, ay = avg_positions[pid]
            cx, cy = p["x"], p["y"]
            p = dict(p)
            p["x"] = cx + blend * (ax - cx)
            p["y"] = cy + blend * (ay - cy)
        result.append(p)
    return result
