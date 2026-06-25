from __future__ import annotations
"""Manager profile statistics — record, formations, tactical tendencies.

Supports tenure-aware filtering: pass start_date/end_date to scope stats
to a specific manager's period in charge.
"""

import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import poisson
from collections import Counter
from data.loader import (
    load_all_season_results, load_season_matches, load_match_raw,
    load_managers, load_standings,
)
from data.event_parser import extract_formation, extract_shots, parse_match_info
from data.paths import list_match_files
from config import POISSON_MAX_GOALS


# ── Tenure date helpers ──────────────────────────────────────────────────────

def _parse_date(date_str: str) -> pd.Timestamp | None:
    """Parse Opta date string (e.g. '2024-11-11Z') to Timestamp."""
    if not date_str:
        return None
    clean = date_str.replace("Z", "").strip()
    try:
        return pd.Timestamp(clean)
    except Exception:
        return None


def _filter_by_tenure(df: pd.DataFrame, start_date: str = "",
                      end_date: str = "") -> pd.DataFrame:
    """Filter a results DataFrame to matches within a manager's tenure."""
    if df.empty or "date" not in df.columns:
        return df

    filtered = df.copy()
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    if start is not None:
        filtered = filtered[filtered["date"] >= start]
    if end is not None:
        filtered = filtered[filtered["date"] <= end]

    return filtered


# ── Coach queries ────────────────────────────────────────────────────────────

def get_head_coaches(league: str, season: str) -> list[dict]:
    """Return only head coaches (type == 'coach'), one per team.

    Filters out assistant coaches and inactive entries where possible.
    """
    managers = load_managers(league, season)
    # Keep only head coaches
    coaches = [m for m in managers if m["type"] == "coach" and m["active"]]
    # Fallback: if a team has no active coach, include inactive ones
    teams_with_coach = {c["team_id"] for c in coaches}
    for m in managers:
        if m["type"] == "coach" and m["team_id"] not in teams_with_coach:
            coaches.append(m)
            teams_with_coach.add(m["team_id"])
    return coaches


def get_all_team_coaches(league: str, season: str, team_id: str) -> list[dict]:
    """Return ALL head coaches for a specific team, sorted by start date.

    Includes both active and inactive coaches — captures full managerial
    history within the season (e.g., Ten Hag → Van Nistelrooij → Amorim).
    """
    managers = load_managers(league, season)
    team_coaches = [
        m for m in managers
        if m["team_id"] == team_id and m["type"] == "coach"
    ]
    # Sort by start_date (earliest first)
    team_coaches.sort(key=lambda c: c.get("start_date", "") or "9999")
    return team_coaches


# ── Tenure-aware stats ───────────────────────────────────────────────────────

def compute_manager_record(league: str, season: str, team_id: str,
                           start_date: str = "", end_date: str = "",
                           stage_filter: str = "") -> dict:
    """Compute a manager's W/D/L record from season results.

    If start_date/end_date are provided, filters to that tenure window.

    Returns dict with: played, won, drawn, lost, win_pct, gf, ga, gd,
    points, ppg (points per game).
    """
    results = load_all_season_results(league, season, stage_filter=stage_filter)
    if results.empty:
        return _empty_record()

    # Filter by team
    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    # Filter by tenure
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    if team_results.empty:
        return _empty_record()

    wins, draws, losses = 0, 0, 0
    gf, ga = 0, 0

    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my_goals = r["home_score"] if is_home else r["away_score"]
        opp_goals = r["away_score"] if is_home else r["home_score"]
        gf += my_goals
        ga += opp_goals

        if my_goals > opp_goals:
            wins += 1
        elif my_goals == opp_goals:
            draws += 1
        else:
            losses += 1

    played = wins + draws + losses
    points = wins * 3 + draws
    return {
        "played": played,
        "won": wins,
        "drawn": draws,
        "lost": losses,
        "win_pct": (wins / played * 100) if played > 0 else 0,
        "gf": gf,
        "ga": ga,
        "gd": gf - ga,
        "points": points,
        "ppg": round(points / played, 2) if played > 0 else 0,
    }


