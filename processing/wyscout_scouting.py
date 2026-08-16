from __future__ import annotations
"""Wyscout search-export analytics for the Scouting Hub page.

Input is one or more "Search results" .xlsx exports from Wyscout (~115 columns
of pre-aggregated per-90 stats). Unlike the rest of processing/, the source is
an uploaded in-memory file, not the Opta data root, so nothing here touches
data.loader — the page caches parsing on the upload bytes instead.

Scoring model: every metric is converted to a percentile *within the player's
position group* across the pooled upload sample, then blended with role
weights into a 0–100 composite. Raw cross-position comparisons are
meaningless (0.2 xG/90 is elite for a CB, terrible for a CF).
"""

import pandas as pd

# ── Position groups ──────────────────────────────────────────────────────────
# Wyscout position codes → coarse group. Primary position = first code listed.
POSITION_GROUP_MAP = {
    "GK": "GK",
    "CB": "CB", "RCB": "CB", "LCB": "CB",
    "RB": "FB", "LB": "FB", "RWB": "FB", "LWB": "FB",
    "DMF": "DM", "RDMF": "DM", "LDMF": "DM",
    "CMF": "CM", "RCMF": "CM", "LCMF": "CM",
    "AMF": "AM", "RAMF": "AM", "LAMF": "AM",
    "RW": "W", "LW": "W", "RWF": "W", "LWF": "W",
    "CF": "ST",
}

GROUP_LABELS = {
    "GK": "Goalkeeper", "CB": "Centre Back", "FB": "Full Back / Wing Back",
    "DM": "Defensive Midfielder", "CM": "Central Midfielder",
    "AM": "Attacking Midfielder", "W": "Winger", "ST": "Striker",
}

# Percentiles get noisy below this many players in a group — flagged in output.
MIN_GROUP_SAMPLE = 8
DEFAULT_MIN_MINUTES = 900  # ~10 full matches, mirrors MIN_APPEARANCES_FOR_RATING spirit

