from __future__ import annotations
"""On-Ball Value (OBV) — a single value for every action a player performs.

The frontier metric this platform was missing: one number per player that adds up
*all* the ways they move the needle on the ball — passing, carrying, shooting,
and defending — onto a common xT/xG scale.  StatsBomb call it OBV; the open
methodology is VAEP (Decroos et al., 2019).

HONEST SCOPE — read this before extending
-----------------------------------------
A *true* VAEP trains two models, P(score next) and P(concede next), and credits
each action the change in those probabilities.  That is powerful but fragile: the
"next goal" label leaks easily (the corner-award-timestamp bug and the
eventId-not-unique bug were the same class of mistake), and it needs a stored,
periodically-retrained artefact this single-process app has nowhere to keep.

So this module ships the robust, transparent alternative: an **additive
action-value composite** built from components the platform already computes and
trusts —

    obv = pass_value      (expected_pass.passes_xp — xP-weighted reward−risk)
        + carry_xt        (carries.carries_value   — xT driven with the ball)
        + shot_value      (xG of the player's shots — goal probability created)
        + def_value       (xdef.defensive_actions_xdef — xT denied)

Every term is already on an xT/xG (probability-of-goal) scale, so the sum is
meaningful and — crucially — has NO forward-looking label, hence no leakage.
The trained two-model VAEP is the documented future upgrade behind this same
``player_obv`` interface.
"""

import json

import pandas as pd
import streamlit as st

from data.paths import partidos_dir
from data.event_parser import extract_shots, parse_match_info
from processing.expected_pass import passes_xp
from processing.carries import carries_value
from processing.xdef import defensive_actions_xdef


