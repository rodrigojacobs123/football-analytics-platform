from __future__ import annotations
"""Game-state segmentation — re-cut attacking output by scoreline.

A leading team deliberately cedes possession; a chasing team inflates xG
against an opened-up defence.  Raw season aggregates silently average these
regimes together, so "team xT" mixes a 3-0 cruise with a 0-1 chase.  This
module tags every moment of a match with the scoreline **state** from one
team's point of view — *Losing / Level / Winning* — and re-buckets that team's
xG, xT and shots accordingly, so "América's xT *while level*" can be read on
its own as a much cleaner signal of true level.

State is derived purely from goal events (``typeId == 16``); own goals are
credited to the opponent.  Two timing conventions, both deliberate:

  • An event is tagged with the state from goals scored *strictly before* it,
    so the shot that becomes the opening goal counts as taken while *Level*
    (the chance existed before the lead did) — the analytically correct
    attribution for xG-by-state.
  • Minutes-in-state use the *midpoint* of each between-goals interval, so the
    goal instant itself never lands ambiguously in two buckets.

Pure pandas/Python — no Streamlit, no model.  The cached season aggregator at
the bottom adds the I/O layer, mirroring ``processing.xt.compute_season_xt``.
"""

import pandas as pd
from config import EVENT_GOAL, QUAL_OWN_GOAL
from data.event_parser import extract_shots
from processing.xt import passes_xt

# Scoreline state from a team's perspective.
STATE_ORDER = [-1, 0, 1]
STATE_LABELS = {-1: "Losing", 0: "Level", 1: "Winning"}


def _ts(ev: dict) -> int:
    """Event timestamp in whole seconds."""
    return int(ev.get("timeMin", 0)) * 60 + int(ev.get("timeSec", 0))


def _has_qual(quals: list[dict], qid: int) -> bool:
    return any(q.get("qualifierId") == qid for q in quals)


def scoring_events(events: list[dict], home_id: str, away_id: str
                   ) -> list[tuple[int, str]]:
    """Chronological ``(timestamp_s, scoring_team_id)`` for every goal.

    Own goals (``typeId 16`` carrying qualifier 28) are credited to the
    opposing team, since for the scoreline that is who benefits.
    """
    out: list[tuple[int, str]] = []
    for e in events:
        if e.get("typeId") != EVENT_GOAL:
            continue
        team = e.get("contestantId")
        if _has_qual(e.get("qualifier", []), QUAL_OWN_GOAL):
            team = away_id if team == home_id else home_id
        out.append((_ts(e), team))
    out.sort(key=lambda r: r[0])
    return out


def _state_at(ts: int, team_id: str, home_id: str, away_id: str,
              goals: list[tuple[int, str]], *, inclusive: bool) -> int:
    """State of ``team_id`` at time ``ts`` → -1 (losing) / 0 (level) / +1.

    ``inclusive`` controls whether a goal exactly at ``ts`` is already counted
    (True for minutes-in-state midpoints, False for event attribution so the
    goal-scoring shot is credited to the pre-goal state).
    """
    home = away = 0
    for gt, tm in goals:
        if (gt <= ts) if inclusive else (gt < ts):
            if tm == home_id:
                home += 1
            elif tm == away_id:
                away += 1
        else:
            break  # goals are sorted; nothing later can qualify
    lead = (home - away) if team_id == home_id else (away - home)
    return (lead > 0) - (lead < 0)


def _state_minutes(events: list[dict], team_id: str, home_id: str,
                   away_id: str, goals: list[tuple[int, str]]) -> dict[int, float]:
    """Minutes ``team_id`` spent in each state across the match."""
    end_ts = max((_ts(e) for e in events), default=0)
    bounds = [0] + [gt for gt, _ in goals] + [end_ts]
    mins = {s: 0.0 for s in STATE_ORDER}
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b <= a:
            continue
        s = _state_at((a + b) // 2, team_id, home_id, away_id, goals,
                      inclusive=True)
        mins[s] += (b - a) / 60.0
    return mins


