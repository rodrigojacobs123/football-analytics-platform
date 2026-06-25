from __future__ import annotations
"""xGChain & xGBuildup — possession-xG credit per player.

Two StatsBomb metrics that answer "who *builds* the chances", not just who
finishes them.  For every possession that **ends in a shot**, the shot's xG is
credited to *every* player who had an on-ball action in that possession:

  • **xGChain**   — full credit to everyone involved (incl. shooter + assister).
  • **xGBuildup** — same, but *excluding* the shooter and the assister, so it
                    isolates the deep build-up contributors whose work never
                    shows up in goals or assists.

A player is credited the shot's xG **once per possession**, however many times
they touched the ball in it (``involved`` is a set) — that's what stops a
high-volume recycler from inflating the number.

Distinct from:
  • ``processing/goal_buildup.py`` — traces *goals* only, no systematic credit.
  • ``processing/sequences.py``     — possession *shape* (directness/speed),
                                      discards the player list xGChain needs.
  • ``processing/buildup_play.py``  — *where* a team plays out from the back.

Possession segmentation mirrors ``sequences.py`` (on-ball events open it; a
shot, stoppage, or turnover closes it).  xG resolution mirrors
``data.event_parser.extract_shots`` (qualifier 395 ÷ 100, else a positional
estimate) so the numbers reconcile with the shot maps.

Pure pandas/Python up to the cached season aggregator at the bottom.
"""

import pandas as pd
from config import (
    EVENT_PASS, EVENT_OFFSIDE_PASS, EVENT_TAKE_ON, EVENT_BALL_TOUCH,
    SHOT_TYPE_IDS, EVENT_OUT, EVENT_FOUL, EVENT_CORNER, EVENT_END,
    QUAL_XG, QUAL_HEAD, QUAL_OWN_GOAL,
)
from processing.xg_model import estimate_xg

_ON_BALL = {EVENT_PASS, EVENT_OFFSIDE_PASS, EVENT_TAKE_ON, EVENT_BALL_TOUCH}
_STOPPAGES = {EVENT_OUT, EVENT_FOUL, EVENT_CORNER, EVENT_END}


def _qual(quals: list[dict], qid: int) -> str | None:
    for q in quals:
        if q.get("qualifierId") == qid:
            return q.get("value")
    return None


def _shot_xg(ev: dict) -> float:
    """xG for a shot event — same resolution order as extract_shots()."""
    quals = ev.get("qualifier", [])
    raw = _qual(quals, QUAL_XG)
    if raw is not None:
        return float(raw) / 100.0
    if any(q.get("qualifierId") == QUAL_OWN_GOAL for q in quals):
        return 0.0
    is_header = any(q.get("qualifierId") == QUAL_HEAD for q in quals)
    return estimate_xg(float(ev.get("x", 0)), float(ev.get("y", 0)),
                       is_header=is_header)


