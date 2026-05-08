"""Athletic-style player profile: dimension ratings, archetypes, and similarity search.

Replicates the card format from The Athletic / Opta SkillCorner:
  - 5 position-specific dimensions (vs percentile across peers in Europe)
  - Archetype label + one-liner description
  - Pan-European similar players via cosine similarity on per-90 feature vectors

Data source: jugadores_seasonstats.csv (aggregated per season, no tracking data).
Press resistance is approximated from pass-completion rates — we don't have SkillCorner.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

# ── Dimension definitions per position group ─────────────────────────────────
# Each dimension = weighted sum of CSV stat columns (per-90 normalized).
# Negative weights = lower value is better (e.g., goals conceded).
# "per90" = True → multiply by (90 / minutes) before weighting.

DIMENSION_CONFIGS: dict[str, dict[str, dict]] = {
    "Forward": {
        "Goal Threat": {
            "stats": {"Goals": 0.40, "Shots On Target ( inc goals )": 0.30, "Total Big Chances Scored": 0.30},
            "per90": True,
        },
        "Box Threat": {
            "stats": {"Total Touches In Opposition Box": 0.50, "Goals from Inside Box": 0.30,
                      "Total Big Chances Missed": 0.20},
            "per90": True,
        },
        "Shot Volume": {
            "stats": {"Total Shots": 0.70, "Attempts from Set Pieces": 0.30},
            "per90": True,
        },
        "Creative Threat": {
            "stats": {"Goal Assists": 0.40, "Key Passes (Attempt Assists)": 0.35,
                      "Total Big Chances Created": 0.25},
            "per90": True,
        },
        "On-ball": {
            "stats": {"Touches": 0.50, "Successful Dribbles": 0.30, "Total Fouls Won": 0.20},
            "per90": True,
        },
    },

    "Midfielder": {
        "On-ball": {
            "stats": {"Touches": 0.40, "Total Passes": 0.35, "Open Play Passes": 0.25},
            "per90": True,
        },
        # Press resistance: proxy via pass accuracy under build-up conditions.
        # Successful open-play passes indicates calmness when pressed;
        # fouls won shows ability to draw pressure and earn set pieces.
        "Press Resistance": {
            "stats": {
                "Successful Open Play Passes": 0.50,
                "Successful Passes Own Half": 0.35,
                "Total Fouls Won": 0.15,
            },
            "per90": True,
        },
        "Carry Progression": {
            "stats": {"Progressive Carries": 0.55, "Successful Dribbles": 0.30, "Carries": 0.15},
            "per90": True,
        },
        "Creative Threat": {
            "stats": {"Key Passes (Attempt Assists)": 0.40, "Total Big Chances Created": 0.30,
                      "Goal Assists": 0.30},
            "per90": True,
        },
        "Defensive Work": {
            "stats": {"Tackles Won": 0.35, "Interceptions": 0.35, "Recoveries": 0.30},
            "per90": True,
        },
    },

    "Defender": {
        "Aerial Threat": {
            "stats": {"Aerial Duels won": 0.55, "Total Clearances": 0.30, "Headed Goals": 0.15},
            "per90": True,
        },
        "Ball-Playing": {
            "stats": {"Successful Long Passes": 0.40, "Successful Passes Opposition Half": 0.35,
                      "Total Successful Passes ( Excl Crosses & Corners ) ": 0.25},
            "per90": True,
        },
        "Press Resistance": {
            "stats": {"Successful Passes Own Half": 0.55, "Successful Open Play Passes": 0.30,
                      "Total Fouls Won": 0.15},
            "per90": True,
        },
        "Tackle Quality": {
            "stats": {"Tackles Won": 0.50, "Last Player Tackle": 0.30, "Interceptions": 0.20},
            "per90": True,
        },
        "Recovery": {
            "stats": {"Recoveries": 0.45, "Total Clearances": 0.35, "Blocks": 0.20},
            "per90": True,
        },
    },

    "Goalkeeper": {
        "Shot Stopping": {
            "stats": {"Saves Made": 0.40, "Saves Made from Inside Box": 0.35,
                      "Total Big Chances Saved": 0.25},
            "per90": True,
        },
        "Distribution": {
            "stats": {"GK Successful Distribution": 0.45, "Successful Long Passes": 0.35,
                      "GK Unsuccessful Distribution": -0.20},
            "per90": True,
        },
        "Command": {
            "stats": {"Catches": 0.40, "Punches": 0.25, "Goalkeeper Smother": 0.20,
                      "Crosses not Claimed": -0.15},
            "per90": True,
        },
        "Reflexes": {
            "stats": {"Saves made - parried": 0.45, "Saves Made from Inside Box": 0.35,
                      "Saves made - caught": 0.20},
            "per90": True,
        },
        "Clean Sheets": {
            "stats": {"Clean Sheets": 0.70, "Goals Conceded": -0.30},
            "per90": False,
        },
    },
}

DIMENSION_CONFIGS["Attacker"] = DIMENSION_CONFIGS["Forward"]

# ── Archetype labels (name, description, one-liner) ──────────────────────────
# Keyed by (position, dominant_dimension).
# Priority: first matching rule wins.

_FWD_ARCHETYPES = [
    ({"Goal Threat": 4, "Shot Volume": 3},
     ("Output Merchant", "High-volume shooter who drives into the box from wide")),
    ({"Creative Threat": 4, "On-ball": 4},
     ("False Nine", "Drops deep to link play and create in pockets of space")),
    ({"Box Threat": 4, "Goal Threat": 3},
     ("Box Predator", "Instinctive mover inside the box who lives for one-touch chances")),
    ({"On-ball": 4, "Creative Threat": 3},
     ("Withdrawn Forward", "Holds the ball up and combines to pull opponents out of shape")),
    ({},
     ("Complete Forward", "Versatile attacker who contributes across all areas of the game")),
]

_MID_ARCHETYPES = [
    ({"On-ball": 4, "Creative Threat": 4},
     ("Playmaker", "Will drop into pockets to receive the ball and create chances")),
    ({"Press Resistance": 4, "On-ball": 4},
     ("Tempo Controller", "Press-resistant midfielder, highly involved in team build-up")),
    ({"Carry Progression": 4, "On-ball": 3},
     ("Midfield Catalyst", "Drives the ball upfield and gets forward himself")),
    ({"Defensive Work": 4},
     ("Defensive Anchor", "Breaks up play and shields the back line to recycle possession")),
    ({},
     ("Box-to-Box", "Covers every blade of grass, contributing at both ends of the pitch")),
]

_DEF_ARCHETYPES = [
    ({"Ball-Playing": 4, "Press Resistance": 4},
     ("Ball-Playing CB", "Comfortable in possession and drives play from the back")),
    ({"Aerial Threat": 4, "Tackle Quality": 3},
     ("Aerial Colossus", "Dominant in the air at both ends and aggressive in the tackle")),
    ({"Tackle Quality": 4},
     ("Defensive Rock", "Reads the game exceptionally and wins his duels consistently")),
    ({},
     ("Reliable Defender", "Disciplined and positionally aware at the back")),
]

_GK_ARCHETYPES = [
    ({"Distribution": 4},
     ("Sweeper Keeper", "Commands his area and distributes effectively to build from the back")),
    ({"Shot Stopping": 4},
     ("Shot Stopper", "Elite reflexes and positioning — a match-winner between the sticks")),
    ({},
     ("Reliable Keeper", "Consistent last line of defense who organises the back line")),
]

_ARCHETYPE_MAP = {
    "Forward": _FWD_ARCHETYPES,
    "Attacker": _FWD_ARCHETYPES,
    "Midfielder": _MID_ARCHETYPES,
    "Defender": _DEF_ARCHETYPES,
    "Goalkeeper": _GK_ARCHETYPES,
}


def _match_archetype_rule(dim_ratings: dict[str, int], rule: dict[str, int]) -> bool:
    if not rule:
        return True
    return all(dim_ratings.get(dim, 0) >= thresh for dim, thresh in rule.items())


def get_archetype(position: str, dim_ratings: dict[str, int]) -> tuple[str, str]:
    """Return (archetype_name, description) for a player given their dimension ratings."""
    rules = _ARCHETYPE_MAP.get(position, _ARCHETYPE_MAP["Midfielder"])
    for rule, result in rules:
        if _match_archetype_rule(dim_ratings, rule):
            return result
    return "Versatile", "Well-rounded profile across multiple positional demands"


# ── Dimension computation ─────────────────────────────────────────────────────

def _raw_score(row: pd.Series, stat_weights: dict[str, float], per90: bool,
               minutes: float) -> float:
    """Compute a weighted raw score from a player's stats row."""
    if minutes < 1:
        return 0.0
    factor = (90.0 / minutes) if per90 else 1.0
    score = 0.0
    for stat, weight in stat_weights.items():
        val = float(row.get(stat, 0) or 0)
        if weight < 0:
            val = -val
            weight = abs(weight)
        score += val * factor * weight
    return score


