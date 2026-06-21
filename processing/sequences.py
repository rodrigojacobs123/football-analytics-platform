from __future__ import annotations
"""Possession sequences → playing-style metrics (Stats Perform conventions).

A **sequence** is a passage of play belonging to one team, ended by an opponent
defensive action, a stoppage, or a shot.  Sequences are the backbone of modern
team-style profiling — they describe *how* a team plays, not how good its
players are (which ``processing/player_ratings.py`` already covers).

From sequences we derive two canonical style metrics:

  • Directness   = upfield (x) progress ÷ total ball-path length.
                   1.0 = a perfectly vertical move; low = patient, lateral build-up.
  • Direct speed = upfield progress (metres) ÷ sequence duration (seconds).
                   How fast the team moves the ball toward goal — m/s.

Plus descriptive shape: passes per sequence, sequences per shot, share of long
("10+ pass") build-ups vs. fast direct attacks.

Opta coordinates are 0-100 in the acting team's attacking frame (x=100 is the
opponent goal), so "progress" is simply the gain in x.

Reference:
    Opta Analyst — "Sequences and Possessions in Football"
    Stats Perform — "Introducing a Possessions Framework"
"""

import math
import pandas as pd
from config import (
    EVENT_PASS, EVENT_OFFSIDE_PASS, EVENT_TAKE_ON, EVENT_BALL_TOUCH,
    EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED, EVENT_GOAL,
    EVENT_OUT, EVENT_FOUL, EVENT_CORNER, EVENT_END,
)

# Pitch scale: Opta x-unit → metres (105 m pitch / 100 units).
_X_SCALE = 1.05

# On-ball events that build a possession sequence.
_ON_BALL = {EVENT_PASS, EVENT_OFFSIDE_PASS, EVENT_TAKE_ON, EVENT_BALL_TOUCH}
_SHOTS = {EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED, EVENT_GOAL}
# Events that force a sequence to end (stoppages).
_STOPPAGES = {EVENT_OUT, EVENT_FOUL, EVENT_CORNER, EVENT_END}


def _ts(ev: dict) -> float:
    return int(ev.get("timeMin", 0)) * 60 + int(ev.get("timeSec", 0))


def _dist(x0: float, y0: float, x1: float, y1: float) -> float:
    return math.hypot(x1 - x0, y1 - y0)