def match_xg_chain(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Per-player xGChain / xGBuildup for a single match.

    Walks events chronologically, accumulating each shot-ending possession's xG
    to the players involved.  Returns a DataFrame ``[player_id, player_name,
    xgchain, xgbuildup, possessions]`` (``possessions`` = shot-ending moves the
    player took part in), filtered to ``team_id`` if given.  Empty → empty.
    """
    chron = sorted(events, key=lambda e: (
        int(e.get("timeMin", 0)), int(e.get("timeSec", 0)),
        int(e.get("eventId", 0))))

    # player_id -> {"name", "xgchain", "xgbuildup", "possessions"}
    acc: dict[str, dict] = {}
    cur: dict | None = None  # {"team", "involved": {pid: name}, "assister": pid|None}

    def _open(team: str):
        return {"team": team, "involved": {}, "assister": None}

    def _credit_shot(shooter_id: str, xg: float):
        """Credit the closing possession's xG to all involved players."""
        if cur is None or xg <= 0:
            return
        assister = cur["assister"]
        for pid, name in cur["involved"].items():
            a = acc.setdefault(pid, {"name": name, "xgchain": 0.0,
                                     "xgbuildup": 0.0, "possessions": 0})
            a["name"] = name or a["name"]
            a["xgchain"] += xg
            a["possessions"] += 1
            if pid != shooter_id and pid != assister:
                a["xgbuildup"] += xg

    for ev in chron:
        tid = ev.get("typeId")
        team = ev.get("contestantId")

        if tid in _ON_BALL:
            if cur is None or cur["team"] != team:
                cur = _open(team)
            pid = ev.get("playerId")
            if pid:
                cur["involved"][pid] = ev.get("playerName", "")
                if tid == EVENT_PASS and int(ev.get("outcome", 0)) == 1:
                    cur["assister"] = pid  # last successful pass = assist candidate

        elif tid in SHOT_TYPE_IDS:
            if cur is not None and cur["team"] == team:
                shooter = ev.get("playerId")
                if shooter:  # ensure the shooter is in the involved set
                    cur["involved"].setdefault(shooter, ev.get("playerName", ""))
                _credit_shot(shooter, _shot_xg(ev))
            cur = None  # shot closes the possession either way

        elif tid in _STOPPAGES:
            cur = None

    rows = [
        {"player_id": pid, "player_name": v["name"],
         "xgchain": round(v["xgchain"], 4),
         "xgbuildup": round(v["xgbuildup"], 4),
         "possessions": v["possessions"]}
        for pid, v in acc.items()
    ]
    df = pd.DataFrame(rows)
    if not df.empty and team_id is not None:
        # team filter: keep players whose touches were for this team.  We don't
        # track team per player here, so filter via the events' team mapping.
        team_players = {e.get("playerId") for e in events
                        if e.get("contestantId") == team_id and e.get("playerId")}
        df = df[df["player_id"].isin(team_players)].reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────────────────────
# Season aggregation (cached "deep tier") — scans partidos/ once and sums each
# match's per-player xGChain/xGBuildup.  Mirrors processing.xt.compute_season_xt:
# accumulate per player, drop players below min_appearances to kill cameo noise.
# ──────────────────────────────────────────────────────────────────────────
import json
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Computing xGChain / xGBuildup…")
def compute_season_xg_chain(league: str, season: str, team_id: str,
                            stage_filter: str = "",
                            min_appearances: int = 1) -> dict:
    """Season-aggregated xGChain / xGBuildup for one team.

    Scans partidos/ (cached), sums each match's per-player credit, and ranks
    build-up contributors over the whole season.  Players below
    ``min_appearances`` matches are dropped (respects
    ``MIN_APPEARANCES_FOR_RATING`` when callers pass it).

    Returns ``{}`` if no matches, else::

        {matches, leaderboard (DataFrame: player_name, xgchain, xgbuildup,
         apps, xgchain_per_match, xgbuildup_per_match)}

    Per-match (not per-90) normalisation mirrors the existing season-xT
    leaderboard — the partidos scan doesn't carry per-player minutes, and apps
    is the consistent guard already used across the Scouting page.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    player_acc: dict[str, dict] = {}
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
        if team_id not in (info["home_id"], info["away_id"]):
            continue
        if stage_filter:
            sn = info.get("stage_name", "")
            if not sn.lower().startswith(stage_filter.lower().strip()):
                continue

        events = raw.get("liveData", {}).get("event", [])
        chain = match_xg_chain(events, team_id=team_id)
        if chain.empty:
            continue
        match_num += 1
        for _, r in chain.iterrows():
            name = r["player_name"]
            acc = player_acc.setdefault(
                name, {"xgchain": 0.0, "xgbuildup": 0.0, "apps": 0})
            acc["xgchain"] += float(r["xgchain"])
            acc["xgbuildup"] += float(r["xgbuildup"])
            acc["apps"] += 1

    if match_num == 0:
        return {}

    leaderboard = pd.DataFrame([
        {
            "player_name": n,
            "xgchain": round(v["xgchain"], 3),
            "xgbuildup": round(v["xgbuildup"], 3),
            "apps": v["apps"],
            "xgchain_per_match": round(v["xgchain"] / v["apps"], 3),
            "xgbuildup_per_match": round(v["xgbuildup"] / v["apps"], 3),
        }
        for n, v in player_acc.items() if v["apps"] >= min_appearances
    ])
    if not leaderboard.empty:
        leaderboard = (leaderboard
                       .sort_values("xgchain", ascending=False)
                       .reset_index(drop=True))

    return {"matches": match_num, "leaderboard": leaderboard}