# ── Role scoring weights ─────────────────────────────────────────────────────
# (column, weight, invert). invert=True → lower raw value is better.
# This dict IS the scouting philosophy of the page: tweak weights here to
# favour e.g. ball-playing CBs over stoppers. Weights are renormalised over
# whichever columns actually exist in the upload, so partial exports still work.
ROLE_METRICS: dict[str, list[tuple[str, float, bool]]] = {
    "GK": [
        ("Prevented goals per 90", 0.30, False),
        ("Save rate, %", 0.20, False),
        ("Conceded goals per 90", 0.10, True),
        ("Exits per 90", 0.10, False),
        ("Aerial duels per 90.1", 0.10, False),
        ("Accurate long passes, %", 0.10, False),
        ("Accurate passes, %", 0.10, False),
    ],
    "CB": [
        ("Defensive duels won, %", 0.16, False),
        ("Aerial duels won, %", 0.14, False),
        ("PAdj Interceptions", 0.12, False),
        ("Successful defensive actions per 90", 0.12, False),
        ("Shots blocked per 90", 0.06, False),
        ("Accurate passes, %", 0.10, False),
        ("Progressive passes per 90", 0.10, False),
        ("Accurate long passes, %", 0.07, False),
        ("Progressive runs per 90", 0.05, False),
        ("Fouls per 90", 0.04, True),
        ("Yellow cards per 90", 0.04, True),
    ],
    "FB": [
        ("Defensive duels won, %", 0.13, False),
        ("Successful defensive actions per 90", 0.11, False),
        ("PAdj Interceptions", 0.08, False),
        ("Crosses per 90", 0.08, False),
        ("Accurate crosses, %", 0.08, False),
        ("Progressive runs per 90", 0.11, False),
        ("Progressive passes per 90", 0.11, False),
        ("xA per 90", 0.10, False),
        ("Key passes per 90", 0.07, False),
        ("Duels won, %", 0.08, False),
        ("Accelerations per 90", 0.05, False),
    ],
    "DM": [
        ("PAdj Interceptions", 0.15, False),
        ("Defensive duels won, %", 0.13, False),
        ("Successful defensive actions per 90", 0.12, False),
        ("Aerial duels won, %", 0.08, False),
        ("Accurate passes, %", 0.12, False),
        ("Progressive passes per 90", 0.12, False),
        ("Passes to final third per 90", 0.10, False),
        ("Accurate long passes, %", 0.07, False),
        ("Received passes per 90", 0.06, False),
        ("Fouls per 90", 0.05, True),
    ],
    "CM": [
        ("Progressive passes per 90", 0.13, False),
        ("Passes to final third per 90", 0.10, False),
        ("Accurate passes, %", 0.10, False),
        ("Key passes per 90", 0.10, False),
        ("xA per 90", 0.10, False),
        ("Successful attacking actions per 90", 0.09, False),
        ("Successful defensive actions per 90", 0.10, False),
        ("Duels won, %", 0.09, False),
        ("Progressive runs per 90", 0.07, False),
        ("Smart passes per 90", 0.06, False),
        ("xG per 90", 0.06, False),
    ],
    "AM": [
        ("xA per 90", 0.14, False),
        ("Key passes per 90", 0.12, False),
        ("Smart passes per 90", 0.09, False),
        ("Shot assists per 90", 0.09, False),
        ("Deep completions per 90", 0.08, False),
        ("Successful dribbles, %", 0.08, False),
        ("Dribbles per 90", 0.07, False),
        ("xG per 90", 0.10, False),
        ("Non-penalty goals per 90", 0.10, False),
        ("Touches in box per 90", 0.07, False),
        ("Passes to penalty area per 90", 0.06, False),
    ],
    "W": [
        ("Dribbles per 90", 0.12, False),
        ("Successful dribbles, %", 0.10, False),
        ("xA per 90", 0.12, False),
        ("Crosses per 90", 0.07, False),
        ("Accurate crosses, %", 0.07, False),
        ("Progressive runs per 90", 0.10, False),
        ("Touches in box per 90", 0.09, False),
        ("xG per 90", 0.10, False),
        ("Non-penalty goals per 90", 0.10, False),
        ("Shot assists per 90", 0.07, False),
        ("Accelerations per 90", 0.06, False),
    ],
    "ST": [
        ("Non-penalty goals per 90", 0.18, False),
        ("xG per 90", 0.16, False),
        ("Shots on target, %", 0.09, False),
        ("Goal conversion, %", 0.09, False),
        ("Touches in box per 90", 0.11, False),
        ("Aerial duels won, %", 0.09, False),
        ("xA per 90", 0.08, False),
        ("Successful attacking actions per 90", 0.08, False),
        ("Offensive duels won, %", 0.06, False),
        ("Received passes per 90", 0.06, False),
    ],
}

