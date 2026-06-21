from __future__ import annotations
"""Expected Defensive Threat Reduction (xDEF) — the defensive mirror of xT.

Our `processing/xt.py` values *attacking* ball progression: moving the ball into
more dangerous space adds threat.  xDEF values the opposite side of the same
coin — a defensive action (tackle, interception, clearance, blocked pass, ball
recovery) *extinguishes* the threat the opponent had at that location.

Reference (event-data formulation):
    Marc Lamberts — "Expected Defensive Threat Reduction (xDEF)"
    https://marclamberts.medium.com/expected-defensive-threat-reduction-xdef-...

Method (event-data only, no tracking data required)
----------------------------------------------------
Opta coordinates are recorded from the *acting* team's attacking perspective:
every team attacks left→right in its own frame (x=0 = own goal, x=100 =
opponent goal).  So a defender's tackle at x=20 is deep in their OWN defensive
third — i.e. they just stopped an attack very close to their own goal.

To price the threat denied, we flip into the attacking team's frame:

    xt_denied = xt_value(100 - x, y)

The Karun-Singh grid is symmetric in y (rows mirror around the centre), so the
y-coordinate does not need flipping.  The deeper the defensive action sits in
the defender's own territory, the higher the opponent's threat there was, and
the more credit the defender earns.

The action is then scaled by:
  • a per-action-type weight  (DEF_ACTION_WEIGHTS — see below), and
  • whether the action succeeded (failed tackles deny nothing).
"""

import json

import pandas as pd
import streamlit as st

from data.paths import partidos_dir
from data.event_parser import (
    extract_tackles, extract_interceptions, extract_clearances,
    extract_ball_recoveries, parse_match_info,
)
from processing.xt import xt_value


# ──────────────────────────────────────────────────────────────────────────
# DESIGN DECISION — how much threat-denial credit each defensive action earns.
#
# Not every defensive action is worth the same. The xT *at the location* is the
# same for a tackle and a clearance made in the same spot, but they are not
# tactically equivalent:
#
#   • A won tackle / interception RECOVERS possession  → your team can now
#     attack. Full value, arguably a bonus.
#   • A blocked pass STOPS a progression but the ball may stay loose.
#   • A clearance KILLS the danger but usually concedes possession (boot it
#     away) — it denies threat but doesn't start anything.
#   • A ball recovery picks up a loose ball — possession regained, but it
#     wasn't a contested intervention.
#
# These weights multiply the location xT to produce the credited xDEF.
# Sensible defaults are provided so the module works out of the box, but this
# is a genuine judgement call — tune it to how Club América wants to value
# ball-winning vs. danger-clearing.
# ──────────────────────────────────────────────────────────────────────────
DEF_ACTION_WEIGHTS: dict[str, float] = {
    "tackle":       1.0,   # won the ball in a duel — possession regained
    "interception": 1.0,   # read the pass, possession regained
    "blocked_pass": 0.8,   # progression stopped, ball may stay loose
    "clearance":    0.6,   # danger killed but possession usually conceded
    "ball_recovery": 0.7,  # loose ball collected (uncontested)
}


def defensive_xt_denied(x: float, y: float) -> float:
    """Threat the opponent held at the location of a defensive action.

    Flips the defender's own-frame coordinate into the attacker's frame and
    reads the xT grid there.  Returns 0 for missing coordinates.
    """
    if x is None or y is None:
        return 0.0
    return xt_value(100.0 - float(x), float(y))


# Map: action label -> (extractor fn, does the extractor expose an `outcome`?)
_ACTION_SOURCES = {
    "tackle":        (extract_tackles,         True),
    "interception":  (extract_interceptions,   True),
    "clearance":     (extract_clearances,      True),
    "ball_recovery": (extract_ball_recoveries, False),  # no outcome col → always counts
}


