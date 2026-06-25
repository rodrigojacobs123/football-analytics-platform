from __future__ import annotations
"""Wide-play value — crossing & cutback expected goals from Opta events.

The app already knows *how many* crosses a player hits (the ``crosses_p90``
archetype feature), but not whether any of them were any *good*.  This module
prices each wide delivery by the chance it creates:

  • **xG generated** = the xG of the first shot the delivering team takes within
    a short window after the cross, attributed back to the cross.  Aggregated to
    **xG-per-cross** by origin zone, this exposes the gap the raw count hides —
    floated crosses convert far worse than cutbacks.
  • **Cutback** = a delivery from the byline zone pulled *back* toward the
    penalty spot (origin near the goal-line, end central and lower up the pitch).
    These are the highest-value wide pattern and are flagged separately.

Crosses are Opta passes (typeId 1) carrying qualifier 2 ("Cross"), confirmed
present in the feed (≈36/match, mean origin x≈84, 94 % from wide).  Coordinates
are the usual 0–100 with the team attacking x→100; y=100 is the LEFT touchline
(matching ``processing/buildup_play.py``).

This is event-data only — no tracking.  Pure pandas, no Streamlit; takes
``events`` so it composes with single-match and merged multi-match pages alike.
"""

import pandas as pd

from config import EVENT_PASS, QUAL_PASS_END_X, QUAL_PASS_END_Y, QUAL_XG
from data.event_parser import extract_shots

CROSS_QUALIFIER = 2          # Opta qualifier 2 = "Cross"

# Geometry (0–100, team attacks x→100).
_BYLINE_X = 83.0             # deep wide origin for a cutback
_CENTRAL_HALF_WIDTH = 15.0   # |y-50| < this ⇒ central target (penalty-spot area)
_LINK_WINDOW_SECS = 6        # a shot within this many seconds of the cross is "from" it

# Origin channels on the y-axis (y=100 LEFT, y=0 RIGHT — as in buildup_play).
_RIGHT_MAX, _LEFT_MIN = 33.33, 66.66


def _qual(quals: list[dict], qid: int):
    for q in quals:
        if q.get("qualifierId") == qid:
            return q.get("value", "1")
    return None


def _channel(y: float) -> str:
    if y >= _LEFT_MIN:
        return "Left"
    if y <= _RIGHT_MAX:
        return "Right"
    return "Central"