# 8 axes per group for the comparison radar: (column, short label).
RADAR_METRICS: dict[str, list[tuple[str, str]]] = {
    "GK": [
        ("Prevented goals per 90", "Prevented"), ("Save rate, %", "Save %"),
        ("Conceded goals per 90", "Conceded"), ("Exits per 90", "Exits"),
        ("Aerial duels per 90.1", "Aerial"), ("Accurate long passes, %", "Long pass %"),
        ("Accurate passes, %", "Pass %"), ("xG against per 90", "xGA/90"),
    ],
    "CB": [
        ("Defensive duels won, %", "Def duels %"), ("Aerial duels won, %", "Aerial %"),
        ("PAdj Interceptions", "PAdj Int"), ("Successful defensive actions per 90", "Def actions"),
        ("Accurate passes, %", "Pass %"), ("Progressive passes per 90", "Prog passes"),
        ("Accurate long passes, %", "Long pass %"), ("Progressive runs per 90", "Prog runs"),
    ],
    "FB": [
        ("Defensive duels won, %", "Def duels %"), ("Successful defensive actions per 90", "Def actions"),
        ("Crosses per 90", "Crosses"), ("Accurate crosses, %", "Cross %"),
        ("Progressive runs per 90", "Prog runs"), ("Progressive passes per 90", "Prog passes"),
        ("xA per 90", "xA/90"), ("Key passes per 90", "Key passes"),
    ],
    "DM": [
        ("PAdj Interceptions", "PAdj Int"), ("Defensive duels won, %", "Def duels %"),
        ("Successful defensive actions per 90", "Def actions"), ("Aerial duels won, %", "Aerial %"),
        ("Accurate passes, %", "Pass %"), ("Progressive passes per 90", "Prog passes"),
        ("Passes to final third per 90", "Final 3rd"), ("Accurate long passes, %", "Long pass %"),
    ],
    "CM": [
        ("Progressive passes per 90", "Prog passes"), ("Passes to final third per 90", "Final 3rd"),
        ("Key passes per 90", "Key passes"), ("xA per 90", "xA/90"),
        ("xG per 90", "xG/90"), ("Duels won, %", "Duels %"),
        ("Successful defensive actions per 90", "Def actions"), ("Accurate passes, %", "Pass %"),
    ],
    "AM": [
        ("xA per 90", "xA/90"), ("Key passes per 90", "Key passes"),
        ("Smart passes per 90", "Smart passes"), ("Successful dribbles, %", "Dribble %"),
        ("xG per 90", "xG/90"), ("Non-penalty goals per 90", "NP goals"),
        ("Touches in box per 90", "Box touches"), ("Deep completions per 90", "Deep compl"),
    ],
    "W": [
        ("Dribbles per 90", "Dribbles"), ("Successful dribbles, %", "Dribble %"),
        ("xA per 90", "xA/90"), ("Accurate crosses, %", "Cross %"),
        ("Progressive runs per 90", "Prog runs"), ("Touches in box per 90", "Box touches"),
        ("xG per 90", "xG/90"), ("Non-penalty goals per 90", "NP goals"),
    ],
    "ST": [
        ("Non-penalty goals per 90", "NP goals"), ("xG per 90", "xG/90"),
        ("Shots on target, %", "SoT %"), ("Goal conversion, %", "Conversion"),
        ("Touches in box per 90", "Box touches"), ("Aerial duels won, %", "Aerial %"),
        ("xA per 90", "xA/90"), ("Offensive duels won, %", "Off duels %"),
    ],
}

