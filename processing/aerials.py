from __future__ import annotations
"""Expected aerial wins — opponent-adjusted, in the spirit of StatsBomb's HOPS.

Raw aerial win % flatters a defender who only ever jumps against small full-backs
and punishes a striker who duels centre-halves all game.  StatsBomb's HOPS model
(refreshed March 2026) reframed the question from *how many* you win to *who you
win against*.  This is the event-data version of that idea.

Method
------
1. **Pair the duels.**  Opta logs an aerial as two ``typeId==44`` events at the
   same timestamp — one per team; the winner has ``outcome==1``, the loser 0.
   We group simultaneous aerials and pair each winner with the opposing loser.
2. **Rate every player with Bradley-Terry.**  Given the win/loss graph, the
   Bradley-Terry MM algorithm assigns each player an aerial strength ``r`` such
   that  P(i beats j) = r_i / (r_i + r_j).  A win over a strong duel-winner moves
   your rating more than a win over a weak one — exactly the HOPS intuition.
3. **Score over/under expectation.**  For each duel, expected = r_i/(r_i+r_j);
   ``won_above_expected = actual_wins − Σ expected``.  Positive = wins more
   aerials than the quality of opponents faced predicts.

Pure pairing/rating below; the cached league scan is at the bottom.
"""

import json

import pandas as pd
import streamlit as st

from data.paths import partidos_dir
from data.event_parser import extract_aerials, parse_match_info


def aerial_duels(events: list[dict]) -> pd.DataFrame:
    """Pair simultaneous aerial events into winner/loser duels.

    Returns [period, minute, second, winner_id, winner_name, winner_team,
    loser_id, loser_name, loser_team] — one row per resolved duel.
    """
    av = extract_aerials(events)   # all teams
    if av.empty:
        return pd.DataFrame(columns=[
            "period", "minute", "second", "winner_id", "winner_name",
            "winner_team", "loser_id", "loser_name", "loser_team"])

    rows = []
    # Group simultaneous aerials; a genuine duel has a winner (outcome 1) and at
    # least one opposing loser (outcome 0) at the same instant.
    for (per, mn, sc), grp in av.groupby(["period", "minute", "second"]):
        winners = grp[grp["outcome"] == 1]
        losers = grp[grp["outcome"] == 0]
        if winners.empty or losers.empty:
            continue
        for w in winners.itertuples():
            opp = losers[losers["team_id"] != w.team_id]
            for l in opp.itertuples():
                rows.append({
                    "period": per, "minute": mn, "second": sc,
                    "winner_id": w.player_id, "winner_name": w.player_name,
                    "winner_team": w.team_id,
                    "loser_id": l.player_id, "loser_name": l.player_name,
                    "loser_team": l.team_id,
                })
    return pd.DataFrame(rows)


def _bradley_terry(duels: pd.DataFrame, iters: int = 60) -> dict[str, float]:
    """Bradley-Terry MM ratings from a winner/loser duel frame.

    Returns {player_id: strength}, geometric-mean-normalised to ~1.0.
    """
    wins: dict[str, int] = {}
    pair_n: dict[tuple, int] = {}      # (a, b) unordered -> total duels
    players: set[str] = set()
    for d in duels.itertuples():
        wi, li = d.winner_id, d.loser_id
        if not wi or not li or wi == li:
            continue
        players.add(wi); players.add(li)
        wins[wi] = wins.get(wi, 0) + 1
        key = (wi, li) if wi < li else (li, wi)
        pair_n[key] = pair_n.get(key, 0) + 1

    if not players:
        return {}

    # adjacency: player -> {opp: n duels}
    adj: dict[str, dict[str, int]] = {p: {} for p in players}
    for (a, b), n in pair_n.items():
        adj[a][b] = adj[a].get(b, 0) + n
        adj[b][a] = adj[b].get(a, 0) + n

    r = {p: 1.0 for p in players}
    for _ in range(iters):
        new = {}
        for p in players:
            w = wins.get(p, 0)
            denom = 0.0
            for opp, n in adj[p].items():
                denom += n / (r[p] + r[opp])
            # +1 smoothing keeps winless players finite and ranked, not zeroed.
            new[p] = (w + 0.5) / (denom + 0.5 / (r[p] + 1.0)) if denom > 0 else r[p]
        # geometric-mean normalise to avoid drift
        import math
        gm = math.exp(sum(math.log(max(v, 1e-9)) for v in new.values()) / len(new))
        r = {p: v / gm for p, v in new.items()}
    return r


