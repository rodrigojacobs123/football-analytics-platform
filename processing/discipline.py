from __future__ import annotations
"""Discipline analytics — Expected Booking (xB) + fouling efficiency.

The app modelled almost everything offensive but had **no discipline analytics**
despite the foul/card constants already living in ``config.py``.  This module
adds the two-sided picture from the 2024 Expected Booking literature:

  • **xB** = P(a foul → a card).  Rather than train a black-box model in a
    cached Streamlit path, we learn an **empirical** booking rate per pitch
    zone (in the *fouling* team's own frame, where the foul's danger lives) over
    a league-wide scan.  Scoring each foul with its zone rate gives:
      – **expected cards** (Σ xB) vs **actual cards** → over/under-booked, and
      – **fouling efficiency** = fouls per card (high = "smart fouls").
  • **Fouls-won dead-ball value** — the offensive mirror: fouls a team *draws*
    in dangerous areas (final third), which manufacture set-piece xG.  Reuses
    ``set_pieces.compute_dangerous_fk_zones``.

Opta semantics: foul = ``typeId 4`` (the committer), card = ``typeId 17``.  A
foul is "booked" if the same player picks up a card in the same period within a
short minute window.  Coordinates are normalised 0-100 (x = 0 own goal in the
fouling team's frame).  Pure pandas in the core; Streamlit only on the cached
league scan.
"""

import json

import pandas as pd
import streamlit as st

from config import EVENT_FOUL, EVENT_CARD
from data.paths import partidos_dir
from data.event_parser import extract_fouls, parse_match_info
from processing.set_pieces import compute_dangerous_fk_zones

# Foul-zone grid in the fouling team's own frame: 6 columns of depth × 3 lanes.
_N_COLS, _N_ROWS = 6, 3
# A card within this many minutes of a foul (same player, same period) is taken
# to belong to that foul.
_CARD_WINDOW_MIN = 2


def _foul_zone(x: float, y: float) -> int:
    """Map a foul's 0-100 (x, y) to a 0..17 zone id (6 depth × 3 lanes)."""
    col = min(int(x / 100.0 * _N_COLS), _N_COLS - 1)
    row = min(int(y / 100.0 * _N_ROWS), _N_ROWS - 1)
    return row * _N_COLS + col


def _red_from_quals(quals: list[dict]) -> bool:
    """Detect a red / second-yellow card from a card event's qualifiers.

    Opta card type lives in qualifier 33 (Red) / 32 (Second yellow) / 31
    (Yellow).  We treat 32 and 33 as red (player leaves the pitch).
    """
    ids = {q.get("qualifierId") for q in quals}
    return bool(ids & {32, 33})


def _card_events(events: list[dict], team_id: str | None = None) -> list[dict]:
    """Card events as ``{player_id, minute, period, is_red}`` dicts."""
    out = []
    for e in events:
        if e.get("typeId") != EVENT_CARD:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        out.append({
            "player_id": e.get("playerId", ""),
            "minute": int(e.get("timeMin", 0)),
            "period": int(e.get("periodId", 0)),
            "is_red": _red_from_quals(e.get("qualifier", [])),
        })
    return out


