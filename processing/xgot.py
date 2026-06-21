from __future__ import annotations
"""Expected Goals on Target (xGOT) — a.k.a. Post-Shot xG (PSxG).

xG (``processing/xg_model.py``) is a *pre-shot* model: it scores chance quality
from where the shot was taken.  xGOT is a *post-shot* model: for shots that hit
the target it adds *execution* — **where in the goal the ball was heading**.
A shot drilled into the top corner is far harder to save than the same chance
poked straight at the keeper, even though both share the same pre-shot xG.

This unlocks two things the platform previously could not measure:

  • Finishing skill   :  Σ xGOT − Σ xG   over a player's on-target shots
                         (> 0 → finishes better than the chance deserved).
  • Goalkeeper value  :  Σ xGOT_faced − goals_conceded
                         (> 0 → stops more than an average keeper would).

Data source (Opta F24, confirmed present on all on-target shots in our feed):
  • qualifier 102 → goal-mouth Y (width where the ball crossed the line)
  • qualifier 103 → goal-mouth Z (height where the ball crossed the line)
Both are surfaced by ``data.event_parser.extract_shots`` as ``goalmouth_y`` /
``goalmouth_z`` together with an ``on_target`` flag.

This is an *event-data-only* model — no tracking, no keeper position.  The 2025
Stats Perform xGOT adds keeper positioning; we deliberately approximate with
placement alone and label it as such (see ``XGOT_DISCLAIMER``).

Reference:
    Stats Perform — "Introducing Expected Goals on Target (xGOT)"
    Opta Analyst — "What Are Expected Goals on Target (xGOT)?"
"""

import math
import pandas as pd

# ── Goal-frame geometry on the Opta 0-100 scale ─────────────────────────────
# The goal is 7.32 m wide on a 68 m pitch → 10.76 width-units, centred at y=50.
GOAL_CENTRE_Y = 50.0
GOAL_HALF_WIDTH_UNITS = 7.32 / 68.0 * 100.0 / 2.0   # ≈ 5.38 → posts at 44.6 / 55.4
# Opta records goal-mouth height (z) on a scale where the crossbar sits near 38.
# (Empirically the tallest on-target z values cluster just below this.)
GOALMOUTH_Z_CROSSBAR = 38.0
# The feed stamps a large share of shots (≈40 %, mostly saves) with z exactly at
# the scale midpoint — a "height not recorded" placeholder, NOT a real mid-height
# shot.  Treat it as missing and fall back to horizontal-only placement so these
# shots aren't spuriously credited as mid-height.
GOALMOUTH_Z_PLACEHOLDER = 19.0
_Z_PLACEHOLDER_TOL = 0.2

# ── Model knobs (the tunable heart of the model) ────────────────────────────
# Monotone placement model:  xGOT = xg + (CEILING − xg) · placement**EXPONENT.
#   • central shot (placement→0)  → xGOT ≈ xg   (tame shot keeps its low value,
#     so the keeper earns ~no credit for an easy save).
#   • corner shot  (placement→1)  → xGOT ≈ CEILING (very likely a goal).
# The exponent controls how sharply placement is rewarded — higher = only the
# genuine corners get a big lift.  This is the most opinionated knob; raise it
# to be stricter, or swap in a trained classifier, to recalibrate.
#
# Calibrated against 60 Liga MX 2025-26 matches (925 on-target shots, 18.9 %
# conversion): exponent 4.0 makes Σ xGOT ≈ goals scored (unbiased aggregate)
# and minimises Brier score.  High-placement shots calibrate almost perfectly
# (predicted 0.95 → observed 0.95); the mid-range is noisier because ~40 % of
# shots carry a placeholder height and are scored on width alone — a documented
# limitation of event-only xGOT without keeper tracking.
PLACEMENT_EXPONENT = 4.0

XGOT_FLOOR, XGOT_CEILING = 0.01, 0.98

XGOT_DISCLAIMER = (
    "xGOT is an event-data model based on shot placement only — it does not "
    "account for goalkeeper position (no tracking data)."
)


# ── Placement → save-difficulty ─────────────────────────────────────────────

def goalmouth_placement_quality(gy: float, gz: float) -> float:
    """Map a goal-mouth landing point to placement quality in [0, 1].

    0.0 → dead-centre, keeper-height (easiest save).
    1.0 → into a top corner (effectively unsaveable).

    Horizontal and vertical placement are each normalised 0→1 (centre→post,
    ground→crossbar) and combined as a Euclidean reach toward the top corners.
    Bottom corners and high-central shots land in between, which matches how
    save probability actually behaves.

    When height is the feed's placeholder (``GOALMOUTH_Z_PLACEHOLDER``) we fall
    back to horizontal placement only — we know the width but not the height.
    """
    horiz = min(abs(gy - GOAL_CENTRE_Y) / GOAL_HALF_WIDTH_UNITS, 1.0)  # 0 centre → 1 post
    if abs(gz - GOALMOUTH_Z_PLACEHOLDER) <= _Z_PLACEHOLDER_TOL:
        return horiz
    vert = min(max(gz, 0.0) / GOALMOUTH_Z_CROSSBAR, 1.0)              # 0 ground → 1 bar
    return min(math.sqrt((horiz * horiz + vert * vert) / 2.0), 1.0)