@st.cache_data(ttl=3600, show_spinner="Computing opponent-adjusted aerial ratings…")
def compute_league_aerials(league: str, season: str, stage_filter: str = "",
                           min_duels: int = 15) -> pd.DataFrame:
    """League-wide opponent-adjusted aerial profiles with percentile ranks.

    Scans every match once, pairs all aerial duels, fits one Bradley-Terry model
    across the whole competition, then scores each player's wins vs the strength
    of opponents faced.  ``min_duels`` gates the sample (aerial ability needs
    duel volume, not appearances).

    Returns [player_id, player_name, team_id, team_name, duels, wins, win_pct,
    expected_wins, won_above_expected, bt_rating, rating_pct, overperf_pct]
    sorted by rating_pct desc, or empty frame.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    all_duels = []
    names: dict[str, str] = {}
    team_of: dict[str, str] = {}
    pname: dict[str, str] = {}
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
        if info["home_id"]:
            names[info["home_id"]] = info["home_team"]
        if info["away_id"]:
            names[info["away_id"]] = info["away_team"]
        d = aerial_duels(raw.get("liveData", {}).get("event", []))
        if d.empty:
            continue
        matches += 1
        all_duels.append(d)
        for row in d.itertuples():
            team_of[row.winner_id] = row.winner_team
            team_of[row.loser_id] = row.loser_team
            if row.winner_name:
                pname[row.winner_id] = row.winner_name
            if row.loser_name:
                pname[row.loser_id] = row.loser_name

    if matches == 0 or not all_duels:
        return pd.DataFrame()

    duels = pd.concat(all_duels, ignore_index=True)
    ratings = _bradley_terry(duels)

    # Per-player accumulation: duels, wins, expected wins (using BT ratings).
    acc: dict[str, dict] = {}

    def _slot(pid: str) -> dict:
        return acc.setdefault(pid, {"duels": 0, "wins": 0, "expected": 0.0})

    for d in duels.itertuples():
        wi, li = d.winner_id, d.loser_id
        if not wi or not li:
            continue
        rw, rl = ratings.get(wi, 1.0), ratings.get(li, 1.0)
        p_w = rw / (rw + rl)
        sw, sl = _slot(wi), _slot(li)
        sw["duels"] += 1; sw["wins"] += 1; sw["expected"] += p_w
        sl["duels"] += 1; sl["expected"] += (1.0 - p_w)

    out = pd.DataFrame([
        {
            "player_id": pid,
            "player_name": pname.get(pid, pid[:8]),
            "team_id": team_of.get(pid, ""),
            "team_name": names.get(team_of.get(pid, ""), ""),
            "duels": a["duels"],
            "wins": a["wins"],
            "win_pct": round(a["wins"] / a["duels"] * 100, 1) if a["duels"] else 0.0,
            "expected_wins": round(a["expected"], 1),
            "won_above_expected": round(a["wins"] - a["expected"], 1),
            "bt_rating": round(ratings.get(pid, 1.0), 3),
        }
        for pid, a in acc.items() if a["duels"] >= min_duels
    ])
    if out.empty:
        return out
    out["rating_pct"] = (out["bt_rating"].rank(pct=True) * 100).round(1)
    out["overperf_pct"] = (out["won_above_expected"].rank(pct=True) * 100).round(1)
    return out.sort_values("rating_pct", ascending=False).reset_index(drop=True)
