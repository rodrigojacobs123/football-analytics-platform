from __future__ import annotations
"""Carry valuation — the xT a player adds by *driving* the ball, not passing it.

Ball-carrying was invisible to the platform: we valued passes (xT, xP) and shots
(xG) but never the ground a player covers with the ball at their feet, which is
~25-30% of all open-play progression and the heart of OBV's "ball-drive"
component.  ``data.event_parser.extract_carries`` reconstructs carries from the
event stream; this module prices each one with the same Karun-Singh xT grid the
pass model uses:

    carry_xt = xt(end) − xt(start)            (positive = drove into danger)

and flags the carries coaches actually care about:

    progressive   — a clearly forward drive (prog_distance ≥ PROG_FORWARD)
    final_third   — carried the ball from outside into the attacking third
    box_entry     — drove into the 18-yard box
    line_break    — crossed a vertical third boundary forward (an EVENT-DATA
                    PROXY for breaking an opponent line; true packing needs
                    tracking data and is never faked here)

All functions are pure (events → DataFrame/dict) except the cached
``compute_season_carries`` at the bottom — same deep-tier pattern as xt.py.
"""

import json

import pandas as pd
import streamlit as st

from data.paths import partidos_dir
from data.event_parser import extract_carries, parse_match_info
from processing.xt import xt_value

# Thresholds (Opta 0-100 pitch; ~1 unit ≈ 1 m).
PROG_FORWARD = 5.0          # forward component to count as "progressive"
_FINAL_THIRD_X = 66.67
_MID_THIRD_X = 33.33
_BOX_X, _BOX_Y_LO, _BOX_Y_HI = 83.0, 21.1, 78.9