def compute_dimension_ratings(
    player_row: pd.Series,
    position: str,
    peer_df: pd.DataFrame,
) -> dict[str, int]:
    """Compute 1–5 dimension ratings for a player vs their positional peers.

    Args:
        player_row: The player's stats row.
        position: Broad position string (Forward/Midfielder/Defender/Goalkeeper).
        peer_df: All players with the same broad position (for percentile ranking).

    Returns:
        {dimension_name: rating_1_to_5}
    """
    pos = position if position in DIMENSION_CONFIGS else "Midfielder"
    dims = DIMENSION_CONFIGS[pos]
    minutes = float(player_row.get("Time Played", 90) or 90)

    results: dict[str, int] = {}
    for dim_name, cfg in dims.items():
        player_score = _raw_score(player_row, cfg["stats"], cfg["per90"], minutes)

        # Compute peer scores
        peer_minutes = peer_df["Time Played"].fillna(90).clip(lower=1).astype(float)
        peer_scores = []
        for _, peer_row in peer_df.iterrows():
            pm = float(peer_row.get("Time Played", 90) or 90)
            peer_scores.append(_raw_score(peer_row, cfg["stats"], cfg["per90"], pm))

        if not peer_scores:
            results[dim_name] = 3
            continue

        peer_arr = np.array(peer_scores)
        pctile = float(np.sum(peer_arr <= player_score)) / len(peer_arr) * 100

        # Bucket percentile → 1-5 squares
        if pctile >= 80:
            results[dim_name] = 5
        elif pctile >= 60:
            results[dim_name] = 4
        elif pctile >= 40:
            results[dim_name] = 3
        elif pctile >= 20:
            results[dim_name] = 2
        else:
            results[dim_name] = 1

    return results