# ── Archetypes ───────────────────────────────────────────────────────────────
# Per group: (label, [metric columns]). A player's archetype is the bundle
# where their within-group percentiles run highest — it describes HOW they
# play, while Score describes how WELL. Two 75-score CBs can be stylistic
# opposites; replacing a stopper with a ball-player changes the whole system.
ARCHETYPES: dict[str, list[tuple[str, list[str]]]] = {
    "GK": [
        ("Shot-Stopper", ["Prevented goals per 90", "Save rate, %"]),
        ("Sweeper Keeper", ["Exits per 90", "Aerial duels per 90.1"]),
        ("Distributor", ["Accurate long passes, %", "Accurate passes, %", "Passes per 90"]),
    ],
    "CB": [
        ("Ball-Playing", ["Progressive passes per 90", "Accurate passes, %",
                          "Accurate long passes, %", "Passes to final third per 90"]),
        ("Stopper", ["Defensive duels won, %", "PAdj Sliding tackles",
                     "Shots blocked per 90", "Successful defensive actions per 90"]),
        ("Aerial Dominator", ["Aerial duels won, %", "Aerial duels per 90", "Head goals per 90"]),
        ("Mobile Carrier", ["Progressive runs per 90", "Accelerations per 90", "Dribbles per 90"]),
    ],
    "FB": [
        ("Attacking", ["Crosses per 90", "xA per 90", "Key passes per 90",
                       "Touches in box per 90"]),
        ("Defensive", ["Defensive duels won, %", "PAdj Interceptions",
                       "Successful defensive actions per 90", "Aerial duels won, %"]),
        ("Inverted Playmaker", ["Passes per 90", "Progressive passes per 90",
                                "Accurate passes, %", "Smart passes per 90"]),
    ],
    "DM": [
        ("Destroyer", ["PAdj Interceptions", "Defensive duels per 90",
                       "Defensive duels won, %", "PAdj Sliding tackles"]),
        ("Deep-Lying Playmaker", ["Progressive passes per 90", "Accurate long passes, %",
                                  "Passes per 90", "Passes to final third per 90"]),
        ("Box-to-Box", ["Progressive runs per 90", "Offensive duels per 90",
                        "xG per 90", "Touches in box per 90"]),
    ],
    "CM": [
        ("Playmaker", ["Key passes per 90", "Smart passes per 90", "xA per 90",
                       "Passes to penalty area per 90"]),
        ("Box-to-Box", ["Progressive runs per 90", "xG per 90",
                        "Touches in box per 90", "Offensive duels per 90"]),
        ("Ball-Winner", ["PAdj Interceptions", "Defensive duels won, %",
                         "Successful defensive actions per 90", "Aerial duels won, %"]),
    ],
    "AM": [
        ("Creator", ["xA per 90", "Key passes per 90", "Smart passes per 90",
                     "Deep completions per 90"]),
        ("Shadow Striker", ["xG per 90", "Non-penalty goals per 90",
                            "Touches in box per 90", "Shots per 90"]),
        ("Dribbler", ["Dribbles per 90", "Successful dribbles, %",
                      "Progressive runs per 90", "Accelerations per 90"]),
    ],
    "W": [
        ("Direct Dribbler", ["Dribbles per 90", "Progressive runs per 90",
                             "Accelerations per 90"]),
        ("Goal Threat", ["xG per 90", "Non-penalty goals per 90",
                         "Touches in box per 90", "Shots per 90"]),
        ("Wide Creator", ["Crosses per 90", "Accurate crosses, %", "xA per 90",
                          "Shot assists per 90"]),
    ],
    "ST": [
        ("Poacher", ["Non-penalty goals per 90", "Goal conversion, %",
                     "Touches in box per 90", "xG per 90"]),
        ("Target Man", ["Aerial duels won, %", "Aerial duels per 90", "Head goals per 90"]),
        ("Link-Up Forward", ["Received passes per 90", "Key passes per 90",
                             "xA per 90", "Passes per 90"]),
    ],
}

# Top-1 vs top-2 bundle gap below this → the player has no dominant style.
_COMPLETE_GAP = 4.0
_COMPLETE_FLOOR = 60.0


def assign_archetypes(scored: pd.DataFrame) -> pd.DataFrame:
    """Add ``Archetype`` plus per-bundle score columns (``arch: <label>``).

    Bundle score = mean within-group percentile of the bundle's metrics.
    A player whose top two bundles are within ~4 points (both decent) is
    labelled "Complete" — forcing a style tag on them would be noise.
    """
    out = scored.copy()
    out["Archetype"] = pd.NA
    for group, gdf in out.groupby("position_group"):
        bundles = ARCHETYPES.get(group, [])
        bundle_scores: dict[str, pd.Series] = {}
        for label, cols in bundles:
            pcts = []
            for col in cols:
                pct_col = f"pct: {col}"
                if pct_col in gdf.columns and gdf[pct_col].notna().any():
                    pcts.append(gdf[pct_col])
                elif col in gdf.columns:
                    pcts.append(_pct(gdf[col]))
            if pcts:
                score = pd.concat(pcts, axis=1).mean(axis=1)
                bundle_scores[label] = score
                out.loc[gdf.index, f"arch: {label}"] = score.round(1)
        if not bundle_scores:
            continue
        mat = pd.DataFrame(bundle_scores)
        top = mat.max(axis=1)
        top_label = mat.idxmax(axis=1)
        second = mat.apply(lambda r: r.nlargest(2).iloc[-1] if r.notna().sum() > 1 else 0.0, axis=1)
        complete = (top - second < _COMPLETE_GAP) & (top >= _COMPLETE_FLOOR)
        out.loc[gdf.index, "Archetype"] = top_label.mask(complete, "Complete")
    return out


