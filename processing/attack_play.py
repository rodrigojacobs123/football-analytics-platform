from __future__ import annotations
"""Attacking-third connection analysis — the mirror of ``buildup_play``.

Where ``buildup_play`` answers "how does the ball LEAVE our defensive third",
this answers the attacking equivalent from Opta event data alone:

  1. HOW does the team connect in the final third?
       → distribution of completed passes that land in the attacking third
         across the Left / Central / Right channels, and whether they were
         **Entries** (played in from outside) or **Combinations** (already
         inside the third).
  2. What is the team's MOST COMMON way in?
       → the dominant channel×type combination + the single most frequent
         passer→receiver link in the final third.
  3. WHICH players connect the most, and what share of the total?
       → ranking of players by final-third involvement (passes made + received),
         each with its **percentage of all connections**, and their average
         attacking position for plotting.

Distinct from ``buildup_play`` (defensive third), ``goal_buildup`` (goals only)
and ``pass_network`` (all passes): this looks *only* at how the team connects
the ball in the attacking third — the final-third creation phase.

Single public entry point takes a **passes DataFrame** (``extract_passes``,
already team-filtered) so it composes with both single-match (Post-Match) and
merged multi-match (Pre-Match) pages — exactly like ``build_up_report``.
"""

import pandas as pd
from processing.game_phases import MID_THIRD_MAX   # 66.66 → final third starts here

# Channel boundaries on the Opta y-axis (team attacks x→100; y=100 LEFT, y=0 RIGHT).
_RIGHT_MAX = 33.33
_LEFT_MIN = 66.66

CHANNELS = ["Left", "Central", "Right"]
TYPES = ["Entry", "Combination"]


def _channel(y: float) -> str:
    if y >= _LEFT_MIN:
        return "Left"
    if y <= _RIGHT_MAX:
        return "Right"
    return "Central"


def _type(start_x: float) -> str:
    """Entry = played in from outside the final third; Combination = already inside."""
    return "Combination" if start_x > MID_THIRD_MAX else "Entry"


def attack_report(passes: pd.DataFrame, min_link: int = 2) -> dict:
    """Summarise how a team connects in the attacking third.

    ``passes`` must carry: x, y, end_x, end_y, player_id, player_name,
    receiver_id, outcome (i.e. ``extract_passes(events, team_id)``).

    A *connection* is a completed pass whose end lands in the final third
    (``end_x > 66.66``).  The channel is the side it connects on (``end_y``).
    Returns a dict consumed by ``viz.attack_play.plot_attack`` /
    ``attack_summary_md``.  All shares are % of *connections*.
    """
    empty = {
        "n_connections": 0, "channels": {}, "types": {},
        "dominant_route": None, "top_link": None,
        "top_players": [], "player_positions": {},
    }
    if passes is None or passes.empty:
        return empty

    df = passes.dropna(subset=["end_x", "end_y"]).copy()
    df = df[df["outcome"] == 1]
    # Connection = a completed pass that lands in the attacking third.
    conn = df[df["end_x"] > MID_THIRD_MAX].copy()
    if conn.empty:
        return empty

    conn["channel"] = conn["end_y"].map(_channel)     # side it connects on
    conn["type"] = conn["x"].map(_type)               # entry vs combination

    n = len(conn)
    channels = {
        c: {"count": int((conn["channel"] == c).sum()),
            "pct": round((conn["channel"] == c).mean() * 100, 1)}
        for c in CHANNELS
    }
    types = {
        t: {"count": int((conn["type"] == t).sum()),
            "pct": round((conn["type"] == t).mean() * 100, 1)}
        for t in TYPES
    }

    # Dominant route = most frequent channel × type combination.
    combo = (conn.groupby(["channel", "type"]).size()
             .sort_values(ascending=False))
    dom_ch, dom_ty = combo.index[0]
    dominant_route = {
        "channel": dom_ch, "type": dom_ty,
        "count": int(combo.iloc[0]),
        "pct": round(combo.iloc[0] / n * 100, 1),
    }

    # Resolve receiver names (extract_passes carries them; fall back to lookup).
    if "receiver_name" not in conn.columns:
        id_to_name = (passes.dropna(subset=["player_id"])
                      .drop_duplicates("player_id")
                      .set_index("player_id")["player_name"].to_dict())
        conn["receiver_name"] = conn["receiver_id"].map(id_to_name)

    # Most frequent passer → receiver link in the final third.
    link = None
    linked = conn.dropna(subset=["receiver_name"])
    if not linked.empty:
        pair = (linked.groupby(["player_name", "receiver_name"]).size()
                .sort_values(ascending=False))
        (passer, receiver), cnt = pair.index[0], int(pair.iloc[0])
        if cnt >= min_link:
            link = {"passer": passer, "receiver": receiver, "count": cnt}

    # Involvement = connections made (passer) + received (receiver).
    made = conn.groupby("player_name").size()
    recv = (conn.dropna(subset=["receiver_name"])
            .groupby("receiver_name").size())
    involve = made.add(recv, fill_value=0).sort_values(ascending=False)
    total_involve = float(involve.sum()) or 1.0

    # Average attacking position per player = mean landing point of the
    # connections they're involved in (as passer OR receiver) — keeps everyone
    # plotted inside the final third.
    pos_src = pd.concat([
        conn[["player_name", "end_x", "end_y"]].rename(
            columns={"player_name": "name"}),
        conn.dropna(subset=["receiver_name"])[["receiver_name", "end_x", "end_y"]]
            .rename(columns={"receiver_name": "name"}),
    ], ignore_index=True)
    pos = (pos_src.groupby("name")[["end_x", "end_y"]].mean()
           .round(1).rename(columns={"end_x": "x", "end_y": "y"})
           .to_dict("index"))

    top_players = [
        {"player": name,
         "connections": int(involve[name]),
         "pct": round(involve[name] / total_involve * 100, 1),
         "made": int(made.get(name, 0)),
         "received": int(recv.get(name, 0))}
        for name in involve.head(6).index
    ]

    return {
        "n_connections": n,
        "channels": channels,
        "types": types,
        "dominant_route": dominant_route,
        "top_link": link,
        "top_players": top_players,
        "player_positions": pos,
    }