# ── Similar players (cosine similarity) ──────────────────────────────────────

FEATURE_COLS = [
    "Goals", "Shots On Target ( inc goals )", "Total Shots",
    "Total Touches In Opposition Box", "Goal Assists",
    "Key Passes (Attempt Assists)", "Total Big Chances Created",
    "Total Passes", "Successful Open Play Passes",
    "Progressive Carries", "Successful Dribbles", "Carries",
    "Tackles Won", "Interceptions", "Recoveries",
    "Aerial Duels won", "Touches", "Total Fouls Won",
]

MAJOR_LEAGUES = [
    "England_Premier_League",
    "Spain_Primera_Division",
    "Germany_Bundesliga",
    "Italy_Serie_A",
    "France_Ligue_1",
    "Portugal_Primeira_Liga",
    "Netherlands_Eredivisie",
    "UEFA_UEFA_Champions_League",
    "UEFA_UEFA_Europa_League",
]


def _build_feature_vector(row: pd.Series) -> np.ndarray:
    """Build a per-90 normalized feature vector for similarity search."""
    minutes = float(row.get("Time Played", 90) or 90)
    minutes = max(minutes, 1.0)
    factor = 90.0 / minutes
    vec = []
    for col in FEATURE_COLS:
        val = float(row.get(col, 0) or 0)
        vec.append(val * factor)
    return np.array(vec, dtype=float)