def compute_sequences(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Segment a match's events into possession sequences.

    Walks events chronologically, opening a sequence when a team starts an
    on-ball passage and closing it on a shot, a stoppage, or possession
    switching to the opponent.  Returns one row per sequence; pass ``team_id``
    to keep only that team's sequences.

    Columns: ``team_id, start_min, n_passes, n_actions, progress (x-units),
    path_length, duration_s, directness, direct_speed (m/s), has_shot,
    ended_by``.
    """
    chron = sorted(events, key=lambda e: (
        int(e.get("timeMin", 0)), int(e.get("timeSec", 0)), int(e.get("eventId", 0))))

    rows: list[dict] = []
    cur: dict | None = None

    def close(ended_by: str):
        nonlocal cur
        if cur and cur["n_actions"] > 0:
            prog = cur["max_x"] - cur["start_x"]                 # x-units gained
            path = cur["path_length"]
            dur = max(cur["last_ts"] - cur["start_ts"], 0.0)
            cur["progress"] = round(prog, 1)
            cur["path_length"] = round(path, 1)
            cur["duration_s"] = round(dur, 1)
            cur["directness"] = round(max(prog, 0) / path, 3) if path > 0 else 0.0
            cur["direct_speed"] = round((prog * _X_SCALE) / dur, 2) if dur > 0 else 0.0
            cur["ended_by"] = ended_by
            rows.append(cur)
        cur = None

    for ev in chron:
        tid = ev.get("typeId")
        team = ev.get("contestantId")
        x, y = float(ev.get("x", 0)), float(ev.get("y", 0))

        if tid in _ON_BALL:
            if cur is None or cur["team_id"] != team:
                # possession switched (or first action) → start fresh sequence
                if cur is not None:
                    close("turnover")
                cur = {
                    "team_id": team, "start_min": int(ev.get("timeMin", 0)),
                    "start_x": x, "max_x": x, "last_x": x, "last_y": y,
                    "path_length": 0.0, "n_passes": 0, "n_actions": 0,
                    "start_ts": _ts(ev), "last_ts": _ts(ev), "has_shot": False,
                }
            cur["path_length"] += _dist(cur["last_x"], cur["last_y"], x, y)
            cur["last_x"], cur["last_y"] = x, y
            cur["last_ts"] = _ts(ev)
            cur["max_x"] = max(cur["max_x"], x)
            cur["n_actions"] += 1
            if tid in (EVENT_PASS, EVENT_OFFSIDE_PASS):
                cur["n_passes"] += 1

        elif tid in _SHOTS:
            if cur is not None and cur["team_id"] == team:
                cur["has_shot"] = True
                cur["max_x"] = max(cur["max_x"], x)
                cur["n_actions"] += 1
                cur["last_ts"] = _ts(ev)
                close("shot")
            else:
                close("shot")
        elif tid in _STOPPAGES:
            close("stoppage")

    close("end")

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[["team_id", "start_min", "n_passes", "n_actions", "progress",
                 "path_length", "duration_s", "directness", "direct_speed",
                 "has_shot", "ended_by"]]
        if team_id is not None:
            df = df[df["team_id"] == team_id].reset_index(drop=True)
    return df


def team_style_summary(sequences: pd.DataFrame, team_id: str) -> dict:
    """Aggregate one team's sequences into playing-style descriptors.

    ``sequences`` may be a single match or many matches concatenated.  Only
    sequences with ≥ 2 actions count toward style (a one-touch clearance isn't
    a build-up).  Returns means and shares used by the style-quadrant chart.
    """
    df = sequences[sequences["team_id"] == team_id] if "team_id" in sequences else sequences
    df = df[df["n_actions"] >= 2]
    n = len(df)
    if n == 0:
        return {"sequences": 0}
    shots = int(df["has_shot"].sum())
    return {
        "sequences": n,
        "avg_passes_per_seq": round(df["n_passes"].mean(), 2),
        "avg_directness": round(df["directness"].mean(), 3),
        "avg_direct_speed": round(df["direct_speed"].mean(), 2),
        "avg_progress": round(df["progress"].mean(), 1),
        "sequences_per_shot": round(n / shots, 1) if shots else None,
        # share of long build-ups (10+ passes) vs. fast direct attacks
        "long_buildup_share": round((df["n_passes"] >= 10).mean(), 3),
        "direct_attack_share": round(
            ((df["direct_speed"] >= 2.0) & (df["progress"] >= 25)).mean(), 3),
    }


# ──────────────────────────────────────────────────────────────────────────
# Season aggregation (cached "deep tier") — scans partidos/ once and returns a
# per-team playing-style table for the whole league, used by the style-quadrant
# chart on the Tactics page.  Same pattern as season_tactics.compute_season_xt.
# ──────────────────────────────────────────────────────────────────────────
import json
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Computing playing-style sequences…")
def compute_season_sequences(league: str, season: str,
                             stage_filter: str = "") -> pd.DataFrame:
    """Per-team playing-style summary across every match in the season.

    Returns a DataFrame indexed by team with the columns from
    ``team_style_summary`` plus ``team_id`` / ``team_name`` — one row per team,
    ready to plot on a directness × passes-per-sequence quadrant.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    per_team: dict[str, list[pd.DataFrame]] = {}
    names: dict[str, str] = {}

    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue
        names[info["home_id"]] = info["home_team"]
        names[info["away_id"]] = info["away_team"]

        events = raw.get("liveData", {}).get("event", [])
        seqs = compute_sequences(events)
        if seqs.empty:
            continue
        for tid, grp in seqs.groupby("team_id"):
            per_team.setdefault(tid, []).append(grp)

    rows = []
    for tid, frames in per_team.items():
        allseq = pd.concat(frames, ignore_index=True)
        s = team_style_summary(allseq, tid)
        if s.get("sequences", 0) == 0:
            continue
        s["team_id"] = tid
        s["team_name"] = names.get(tid, tid)
        rows.append(s)

    return pd.DataFrame(rows)
