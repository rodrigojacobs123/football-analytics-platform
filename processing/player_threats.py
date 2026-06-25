from __future__ import annotations
"""Player threat indices — who hurts the opponent most, per team.

For a single team over its last *N* matches, this collapses the per-player
event aggregates already produced by ``data.event_parser`` into two
squad-relative indices:

* **Offensive threat** — danger to the opponent's goal (finishing + chance
  involvement + carrying): the attacker the opposition must contain.
* **Defensive threat** — danger to the opponent's attack (ball-winning +
  duels): the destroyer who breaks up the opposition's build-up.

Both indices are **squad-relative**: each component is min-max scaled across
*this* team's players, then weighted-summed to a 0–100 index. So a score of
100 means "most dangerous on this team in this component mix", not an absolute
league rating — exactly the read a coach wants for *this* fixture.

Pure pandas, no Streamlit. Feeds ``viz.tables.player_threats_panel`` and the
Pre-Match Analysis page.
"""

import pandas as pd

from data.event_parser import (
    extract_shots, extract_passes, extract_tackles, extract_interceptions,
    extract_ball_recoveries, extract_clearances, extract_aerials,
    extract_take_ons,
)
from processing.xg_chain import match_xg_chain

# ── Component weighting — the design decision ──────────────────────────────
# How much each raw signal contributes to the blended index. These are the
# single most important knobs in this module: they encode what "dangerous"
# *means* for this platform. Each block is min-max normalised within the squad
# first (see _index_from_components), so weights compare like-for-like and only
# need to sum to 1.0 per block.
#
# Offensive: xG = pure finishing threat; xgchain = involvement in any move that
#   ended in a shot (rewards deep creators, not just shooters); shots = volume;
#   key_passes = chance creation; take_ons_won = ball-carrying danger.
# Defensive: ball-winning actions (tackles/interceptions/recoveries) weighted
#   above territory-clearing (clearances) and duels (aerials).
OFF_WEIGHTS: dict[str, float] = {
    "xg":            0.35,
    "xgchain":       0.25,
    "shots":         0.15,
    "key_passes":    0.15,
    "take_ons_won":  0.10,
}
DEF_WEIGHTS: dict[str, float] = {
    "tackles_won":   0.25,
    "interceptions": 0.25,
    "recoveries":    0.25,
    "clearances":    0.15,
    "aerials_won":   0.10,
}

# Human labels for the standout-stat callout on each danger-man card.
_OFF_LABELS = {
    "xg": "xG", "xgchain": "xGChain", "shots": "shots",
    "key_passes": "key passes", "take_ons_won": "dribbles won",
}
_DEF_LABELS = {
    "tackles_won": "tackles won", "interceptions": "interceptions",
    "recoveries": "recoveries", "clearances": "clearances",
    "aerials_won": "aerials won",
}

# Drop cameo noise: a player needs at least this many contributing actions on a
# side to be ranked there (mirrors the project's minimum-sample philosophy).
MIN_ACTIONS = 3


def _index_from_components(comp: pd.DataFrame, weights: dict[str, float]
                          ) -> tuple[pd.Series, pd.Series]:
    """Scale each component to the squad-best (``v / max``), then weighted-sum to 0–100.

    Max-only normalisation answers "what fraction of the squad-best are you in
    this component" — the player who tops a component gets 1.0 there. This stays
    well-behaved when only one player qualifies (they keep their true weighted
    value instead of collapsing to 0) and never artificially zeroes the weakest
    player the way ``(v-min)/(max-min)`` would. A component that is zero for the
    whole squad contributes 0 to everyone.

    Returns ``(index, top_component)`` where ``top_component`` names, per player,
    the component contributing the most to their score — used for the "why"
    callout.
    """
    contrib = pd.DataFrame(index=comp.index)
    for col, w in weights.items():
        v = comp[col].astype(float)
        mx = v.max()
        norm = v / mx if mx > 0 else pd.Series(0.0, index=v.index)
        contrib[col] = norm * w
    index = contrib.sum(axis=1) * 100.0
    top_component = contrib.idxmax(axis=1)
    return index.round(1), top_component


def _per_game(value: float, n_matches: int) -> float:
    return round(value / max(n_matches, 1), 2)