def carries_value(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Per-carry xT and progression flags for every carry by ``team_id``.

    Returns the ``extract_carries`` frame with added columns:
        xt_start, xt_end, carry_xt (clipped ≥ 0 — threat *added*),
        progressive, final_third, box_entry, line_break.
    """
    df = extract_carries(events, team_id=team_id)
    if df.empty:
        return df

    df = df.copy()
    df["xt_start"] = df.apply(lambda r: xt_value(r["x"], r["y"]), axis=1)
    df["xt_end"] = df.apply(lambda r: xt_value(r["end_x"], r["end_y"]), axis=1)
    # Threat ADDED — a carry that retreats adds none (its worth is escaping
    # pressure, not creating danger), so clip at 0, mirroring expected_pass.reward.
    df["carry_xt"] = (df["xt_end"] - df["xt_start"]).clip(lower=0.0)

    df["progressive"] = df["prog_distance"] >= PROG_FORWARD
    df["final_third"] = (df["x"] < _FINAL_THIRD_X) & (df["end_x"] >= _FINAL_THIRD_X)
    df["box_entry"] = (
        (df["x"] < _BOX_X) & (df["end_x"] >= _BOX_X)
        & (df["end_y"] >= _BOX_Y_LO) & (df["end_y"] <= _BOX_Y_HI)
    )
    # Line-break PROXY: forward carry crossing a third boundary (def→mid or
    # mid→att). Counts defenders bypassed only by inference — labelled a proxy.
    def_to_mid = (df["x"] < _MID_THIRD_X) & (df["end_x"] >= _MID_THIRD_X)
    mid_to_att = (df["x"] < _FINAL_THIRD_X) & (df["end_x"] >= _FINAL_THIRD_X)
    df["line_break"] = (def_to_mid | mid_to_att) & (df["prog_distance"] > 0)
    return df


def carry_summary(events: list[dict], team_id: str) -> dict:
    """One-call team carry summary (mirrors xt.xt_summary).

    Returns {
        carries, progressive, final_third_entries, box_entries, line_breaks,
        total_carry_xt, total_distance,
        leaders (DataFrame: player_name, carries, prog, carry_xt, dist),
        carries_df (full frame),
    }.
    """
    df = carries_value(events, team_id=team_id)
    if df.empty:
        return {"carries": 0, "progressive": 0, "final_third_entries": 0,
                "box_entries": 0, "line_breaks": 0, "total_carry_xt": 0.0,
                "total_distance": 0.0, "leaders": pd.DataFrame(), "carries_df": df}

    leaders = pd.DataFrame()
    if "player_name" in df.columns:
        leaders = (df.groupby("player_name").agg(
            carries=("carry_xt", "size"),
            prog=("progressive", "sum"),
            carry_xt=("carry_xt", "sum"),
            dist=("distance", "sum"))
            .sort_values("carry_xt", ascending=False)
            .head(8).reset_index())
        leaders["carry_xt"] = leaders["carry_xt"].round(3)
        leaders["dist"] = leaders["dist"].round(0)

    return {
        "carries": len(df),
        "progressive": int(df["progressive"].sum()),
        "final_third_entries": int(df["final_third"].sum()),
        "box_entries": int(df["box_entry"].sum()),
        "line_breaks": int(df["line_break"].sum()),
        "total_carry_xt": round(float(df["carry_xt"].sum()), 3),
        "total_distance": round(float(df["distance"].sum()), 0),
        "leaders": leaders,
        "carries_df": df,
    }


@st.cache_data(ttl=3600, show_spinner="Computing season carries…")
def compute_season_carries(league: str, season: str, team_id: str,
                           stage_filter: str = "", min_appearances: int = 1) -> dict:
    """Season carry leaderboard for one team — who drives the ball, and how far.

    Returns {} if no matches, else {
        matches, carries, progressive, line_breaks, total_carry_xt,
        carry_xt_per_match, leaderboard (DataFrame)
    }.  ``leaderboard`` columns: player_name, carries, prog, final_third,
    box_entries, line_breaks, carry_xt, distance, apps, carry_xt_per_match.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    acc: dict[str, dict] = {}
    matches = 0
    tot_carries = tot_prog = tot_lb = 0
    tot_xt = tot_dist = 0.0

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

        df = carries_value(raw.get("liveData", {}).get("event", []), team_id=team_id)
        if df.empty:
            continue
        matches += 1
        tot_carries += len(df);  tot_prog += int(df["progressive"].sum())
        tot_lb += int(df["line_break"].sum())
        tot_xt += float(df["carry_xt"].sum());  tot_dist += float(df["distance"].sum())

        if "player_name" not in df.columns:
            continue
        g = df.groupby("player_name").agg(
            carries=("carry_xt", "size"), prog=("progressive", "sum"),
            final_third=("final_third", "sum"), box=("box_entry", "sum"),
            lb=("line_break", "sum"), xt=("carry_xt", "sum"),
            dist=("distance", "sum"))
        for name, r in g.iterrows():
            a = acc.setdefault(name, {"carries": 0, "prog": 0, "final_third": 0,
                                      "box": 0, "lb": 0, "xt": 0.0, "dist": 0.0,
                                      "apps": 0})
            a["carries"] += int(r["carries"]);  a["prog"] += int(r["prog"])
            a["final_third"] += int(r["final_third"]);  a["box"] += int(r["box"])
            a["lb"] += int(r["lb"]);  a["xt"] += float(r["xt"])
            a["dist"] += float(r["dist"]);  a["apps"] += 1

    if matches == 0:
        return {}

    leaderboard = pd.DataFrame([
        {
            "player_name": n,
            "carries": a["carries"],
            "prog": a["prog"],
            "final_third": a["final_third"],
            "box_entries": a["box"],
            "line_breaks": a["lb"],
            "carry_xt": round(a["xt"], 3),
            "distance": round(a["dist"], 0),
            "apps": a["apps"],
            "carry_xt_per_match": round(a["xt"] / a["apps"], 4),
        }
        for n, a in acc.items() if a["apps"] >= min_appearances
    ])
    if not leaderboard.empty:
        leaderboard = leaderboard.sort_values("carry_xt", ascending=False).reset_index(drop=True)

    return {
        "matches": matches,
        "carries": tot_carries,
        "progressive": tot_prog,
        "line_breaks": tot_lb,
        "total_carry_xt": round(tot_xt, 2),
        "carry_xt_per_match": round(tot_xt / matches, 3),
        "leaderboard": leaderboard,
    }