def foul_card_frame(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """One row per foul committed, flagged with whether it was booked.

    Columns: minute, period, team_id, player_id, player_name, x, y, zone,
    booked (bool), is_red (bool).
    """
    fouls = extract_fouls(events, team_id)
    if fouls.empty:
        return pd.DataFrame()

    cards = _card_events(events, team_id)
    df = fouls.copy()
    df["zone"] = df.apply(lambda r: _foul_zone(r["x"], r["y"]), axis=1)

    booked, is_red = [], []
    for _, f in df.iterrows():
        hit = next(
            (c for c in cards
             if c["player_id"] == f["player_id"] and c["period"] == f["period"]
             and 0 <= (c["minute"] - f["minute"]) <= _CARD_WINDOW_MIN),
            None,
        )
        booked.append(hit is not None)
        is_red.append(bool(hit and hit["is_red"]))
    df["booked"] = booked
    df["is_red"] = is_red
    return df


def build_xb_table(league_frame: pd.DataFrame, min_zone_n: int = 30
                   ) -> tuple[dict[int, float], float]:
    """Empirical xB lookup: ``{zone: booking_rate}`` + the overall fallback rate.

    Zones with fewer than ``min_zone_n`` fouls fall back to the overall rate so
    a thin zone can't swing a team's expected-cards total.
    """
    if league_frame is None or league_frame.empty:
        return {}, 0.0
    overall = float(league_frame["booked"].mean())
    grp = league_frame.groupby("zone")["booked"].agg(["mean", "size"])
    table = {int(z): float(r["mean"]) for z, r in grp.iterrows()
             if r["size"] >= min_zone_n}
    return table, round(overall, 4)


def score_xb(frame: pd.DataFrame, xb_table: dict[int, float],
             overall: float) -> pd.Series:
    """xB for each foul = its zone's empirical booking rate (overall fallback)."""
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    return frame["zone"].map(lambda z: xb_table.get(int(z), overall))


@st.cache_data(ttl=3600, show_spinner="Computing league discipline (xB)…")
def compute_league_discipline(league: str, season: str,
                              stage_filter: str = "") -> dict:
    """League-wide discipline scan → xB table + per-team fouling efficiency.

    Single pass over ``partidos/``: collect every foul (zone + booked) to learn
    the empirical xB table, and per team accumulate fouls, cards, matches and
    dangerous fouls *won* (final-third fouls drawn).  Then score each team's
    fouls with the xB table for expected cards.

    Returns ``{}`` if no matches, else::

        {
          overall_rate, xb_table (dict),
          per_team   (DataFrame: team_id, team_name, matches, fouls,
                      cards, yellows, reds, fouls_per_card, expected_cards,
                      cards_vs_expected, dangerous_fouls_won, fouls_per_match,
                      cards_per_match),
          zone_rates (DataFrame: zone, rate, n),
        }
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return {}

    league_rows: list[dict] = []        # league-wide foul frame (for xB table)
    acc: dict[str, dict] = {}           # per-team accumulator
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

        for tid, opp in ((home_id, away_id), (away_id, home_id)):
            fc = foul_card_frame(events, tid)
            a = acc.setdefault(tid, {
                "matches": 0, "fouls": 0, "cards": 0, "reds": 0,
                "dangerous_fouls_won": 0, "fouls_frame": []})
            a["matches"] += 1
            if not fc.empty:
                a["fouls"] += len(fc)
                a["cards"] += int(fc["booked"].sum())
                a["reds"] += int(fc["is_red"].sum())
                a["fouls_frame"].append(fc[["team_id", "zone", "booked"]])
                fc2 = fc.copy()
                fc2["team_id"] = tid
                league_rows.append(fc2[["team_id", "zone", "booked"]])
            won = compute_dangerous_fk_zones(events, tid, opp)
            if not won.empty and "dangerous" in won.columns:
                a["dangerous_fouls_won"] += int(won["dangerous"].sum())

    if matches == 0:
        return {}

    league_frame = (pd.concat(league_rows, ignore_index=True)
                    if league_rows else pd.DataFrame(columns=["team_id", "zone", "booked"]))
    xb_table, overall = build_xb_table(league_frame)

    rows = []
    for tid, a in acc.items():
        team_frame = (pd.concat(a["fouls_frame"], ignore_index=True)
                      if a["fouls_frame"] else pd.DataFrame(columns=["zone"]))
        expected = float(score_xb(team_frame, xb_table, overall).sum()) if not team_frame.empty else 0.0
        m = max(a["matches"], 1)
        cards = a["cards"]
        rows.append({
            "team_id": tid,
            "team_name": names.get(tid, tid[:8]),
            "matches": a["matches"],
            "fouls": a["fouls"],
            "cards": cards,
            "yellows": cards - a["reds"],
            "reds": a["reds"],
            "fouls_per_card": round(a["fouls"] / cards, 1) if cards else float(a["fouls"]),
            "expected_cards": round(expected, 1),
            "cards_vs_expected": round(cards - expected, 1),
            "dangerous_fouls_won": a["dangerous_fouls_won"],
            "fouls_per_match": round(a["fouls"] / m, 1),
            "cards_per_match": round(cards / m, 2),
            "exp_cards_per_match": round(expected / m, 2),
        })

    per_team = pd.DataFrame(rows).sort_values("fouls_per_card", ascending=False).reset_index(drop=True)

    zr = league_frame.groupby("zone")["booked"].agg(["mean", "size"]).reset_index()
    zr.columns = ["zone", "rate", "n"]
    zr["rate"] = zr["rate"].round(3)

    return {
        "overall_rate": overall,
        "xb_table": xb_table,
        "per_team": per_team,
        "zone_rates": zr,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def load_team_foul_locations(league: str, season: str, team_id: str,
                             stage_filter: str = "") -> pd.DataFrame:
    """The selected team's foul coordinates (committed) for a location heatmap.

    Light per-team scan returning columns x, y, booked — used by the discipline
    dashboard's foul-location map.  ``{}``-equivalent empty frame if none found.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    frames = []
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
        fc = foul_card_frame(events, team_id)
        if not fc.empty:
            frames.append(fc[["x", "y", "booked"]])

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