def archetype_breakdown(scored: pd.DataFrame, index) -> dict[str, float]:
    """Bundle scores for one player row (for the archetype bar chart)."""
    row = scored.loc[index]
    return {
        c.removeprefix("arch: "): float(row[c])
        for c in scored.columns
        if c.startswith("arch: ") and pd.notna(row[c])
    }


def find_similar(scored: pd.DataFrame, index, k: int = 10) -> pd.DataFrame:
    """Top-k stylistically closest players (same position group).

    Similarity = 100 − mean absolute percentile difference across the group's
    scoring metrics: "92% similar" literally means their percentile profiles
    differ by 8 points on average. Metrics missing for a player fall back to
    the 50th percentile so one missing column doesn't sink the comparison.
    """
    group = scored.loc[index, "position_group"]
    gdf = scored[scored["position_group"] == group]
    pct_cols = [c for c in gdf.columns
                if c.startswith("pct: ") and gdf[c].notna().mean() > 0.5]
    if not pct_cols or len(gdf) < 2:
        return gdf.iloc[0:0]
    mat = gdf[pct_cols].astype(float).fillna(50.0)
    diffs = (mat - mat.loc[index]).abs().mean(axis=1)
    out = gdf.copy()
    out["similarity"] = (100.0 - diffs).round(1)
    out = out.drop(index=index).sort_values("similarity", ascending=False)
    return out.head(k)


# Columns carried through for display/filtering (beyond scoring metrics).
_ID_COLS = ["Player", "Team", "Position", "Age", "Market value",
            "Contract expires", "Matches played", "Minutes played",
            "Foot", "Height", "Birth country", "Passport country", "On loan"]


def primary_position_group(position: str | float) -> str | None:
    """Map a Wyscout position string ('RCB, LCB') to a group via its primary code."""
    if not isinstance(position, str) or not position.strip():
        return None
    primary = position.split(",")[0].strip().upper()
    return POSITION_GROUP_MAP.get(primary)


def all_position_groups(position: str | float) -> list[str]:
    """Every distinct group a player covers, in Wyscout's listed order.

    'LB, LCB, LWB' → ['FB', 'CB']: the player is scored in BOTH groups, each
    against that group's sample. Wyscout lists positions by minutes played,
    so the first group is the primary role.
    """
    if not isinstance(position, str):
        return []
    groups: list[str] = []
    for code in position.split(","):
        g = POSITION_GROUP_MAP.get(code.strip().upper())
        if g and g not in groups:
            groups.append(g)
    return groups