def compute_formation_usage(league: str, season: str, team_id: str,
                            start_date: str = "", end_date: str = "",
                            stage_filter: str = "") -> list[dict]:
    """Scan all matches for a team and count formation usage.

    If start_date/end_date are provided, only counts matches in that window.

    Returns list of dicts sorted by frequency: [{formation, count, pct}]
    """
    from data.loader import load_match_raw
    from data.paths import partidos_dir
    import json

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    formation_counter = Counter()

    pdir = partidos_dir(league, season)
    if pdir.exists():
        for fpath in pdir.iterdir():
            if fpath.suffix != ".json":
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                info = parse_match_info(raw)
                if team_id not in (info["home_id"], info["away_id"]):
                    continue

                # Stage filter (prefix match)
                if stage_filter:
                    sn = info.get("stage_name", "")
                    if not sn.lower().startswith(stage_filter.lower().strip()):
                        continue

                # Date filter for tenure
                if start or end:
                    match_date = _parse_date(info.get("date", ""))
                    if match_date:
                        if start and match_date < start:
                            continue
                        if end and match_date > end:
                            continue

                events = raw.get("liveData", {}).get("event", [])
                fm = extract_formation(events, team_id)
                if fm and fm["formation_str"]:
                    formation_counter[fm["formation_str"]] += 1
            except (json.JSONDecodeError, KeyError):
                continue

    total = sum(formation_counter.values())
    result = []
    for formation, count in formation_counter.most_common():
        result.append({
            "formation": formation,
            "count": count,
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return result


def compute_recent_form(league: str, season: str, team_id: str,
                        n: int = 5, start_date: str = "",
                        end_date: str = "", stage_filter: str = "") -> list[str]:
    """Get the last N results as W/D/L strings within tenure window."""
    results = load_all_season_results(league, season, stage_filter=stage_filter)
    if results.empty:
        return []

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)
    team_results = team_results.tail(n)

    form = []
    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        if my > opp:
            form.append("W")
        elif my == opp:
            form.append("D")
        else:
            form.append("L")
    return form


def compute_home_away_split(league: str, season: str, team_id: str,
                            start_date: str = "", end_date: str = "",
                            stage_filter: str = "") -> dict:
    """Compute home vs away performance split within tenure window.

    Returns dict with home_{w,d,l,gf,ga} and away_{w,d,l,gf,ga}.
    """
    results = load_all_season_results(league, season, stage_filter=stage_filter)
    if results.empty:
        return _empty_split()

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    split = _empty_split()

    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        prefix = "home" if is_home else "away"

        split[f"{prefix}_gf"] += my
        split[f"{prefix}_ga"] += opp

        if my > opp:
            split[f"{prefix}_w"] += 1
        elif my == opp:
            split[f"{prefix}_d"] += 1
        else:
            split[f"{prefix}_l"] += 1

    return split


def compute_goals_timeline(league: str, season: str, team_id: str,
                           start_date: str = "", end_date: str = "",
                           stage_filter: str = "") -> pd.DataFrame:
    """Build a matchday-by-matchday goals scored/conceded timeline.

    Returns DataFrame: match_num, matchday, gf, ga, gd_cumulative.
    """
    results = load_all_season_results(league, season, stage_filter=stage_filter)
    if results.empty:
        return pd.DataFrame()

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    rows = []
    cum_gd = 0
    for i, (_, r) in enumerate(team_results.iterrows(), 1):
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        cum_gd += my - opp
        rows.append({
            "match_num": i,
            "matchday": r.get("matchday", i),
            "gf": my,
            "ga": opp,
            "gd_cumulative": cum_gd,
        })

    return pd.DataFrame(rows)


# ── Comparison helper ────────────────────────────────────────────────────────

def compare_managers(league: str, season: str, team_id: str,
                     coaches: list[dict], stage_filter: str = "") -> pd.DataFrame:
    """Build a comparison DataFrame across multiple coaches for the same team.

    Returns DataFrame with one row per coach: name, tenure, record, PPG,
    win rate, GF/game, GA/game, preferred formation.
    """
    rows = []
    for c in coaches:
        rec = compute_manager_record(
            league, season, team_id,
            start_date=c.get("start_date", ""),
            end_date=c.get("end_date", ""),
            stage_filter=stage_filter,
        )
        forms = compute_formation_usage(
            league, season, team_id,
            start_date=c.get("start_date", ""),
            end_date=c.get("end_date", ""),
            stage_filter=stage_filter,
        )
        pref_formation = forms[0]["formation"] if forms else "N/A"

        start = c.get("start_date", "")[:10] or "?"
        end = c.get("end_date", "")[:10] or "Present"

        rows.append({
            "Manager": c["name"],
            "Tenure": f"{start} → {end}",
            "P": rec["played"],
            "W": rec["won"],
            "D": rec["drawn"],
            "L": rec["lost"],
            "Win %": round(rec["win_pct"], 1),
            "PPG": rec["ppg"],
            "GF/G": round(rec["gf"] / rec["played"], 2) if rec["played"] else 0,
            "GA/G": round(rec["ga"] / rec["played"], 2) if rec["played"] else 0,
            "GD": rec["gd"],
            "Formation": pref_formation,
        })

    return pd.DataFrame(rows)


# ── Manager Over/Under-achievement (MOU) — expected points vs actual ─────────
#
# MOU asks whether a manager's *results* are backed by the underlying chances:
# convert each match's xG-for and xG-against into an expected-points value
# (xPts), sum over the tenure, and compare to points actually taken.
#   MOU = actual_points − expected_points
# A large positive MOU = over-achieving (clinical, lucky, or great in low-xG
# moments); negative = under-achieving (creating more than the table shows).
# Reuses the platform's xG (Σ shot xG per team per match) — no new model.


def match_expected_points(xg_for: float, xg_against: float,
                          *, max_goals: int = POISSON_MAX_GOALS) -> tuple[float, float, float]:
    """Convert a single match's xG into (P(win), P(draw), P(loss)) for the team.

    Implemented with **Approach A** (closed-form Poisson) below — the choice is
    documented here because the whole MOU index hangs on how you turn two
    expected-goal totals into an outcome distribution.  Two defensible
    approaches, with a real trade-off:

      A) **Closed-form Poisson** (simple, fast, the standard).  Model goals as
         two independent Poissons: ``G_for ~ Poisson(xg_for)`` and
         ``G_against ~ Poisson(xg_against)``.  Then
            P(win)  = Σ_{a>b} pmf(a; xg_for)·pmf(b; xg_against)
            P(draw) = Σ_{a=b} pmf(a; xg_for)·pmf(b; xg_against)
            P(loss) = 1 − P(win) − P(draw)
         Iterate a,b over 0..max_goals.  ``scipy.stats.poisson.pmf`` is already
         a dependency (see processing/poisson.py).  Cons: treats total xG as if
         it arrived in one lump — three 0.3-xG shots look identical to one
         0.9-xG shot, which slightly understates the variance of many small
         chances.

      B) **Per-shot Bernoulli Monte-Carlo** (more faithful).  Simulate each
         individual shot as a Bernoulli(shot_xg) and count goals across N sims.
         Captures that many small chances ≠ one big chance.  Needs the per-shot
         xG lists passed in (a richer signature) and is slower.

    Approach A is the recommended default — it matches the rest of the app's
    Poisson machinery and needs only the two aggregate xG numbers this function
    already receives.  Return the three probabilities; the caller derives
    ``xPts = 3·P(win) + 1·P(draw)``.

    Approach A naturally handles the degenerate case: with xg ≈ 0 the Poisson
    mass collapses onto 0 goals, so ``grid[0,0]→1`` and the match reads as a
    draw.  We renormalise to absorb the truncated tail beyond ``max_goals`` so
    the three probabilities sum to 1.0.
    """
    a = poisson.pmf(np.arange(max_goals + 1), max(xg_for, 1e-9))
    b = poisson.pmf(np.arange(max_goals + 1), max(xg_against, 1e-9))
    grid = np.outer(a, b)                      # grid[i, j] = P(for=i, against=j)
    p_win = float(np.tril(grid, -1).sum())     # for > against
    p_draw = float(np.trace(grid))             # for == against
    p_loss = float(np.triu(grid, 1).sum())     # for < against
    total = p_win + p_draw + p_loss            # < 1.0 by the truncated tail
    if total > 0:
        p_win, p_draw, p_loss = p_win / total, p_draw / total, p_loss / total
    return p_win, p_draw, p_loss


def _match_xg_totals(events: list[dict], home_id: str, away_id: str) -> tuple[float, float]:
    """Sum each side's shot xG for one match → (home_xg, away_xg)."""
    shots = extract_shots(events)
    if shots.empty:
        return 0.0, 0.0
    home_xg = float(shots.loc[shots["team_id"] == home_id, "xg"].sum())
    away_xg = float(shots.loc[shots["team_id"] == away_id, "xg"].sum())
    return home_xg, away_xg


def compute_manager_xpts(league: str, season: str, team_id: str,
                         start_date: str = "", end_date: str = "",
                         stage_filter: str = "") -> pd.DataFrame:
    """Per-match xPts vs actual points for ``team_id`` within a tenure window.

    Scans ``partidos/`` (heavy tier — same pattern as ``compute_formation_usage``),
    aggregates each match's xG-for / xG-against, and calls
    ``match_expected_points`` to get the outcome distribution.  Returns one row
    per match with: opponent, venue, xg_for, xg_against, actual_pts, xpts,
    plus running totals available via ``.sum()`` by the caller.

    Returns an empty frame if no matches match the filters.
    """
    import json
    from data.paths import partidos_dir

    start = _parse_date(start_date)
    end = _parse_date(end_date)

    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    rows: list[dict] = []
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
        if info.get("match_status") != "Played":
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue
        if start or end:
            md = _parse_date(info.get("date", ""))
            if md and ((start and md < start) or (end and md > end)):
                continue

        events = raw.get("liveData", {}).get("event", [])
        home_xg, away_xg = _match_xg_totals(events, home_id, away_id)

        is_home = team_id == home_id
        xg_for = home_xg if is_home else away_xg
        xg_against = away_xg if is_home else home_xg
        my_goals = info["home_score"] if is_home else info["away_score"]
        opp_goals = info["away_score"] if is_home else info["home_score"]
        actual_pts = 3 if my_goals > opp_goals else (1 if my_goals == opp_goals else 0)

        p_win, p_draw, _ = match_expected_points(xg_for, xg_against)
        xpts = 3.0 * p_win + 1.0 * p_draw

        rows.append({
            "date": info.get("date", "")[:10],
            "opponent": info["away_team"] if is_home else info["home_team"],
            "venue": "H" if is_home else "A",
            "xg_for": round(xg_for, 2),
            "xg_against": round(xg_against, 2),
            "actual_pts": actual_pts,
            "xpts": round(xpts, 2),
        })

    return pd.DataFrame(rows)


def compute_mou_index(league: str, season: str, team_id: str,
                      start_date: str = "", end_date: str = "",
                      stage_filter: str = "") -> dict:
    """Manager Over/Under-achievement summary for a tenure window.

    Returns: matches, actual_points, expected_points (xPts), mou (actual −
    expected), mou_per_game, plus xg_for/xg_against totals.  Empty-safe.
    Respects ``MIN_MATCHES_FOR_PREDICTION`` is the caller's job — xPts is noisy
    over a handful of games, so surface the match count alongside MOU.
    """
    per_match = compute_manager_xpts(
        league, season, team_id, start_date, end_date, stage_filter)
    if per_match.empty:
        return {"matches": 0, "actual_points": 0, "expected_points": 0.0,
                "mou": 0.0, "mou_per_game": 0.0, "xg_for": 0.0, "xg_against": 0.0}

    n = len(per_match)
    actual = int(per_match["actual_pts"].sum())
    expected = float(per_match["xpts"].sum())
    return {
        "matches": n,
        "actual_points": actual,
        "expected_points": round(expected, 2),
        "mou": round(actual - expected, 2),
        "mou_per_game": round((actual - expected) / n, 3),
        "xg_for": round(float(per_match["xg_for"].sum()), 2),
        "xg_against": round(float(per_match["xg_against"].sum()), 2),
    }


@st.cache_data(ttl=3600, show_spinner="Computing league xPts…")
def compute_league_mou(league: str, season: str, stage_filter: str = "") -> pd.DataFrame:
    """League-wide xPts vs actual points for every team, in ONE partidos pass.

    Per-team MOU (``compute_mou_index``) scans ``partidos/`` once *per team*;
    for a league-wide scatter that is N redundant scans, so this walks the
    folder a single time and accumulates both sides of every match.  Cached, so
    the All-Coaches scatter recomputes only when the competition changes.

    Returns one row per team: ``team_id, team_name, matches, actual_points,
    expected_points, ppg, xppg, mou, mou_per_game`` (empty frame if none).
    The per-team value maps to that team's season head coach in the page.
    """
    import json
    from data.paths import partidos_dir

    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    acc: dict[str, dict] = {}
    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        if info.get("match_status") != "Played":
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue

        home_id, away_id = info["home_id"], info["away_id"]
        events = raw.get("liveData", {}).get("event", [])
        home_xg, away_xg = _match_xg_totals(events, home_id, away_id)

        for tid, name, xg_for, xg_against, my_g, opp_g in [
            (home_id, info["home_team"], home_xg, away_xg, info["home_score"], info["away_score"]),
            (away_id, info["away_team"], away_xg, home_xg, info["away_score"], info["home_score"]),
        ]:
            if not tid:
                continue
            a = acc.setdefault(tid, {"team_name": name, "matches": 0,
                                     "actual_points": 0, "expected_points": 0.0})
            p_win, p_draw, _ = match_expected_points(xg_for, xg_against)
            a["matches"] += 1
            a["actual_points"] += 3 if my_g > opp_g else (1 if my_g == opp_g else 0)
            a["expected_points"] += 3.0 * p_win + 1.0 * p_draw

    if not acc:
        return pd.DataFrame()

    rows = []
    for tid, a in acc.items():
        n = max(a["matches"], 1)
        rows.append({
            "team_id": tid,
            "team_name": a["team_name"],
            "matches": a["matches"],
            "actual_points": a["actual_points"],
            "expected_points": round(a["expected_points"], 2),
            "ppg": round(a["actual_points"] / n, 3),
            "xppg": round(a["expected_points"] / n, 3),
            "mou": round(a["actual_points"] - a["expected_points"], 2),
            "mou_per_game": round((a["actual_points"] - a["expected_points"]) / n, 3),
        })
    return pd.DataFrame(rows).sort_values("mou", ascending=False).reset_index(drop=True)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _empty_record() -> dict:
    return {
        "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "win_pct": 0, "gf": 0, "ga": 0, "gd": 0,
        "points": 0, "ppg": 0,
    }


def _empty_split() -> dict:
    return {
        "home_w": 0, "home_d": 0, "home_l": 0, "home_gf": 0, "home_ga": 0,
        "away_w": 0, "away_d": 0, "away_l": 0, "away_gf": 0, "away_ga": 0,
    }
