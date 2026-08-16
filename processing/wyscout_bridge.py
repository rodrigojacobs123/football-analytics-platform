from __future__ import annotations
"""Bridge between Opta season stats (equipos/ CSVs) and the Wyscout metric space.

Powers the Scouting Hub's "replace a squad player" flow: take a Club América
player's Opta season totals, project them onto the subset of Wyscout columns
both feeds can express, percentile him against the uploaded market sample, and
find the closest market profiles.

Only ~25 metrics are shared (the Opta CSVs have no xG, xA or progressive
passes), so every result carries the list of metrics actually compared —
similarity over 12 shared metrics is honest; pretending it used all 115 isn't.

Pure pandas: the page loads the Opta CSV via data.loader and passes rows in.
"""

import pandas as pd

from processing.wyscout_scouting import ROLE_METRICS, RADAR_METRICS

# Opta `posicion` is coarse (4 buckets) — default group per bucket, overridable
# in the UI (a "Defender" may need to be shopped as FB, a "Midfielder" as DM).
OPTA_POSITION_DEFAULT_GROUP = {
    "Goalkeeper": "GK",
    "Defender": "CB",
    "Midfielder": "CM",
    "Forward": "ST",
}


def opta_to_wyscout_profile(stats_row: pd.Series) -> dict[str, float]:
    """Project one Opta season-stats row onto Wyscout column names (per-90 / %).

    Returns only the metrics that are computable from the row; callers must
    treat missing keys as "not comparable", not zero. Proxy mappings worth
    knowing: PAdj Interceptions ← raw interceptions per 90 (no possession
    adjustment available); Wyscout 'Shot assists' ← Opta 'Key Passes (Attempt
    Assists)' (both = pass leading to a shot); Wyscout 'Key passes' ← Opta
    'Total Big Chances Created'.
    """
    row = stats_row.copy()
    row.index = row.index.str.strip()  # several Opta CSV headers have trailing spaces
    minutes = float(row.get("Time Played") or 0)
    if minutes < 1:
        return {}

    def tot(col: str) -> float:
        v = row.get(col)
        return float(v) if pd.notna(v) else 0.0

    def per90(*cols: str) -> float:
        return sum(tot(c) for c in cols) * 90.0 / minutes

    def pct_of(success: str, fail: str) -> float | None:
        total = tot(success) + tot(fail)
        return 100.0 * tot(success) / total if total > 0 else None

    p: dict[str, float | None] = {
        # attacking
        "Goals per 90": per90("Goals"),
        "Non-penalty goals per 90": max(0.0, tot("Goals") - tot("Penalty Goals")) * 90.0 / minutes,
        "Head goals per 90": per90("Headed Goals"),
        "Shots per 90": per90("Total Shots"),
        "Shots on target, %": (100.0 * tot("Shots On Target ( inc goals )") / tot("Total Shots"))
                              if tot("Total Shots") > 0 else None,
        "Goal conversion, %": (100.0 * tot("Goals") / tot("Total Shots"))
                              if tot("Total Shots") > 0 else None,
        "Touches in box per 90": per90("Total Touches In Opposition Box"),
        "Dribbles per 90": per90("Successful Dribbles", "Unsuccessful Dribbles"),
        "Successful dribbles, %": pct_of("Successful Dribbles", "Unsuccessful Dribbles"),
        "Progressive runs per 90": per90("Progressive Carries"),
        # creation
        "Assists per 90": per90("Assists (Intentional)"),
        "Shot assists per 90": per90("Key Passes (Attempt Assists)"),
        "Key passes per 90": per90("Total Big Chances Created"),
        "Through passes per 90": per90("Through balls"),
        "Crosses per 90": per90("Successful Crosses open play", "Unsuccessful Crosses open play"),
        "Accurate crosses, %": pct_of("Successful Crosses open play", "Unsuccessful Crosses open play"),
        # passing
        "Passes per 90": per90("Total Passes"),
        "Accurate passes, %": pct_of("Total Successful Passes ( Excl Crosses & Corners )",
                                     "Total Unsuccessful Passes ( Excl Crosses & Corners )"),
        "Forward passes per 90": per90("Forward Passes"),
        "Long passes per 90": per90("Successful Long Passes", "Unsuccessful Long Passes"),
        "Accurate long passes, %": pct_of("Successful Long Passes", "Unsuccessful Long Passes"),
        # defending
        "Duels won, %": (100.0 * tot("Duels won") / tot("Duels")) if tot("Duels") > 0 else None,
        "Aerial duels per 90": per90("Aerial Duels"),
        "Aerial duels won, %": (100.0 * tot("Aerial Duels won") / tot("Aerial Duels"))
                               if tot("Aerial Duels") > 0 else None,
        "Defensive duels won, %": pct_of("Tackles Won", "Tackles Lost"),
        "Interceptions per 90": per90("Interceptions"),
        "PAdj Interceptions": per90("Interceptions"),  # proxy: not possession-adjusted
        "Successful defensive actions per 90": per90("Tackles Won", "Interceptions", "Blocks"),
        "Shots blocked per 90": per90("Blocks"),
        "Fouls per 90": per90("Total Fouls Conceded"),
        "Yellow cards per 90": per90("Yellow Cards"),
        # goalkeeping
        "Conceded goals per 90": per90("Goals Conceded"),
        "Save rate, %": (100.0 * tot("Saves Made") / (tot("Saves Made") + tot("Goals Conceded")))
                        if (tot("Saves Made") + tot("Goals Conceded")) > 0 else None,
        "Exits per 90": per90("Catches", "Punches", "Goalkeeper Smother"),
        "Aerial duels per 90.1": per90("Aerial Duels"),
    }
    return {k: v for k, v in p.items() if v is not None}