@st.cache_data(ttl=7200, show_spinner=False)
def load_cross_league_stats(season: str) -> pd.DataFrame:
    """Load player stats from all major leagues for similarity search.

    Returns a combined DataFrame with an added 'league' column.
    Cached for 2 hours — this scans multiple league directories.
    """
    from data.paths import equipos_dir, list_team_folders
    from config import DATA_ROOT
    import pathlib

    frames = []
    for league in MAJOR_LEAGUES:
        league_path = DATA_ROOT / league / season
        if not league_path.exists():
            continue
        eq_dir = league_path / "equipos"
        if not eq_dir.exists():
            continue
        for team_dir in eq_dir.iterdir():
            if not team_dir.is_dir():
                continue
            csv = team_dir / f"{team_dir.name}_jugadores_seasonstats.csv"
            if not csv.exists():
                continue
            try:
                df = pd.read_csv(csv)
                df["_league"] = league.replace("_", " ")
                frames.append(df)
            except Exception:
                continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Minimum minutes filter
    if "Time Played" in combined.columns:
        combined = combined[combined["Time Played"].fillna(0) >= 450]
    return combined


def find_similar_players(
    player_id: str,
    player_position: str,
    all_stats: pd.DataFrame,
    cross_league_df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Find the top-N most similar players to the target player across Europe.

    Uses cosine similarity on per-90 feature vectors within the same broad position.

    Args:
        player_id: Opta player ID of the target.
        player_position: Broad position for peer filtering.
        all_stats: Current-league player stats (already loaded).
        cross_league_df: Combined stats from major European leagues.
        top_n: How many similar players to return.

    Returns:
        DataFrame with columns: nombre, equipo, liga, similarity_pct
    """
    frames = [df for df in [all_stats, cross_league_df] if not df.empty]
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    if "id" in combined.columns:
        combined = combined.drop_duplicates(subset=["id"], keep="first")

    peers = combined[combined["posicion"] == player_position].copy()
    peers = peers[peers["Time Played"].fillna(0) >= 450].reset_index(drop=True)

    target_rows = peers[peers["id"].astype(str) == str(player_id)]
    if target_rows.empty:
        return pd.DataFrame()

    target_row = target_rows.iloc[0]
    target_vec = np.nan_to_num(_build_feature_vector(target_row), nan=0.0)

    # Build peer list in parallel with their info — avoids index confusion later
    peer_vecs = []
    peer_info = []
    for _, row in peers.iterrows():
        if str(row.get("id", "")) == str(player_id):
            continue
        vec = np.nan_to_num(_build_feature_vector(row), nan=0.0)
        peer_vecs.append(vec)
        peer_info.append({
            "nombre":   row.get("nombre", "Unknown"),
            "equipo":   row.get("equipo", ""),
            "liga":     row.get("_league", row.get("liga", "")),
            "posicion": row.get("posicion", ""),
        })

    if len(peer_vecs) < 2:
        return pd.DataFrame()

    peer_matrix = np.vstack(peer_vecs)

    # Stack target + peers, scale together, then split back
    all_matrix = np.vstack([target_vec.reshape(1, -1), peer_matrix])
    scaler = MinMaxScaler()
    all_scaled = scaler.fit_transform(all_matrix)
    # Replace any NaN introduced by zero-variance columns
    all_scaled = np.nan_to_num(all_scaled, nan=0.0)
    target_scaled = all_scaled[0:1]
    peers_scaled = all_scaled[1:]

    sims = cosine_similarity(target_scaled, peers_scaled)[0]

    top_idx = np.argsort(sims)[::-1][:top_n]
    result_rows = []
    for i in top_idx:
        if i >= len(peer_info):
            continue
        info = peer_info[i].copy()
        info["similarity_pct"] = round(float(sims[i]) * 100, 1)
        result_rows.append(info)

    return pd.DataFrame(result_rows)