def defensive_actions_xdef(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Per-action xDEF for every defensive action by `team_id`.

    Returns one row per defensive event with columns:
        minute, team_id, player_id, player_name, x, y, period,
        action, weight, xt_location, xdef
    `xdef` is 0 when the action failed (e.g. a lost tackle).
    """
    frames = []
    for action, (extractor, has_outcome) in _ACTION_SOURCES.items():
        df = extractor(events, team_id=team_id)
        if df.empty:
            continue
        df = df.copy()
        df["action"] = action
        df["weight"] = DEF_ACTION_WEIGHTS.get(action, 1.0)
        df["xt_location"] = df.apply(
            lambda r: defensive_xt_denied(r["x"], r["y"]), axis=1)
        # Failed actions (lost tackles, blocked-but-not-won) deny nothing.
        if has_outcome and "outcome" in df.columns:
            success = (df["outcome"] == 1).astype(float)
        else:
            success = 1.0
        df["xdef"] = df["xt_location"] * df["weight"] * success
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=[
            "minute", "team_id", "player_id", "player_name", "x", "y",
            "period", "action", "weight", "xt_location", "xdef",
        ])
    return pd.concat(frames, ignore_index=True)


def xdef_summary(events: list[dict], team_id: str) -> dict:
    """One-call team-level xDEF summary (mirrors xt.xt_summary).

    Returns: {
        total_xdef,                       float
        by_action,                        dict {action: summed xdef}
        top_defenders,                    DataFrame [player_name, xdef, actions]
        actions_df,                       full per-action DataFrame
    }
    """
    df = defensive_actions_xdef(events, team_id=team_id)
    total = float(df["xdef"].sum()) if not df.empty else 0.0

    by_action: dict[str, float] = {}
    top_defenders = pd.DataFrame()
    if not df.empty:
        by_action = {
            a: round(float(v), 3)
            for a, v in df.groupby("action")["xdef"].sum().items()
        }
        credited = df[df["xdef"] > 0]
        if not credited.empty and "player_name" in credited.columns:
            top_defenders = (
                credited.groupby("player_name")
                        .agg(xdef=("xdef", "sum"), actions=("xdef", "size"))
                        .sort_values("xdef", ascending=False)
                        .head(8)
                        .reset_index()
            )
            top_defenders["xdef"] = top_defenders["xdef"].round(3)

    return {
        "total_xdef": round(total, 3),
        "by_action": by_action,
        "top_defenders": top_defenders,
        "actions_df": df,
    }


@st.cache_data(ttl=3600, show_spinner="Computing season Expected Defensive Threat (xDEF)...")
def compute_season_xdef(league: str, season: str, team_id: str,
                        stage_filter: str = "",
                        min_appearances: int = 1) -> dict:
    """Season-aggregated xDEF for one team — the defensive mirror of
    ``processing.xt.compute_season_xt``.

    Scans partidos/ (deep tier, cached), accumulating each player's credited
    threat-denial so we can rank ball-winners / danger-clearers over a full
    season.  Players below ``min_appearances`` are dropped to filter cameo
    noise — symmetric with the xT leaderboard (respects
    MIN_APPEARANCES_FOR_RATING when callers pass it).

    Returns {} if no matches found, else {
        matches, total_xdef, xdef_per_match,
        by_action (dict), leaderboard (DataFrame),
    }.
    ``leaderboard`` columns: player_name, xdef, actions, apps, xdef_per_match.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    player_acc: dict[str, dict] = {}
    by_action_acc: dict[str, float] = {}
    total = 0.0
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

        events = raw.get("liveData", {}).get("event", [])
        df = defensive_actions_xdef(events, team_id=team_id)
        match_num += 1
        if df.empty:
            continue

        credited = df[df["xdef"] > 0]
        if credited.empty:
            continue
        total += float(credited["xdef"].sum())

        for action, v in credited.groupby("action")["xdef"].sum().items():
            by_action_acc[action] = by_action_acc.get(action, 0.0) + float(v)

        if "player_name" in credited.columns:
            grp = credited.groupby("player_name").agg(
                xdef=("xdef", "sum"), actions=("xdef", "size"))
            for name, r in grp.iterrows():
                acc = player_acc.setdefault(
                    name, {"xdef": 0.0, "actions": 0, "apps": 0})
                acc["xdef"] += float(r["xdef"])
                acc["actions"] += int(r["actions"])
                acc["apps"] += 1

    if match_num == 0:
        return {}

    leaderboard = pd.DataFrame([
        {
            "player_name": n,
            "xdef": round(v["xdef"], 3),
            "actions": v["actions"],
            "apps": v["apps"],
            "xdef_per_match": round(v["xdef"] / v["apps"], 3),
        }
        for n, v in player_acc.items() if v["apps"] >= min_appearances
    ])
    if not leaderboard.empty:
        leaderboard = (leaderboard
                       .sort_values("xdef", ascending=False)
                       .reset_index(drop=True))

    return {
        "matches": match_num,
        "total_xdef": round(total, 2),
        "xdef_per_match": round(total / match_num, 3),
        "by_action": {k: round(v, 3) for k, v in by_action_acc.items()},
        "leaderboard": leaderboard,
    }
