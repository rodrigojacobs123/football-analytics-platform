from __future__ import annotations
"""Goalkeeper Value Model (GVM) — a composite keeper rating from Opta events.

The Scouting / Player-Intelligence GK block currently leans on *raw counting
stats* (``GK Successful Distribution``, ``Catches`` …) which reward a keeper who
faces many easy shots and punish a sweeper-keeper on a dominant team.  GVM is
the execution-vs-situation pattern (the same idea behind xG→xGOT) applied to the
most under-modelled position in the app, built from four event-derived
sub-scores:

  1. Shot-stopping  — goals prevented  = Σ xGOT_faced − goals_conceded
                       (folds the *existing* ``xgot.keeper_shot_stopping`` —
                       we do NOT re-derive it).
  2. Distribution   — threat added by the keeper's own passes (Σ xT_added),
                       plus launch% and completion, the "ball-playing keeper"
                       signal (Ederson/Neuer).
  3. Sweeper        — proactive defensive actions *outside the own box*
                       (clearances/interceptions/recoveries), per 90 — the
                       high-line line-manager signal.
  4. Claims         — cross-claim / catch involvement per 90 (typeId 11/52).

Each sub-score is a raw per-match (or per-90) number.  ``combine_gvm`` then
z-scores them across a population of keepers and blends them with
``DEFAULT_GVM_WEIGHTS`` into a single 0-100 rating, mirroring the
``RATING_FLOOR``/``RATING_CEILING`` scaling used by ``player_ratings``.

This is event-data only — no tracking, no keeper positioning (same honest
limitation as ``xgot``).  Like ``buildup_play``, the per-match entry points take
``events``/extracted frames so they compose with both the single-match
(Post-Match) and merged-multi-match (Scouting) pages.

Reference:
    Marc Lamberts — "Introducing the Goalkeeper Value Model (GVM)"
    StatsBomb — goalkeeper shot-stopping & sweeper metrics
"""

import numpy as np
import pandas as pd

from config import (
    EVENT_SAVE, EVENT_CLAIM, EVENT_KEEPER_PICKUP,
    EVENT_CLEARANCE, EVENT_INTERCEPTION, EVENT_TACKLE, EVENT_BALL_RECOVERY,
    RATING_FLOOR, RATING_CEILING,
)
from data.event_parser import extract_shots, extract_passes
from processing.xgot import keeper_shot_stopping
from processing.xt import xt_value

# ── Pitch geometry on the Opta 0-100 scale (team attacks x→100, own goal x=0) ──
# The penalty box is 16.5 m deep on a 105 m pitch → ~15.7 units.  A keeper acting
# *beyond* this edge is sweeping behind a high line, not handling a routine box
# situation, so OWN_BOX_EDGE_X is the threshold for a "sweeper" action.
OWN_BOX_EDGE_X = 16.0

# A "launch" is a long delivery that skips the build-up.  Opta x-units ≈ 1.05 m,
# y-units ≈ 0.68 m on a 105×68 pitch; >40 m of travel ≈ a clearance/long ball.
LAUNCH_DISTANCE_M = 40.0
_X_UNIT_M, _Y_UNIT_M = 105.0 / 100.0, 68.0 / 100.0

# Defensive-action event types a sweeper-keeper produces outside the box.
_SWEEPER_TYPE_IDS = {
    EVENT_CLEARANCE, EVENT_INTERCEPTION, EVENT_TACKLE, EVENT_BALL_RECOVERY,
}

# ── The opinionated knob: how the four sub-scores blend into one rating ───────
# These weights encode what "a valuable keeper" means for this platform.  They
# sum to 1.0 so the composite stays interpretable as a weighted z-score.  Shot-
# stopping dominates (it is still the core job); distribution and sweeping carry
# the modern ball-playing/high-line value; claims are the smallest slice because
# the event signal is sparse and noisy.  Tune freely — this is the single most
# subjective choice in the model.
DEFAULT_GVM_WEIGHTS = {
    "shot_stopping": 0.45,
    "distribution":  0.25,
    "sweeper":       0.20,
    "claims":        0.10,
}