def extract_crosses(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Open-play crosses (passes with qualifier 2) with a cutback flag.

    Returns columns: minute, second, abs_sec, period, team_id, player_id,
    player_name, x, y, end_x, end_y, outcome, channel, is_cutback.  A cutback is
    a completed delivery from the byline (x>83) ending central (|end_y-50|<15)
    and pulled back up the pitch (end_x < start_x).
    """
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_PASS:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        quals = e.get("qualifier", [])
        if not any(q.get("qualifierId") == CROSS_QUALIFIER for q in quals):
            continue

        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        ex, ey = _qual(quals, QUAL_PASS_END_X), _qual(quals, QUAL_PASS_END_Y)
        ex = float(ex) if ex is not None else None
        ey = float(ey) if ey is not None else None
        outcome = int(e.get("outcome", 0))

        is_cutback = bool(
            outcome == 1 and ex is not None and ey is not None
            and x > _BYLINE_X and abs(ey - 50) < _CENTRAL_HALF_WIDTH and ex < x
        )
        mn, sec = int(e.get("timeMin", 0)), int(e.get("timeSec", 0))
        rows.append({
            "minute": mn, "second": sec, "abs_sec": mn * 60 + sec,
            "period": int(e.get("periodId", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": x, "y": y, "end_x": ex, "end_y": ey,
            "outcome": outcome, "channel": _channel(y), "is_cutback": is_cutback,
        })
    return pd.DataFrame(rows)


def link_cross_xg(crosses: pd.DataFrame, shots: pd.DataFrame,
                  window_secs: int = _LINK_WINDOW_SECS) -> pd.DataFrame:
    """Attribute to each cross the xG of the first shot it set up.

    For each cross (chronologically) we claim the earliest *unconsumed* shot by
    the same team within ``window_secs`` and the same period, so one shot is
    credited to at most one cross.  Adds ``shot_xg`` (0.0 if none) and
    ``led_to_shot`` columns.
    """
    out = crosses.copy()
    if out.empty:
        out["shot_xg"] = pd.Series(dtype=float)
        out["led_to_shot"] = pd.Series(dtype=bool)
        return out

    out["shot_xg"] = 0.0
    out["led_to_shot"] = False
    if shots is None or shots.empty:
        return out

    sh = shots.copy()
    sh["abs_sec"] = sh["minute"] * 60 + sh["second"]
    consumed: set[int] = set()

    for idx, cr in out.sort_values("abs_sec").iterrows():
        cand = sh[(sh["team_id"] == cr["team_id"])
                  & (sh["period"] == cr["period"])
                  & (sh["abs_sec"] >= cr["abs_sec"])
                  & (sh["abs_sec"] <= cr["abs_sec"] + window_secs)]
        cand = cand[~cand.index.isin(consumed)]
        if cand.empty:
            continue
        pick = cand.sort_values("abs_sec").index[0]
        consumed.add(pick)
        out.at[idx, "shot_xg"] = float(sh.at[pick, "xg"])
        out.at[idx, "led_to_shot"] = True
    return out


def _empty_summary() -> dict:
    return {
        "crosses": 0, "completed": 0, "completion_pct": 0.0, "cutbacks": 0,
        "xg_generated": 0.0, "xg_per_cross": 0.0, "xg_per_cutback": 0.0,
        "shots_created": 0, "per_match": {"crosses": 0.0, "xg_generated": 0.0},
        "by_channel": pd.DataFrame(), "leaderboard": pd.DataFrame(),
    }


def _summarize_linked(linked: pd.DataFrame, n_matches: int) -> dict:
    """Aggregate a (per-match-linked) cross frame into the headline summary.

    Kept separate from linking so season aggregation can link each match on its
    own (minute counters reset per match — linking merged events would leak a
    cross to another game's shot) then concat and summarise once here.
    """
    if linked is None or linked.empty:
        return _empty_summary()
    n = len(linked)
    completed = int((linked["outcome"] == 1).sum())
    cutbacks = linked[linked["is_cutback"]]
    xg_total = float(linked["shot_xg"].sum())
    nm = max(n_matches, 1)

    by_channel = (linked.groupby("channel").agg(
        crosses=("outcome", "size"),
        completed=("outcome", lambda s: int((s == 1).sum())),
        xg=("shot_xg", "sum"),
    ).reset_index())
    if not by_channel.empty:
        by_channel["completion_pct"] = (by_channel["completed"]
                                        / by_channel["crosses"] * 100).round(1)
        by_channel["xg_per_cross"] = (by_channel["xg"]
                                      / by_channel["crosses"]).round(4)
        by_channel["xg"] = by_channel["xg"].round(3)

    leaderboard = (linked.groupby(["player_id", "player_name"]).agg(
        crosses=("outcome", "size"),
        completed=("outcome", lambda s: int((s == 1).sum())),
        cutbacks=("is_cutback", "sum"),
        xg_generated=("shot_xg", "sum"),
    ).reset_index())
    if not leaderboard.empty:
        leaderboard["xg_generated"] = leaderboard["xg_generated"].round(3)
        leaderboard = leaderboard.sort_values("xg_generated", ascending=False).reset_index(drop=True)

    return {
        "crosses": n,
        "completed": completed,
        "completion_pct": round(completed / n * 100, 1) if n else 0.0,
        "cutbacks": int(len(cutbacks)),
        "xg_generated": round(xg_total, 3),
        "xg_per_cross": round(xg_total / n, 4) if n else 0.0,
        "xg_per_cutback": round(float(cutbacks["shot_xg"].sum()) / len(cutbacks), 4)
                          if len(cutbacks) else 0.0,
        "shots_created": int(linked["led_to_shot"].sum()),
        "per_match": {"crosses": round(n / nm, 2),
                      "xg_generated": round(xg_total / nm, 3)},
        "by_channel": by_channel,
        "leaderboard": leaderboard,
    }


def compute_cross_value(events: list[dict], team_id: str, n_matches: int = 1) -> dict:
    """One-call wide-play summary for a team over a single match's events.

    Returns headline rates plus a per-channel breakdown and per-player
    leaderboard (see ``_summarize_linked``).  For multi-match windows use
    ``compute_season_cross_value`` so each match is linked independently.
    Empty/insufficient input → zeros and empty frames.
    """
    if not events or not team_id:
        return _empty_summary()
    crosses = extract_crosses(events, team_id)
    if crosses.empty:
        return _empty_summary()
    linked = link_cross_xg(crosses, extract_shots(events, team_id))
    return _summarize_linked(linked, n_matches)


# ── Season aggregation (cached deep tier) ────────────────────────────────────
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info
from data.loader import load_match_events


@st.cache_data(ttl=3600, show_spinner="Computing season crossing value…")
def compute_season_cross_value(league: str, season: str, team_id: str,
                               stage_filter: str = "") -> dict:
    """Season-aggregated crossing/cutback value for one team.

    Scans ``partidos/`` (cached), links crosses→shots **per match** (so a cross
    never claims another game's shot — minute counters reset each match), concats
    the per-match linked frames, and summarises once.  Returns the same dict as
    ``compute_cross_value`` plus a ``matches`` count; ``{}`` if no matches found.
    """
    import json

    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    frames: list[pd.DataFrame] = []
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
        crosses = extract_crosses(events, team_id)
        matches += 1
        if crosses.empty:
            continue
        frames.append(link_cross_xg(crosses, extract_shots(events, team_id)))

    if matches == 0:
        return {}
    linked = (pd.concat(frames, ignore_index=True) if frames
              else pd.DataFrame())
    summary = _summarize_linked(linked, matches)
    summary["matches"] = matches
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Throw-in / long-throw threat
# ─────────────────────────────────────────────────────────────────────────────
# The breakout 2025-26 trend: long throws into the box now produce ~0.12
# goals/match in the Premier League (more than double last season).  The app
# had no throw-in handling at all.  Throw-ins are Opta passes (typeId 1) with
# qualifier 107 ("Throw-in"); a *long throw* is one delivered into the penalty
# area.  We price each by the xG of the shot it sets up — reusing the same
# per-match linker as crosses (link PER MATCH so a throw never claims another
# game's shot).

THROWIN_QUALIFIER = 107      # Opta qualifier 107 = "Throw-in"

# Penalty-area target box (0-100, team attacks x→100; y=100 LEFT, y=0 RIGHT).
_BOX_X = 83.0
_BOX_Y_LO, _BOX_Y_HI = 21.0, 79.0


def extract_throwins(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Throw-ins (passes with qualifier 107) with a long-throw flag.

    Returns the same shape as ``extract_crosses`` plus ``is_long_throw`` — a
    completed throw whose delivery lands in the penalty area (end_x > 83 and
    21 < end_y < 79).  ``is_cutback`` is included (always False) so the throw
    frame is link-compatible with ``link_cross_xg``.
    """
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_PASS:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        quals = e.get("qualifier", [])
        if not any(q.get("qualifierId") == THROWIN_QUALIFIER for q in quals):
            continue

        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        ex, ey = _qual(quals, QUAL_PASS_END_X), _qual(quals, QUAL_PASS_END_Y)
        ex = float(ex) if ex is not None else None
        ey = float(ey) if ey is not None else None
        outcome = int(e.get("outcome", 0))

        is_long_throw = bool(
            ex is not None and ey is not None
            and ex > _BOX_X and _BOX_Y_LO < ey < _BOX_Y_HI
        )
        mn, sec = int(e.get("timeMin", 0)), int(e.get("timeSec", 0))
        rows.append({
            "minute": mn, "second": sec, "abs_sec": mn * 60 + sec,
            "period": int(e.get("periodId", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": x, "y": y, "end_x": ex, "end_y": ey,
            "outcome": outcome, "channel": _channel(y),
            "is_long_throw": is_long_throw, "is_cutback": False,
        })
    return pd.DataFrame(rows)


def _empty_throwin_summary() -> dict:
    return {
        "throwins": 0, "long_throws": 0, "attacking_third": 0,
        "xg_generated": 0.0, "xg_per_long_throw": 0.0, "shots_created": 0,
        "per_match": {"throwins": 0.0, "long_throws": 0.0, "xg_generated": 0.0},
        "leaderboard": pd.DataFrame(),
    }


def _summarize_throwins(linked: pd.DataFrame, n_matches: int) -> dict:
    """Aggregate a (per-match-linked) throw-in frame into the headline summary."""
    if linked is None or linked.empty:
        return _empty_throwin_summary()
    n = len(linked)
    longs = linked[linked["is_long_throw"]]
    att_third = int((linked["x"] > 66.66).sum())
    xg_total = float(linked["shot_xg"].sum())
    long_xg = float(longs["shot_xg"].sum())
    nm = max(n_matches, 1)

    leaderboard = (linked.groupby(["player_id", "player_name"]).agg(
        throwins=("outcome", "size"),
        long_throws=("is_long_throw", "sum"),
        xg_generated=("shot_xg", "sum"),
    ).reset_index())
    if not leaderboard.empty:
        leaderboard["xg_generated"] = leaderboard["xg_generated"].round(3)
        leaderboard = leaderboard.sort_values(
            ["long_throws", "xg_generated"], ascending=False).reset_index(drop=True)

    return {
        "throwins": n,
        "long_throws": int(len(longs)),
        "attacking_third": att_third,
        "xg_generated": round(xg_total, 3),
        "xg_per_long_throw": round(long_xg / len(longs), 4) if len(longs) else 0.0,
        "shots_created": int(linked["led_to_shot"].sum()),
        "per_match": {"throwins": round(n / nm, 1),
                      "long_throws": round(len(longs) / nm, 2),
                      "xg_generated": round(xg_total / nm, 3)},
        "leaderboard": leaderboard,
    }


def compute_throwin_value(events: list[dict], team_id: str, n_matches: int = 1) -> dict:
    """One-call throw-in / long-throw summary for a team over one match."""
    if not events or not team_id:
        return _empty_throwin_summary()
    throws = extract_throwins(events, team_id)
    if throws.empty:
        return _empty_throwin_summary()
    linked = link_cross_xg(throws, extract_shots(events, team_id))
    return _summarize_throwins(linked, n_matches)


@st.cache_data(ttl=3600, show_spinner="Computing season throw-in value…")
def compute_season_throwin_value(league: str, season: str, team_id: str,
                                 stage_filter: str = "") -> dict:
    """Season-aggregated throw-in / long-throw value for one team.

    Mirrors ``compute_season_cross_value`` — links throws→shots **per match**
    (minute counters reset each match), concats, summarises once.
    """
    import json

    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    frames: list[pd.DataFrame] = []
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
        throws = extract_throwins(events, team_id)
        matches += 1
        if throws.empty:
            continue
        frames.append(link_cross_xg(throws, extract_shots(events, team_id)))

    if matches == 0:
        return {}
    linked = (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
    summary = _summarize_throwins(linked, matches)
    summary["matches"] = matches
    return summary