def compute_xgot(xg: float, gy: float | None, gz: float | None) -> float | None:
    """xGOT for a single on-target shot.

    ``xGOT = xg + (CEILING − xg) · placement**EXPONENT`` — monotone in placement,
    anchored to the pre-shot xG so a centrally-placed shot keeps roughly its
    chance value and only well-placed shots are lifted toward a near-certain
    goal.  Returns ``None`` when goal-mouth coordinates are missing (off-target,
    blocked, or an incomplete feed) — those shots have no post-shot value.
    """
    if gy is None or gz is None or pd.isna(gy) or pd.isna(gz):
        return None
    placement = goalmouth_placement_quality(gy, gz)
    xg = float(xg)
    xgot = xg + (XGOT_CEILING - xg) * (placement ** PLACEMENT_EXPONENT)
    return max(XGOT_FLOOR, min(XGOT_CEILING, xgot))


# ── DataFrame helpers ───────────────────────────────────────────────────────

def add_xgot(shots: pd.DataFrame) -> pd.DataFrame:
    """Return ``shots`` with an ``xgot`` column (NaN for off-target shots).

    Expects the columns produced by ``extract_shots``: ``xg``, ``goalmouth_y``,
    ``goalmouth_z``, ``on_target``.
    """
    out = shots.copy()
    if out.empty:
        out["xgot"] = pd.Series(dtype=float)
        return out
    out["xgot"] = out.apply(
        lambda r: compute_xgot(r.get("xg", 0.0), r.get("goalmouth_y"), r.get("goalmouth_z"))
        if r.get("on_target") else None,
        axis=1,
    )
    return out


def player_finishing(shots: pd.DataFrame) -> pd.DataFrame:
    """Per-player finishing from on-target shots.

    ``finishing = Σ xGOT − Σ xG`` over the player's *on-target* shots — i.e.
    placement skill, isolated from chance quality.  Positive → the player beats
    keepers more than an average finisher would from those positions.
    """
    df = add_xgot(shots)
    ot = df[df["on_target"] & df["xgot"].notna()].copy()
    # Penalties have a fixed ~0.76 xG and trivial placement skill — excluding
    # them keeps "finishing" about open-play execution (industry convention).
    if "is_penalty" in ot.columns:
        ot = ot[~ot["is_penalty"].fillna(False)]
    if ot.empty:
        return pd.DataFrame(columns=[
            "player_id", "player_name", "shots_on_target", "goals",
            "xg", "xgot", "finishing", "finishing_per_shot",
        ])
    ot["goal"] = (ot["outcome"] == "Goal").astype(int)
    g = ot.groupby(["player_id", "player_name"], as_index=False).agg(
        shots_on_target=("xgot", "size"),
        goals=("goal", "sum"),
        xg=("xg", "sum"),
        xgot=("xgot", "sum"),
    )
    g["finishing"] = g["xgot"] - g["xg"]
    g["finishing_per_shot"] = g["finishing"] / g["shots_on_target"]
    return g.sort_values("finishing", ascending=False).reset_index(drop=True)


def keeper_shot_stopping(shots: pd.DataFrame, team_id: str) -> dict:
    """Goalkeeping value for the team *facing* the shots in ``shots``.

    Pass the full match/season shot frame and the **defending** team_id; this
    sums xGOT of on-target shots taken *against* that team and compares it to
    goals actually conceded.

        shot_stopping = Σ xGOT_faced − goals_conceded   (> 0 → above average)

    Returns a dict of aggregates (team-level; per-keeper attribution needs the
    keeper's player_id, which shot events don't carry — left for callers that
    join lineup data).
    """
    df = add_xgot(shots)
    faced = df[(df["team_id"] != team_id) & df["on_target"] & df["xgot"].notna()].copy()
    # Penalties are a separate skill (penalty-saving) — exclude from open-play
    # shot-stopping so a conceded penalty doesn't tank the keeper's number.
    if "is_penalty" in faced.columns:
        faced = faced[~faced["is_penalty"].fillna(False)]
    if faced.empty:
        return {"shots_faced": 0, "goals_conceded": 0, "psxg_faced": 0.0,
                "shot_stopping": 0.0}
    goals_conceded = int((faced["outcome"] == "Goal").sum())
    psxg = float(faced["xgot"].sum())
    return {
        "shots_faced": int(len(faced)),
        "goals_conceded": goals_conceded,
        "psxg_faced": round(psxg, 3),
        # positive = saved more than an average keeper would have
        "shot_stopping": round(psxg - goals_conceded, 3),
    }
