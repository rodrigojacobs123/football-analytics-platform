from __future__ import annotations
"""Silver event layer — a flattened, columnar Parquet table of Opta events.

Why this exists
---------------
The heaviest read path in the app is ``loader.load_player_events_season``: to
build one player's card it ``json.loads`` every match file in ``partidos/`` (698
MB / 334 files for a single Liga-MX season) and filters in Python — on *every*
distinct player query. Three architect cycles flagged this as the platform's
top storage risk: nested JSON parsed on the request hot path.

This module materialises the "silver" tier of a medallion layout. It mirrors
the proven, signature-gated pattern of :mod:`data.match_index` exactly:

  * **bronze** = the raw Opta JSON under ``partidos/`` (never mutated).
  * **silver** = this Parquet: one typed row per event, all matches in a
    season, written once and rebuilt only when ``partidos/`` changes.

Once built, ``load_player_events_season`` reads the columnar file with a
``player_id`` predicate instead of re-parsing 698 MB — turning an O(season)
JSON scan per player into a single columnar read.

Two design decisions carried from the architecture reviews:

  * **Provider-neutral ``action`` column** (the UIED idea). Each row carries a
    semantic ``action`` ('shot','pass','tackle',...) derived from the raw Opta
    ``type_id`` at build time, with ``type_id`` retained for lineage. A future
    Wyscout/StatsBomb feed maps into the same vocabulary instead of forking
    every ``processing/`` module on provider.
  * **Known gotchas codified into the schema, not into every consumer.**
    ``goalmouth_z`` is materialised NULL when the raw Opta value is the 19
    "height-not-recorded" sentinel, and ``is_penalty`` is computed once from
    qualifier 9 (not 22). A new analytic physically cannot re-introduce those
    bugs because the bad sentinel never reaches it.

The table is a rebuildable cache: if a row is ever wrong, delete the Parquet
and rebuild — the exact contract :mod:`data.match_index` already honours.
"""

import json

import pandas as pd
import streamlit as st

from config import SHOT_TYPE_IDS
from data.paths import partidos_dir, silver_events_parquet
# Reuse the match-index freshness policy so silver and the match index stay in
# lockstep on what "the data changed" means (one directory stat, no file reads).
from data.match_index import _partidos_signature, _is_stale


# Bump when the row schema or a derivation below changes, so a stale Parquet
# built under an older definition is detected and rebuilt. Stored in the meta
# sidecar alongside the partidos signature.
SILVER_SCHEMA_VERSION = "opta_v1.1"

# Opta z value that means "shot height not recorded" — must become NULL, never a
# real height. (~40% of on-target shots carry it; see project memory.)
_GOALMOUTH_Z_NOT_RECORDED = 19.0

# Provider-neutral action vocabulary, derived from the raw Opta typeId. Extend
# here, not in consumers — this is the single mapping a second feed would target.
_ACTION_BY_TYPE_ID: dict[int, str] = {
    1: "pass", 2: "offside_pass", 3: "take_on", 4: "foul", 6: "corner",
    7: "tackle", 8: "interception", 9: "turnover", 10: "save", 12: "clearance",
    13: "shot", 14: "shot", 15: "shot", 16: "shot", 17: "card",
    18: "sub_off", 19: "sub_on", 44: "aerial", 49: "recovery", 50: "dispossessed",
    61: "ball_touch", 74: "blocked_pass",
}

SILVER_COLUMNS = [
    "match_id", "team_id", "player_id", "period", "minute", "second",
    "type_id", "action", "x", "y", "end_x", "end_y", "outcome",
    "xg", "is_penalty", "is_header", "zone", "pass_len", "angle_deg",
    "goalmouth_z",
]

# Legacy column shape that ``load_player_events_season`` has always returned, so
# the silver-backed read is a drop-in. (period→periodId, minute→timeMin,
# type_id→typeId.)
_LEGACY_RENAME = {"type_id": "typeId", "period": "periodId", "minute": "timeMin"}
_LEGACY_COLUMNS = [
    "typeId", "x", "y", "end_x", "end_y", "outcome", "periodId", "timeMin",
    "xg", "is_penalty", "is_header", "zone", "pass_len", "angle_deg",
]


# ── Row construction ─────────────────────────────────────────────────────────

def _action_for(type_id: int) -> str:
    """Map a raw Opta typeId to the provider-neutral action vocabulary."""
    return _ACTION_BY_TYPE_ID.get(type_id, "other")