def normalize_wyscout(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Validate + normalise one Wyscout export. Adds source_file / position_group."""
    if "Player" not in df.columns or "Position" not in df.columns:
        raise ValueError(
            f"'{source_name}' does not look like a Wyscout search export "
            "(missing 'Player'/'Position' columns)."
        )
    out = df.copy()
    out["source_file"] = source_name
    # Mixed-type Position values (Wyscout writes a literal 0 sometimes) break
    # Arrow serialization in st.dataframe — normalise to str up front.
    out["Position"] = out["Position"].astype(str)
    out["position_group"] = out["Position"].map(primary_position_group)
    out["position_groups"] = out["Position"].map(all_position_groups)
    # Reduced exports (column subsets) may lack these; pages and the PDF
    # assume they exist, so guarantee the full identity set.
    if "Market value" not in out.columns:
        out["Market value"] = 0.0
    if "Contract expires" not in out.columns:
        out["Contract expires"] = pd.NaT
    for col in ("Foot", "Birth country", "Passport country", "On loan"):
        if col not in out.columns:
            out[col] = pd.NA
    for col in ("Height", "Weight", "Age", "Matches played"):
        if col not in out.columns:
            out[col] = 0.0
    out["Contract expires"] = pd.to_datetime(out.get("Contract expires"), errors="coerce")
    for col in out.columns:
        if col in ("Player", "Team", "Team within selected timeframe", "Position",
                   "Foot", "Birth country", "Passport country", "On loan",
                   "source_file", "position_group", "position_groups",
                   "Contract expires"):
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Player"])
    out = out[out["position_group"].notna()]
    return out


def combine_sources(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Pool uploads into one frame, deduping players that appear in several files.

    Duplicate key is (Player, Team): the row with most minutes wins, but we keep
    the list of files each player appeared in (useful to know which searches
    surfaced them).
    """
    pooled = pd.concat(frames, ignore_index=True)
    files_per_player = (
        pooled.groupby(["Player", "Team"])["source_file"]
        .agg(lambda s: sorted(set(s))).rename("found_in")
    )
    pooled = (
        pooled.sort_values("Minutes played", ascending=False)
        .drop_duplicates(subset=["Player", "Team"], keep="first")
        .merge(files_per_player, on=["Player", "Team"], how="left")
    )
    pooled["n_files"] = pooled["found_in"].str.len()
    return pooled.reset_index(drop=True)


def _pct(series: pd.Series, invert: bool = False) -> pd.Series:
    """Percentile rank 0–100 within the series (NaNs stay NaN)."""
    ranked = series.rank(pct=True) * 100.0
    return 100.0 - ranked if invert else ranked


def score_players(pooled: pd.DataFrame,
                  min_minutes: int = DEFAULT_MIN_MINUTES) -> pd.DataFrame:
    """Composite 0–100 role score per (player × position group).

    Multi-position players ('LB, LCB') get one row PER group they cover, each
    percentiled against that group's sample — a player can be the 5th-best FB
    and the 12th-best CB at once. ``group_role`` says whether the row is their
    primary or secondary role. Rankings that want one row per player must
    dedupe afterwards (see :func:`dedupe_best`).

    Players under ``min_minutes`` are excluded from the percentile sample AND
    the output — small-minute per-90 numbers are pure noise. Weights are
    renormalised over the metric columns actually present.
    """
    df = pooled[pooled["Minutes played"] >= min_minutes].copy()
    primary = df["position_group"]
    df = df.assign(position_group=df["position_groups"]).explode("position_group")
    df = df[df["position_group"].notna()]
    df["group_role"] = "secondary"
    df.loc[df["position_group"] == primary.reindex(df.index), "group_role"] = "primary"
    # Explode duplicates index values; similarity/archetypes key rows by index,
    # so make it unique again (same failure mode as Opta's per-period eventId).
    df = df.reset_index(drop=True)
    scored_groups = []
    for group, gdf in df.groupby("position_group"):
        gdf = gdf.copy()
        metrics = [(c, w, inv) for c, w, inv in ROLE_METRICS.get(group, [])
                   if c in gdf.columns]
        total_w = sum(w for _, w, _ in metrics)
        if not metrics or total_w == 0:
            gdf["Score"] = pd.NA
            scored_groups.append(gdf)
            continue
        weighted = pd.Series(0.0, index=gdf.index)
        weight_used = pd.Series(0.0, index=gdf.index)
        for col, w, inv in metrics:
            pct = _pct(gdf[col], invert=inv)
            gdf[f"pct: {col}"] = pct
            valid = pct.notna()
            weighted[valid] += pct[valid] * w
            weight_used[valid] += w
        gdf["Score"] = (weighted / weight_used.replace(0, pd.NA)).round(1)
        gdf["small_sample"] = len(gdf) < MIN_GROUP_SAMPLE
        scored_groups.append(gdf)
    if not scored_groups:
        return df.assign(Score=pd.NA, small_sample=True)
    return pd.concat(scored_groups).sort_values("Score", ascending=False)


def add_value_index(scored: pd.DataFrame) -> pd.DataFrame:
    """Value index = performance percentile − market-value percentile (per group).

    Positive → performs above their price bracket (undervalued); negative →
    the market already prices in their level. Only defined where Wyscout has
    a market value (> 0).
    """
    out = scored.copy()
    out["value_index"] = pd.NA
    for _, gdf in out.groupby("position_group"):
        has_value = gdf["Market value"] > 0
        sub = gdf[has_value]
        if sub.empty:
            continue
        value_pct = _pct(sub["Market value"])
        score_pct = _pct(sub["Score"])
        out.loc[sub.index, "value_index"] = (score_pct - value_pct).round(1)
    return out


# ── League level adjustment ──────────────────────────────────────────────────
# A 90th-percentile passer in a development league is not a 90th-percentile
# passer in the Bundesliga. Wyscout exports carry no league column, but each
# search file is usually one league, so the tier is tagged per FILE at upload.
# The coefficient scales the composite Score only — percentiles, archetypes and
# similarity stay raw (style doesn't change with league level; quality does).
LEAGUE_TIERS: dict[str, float] = {
    "Elite (×1.00)": 1.00,        # top-5 UEFA, continental elite
    "Fuerte (×0.92)": 0.92,       # Liga MX, Eredivisie, Primeira, Championship
    "Media (×0.85)": 0.85,        # MLS, mid European leagues, 2nd divisions top-5
    "Desarrollo (×0.75)": 0.75,   # smaller leagues, CONCACAF mid
    "Menor (×0.65)": 0.65,        # lower divisions
}
DEFAULT_TIER = "Elite (×1.00)"


def apply_league_coefficients(scored: pd.DataFrame,
                              coeff_by_file: dict[str, float]) -> pd.DataFrame:
    """Add ``Score (adj)`` = Score × the tier coefficient of the player's file."""
    out = scored.copy()
    out["league_coeff"] = out["source_file"].map(coeff_by_file).fillna(1.0)
    out["Score (adj)"] = (out["Score"] * out["league_coeff"]).round(1)
    return out


def rank_col(scored: pd.DataFrame) -> str:
    """Ranking column: league-adjusted score when tiers were applied."""
    return "Score (adj)" if "Score (adj)" in scored.columns else "Score"


def dedupe_best(scored: pd.DataFrame) -> pd.DataFrame:
    """One row per player: keep their best-scoring position group.

    Use for player-level views (per-file tops, market tables, KPI counts)
    where the group-exploded frame would double-count multi-position players.
    """
    return (
        scored.sort_values(rank_col(scored), ascending=False)
        .drop_duplicates(subset=["Player", "Team"], keep="first")
    )


def top_by_file(scored: pd.DataFrame, n: int = 10) -> dict[str, pd.DataFrame]:
    """Best N players per uploaded file (by composite score, best group each)."""
    exploded = dedupe_best(scored).explode("found_in")
    return {
        fname: fdf.sort_values(rank_col(fdf), ascending=False).head(n)
        for fname, fdf in exploded.groupby("found_in")
    }


def radar_data(scored: pd.DataFrame, group: str,
               players: list[str]) -> tuple[list[str], dict[str, list[float]]]:
    """Radar axes (percentile 0–100) for selected players of one group."""
    gdf = scored[scored["position_group"] == group]
    axes = [(c, label) for c, label in RADAR_METRICS.get(group, []) if c in gdf.columns]
    categories = [label for _, label in axes]
    values: dict[str, list[float]] = {}
    for name in players:
        row = gdf[gdf["Player"] == name]
        if row.empty:
            continue
        row = row.iloc[0]
        vals = []
        for col, _ in axes:
            pct_col = f"pct: {col}"
            if pct_col in gdf.columns and pd.notna(row.get(pct_col)):
                vals.append(float(row[pct_col]))
            else:
                # Radar axis not part of the scoring set → percentile on the fly
                pct = _pct(gdf[col])
                v = pct.loc[row.name] if row.name in pct.index else None
                vals.append(float(v) if pd.notna(v) else 0.0)
        values[name] = vals
    return categories, values


def display_columns(scored: pd.DataFrame) -> list[str]:
    """Stable column order for ranking tables."""
    cols = (["Score", "Score (adj)", "value_index", "Archetype"] + _ID_COLS
            + ["position_group", "group_role", "found_in"])
    return [c for c in cols if c in scored.columns]