def player_stats_profile(agg: dict) -> dict[str, float]:
    """Windowed aggregate from a 'Player stats' export → Search column space.

    Both feeds are Wyscout, so most mappings are exact. Known proxies:
    Non-penalty goals ← total goals (the match-by-match export has no penalty
    split) and PAdj Interceptions ← raw interceptions per 90. Consumers get
    only the shared metrics — market_comparison reports which ones were used.
    """
    if not agg:
        return {}
    shots_total = agg["shots90"] * agg["minutes"] / 90.0
    p: dict[str, float | None] = {
        "Goals per 90": agg["goals90"],
        "Non-penalty goals per 90": agg["goals90"],  # proxy: no penalty split
        "Assists per 90": agg["assists90"],
        "xG per 90": agg["xg90"],
        "Shots per 90": agg["shots90"],
        "Shots on target, %": agg["shots_pct"] or None,
        "Goal conversion, %": (100.0 * agg["goals"] / shots_total
                               if shots_total > 0 else None),
        "Dribbles per 90": agg["dribbles90"],
        "Successful dribbles, %": agg["dribbles_pct"] or None,
        "Crosses per 90": agg["crosses90"],
        "Accurate crosses, %": agg.get("crosses_pct") or None,
        "Aerial duels per 90": agg["aerials90"],
        "Aerial duels won, %": agg["aerials_pct"] or None,
        "Duels won, %": agg["duels_pct"] or None,
        "Passes per 90": agg["passes90"],
        "Accurate passes, %": agg["passes_pct"] or None,
        "Long passes per 90": agg["long_passes90"],
        "Interceptions per 90": agg["interceptions90"],
        "PAdj Interceptions": agg["interceptions90"],  # proxy: not possession-adjusted
    }
    return {k: v for k, v in p.items() if v is not None}


def market_comparison(scored: pd.DataFrame, profile: dict[str, float],
                      group: str, k: int = 10):
    """Percentile an Opta-derived profile against the market and find matches.

    Returns ``(matches, pseudo_pct, pseudo_score, shared)``:
      matches     – top-k market rows by similarity, with ``similarity`` and
                    ``upgrade`` (their score beats the squad player's) columns
      pseudo_pct  – the player's percentile per shared metric (radar-ready)
      pseudo_score– his composite ROLE_METRICS score inside THIS market sample
                    ("he'd rank as a 71 among these CBs"), None if no overlap
      shared      – the shared metric names the whole comparison rests on
    """
    gdf = scored[scored["position_group"] == group]
    inverts = {c: inv for c, _, inv in ROLE_METRICS.get(group, [])}
    pseudo_pct: dict[str, float] = {}
    for col, inv in inverts.items():
        if col not in profile or col not in gdf.columns:
            continue
        sample = gdf[col].dropna()
        if sample.empty:
            continue
        pct = 100.0 * (sample <= profile[col]).mean()
        pseudo_pct[col] = round(100.0 - pct if inv else pct, 1)
    shared = sorted(pseudo_pct)
    if not shared or gdf.empty:
        return gdf.iloc[0:0], pseudo_pct, None, shared

    weights = {c: w for c, w, _ in ROLE_METRICS[group] if c in pseudo_pct}
    pseudo_score = round(
        sum(pseudo_pct[c] * w for c, w in weights.items()) / sum(weights.values()), 1
    )

    pct_cols = [f"pct: {c}" for c in shared if f"pct: {c}" in gdf.columns]
    mat = gdf[pct_cols].astype(float).fillna(50.0)
    ref = pd.Series({f"pct: {c}": pseudo_pct[c] for c in shared})[pct_cols]
    matches = gdf.copy()
    matches["similarity"] = (100.0 - (mat - ref).abs().mean(axis=1)).round(1)
    rank_col = "Score (adj)" if "Score (adj)" in matches.columns else "Score"
    matches["upgrade"] = matches[rank_col] > pseudo_score
    return (matches.sort_values("similarity", ascending=False).head(k),
            pseudo_pct, pseudo_score, shared)


def bridge_radar(scored: pd.DataFrame, group: str, squad_name: str,
                 pseudo_pct: dict[str, float],
                 market_players: list[str]) -> tuple[list[str], dict[str, list[float]]]:
    """Radar axes restricted to metrics the Opta profile can actually express."""
    gdf = scored[scored["position_group"] == group]
    axes = [(c, label) for c, label in RADAR_METRICS.get(group, []) if c in pseudo_pct]
    categories = [label for _, label in axes]
    values = {squad_name: [pseudo_pct[c] for c, _ in axes]}
    for name in market_players:
        row = gdf[gdf["Player"] == name]
        if row.empty:
            continue
        row = row.iloc[0]
        values[name] = [
            float(row[f"pct: {c}"]) if f"pct: {c}" in gdf.columns and pd.notna(row.get(f"pct: {c}"))
            else 50.0
            for c, _ in axes
        ]
    return categories, values