def player_obv(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Per-player On-Ball Value for one match, decomposed by component.

    Returns a DataFrame [player_id, player_name, pass_value, carry_value,
    shot_value, def_value, obv] — one row per player who had ≥1 on-ball action.
    ``obv`` = sum of the four components (all on an xT/xG scale).
    """
    acc: dict[str, dict] = {}

    def _slot(pid: str, pname: str) -> dict:
        s = acc.get(pid)
        if s is None:
            s = {"player_name": pname, "pass_value": 0.0, "carry_value": 0.0,
                 "shot_value": 0.0, "def_value": 0.0}
            acc[pid] = s
        elif pname:
            s["player_name"] = pname
        return s

    # Passing — xP-weighted decision value.
    p = passes_xp(events, team_id=team_id)
    if not p.empty and "player_id" in p.columns:
        for pid, r in p.groupby("player_id").agg(
                v=("pass_value", "sum"), name=("player_name", "first")).iterrows():
            if pid:
                _slot(pid, r["name"])["pass_value"] += float(r["v"])

    # Carrying — xT driven.
    c = carries_value(events, team_id=team_id)
    if not c.empty and "player_id" in c.columns:
        for pid, r in c.groupby("player_id").agg(
                v=("carry_xt", "sum"), name=("player_name", "first")).iterrows():
            if pid:
                _slot(pid, r["name"])["carry_value"] += float(r["v"])

    # Shooting — goal probability created (xG).
    s = extract_shots(events, team_id=team_id)
    if not s.empty and "player_id" in s.columns:
        for pid, r in s.groupby("player_id").agg(
                v=("xg", "sum"), name=("player_name", "first")).iterrows():
            if pid:
                _slot(pid, r["name"])["shot_value"] += float(r["v"])

    # Defending — xT denied (only credited team actions; xdef already zeroes
    # failed actions).
    d = defensive_actions_xdef(events, team_id=team_id)
    if not d.empty and "player_id" in d.columns:
        for pid, r in d.groupby("player_id").agg(
                v=("xdef", "sum"), name=("player_name", "first")).iterrows():
            if pid:
                _slot(pid, r["name"])["def_value"] += float(r["v"])

    if not acc:
        return pd.DataFrame(columns=["player_id", "player_name", "pass_value",
                                     "carry_value", "shot_value", "def_value", "obv"])

    out = pd.DataFrame([
        {"player_id": pid, **v} for pid, v in acc.items()
    ])
    out["obv"] = (out["pass_value"] + out["carry_value"]
                  + out["shot_value"] + out["def_value"])
    for col in ("pass_value", "carry_value", "shot_value", "def_value", "obv"):
        out[col] = out[col].round(3)
    return out.sort_values("obv", ascending=False).reset_index(drop=True)


def obv_summary(events: list[dict], team_id: str) -> dict:
    """Team OBV summary: totals by component + per-player table."""
    df = player_obv(events, team_id=team_id)
    if df.empty:
        return {"total_obv": 0.0, "by_component": {}, "players": df}
    return {
        "total_obv": round(float(df["obv"].sum()), 3),
        "by_component": {
            "passing": round(float(df["pass_value"].sum()), 3),
            "carrying": round(float(df["carry_value"].sum()), 3),
            "shooting": round(float(df["shot_value"].sum()), 3),
            "defending": round(float(df["def_value"].sum()), 3),
        },
        "players": df,
    }


@st.cache_data(ttl=3600, show_spinner="Computing league-wide On-Ball Value (OBV)…")
def compute_league_obv(league: str, season: str, stage_filter: str = "",
                       min_appearances: int = 3) -> pd.DataFrame:
    """League-wide, cross-team player OBV with percentile ranks.

    Walks every match once, credits BOTH teams, accumulates each component, and
    percentile-ranks OBV-per-appearance across the competition — the cross-team
    scan a player-value rating needs (same rationale as compute_league_xdef).

    Returns [player_id, player_name, team_id, team_name, apps, pass_value,
    carry_value, shot_value, def_value, obv, obv_per_match, pct] sorted by pct
    desc, or empty frame.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    acc: dict[str, dict] = {}
    names: dict[str, str] = {}
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
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue
        home_id, away_id = info["home_id"], info["away_id"]
        if not home_id or not away_id:
            continue
        names[home_id] = info["home_team"]
        names[away_id] = info["away_team"]
        events = raw.get("liveData", {}).get("event", [])
        matches += 1

        for tid in (home_id, away_id):
            df = player_obv(events, team_id=tid)
            if df.empty:
                continue
            for r in df.itertuples():
                if not r.player_id:
                    continue
                a = acc.setdefault(r.player_id, {
                    "player_name": r.player_name, "team_id": tid,
                    "pass_value": 0.0, "carry_value": 0.0, "shot_value": 0.0,
                    "def_value": 0.0, "obv": 0.0, "apps": 0})
                a["pass_value"] += r.pass_value;  a["carry_value"] += r.carry_value
                a["shot_value"] += r.shot_value;  a["def_value"] += r.def_value
                a["obv"] += r.obv;  a["apps"] += 1;  a["team_id"] = tid
                if r.player_name:
                    a["player_name"] = r.player_name

    if matches == 0:
        return pd.DataFrame()

    out = pd.DataFrame([
        {
            "player_id": pid,
            "player_name": a["player_name"],
            "team_id": a["team_id"],
            "team_name": names.get(a["team_id"], a["team_id"][:8]),
            "apps": a["apps"],
            "pass_value": round(a["pass_value"], 2),
            "carry_value": round(a["carry_value"], 2),
            "shot_value": round(a["shot_value"], 2),
            "def_value": round(a["def_value"], 2),
            # Per-match component rates — the basis for the balanced blend.
            "pass_pm": a["pass_value"] / a["apps"],
            "carry_pm": a["carry_value"] / a["apps"],
            "shot_pm": a["shot_value"] / a["apps"],
            "def_pm": a["def_value"] / a["apps"],
            "obv": round(a["obv"], 2),
            "obv_per_match": round(a["obv"] / a["apps"], 3),
        }
        for pid, a in acc.items() if a["apps"] >= min_appearances
    ])
    if out.empty:
        return out

    # ── Balanced blend (the GVM z-score pattern) ──────────────────────────
    # A naive sum of the four components lets the defensive term dominate: xdef
    # credits the FULL location-xT per action, while passing nets reward−risk to
    # near zero, so raw OBV just re-ranks defenders. We instead z-score each
    # per-match component across the league and sum in standard-deviation space,
    # so a +2σ playmaker and a +2σ ball-winner score alike. ``obv_score`` is the
    # 0-100 rescale; ``pct`` percentile-ranks it. Raw component sums are kept
    # above for transparency about where a player's value actually comes from.
    def _z(col: str) -> pd.Series:
        s = out[col]
        sd = s.std(ddof=0)
        return (s - s.mean()) / sd if sd > 1e-9 else s * 0.0

    out["obv_z"] = _z("pass_pm") + _z("carry_pm") + _z("shot_pm") + _z("def_pm")
    zmin, zmax = out["obv_z"].min(), out["obv_z"].max()
    rng = (zmax - zmin) or 1.0
    out["obv_score"] = ((out["obv_z"] - zmin) / rng * 100).round(1)
    out["pct"] = (out["obv_z"].rank(pct=True) * 100).round(1)
    out = out.drop(columns=["pass_pm", "carry_pm", "shot_pm", "def_pm"])
    return out.sort_values("pct", ascending=False).reset_index(drop=True)
