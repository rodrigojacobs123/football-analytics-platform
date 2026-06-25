from __future__ import annotations
"""Expected Pass Completion (xP) + pass risk / reward decomposition.

The platform already values *where* a pass goes (``processing/xt.py`` — the
threat added if it is completed).  What it has never modelled is *how hard the
pass was to complete in the first place*.  Two midfielders can both add the same
xT per pass while one is threading 60-40 balls into the box and the other is
recycling 90-10 sideways passes — xT alone cannot tell them apart.  That is
exactly the gap **xP** closes:

    xp     = P(pass completed)                 — execution difficulty
    reward = xT added IF completed             — ambition / value
    risk   = 1 − xp                            — turnover probability

and a single decision-quality number that trades the two off:

    pass_value = xp · reward − (1 − xp) · TURNOVER_WEIGHT · xt_conceded_at_end

where ``xt_conceded_at_end`` is the threat the *opponent* inherits if the pass is
lost where it was aimed (its xT in the defender's flipped frame, exactly as
``xdef.py`` prices threat-denial).

Model
-----
``estimate_xp`` is a **closed-form calibrated logistic** — deterministic, needs
no trained artefact, and runs identically on a single match or a whole-season
scan.  This is the same design choice as ``processing/xg_model.estimate_xg``:
the absolute calibration is approximate, but the *relative* ordering of passes
(which is all a risk/reward comparison needs) is robust.  Coefficients are
grounded in published Opta completion baselines (~80% overall; short backward
passes ~95%; long balls into the box / crosses ~25-40%).  A fitted
GradientBoosting model can later drop in behind ``estimate_xp`` without touching
any caller.

Everything below is pure pandas/numpy (no Streamlit) except the cached
``compute_season_xp`` / ``compute_league_xp`` at the bottom, mirroring the
xT / xDEF deep-tier pattern.
"""

import numpy as np
import pandas as pd

from data.event_parser import extract_passes
from processing.xt import xt_value


# ──────────────────────────────────────────────────────────────────────────
# DESIGN DECISION — how harshly a giveaway is punished relative to the reward.
#
# pass_value trades the reward of a completed pass against the danger conceded
# on a turnover.  TURNOVER_WEIGHT scales that downside:
#   • 1.0  → a unit of conceded threat hurts exactly as much as a unit gained
#            (symmetric — values safe possession highly).
#   • <1.0 → encourages ambition; turnovers in the opponent half are cheap.
#   • >1.0 → ultra risk-averse; punishes any loss of the ball.
# Like xdef.DEF_ACTION_WEIGHTS, this is a genuine club-philosophy knob, not a
# fact — América's vertical, front-foot identity argues for a value < 1.
# ──────────────────────────────────────────────────────────────────────────
TURNOVER_WEIGHT: float = 0.6

# Logistic coefficients (logit space). Tuned to published completion baselines.
_XP_INTERCEPT = 2.40          # ~0.917 for a 0-length sideways pass in own half
_XP_B_DISTANCE = -0.045       # per Opta length unit (0-100 pitch)
_XP_B_FORWARD = -0.018        # per unit of FORWARD progression (dx>0)
_XP_B_BACKWARD = 0.010        # backward passes are easier (dx<0 → +logit)
_XP_FINAL_THIRD = -0.55       # entering the attacking third under pressure
_XP_INTO_BOX = -0.90          # into the 18-yard box
_XP_CROSS = -1.30             # crosses complete ~25-30%
_XP_THROUGH = -1.00           # through balls split the line
_XP_LONGBALL = -0.45          # aerial long balls are contested
_XP_HEADER = -0.40            # headed passes less controlled

_FINAL_THIRD_X = 66.67
_BOX_X, _BOX_Y_LO, _BOX_Y_HI = 83.0, 21.1, 78.9