def segment_match_by_state(events: list[dict], team_id: str, home_id: str,
                           away_id: str) -> pd.DataFrame:
    """Re-cut one team's xG / xT / shots by scoreline state for a single match.

    Returns a DataFrame with one row per state (always all three, zero-filled)
    and columns ``state, label, minutes, shots, xg, xt, xg_per90, xt_per90``.
    ``xt`` is the net per-pass xT added (same convention as ``xt_summary``'s
    total xT).  Empty events → empty frame.
    """
    goals = scoring_events(events, home_id, away_id)

    acc = {s: {"minutes": 0.0, "shots": 0, "xg": 0.0, "xt": 0.0}
           for s in STATE_ORDER}
    for s, m in _state_minutes(events, team_id, home_id, away_id, goals).items():
        acc[s]["minutes"] = m

    shots = extract_shots(events, team_id=team_id)
    if not shots.empty:
        for _, sh in shots.iterrows():
            ts = int(sh["minute"]) * 60 + int(sh["second"])
            s = _state_at(ts, team_id, home_id, away_id, goals, inclusive=False)
            acc[s]["shots"] += 1
            acc[s]["xg"] += float(sh["xg"])

    passes = passes_xt(events, team_id=team_id)
    if not passes.empty:
        for _, p in passes.iterrows():
            ts = int(p["minute"]) * 60 + int(p["second"])
            s = _state_at(ts, team_id, home_id, away_id, goals, inclusive=False)
            acc[s]["xt"] += float(p["xt_added"])

    rows = []
    for s in STATE_ORDER:
        a = acc[s]
        mins = a["minutes"]
        rows.append({
            "state": s,
            "label": STATE_LABELS[s],
            "minutes": round(mins, 1),
            "shots": a["shots"],
            "xg": round(a["xg"], 3),
            "xt": round(a["xt"], 3),
            "xg_per90": round(a["xg"] / mins * 90, 3) if mins > 0 else 0.0,
            "xt_per90": round(a["xt"] / mins * 90, 3) if mins > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────
# Season aggregation (cached "deep tier") — scans partidos/ once and sums each
# match's per-state buckets, so Home / Pre-Match can show season-wide
# game-state splits.  Same caching pattern as processing.xt.compute_season_xt.
# ──────────────────────────────────────────────────────────────────────────
import json
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Segmenting by game state…")
def compute_season_game_state(league: str, season: str, team_id: str,
                              stage_filter: str = "") -> pd.DataFrame:
    """Season-wide game-state split for one team across all its matches.

    Sums minutes / shots / xG / xT per state over every match the team played,
    and counts how many matches contributed to each state (``matches``) so the
    UI can grey out states below ``MIN_MATCHES_FOR_PREDICTION`` — winning early
    in a thin Liga MX season may have a 2-match sample that isn't yet signal.

    Returns a DataFrame ``[state, label, matches, minutes, shots, xg, xt,
    xg_per90, xt_per90]`` (one row per state), or empty if no matches found.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    acc = {s: {"matches": 0, "minutes": 0.0, "shots": 0, "xg": 0.0, "xt": 0.0}
           for s in STATE_ORDER}
    found = 0

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
        seg = segment_match_by_state(events, team_id, home_id, away_id)
        if seg.empty:
            continue
        found += 1
        for _, r in seg.iterrows():
            s = int(r["state"])
            acc[s]["minutes"] += r["minutes"]
            acc[s]["shots"] += int(r["shots"])
            acc[s]["xg"] += r["xg"]
            acc[s]["xt"] += r["xt"]
            # a state "appears" in a match only if the team spent time there
            if r["minutes"] > 0:
                acc[s]["matches"] += 1

    if found == 0:
        return pd.DataFrame()

    rows = []
    for s in STATE_ORDER:
        a = acc[s]
        mins = a["minutes"]
        rows.append({
            "state": s,
            "label": STATE_LABELS[s],
            "matches": a["matches"],
            "minutes": round(mins, 1),
            "shots": a["shots"],
            "xg": round(a["xg"], 2),
            "xt": round(a["xt"], 2),
            "xg_per90": round(a["xg"] / mins * 90, 3) if mins > 0 else 0.0,
            "xt_per90": round(a["xt"] / mins * 90, 3) if mins > 0 else 0.0,
        })
    return pd.DataFrame(rows)
