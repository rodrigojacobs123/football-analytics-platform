from __future__ import annotations
"""Build-up / playing-out-from-the-back analysis.

Answers three coaching questions from Opta event data alone:
  1. HOW does a team take the ball out of its own defensive third?
       → distribution of *exit passes* across the Left / Central / Right channels
         and across Short (build short) vs Long/Direct (skip the press) styles.
  2. What is the team's MOST COMMON way out?
       → the dominant channel×style combination + the single most frequent
         passer→receiver link used to escape the defensive third.
  3. WHICH players take the ball out?
       → ranking of players by build-up involvement (exits made + received),
         with their average build-up position for plotting.

Distinct from `goal_buildup.py` (traces goals only) and `pass_network.py`
(all passes, full pitch): this looks *only* at how possession leaves the
defensive third — the build-out phase.

The single public entry point takes a **passes DataFrame** (the output of
`data.event_parser.extract_passes`, already team-filtered) so it composes with
both the single-match (Post-Match) and merged-multi-match (Pre-Match) pages.
"""

import pandas as pd
from processing.game_phases import DEF_THIRD_MAX, MID_THIRD_MAX   # 33.33 / 66.66

# Channel boundaries on the Opta y-axis (0–100). For the team attacking
# x:0→100, y=100 is its LEFT touchline and y=0 its RIGHT touchline.
_RIGHT_MAX = 33.33
_LEFT_MIN = 66.66

CHANNELS = ["Left", "Central", "Right"]
STYLES = ["Short", "Long / Direct"]


def _channel(y: float) -> str:
    if y >= _LEFT_MIN:
        return "Left"
    if y <= _RIGHT_MAX:
        return "Right"
    return "Central"


def _style(end_x: float) -> str:
    """Short = built out into the middle third; Long/Direct = skipped it."""
    return "Short" if end_x <= MID_THIRD_MAX else "Long / Direct"


def build_up_report(passes: pd.DataFrame, min_link: int = 2) -> dict:
    """Summarise how a team plays the ball out of its defensive third.

    `passes` must carry: x, y, end_x, end_y, player_id, player_name,
    receiver_id, outcome  (i.e. `extract_passes(events, team_id)`).

    Returns a dict consumed by `viz.buildup.plot_build_up` /
    `build_up_summary_md`. All shares are % of *exit* passes.
    """
    empty = {
        "n_exits": 0, "channels": {}, "styles": {},
        "dominant_route": None, "top_link": None,
        "top_players": [], "player_positions": {},
    }
    if passes is None or passes.empty:
        return empty

    df = passes.dropna(subset=["end_x", "end_y"]).copy()
    df = df[df["outcome"] == 1]
    # Build-up = starts in own defensive third
    bu = df[df["x"] <= DEF_THIRD_MAX].copy()
    # Exit = the pass actually moves the ball out of the defensive third
    exits = bu[bu["end_x"] > DEF_THIRD_MAX].copy()
    if exits.empty:
        return empty

    exits["channel"] = exits["y"].map(_channel)
    exits["style"] = exits["end_x"].map(_style)

    n = len(exits)
    channels = {
        c: {"count": int((exits["channel"] == c).sum()),
            "pct": round((exits["channel"] == c).mean() * 100, 1)}
        for c in CHANNELS
    }
    styles = {
        s: {"count": int((exits["style"] == s).sum()),
            "pct": round((exits["style"] == s).mean() * 100, 1)}
        for s in STYLES
    }

    # Dominant route = most frequent channel × style combination
    combo = (exits.groupby(["channel", "style"]).size()
             .sort_values(ascending=False))
    dom_ch, dom_st = combo.index[0]
    dominant_route = {
        "channel": dom_ch, "style": dom_st,
        "count": int(combo.iloc[0]),
        "pct": round(combo.iloc[0] / n * 100, 1),
    }

    # Resolve receiver names. `extract_passes` carries receiver_name directly;
    # fall back to an id→name lookup for any older caller without that column.
    if "receiver_name" not in exits.columns:
        id_to_name = (passes.dropna(subset=["player_id"])
                      .drop_duplicates("player_id")
                      .set_index("player_id")["player_name"].to_dict())
        exits["receiver_name"] = exits["receiver_id"].map(id_to_name)

    # Most frequent passer → receiver link used to escape the third
    link = None
    linked = exits.dropna(subset=["receiver_name"])
    if not linked.empty:
        pair = (linked.groupby(["player_name", "receiver_name"]).size()
                .sort_values(ascending=False))
        (passer, receiver), cnt = pair.index[0], int(pair.iloc[0])
        if cnt >= min_link:
            link = {"passer": passer, "receiver": receiver, "count": cnt}

    # Player involvement = exits made (passer) + exits received (receiver)
    made = exits.groupby("player_name").size()
    recv = (exits.dropna(subset=["receiver_name"])
            .groupby("receiver_name").size())
    involve = made.add(recv, fill_value=0).sort_values(ascending=False)

    # Average build-up position per player (from their build-up touches)
    pos = (bu.groupby("player_name")[["x", "y"]].mean()
           .round(1).to_dict("index"))

    top_players = [
        {"player": name, "exits": int(involve[name]),
         "made": int(made.get(name, 0)),
         "received": int(recv.get(name, 0))}
        for name in involve.head(6).index
    ]

    return {
        "n_exits": n,
        "channels": channels,
        "styles": styles,
        "dominant_route": dominant_route,
        "top_link": link,
        "top_players": top_players,
        "player_positions": pos,
    }