def _pass_distance_m(r: pd.Series) -> float:
    """Euclidean pass length in metres from 0-100 start/end coords."""
    if pd.isna(r.get("end_x")) or pd.isna(r.get("end_y")):
        return 0.0
    dx = (r["end_x"] - r["x"]) * _X_UNIT_M
    dy = (r["end_y"] - r["y"]) * _Y_UNIT_M
    return float(np.hypot(dx, dy))


def infer_gk_id(events: list[dict], team_id: str) -> str | None:
    """Best-effort identification of a team's goalkeeper from its events.

    The GK is the player who pickups/saves/claims for ``team_id``; we take the
    most frequent such actor.  Falls back to the player with the most passes
    originating from deep in their own third (x < 10).  Returns ``None`` if no
    candidate is found (e.g. events don't carry keeper actions for this team).
    """
    gk_event_ids = {EVENT_SAVE, EVENT_CLAIM, EVENT_KEEPER_PICKUP}
    counts: dict[str, int] = {}
    for e in events:
        if e.get("contestantId") != team_id:
            continue
        if e.get("typeId") in gk_event_ids and e.get("playerId"):
            counts[e["playerId"]] = counts.get(e["playerId"], 0) + 1
    if counts:
        return max(counts, key=counts.get)

    # Fallback: deepest-originating passer.
    deep: dict[str, int] = {}
    for e in events:
        if e.get("contestantId") != team_id or e.get("typeId") != 1:
            continue
        if float(e.get("x", 100)) < 10 and e.get("playerId"):
            deep[e["playerId"]] = deep.get(e["playerId"], 0) + 1
    return max(deep, key=deep.get) if deep else None


def gk_distribution(events: list[dict], team_id: str, gk_id: str) -> dict:
    """Threat and accuracy of the keeper's own passing.

    ``dist_xt`` = Σ xT_added over the keeper's successful passes (reuses the
    ``xt`` grid); ``launch_pct`` = share of attempts that travel >40 m;
    ``completion`` = pass success rate.
    """
    passes = extract_passes(events, team_id=team_id)
    if passes.empty:
        return {"gk_passes": 0, "dist_xt": 0.0, "launch_pct": 0.0, "completion": 0.0}
    gp = passes[passes["player_id"] == gk_id].copy()
    if gp.empty:
        return {"gk_passes": 0, "dist_xt": 0.0, "launch_pct": 0.0, "completion": 0.0}

    gp["dist_m"] = gp.apply(_pass_distance_m, axis=1)
    success = gp["outcome"] == 1
    gp["xt_start"] = gp.apply(lambda r: xt_value(r["x"], r["y"]), axis=1)
    gp["xt_end"] = gp.apply(
        lambda r: xt_value(r["end_x"], r["end_y"])
        if pd.notna(r.get("end_x")) and pd.notna(r.get("end_y")) else r["xt_start"],
        axis=1,
    )
    dist_xt = float(((gp["xt_end"] - gp["xt_start"]) * success.astype(float)).sum())
    return {
        "gk_passes": int(len(gp)),
        "dist_xt": round(dist_xt, 4),
        "launch_pct": round(float((gp["dist_m"] > LAUNCH_DISTANCE_M).mean()), 3),
        "completion": round(float(success.mean()), 3),
    }


def gk_sweeper_claims(events: list[dict], team_id: str, gk_id: str) -> dict:
    """Sweeper actions (defensive actions outside the own box) and claims.

    Sweeper actions count the keeper's clearances/interceptions/tackles/
    recoveries with ``x > OWN_BOX_EDGE_X``; claims count typeId 11/52 (catch /
    pickup).  Both are raw counts — ``goalkeeper_value`` normalises per 90.
    """
    sweeper = claims = 0
    for e in events:
        if e.get("contestantId") != team_id or e.get("playerId") != gk_id:
            continue
        tid = e.get("typeId")
        if tid in _SWEEPER_TYPE_IDS and float(e.get("x", 0)) > OWN_BOX_EDGE_X:
            sweeper += 1
        elif tid in (EVENT_CLAIM, EVENT_KEEPER_PICKUP):
            claims += 1
    return {"sweeper_actions": sweeper, "claims": claims}