def _float_or(value, default):
    """Coerce a (possibly string) Opta qualifier value to float, else default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_from_event(e: dict, match_id: str) -> dict | None:
    """Flatten one raw Opta event into a typed silver row (or None to skip).

    Replicates ``loader.load_player_events_season``'s field derivations exactly
    so the silver-backed read is byte-for-byte compatible, then adds the
    provider-neutral ``action`` and the gotcha-guarded ``goalmouth_z``.
    """
    pid = e.get("playerId")
    if not pid:
        return None  # silver is keyed for player queries; skip team-only events
    tid = e.get("typeId", 0)
    quals = {q.get("qualifierId"): q.get("value", "1")
             for q in e.get("qualifier", [])}

    x = _float_or(e.get("x", 0), 0.0)
    y = _float_or(e.get("y", 0), 0.0)

    # goalmouth height: NULL out the "not recorded" sentinel at the storage edge
    raw_z = quals.get(103)
    gz = _float_or(raw_z, None) if raw_z is not None else None
    if gz is not None and gz == _GOALMOUTH_Z_NOT_RECORDED:
        gz = None

    return {
        "match_id":   match_id,
        "team_id":    e.get("contestantId", ""),
        "player_id":  pid,
        "period":     int(e.get("periodId", 1) or 1),
        "minute":     int(e.get("timeMin", 0) or 0),
        "second":     int(e.get("timeSec", 0) or 0),
        "type_id":    tid,
        "action":     _action_for(tid),
        "x":          x,
        "y":          y,
        "end_x":      _float_or(quals.get(140), x),
        "end_y":      _float_or(quals.get(141), y),
        "outcome":    int(e.get("outcome", 0) or 0),
        "xg":         (_float_or(quals[395], None) / 100
                       if 395 in quals and _float_or(quals[395], None) is not None
                       else None),
        "is_penalty": 9 in quals,
        "is_header":  15 in quals,
        "zone":       quals.get(56, ""),
        "pass_len":   _float_or(quals.get(140, 0), 0.0) if tid == 1 else None,
        "angle_deg":  _float_or(quals.get(213), None) if 213 in quals else None,
        "goalmouth_z": gz,
    }


def _scan_events(league: str, season: str, max_files: int | None = None) -> pd.DataFrame:
    """Parse every ``partidos/`` file into a flat, player-keyed event table.

    The only full ``partidos/`` event scan in the system — it runs once per
    (league, season, data-change), not per player lookup. A single corrupt file
    or event is skipped, never aborting the build.
    """
    p_dir = partidos_dir(league, season)
    if not p_dir.exists():
        return pd.DataFrame(columns=SILVER_COLUMNS)

    files = sorted(p_dir.glob("*.json"))
    if max_files is not None:
        files = files[:max_files]

    rows: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # skip a single corrupt file, keep building
        match_id = data.get("matchInfo", {}).get("id", "") or f.stem
        for e in data.get("liveData", {}).get("event", []):
            try:
                row = _row_from_event(e, match_id)
            except Exception:
                continue  # one malformed event must not abort the season build
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame(columns=SILVER_COLUMNS)
    return pd.DataFrame(rows, columns=SILVER_COLUMNS)


# ── Build / load ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _read_silver_cached(parquet_path: str, signature: tuple) -> pd.DataFrame:
    """In-process cache of the Parquet read, keyed by path + data signature.

    The ``signature`` in the key means a data change (new/edited match files)
    invalidates this automatically — no manual cache clearing needed.
    """
    return pd.read_parquet(parquet_path)


def build_silver_events(
    league: str,
    season: str,
    *,
    force: bool = False,
    max_files: int | None = None,
) -> pd.DataFrame:
    """Return the silver event table, (re)building the Parquet only if stale.

    Staleness is decided by the same ``(file_count, newest_mtime)`` signature
    the match index uses, plus the :data:`SILVER_SCHEMA_VERSION` — so changing a
    derivation here also forces a rebuild.

    Args:
        league: League folder name (e.g. "Mexico_Liga_MX").
        season: Season string (e.g. "2025-2026").
        force: Rebuild from source even if the cache looks fresh.
        max_files: Cap matches scanned (smoke tests / partial builds). A capped
            build is never cached to Parquet — it would masquerade as complete.
    """
    out = silver_events_parquet(league, season)
    meta = out.with_suffix(".meta.json")
    current_sig = list(_partidos_signature(league, season))

    # Fast path: cache exists, signature fresh, schema version matches.
    if not force and max_files is None and out.exists() and meta.exists():
        try:
            cached = json.loads(meta.read_text())
            cached_sig = tuple(cached.get("signature", []))
            same_schema = cached.get("schema_version") == SILVER_SCHEMA_VERSION
            if same_schema and not _is_stale(cached_sig, tuple(current_sig)):
                return _read_silver_cached(str(out), tuple(current_sig))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass  # any cache-read problem → fall through and rebuild

    df = _scan_events(league, season, max_files=max_files)

    # A capped build is partial — return it but never persist it as the cache.
    if max_files is not None:
        return df

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    meta.write_text(json.dumps(
        {"signature": current_sig, "schema_version": SILVER_SCHEMA_VERSION}))
    return _read_silver_cached(str(out), tuple(current_sig))


# ── The access path silver exists to serve ───────────────────────────────────

def player_events(
    league: str,
    season: str,
    player_id: str,
    type_ids: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """All events for one player in a season, read from silver, legacy-shaped.

    Returns exactly the columns ``loader.load_player_events_season`` has always
    returned (``typeId, x, y, end_x, end_y, outcome, periodId, timeMin, xg,
    is_penalty, is_header, zone, pass_len, angle_deg``) so it is a drop-in for
    that JSON-scanning implementation. Raises if the silver table can't be built
    or read, so the caller can fall back to the JSON path.
    """
    silver = build_silver_events(league, season)
    if silver.empty:
        return pd.DataFrame(columns=_LEGACY_COLUMNS)

    df = silver[silver["player_id"] == player_id]
    if type_ids:
        df = df[df["type_id"].isin(type_ids)]
    if df.empty:
        return pd.DataFrame(columns=_LEGACY_COLUMNS)

    return df.rename(columns=_LEGACY_RENAME)[_LEGACY_COLUMNS].reset_index(drop=True)


if __name__ == "__main__":
    # Build silver for the default competition without launching Streamlit.
    from config import DEFAULT_LEAGUE, DEFAULT_SEASON

    df = build_silver_events(DEFAULT_LEAGUE, DEFAULT_SEASON, force=True)
    print(f"Built silver events: {len(df):,} rows, "
          f"{df['match_id'].nunique()} matches, "
          f"{df['player_id'].nunique()} players "
          f"→ {silver_events_parquet(DEFAULT_LEAGUE, DEFAULT_SEASON)}")