def estimate_xp(length: float, dx: float, end_x: float, end_y: float,
                is_cross: bool = False, is_through: bool = False,
                is_longball: bool = False, is_header: bool = False) -> float:
    """Completion probability for one pass (closed-form calibrated logistic)."""
    logit = _XP_INTERCEPT
    logit += _XP_B_DISTANCE * length
    if dx >= 0:
        logit += _XP_B_FORWARD * dx
    else:
        logit += _XP_B_BACKWARD * (-dx)
    if end_x >= _FINAL_THIRD_X and dx > 0:
        logit += _XP_FINAL_THIRD
    if end_x >= _BOX_X and _BOX_Y_LO <= end_y <= _BOX_Y_HI:
        logit += _XP_INTO_BOX
    if is_cross:
        logit += _XP_CROSS
    if is_through:
        logit += _XP_THROUGH
    if is_longball:
        logit += _XP_LONGBALL
    if is_header:
        logit += _XP_HEADER
    p = 1.0 / (1.0 + np.exp(-logit))
    return float(min(max(p, 0.01), 0.999))


def passes_xp(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Per-pass xP, reward, risk and pass_value for every open-play pass.

    Returns the ``extract_passes`` frame with added columns:
        length, dx, xp, reward, risk, pass_value, completed.
    Set pieces still come through ``extract_passes`` — they carry their geometry
    so xP still scores them sensibly (a corner is just a long cross-flagged
    pass); callers wanting open-play only can filter upstream.
    """
    df = extract_passes(events, team_id=team_id)
    if df.empty or "end_x" not in df.columns:
        return df

    df = df.copy()
    clean = df["end_x"].notna() & df["end_y"].notna()
    # Geometry — vectorised.
    dx = (df["end_x"] - df["x"]).where(clean, 0.0)
    dy = (df["end_y"] - df["y"]).where(clean, 0.0)
    df["length"] = np.sqrt(dx ** 2 + dy ** 2).fillna(0.0)
    df["dx"] = dx.fillna(0.0)

    for col in ("is_cross", "is_through", "is_longball", "is_header"):
        if col not in df.columns:
            df[col] = False

    def _row_xp(r) -> float:
        if not (pd.notna(r["end_x"]) and pd.notna(r["end_y"])):
            return 0.85   # geometry unknown → neutral prior
        return estimate_xp(r["length"], r["dx"], r["end_x"], r["end_y"],
                           bool(r["is_cross"]), bool(r["is_through"]),
                           bool(r["is_longball"]), bool(r["is_header"]))

    df["xp"] = df.apply(_row_xp, axis=1)
    df["risk"] = 1.0 - df["xp"]

    # Reward = xT gained if completed (clip negatives — a backward pass that
    # *loses* threat shouldn't read as "reward"; its value is in retaining
    # possession, captured by the low risk term).
    reward = df.apply(
        lambda r: max(xt_value(r["end_x"], r["end_y"]) - xt_value(r["x"], r["y"]), 0.0)
        if pd.notna(r["end_x"]) and pd.notna(r["end_y"]) else 0.0,
        axis=1)
    df["reward"] = reward

    # Threat the opponent inherits if the ball is turned over where it was
    # aimed (defender's flipped frame, same as xdef.defensive_xt_denied).
    conceded = df.apply(
        lambda r: xt_value(100.0 - r["end_x"], r["end_y"])
        if pd.notna(r["end_x"]) and pd.notna(r["end_y"]) else 0.0,
        axis=1)
    df["completed"] = (df.get("outcome", 0) == 1)
    # REALIZED decision value: a completed pass banks its reward; a failed pass
    # concedes the opponent the threat at the loss location (scaled by the
    # club's risk appetite). Summing this over a player/team gives an
    # interpretable net contribution. (The ex-ante risk/reward AXES — avg_risk,
    # avg_reward — are kept separately for the decision-quality scatter.)
    df["pass_value"] = df["reward"].where(df["completed"],
                                          -TURNOVER_WEIGHT * conceded)
    return df


def xp_summary(events: list[dict], team_id: str) -> dict:
    """One-call team-level xP summary (mirrors xt.xt_summary).

    Returns {
        passes, completion_pct, exp_completion_pct (mean xp), pass_rating
            (actual − expected completion, ×100 = "passing over expectation"),
        avg_risk, avg_reward, total_pass_value,
        leaders (DataFrame: player_name, passes, completion, xp, over_exp,
                 reward, risk, pass_value),
        passes_df (full frame with xp columns),
    }.
    """
    df = passes_xp(events, team_id=team_id)
    if df.empty:
        return {"passes": 0, "completion_pct": 0.0, "exp_completion_pct": 0.0,
                "pass_rating": 0.0, "avg_risk": 0.0, "avg_reward": 0.0,
                "total_pass_value": 0.0, "leaders": pd.DataFrame(),
                "passes_df": df}

    n = len(df)
    actual = float(df["completed"].mean())
    expected = float(df["xp"].mean())

    leaders = pd.DataFrame()
    if "player_name" in df.columns:
        g = df.groupby("player_name").agg(
            passes=("xp", "size"),
            completion=("completed", "mean"),
            xp=("xp", "mean"),
            reward=("reward", "mean"),
            risk=("risk", "mean"),
            pass_value=("pass_value", "sum"),
        )
        g = g[g["passes"] >= 10]      # ignore cameo passers in the per-match view
        if not g.empty:
            g["over_exp"] = (g["completion"] - g["xp"]) * 100
            leaders = (g.sort_values("pass_value", ascending=False)
                       .round({"completion": 3, "xp": 3, "reward": 4,
                               "risk": 3, "over_exp": 1, "pass_value": 3})
                       .reset_index())

    return {
        "passes": n,
        "completion_pct": round(actual * 100, 1),
        "exp_completion_pct": round(expected * 100, 1),
        "pass_rating": round((actual - expected) * 100, 1),
        "avg_risk": round(float(df["risk"].mean()), 3),
        "avg_reward": round(float(df["reward"].mean()), 4),
        "total_pass_value": round(float(df["pass_value"].sum()), 3),
        "leaders": leaders,
        "passes_df": df,
    }


# ──────────────────────────────────────────────────────────────────────────
# Cached deep tier — season aggregation + league-wide percentile scan.
# Same pattern as xt.compute_season_xt / xdef.compute_league_xdef.
# ──────────────────────────────────────────────────────────────────────────
import json
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


def _scan_partidos(league: str, season: str, stage_filter: str = ""):
    """Yield (info, events) for each played match file, stage-filtered."""
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return
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
        yield info, raw.get("liveData", {}).get("event", [])


@st.cache_data(ttl=3600, show_spinner="Computing season Expected Pass (xP)…")
def compute_season_xp(league: str, season: str, team_id: str,
                      stage_filter: str = "", min_appearances: int = 1) -> dict:
    """Season xP leaderboard for one team — who passes well, and how ambitiously.

    Returns {} if no matches, else {
        matches, passes, completion_pct, exp_completion_pct, pass_rating,
        total_pass_value, leaderboard (DataFrame)
    }.  ``leaderboard`` columns: player_name, passes, completion, xp, over_exp,
    avg_reward, avg_risk, pass_value, apps.
    """
    acc: dict[str, dict] = {}
    matches = tot_pass = 0
    tot_complete = tot_xp = tot_value = 0.0

    for info, events in _scan_partidos(league, season, stage_filter):
        if team_id not in (info["home_id"], info["away_id"]):
            continue
        df = passes_xp(events, team_id=team_id)
        if df.empty:
            continue
        matches += 1
        tot_pass += len(df)
        tot_complete += float(df["completed"].sum())
        tot_xp += float(df["xp"].sum())
        tot_value += float(df["pass_value"].sum())
        if "player_name" not in df.columns:
            continue
        g = df.groupby("player_name").agg(
            passes=("xp", "size"), complete=("completed", "sum"),
            xp=("xp", "sum"), reward=("reward", "sum"),
            risk=("risk", "sum"), value=("pass_value", "sum"))
        for name, r in g.iterrows():
            a = acc.setdefault(name, {"passes": 0, "complete": 0.0, "xp": 0.0,
                                      "reward": 0.0, "risk": 0.0, "value": 0.0,
                                      "apps": 0})
            a["passes"] += int(r["passes"]);  a["complete"] += float(r["complete"])
            a["xp"] += float(r["xp"]);        a["reward"] += float(r["reward"])
            a["risk"] += float(r["risk"]);    a["value"] += float(r["value"])
            a["apps"] += 1

    if matches == 0:
        return {}

    leaderboard = pd.DataFrame([
        {
            "player_name": n,
            "passes": a["passes"],
            "completion": round(a["complete"] / a["passes"], 3) if a["passes"] else 0.0,
            "xp": round(a["xp"] / a["passes"], 3) if a["passes"] else 0.0,
            "over_exp": round((a["complete"] - a["xp"]) / a["passes"] * 100, 1) if a["passes"] else 0.0,
            "avg_reward": round(a["reward"] / a["passes"], 4) if a["passes"] else 0.0,
            "avg_risk": round(a["risk"] / a["passes"], 3) if a["passes"] else 0.0,
            "pass_value": round(a["value"], 2),
            "apps": a["apps"],
        }
        for n, a in acc.items() if a["apps"] >= min_appearances
    ])
    if not leaderboard.empty:
        leaderboard = leaderboard.sort_values("pass_value", ascending=False).reset_index(drop=True)

    return {
        "matches": matches,
        "passes": tot_pass,
        "completion_pct": round(tot_complete / tot_pass * 100, 1) if tot_pass else 0.0,
        "exp_completion_pct": round(tot_xp / tot_pass * 100, 1) if tot_pass else 0.0,
        "pass_rating": round((tot_complete - tot_xp) / tot_pass * 100, 1) if tot_pass else 0.0,
        "total_pass_value": round(tot_value, 2),
        "leaderboard": leaderboard,
    }


@st.cache_data(ttl=3600, show_spinner="Computing league-wide xP percentiles…")
def compute_league_xp(league: str, season: str, stage_filter: str = "",
                      min_passes: int = 200) -> pd.DataFrame:
    """League-wide, cross-team player passing profiles with percentile ranks.

    Walks every match once, credits BOTH teams' passes, and percentile-ranks
    each qualifying passer.  ``min_passes`` (not appearances) gates the sample —
    passing metrics stabilise on volume, not match count.

    Returns [player_id, player_name, team_id, team_name, passes, completion,
    xp, over_exp, avg_reward, avg_risk, pass_value_p90, value_pct,
    overexp_pct] sorted by value_pct desc, or empty frame.
    ``over_exp`` is passing-over-expectation (×100); ``pass_value_p90`` is
    decision value per ~1000 passes for a fair cross-volume comparison.
    """
    acc: dict[str, dict] = {}
    names: dict[str, str] = {}
    matches = 0

    for info, events in _scan_partidos(league, season, stage_filter):
        home_id, away_id = info["home_id"], info["away_id"]
        if not home_id or not away_id:
            continue
        names[home_id] = info["home_team"]
        names[away_id] = info["away_team"]
        matches += 1
        for tid in (home_id, away_id):
            df = passes_xp(events, team_id=tid)
            if df.empty or "player_id" not in df.columns:
                continue
            g = df.groupby(["player_id", "player_name"]).agg(
                passes=("xp", "size"), complete=("completed", "sum"),
                xp=("xp", "sum"), reward=("reward", "sum"),
                risk=("risk", "sum"), value=("pass_value", "sum"))
            for (pid, pname), r in g.iterrows():
                if not pid:
                    continue
                a = acc.setdefault(pid, {"player_name": pname, "team_id": tid,
                                         "passes": 0, "complete": 0.0, "xp": 0.0,
                                         "reward": 0.0, "risk": 0.0, "value": 0.0})
                a["passes"] += int(r["passes"]);  a["complete"] += float(r["complete"])
                a["xp"] += float(r["xp"]);        a["reward"] += float(r["reward"])
                a["risk"] += float(r["risk"]);    a["value"] += float(r["value"])
                a["team_id"] = tid
                if pname:
                    a["player_name"] = pname

    if matches == 0:
        return pd.DataFrame()

    out = pd.DataFrame([
        {
            "player_id": pid,
            "player_name": a["player_name"],
            "team_id": a["team_id"],
            "team_name": names.get(a["team_id"], a["team_id"][:8]),
            "passes": a["passes"],
            "completion": round(a["complete"] / a["passes"], 3),
            "xp": round(a["xp"] / a["passes"], 3),
            "over_exp": round((a["complete"] - a["xp"]) / a["passes"] * 100, 1),
            "avg_reward": round(a["reward"] / a["passes"], 4),
            "avg_risk": round(a["risk"] / a["passes"], 3),
            "pass_value_p90": round(a["value"] / a["passes"] * 1000, 2),
        }
        for pid, a in acc.items() if a["passes"] >= min_passes
    ])
    if out.empty:
        return out
    out["value_pct"] = (out["pass_value_p90"].rank(pct=True) * 100).round(1)
    out["overexp_pct"] = (out["over_exp"].rank(pct=True) * 100).round(1)
    return out.sort_values("value_pct", ascending=False).reset_index(drop=True)