def goalkeeper_value(events: list[dict], team_id: str,
                     gk_id: str | None = None, minutes: float = 90.0) -> dict:
    """One-call raw GVM sub-metrics for a keeper performance.

    ``events`` may be a single match or merged multi-match events (pass the
    keeper's total ``minutes`` so per-90 rates are correct).  Sweeper and claim
    counts are normalised per 90; shot-stopping and distribution-xT are kept as
    totals (they are already volume-fair via xGOT / xT).  Returns ``{}`` if no
    keeper can be identified.

    NOTE: ``shot_stopping`` is team-level (xGOT-faced minus goals conceded) — it
    is attributed to whichever keeper played, which is correct for a full match
    but blends keepers if one was subbed; callers wanting per-keeper precision
    should pass single-keeper match windows.
    """
    gk_id = gk_id or infer_gk_id(events, team_id)
    if not gk_id:
        return {}

    shots = extract_shots(events)
    stop = keeper_shot_stopping(shots, team_id)
    dist = gk_distribution(events, team_id, gk_id)
    sc = gk_sweeper_claims(events, team_id, gk_id)
    per90 = 90.0 / minutes if minutes else 0.0

    return {
        "gk_id": gk_id,
        "minutes": minutes,
        # core sub-scores (raw, pre-normalisation)
        "shot_stopping": stop["shot_stopping"],     # goals prevented
        "distribution": dist["dist_xt"],            # threat added by passing
        "sweeper": round(sc["sweeper_actions"] * per90, 3),
        "claims": round(sc["claims"] * per90, 3),
        # supporting detail (surfaced in the GK dashboard, not blended directly)
        "psxg_faced": stop["psxg_faced"],
        "goals_conceded": stop["goals_conceded"],
        "shots_faced": stop["shots_faced"],
        "launch_pct": dist["launch_pct"],
        "pass_completion": dist["completion"],
        "gk_passes": dist["gk_passes"],
    }


def _z(s: pd.Series) -> pd.Series:
    """Population z-score; 0 everywhere if the column has no spread."""
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else pd.Series(0.0, index=s.index)


def combine_gvm(metrics: pd.DataFrame,
                weights: dict[str, float] = DEFAULT_GVM_WEIGHTS) -> pd.DataFrame:
    """Blend the four sub-scores into a single 0-100 GVM rating across keepers.

    Each sub-score is z-scored *across the supplied population* of keepers, then
    combined with ``weights`` (so a keeper is rated relative to peers, not on an
    absolute scale — the only meaningful way to read shot-stopping/sweeping).
    The weighted z is squashed through a logistic and mapped onto
    ``[RATING_FLOOR, RATING_CEILING]`` so the output reads like the rest of the
    app's FC-style ratings.  Requires ≥2 keepers (z-scores need spread); with
    one row it returns the midpoint rating.

    Expects one row per keeper with the sub-score columns from
    ``goalkeeper_value``.  Returns ``metrics`` with added ``z_*`` columns and a
    final ``gvm`` rating, sorted high→low.
    """
    out = metrics.copy()
    if out.empty:
        out["gvm"] = pd.Series(dtype=float)
        return out
    if len(out) == 1:
        out["gvm"] = (RATING_FLOOR + RATING_CEILING) / 2.0
        return out

    blended = pd.Series(0.0, index=out.index)
    for key, w in weights.items():
        if key in out.columns:
            z = _z(out[key].astype(float))
            out[f"z_{key}"] = z.round(3)
            blended += w * z

    # Logistic squash keeps outliers from saturating the scale, then map to
    # the app's rating band.  Divisor 1.5 ≈ 1 SD of a typical weighted-z spread.
    squashed = 1.0 / (1.0 + np.exp(-blended / 1.5))
    out["gvm"] = (RATING_FLOOR + squashed * (RATING_CEILING - RATING_FLOOR)).round(1)
    return out.sort_values("gvm", ascending=False).reset_index(drop=True)