def compute_player_threats(events: list[dict], team_id: str, n_matches: int = 1
                          ) -> dict:
    """Rank one team's players by offensive and defensive threat.

    ``events`` is the merged event list for the team's last ``n_matches``
    matches; ``team_id`` filters to that team. Returns::

        {
          "offensive": DataFrame[player, threat, xg, xgchain, shots,
                                 key_passes, take_ons_won, _why],
          "defensive": DataFrame[player, threat, tackles_won, interceptions,
                                 recoveries, clearances, aerials_won, _why],
          "top_offensive": {...} | None,   # single danger-man rows
          "top_defensive": {...} | None,
        }

    Component columns are per-game; ``threat`` is the squad-relative 0–100 index.
    Empty/insufficient input → empty frames and None danger-men.
    """
    empty = {"offensive": pd.DataFrame(), "defensive": pd.DataFrame(),
             "top_offensive": None, "top_defensive": None}
    if not events or not team_id:
        return empty

    shots = extract_shots(events, team_id)
    passes = extract_passes(events, team_id=team_id)
    tackles = extract_tackles(events, team_id)
    interceptions = extract_interceptions(events, team_id)
    recoveries = extract_ball_recoveries(events, team_id)
    clearances = extract_clearances(events, team_id)
    aerials = extract_aerials(events, team_id)
    take_ons = extract_take_ons(events, team_id)
    chain = match_xg_chain(events, team_id)  # player_id, xgchain, possessions

    # Collect every player who did anything, with a best-effort name.
    names: dict[str, str] = {}
    for df in [shots, passes, tackles, interceptions, recoveries,
               clearances, aerials, take_ons, chain]:
        if df.empty or "player_id" not in df.columns:
            continue
        for pid, nm in zip(df["player_id"], df.get("player_name", "")):
            if pid and (pid not in names or not names[pid]):
                names[pid] = nm or names.get(pid, "")
    if not names:
        return empty

    def _count(df: pd.DataFrame, pid: str, mask=None) -> int:
        if df.empty or "player_id" not in df.columns:
            return 0
        sub = df[df["player_id"] == pid]
        if mask is not None and not sub.empty:
            sub = sub[mask(sub)]
        return len(sub)

    off_rows, def_rows = [], []
    for pid, name in names.items():
        if not pid:
            continue
        disp = name or f"Unknown ({pid[:8]})"

        # ── Offensive components ──
        p_shots = shots[shots["player_id"] == pid] if not shots.empty else pd.DataFrame()
        n_shots = len(p_shots)
        xg = float(p_shots["xg"].sum()) if not p_shots.empty and "xg" in p_shots else 0.0
        key_passes = 0
        if not passes.empty and "end_x" in passes.columns:
            kp = passes[passes["player_id"] == pid].dropna(subset=["end_x", "end_y"])
            key_passes = int(((kp["end_x"] > 83) & (kp["end_y"] > 21)
                              & (kp["end_y"] < 79) & (kp["outcome"] == 1)).sum())
        take_ons_won = _count(take_ons, pid, lambda s: s["outcome"] == 1)
        xgchain = 0.0
        if not chain.empty:
            c = chain[chain["player_id"] == pid]
            xgchain = float(c["xgchain"].iloc[0]) if not c.empty else 0.0

        # Include deep creators (high xGChain involvement) even with few shots.
        off_actions = n_shots + key_passes + take_ons_won
        if off_actions >= MIN_ACTIONS or xg > 0.15 or xgchain > 0.15:
            off_rows.append({
                "player": disp,
                "xg": _per_game(xg, n_matches),
                "xgchain": _per_game(xgchain, n_matches),
                "shots": _per_game(n_shots, n_matches),
                "key_passes": _per_game(key_passes, n_matches),
                "take_ons_won": _per_game(take_ons_won, n_matches),
            })

        # ── Defensive components ──
        tackles_won = _count(tackles, pid, lambda s: s["outcome"] == 1)
        n_int = _count(interceptions, pid)
        n_rec = _count(recoveries, pid)
        n_clr = _count(clearances, pid)
        aerials_won = _count(aerials, pid, lambda s: s["outcome"] == 1)

        def_actions = tackles_won + n_int + n_rec + n_clr + aerials_won
        if def_actions >= MIN_ACTIONS:
            def_rows.append({
                "player": disp,
                "tackles_won": _per_game(tackles_won, n_matches),
                "interceptions": _per_game(n_int, n_matches),
                "recoveries": _per_game(n_rec, n_matches),
                "clearances": _per_game(n_clr, n_matches),
                "aerials_won": _per_game(aerials_won, n_matches),
            })

    off = _rank(pd.DataFrame(off_rows), OFF_WEIGHTS, _OFF_LABELS)
    deff = _rank(pd.DataFrame(def_rows), DEF_WEIGHTS, _DEF_LABELS)

    return {
        "offensive": off,
        "defensive": deff,
        "top_offensive": off.iloc[0].to_dict() if not off.empty else None,
        "top_defensive": deff.iloc[0].to_dict() if not deff.empty else None,
    }


def _rank(comp: pd.DataFrame, weights: dict[str, float],
          labels: dict[str, str]) -> pd.DataFrame:
    """Attach the 0–100 ``threat`` index + ``_why`` callout and sort descending."""
    if comp.empty:
        return comp
    comp = comp.set_index("player")
    index, top = _index_from_components(comp[list(weights)], weights)
    comp.insert(0, "threat", index)
    comp["_why"] = [
        f"{comp.loc[p, top[p]]:g} {labels.get(top[p], top[p])}/g"
        for p in comp.index
    ]
    comp = comp.sort_values("threat", ascending=False)
    return comp.reset_index()