# ── Season / league aggregation (cached deep tier) ───────────────────────────
import streamlit as st
from data.paths import partidos_dir
from data.event_parser import parse_match_info


@st.cache_data(ttl=3600, show_spinner="Computing league goalkeeper value…")
def compute_league_gk_value(league: str, season: str,
                            stage_filter: str = "") -> pd.DataFrame:
    """League-wide GVM for every team's goalkeeping, in ONE partidos pass.

    Walks ``partidos/`` once, accumulating each team's keeper sub-metrics across
    its matches (raw sums), normalises to per-game / per-90 so match count does
    not bias the cross-team z-scores, then runs ``combine_gvm`` to produce the
    0–100 composite.  Cached, so the GVM panel recomputes only on competition
    change.  Returns one row per team with the sub-scores, supporting detail and
    ``gvm`` (empty frame if no matches).
    """
    import json

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

        events = raw.get("liveData", {}).get("event", [])
        if not events:
            continue
        shots = extract_shots(events)
        minutes = float(info.get("match_length_min", 90) or 90)

        for tid, name in [(info["home_id"], info["home_team"]),
                          (info["away_id"], info["away_team"])]:
            if not tid:
                continue
            gk_id = infer_gk_id(events, tid)
            if not gk_id:
                continue
            stop = keeper_shot_stopping(shots, tid)
            dist = gk_distribution(events, tid, gk_id)
            sc = gk_sweeper_claims(events, tid, gk_id)
            launches = dist["launch_pct"] * dist["gk_passes"]

            a = acc.setdefault(tid, {
                "team_name": name, "matches": 0, "minutes": 0.0,
                "shot_stopping": 0.0, "dist_xt": 0.0, "sweeper": 0, "claims": 0,
                "psxg_faced": 0.0, "goals_conceded": 0, "shots_faced": 0,
                "gk_passes": 0, "launches": 0.0,
            })
            a["matches"] += 1
            a["minutes"] += minutes
            a["shot_stopping"] += stop["shot_stopping"]
            a["dist_xt"] += dist["dist_xt"]
            a["sweeper"] += sc["sweeper_actions"]
            a["claims"] += sc["claims"]
            a["psxg_faced"] += stop["psxg_faced"]
            a["goals_conceded"] += stop["goals_conceded"]
            a["shots_faced"] += stop["shots_faced"]
            a["gk_passes"] += dist["gk_passes"]
            a["launches"] += launches

    if not acc:
        return pd.DataFrame()

    rows = []
    for tid, a in acc.items():
        m = max(a["matches"], 1)
        mins = max(a["minutes"], 1.0)
        rows.append({
            "team_id": tid,
            "team_name": a["team_name"],
            "matches": a["matches"],
            # sub-scores fed to combine_gvm — per-game / per-90 (match-count fair)
            "shot_stopping": round(a["shot_stopping"] / m, 3),
            "distribution": round(a["dist_xt"] / m, 4),
            "sweeper": round(a["sweeper"] * 90.0 / mins, 3),
            "claims": round(a["claims"] * 90.0 / mins, 3),
            # supporting detail for display
            "psxg_faced": round(a["psxg_faced"], 2),
            "goals_conceded": a["goals_conceded"],
            "shots_faced": a["shots_faced"],
            "launch_pct": round(a["launches"] / a["gk_passes"], 3) if a["gk_passes"] else 0.0,
            "gk_passes": a["gk_passes"],
        })

    return combine_gvm(pd.DataFrame(rows))
