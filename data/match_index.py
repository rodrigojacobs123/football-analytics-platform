from __future__ import annotations
"""Durable, ID-keyed match index — replaces fuzzy string-based match resolution.

Why this exists
---------------
The old resolver (``loader._team_name_match`` / ``_short_team_name``) matched
matches by hardcoded Liga-MX name spellings and ``first_word[:3]`` heuristics.
It silently failed for MLS / USL / CONCACAF and re-globbed ``partidos/`` on
every call.

This module builds a single Parquet table per league/season — one row per
match, keyed by the canonical Opta ``match_id`` and carrying ``home_id`` /
``away_id`` — then resolves matches by an **exact ID join**, never by string
similarity. The Parquet is built once and rebuilt only when ``partidos/``
changes (see :func:`_is_stale`), so cold lookups stop re-parsing the 47 GB tree.

Build sources (later wins on conflict):
  1. ``jsons/matches.json``  — fast, season-wide, may lag the per-match files.
  2. ``partidos/*.json``     — authoritative; carries the on-disk file name.
"""

import json

import pandas as pd
import streamlit as st

from data.paths import jsons_dir, partidos_dir, match_index_parquet
from data.event_parser import parse_match_info


INDEX_COLUMNS = [
    "match_id", "date", "matchday", "stage_name", "match_status",
    "home_id", "away_id", "home_team", "away_team",
    "home_score", "away_score", "file_name",
]


# ── Row construction ─────────────────────────────────────────────────────────

def _row_from_info(info: dict, file_name: str) -> dict:
    """Project a ``parse_match_info`` dict onto the index schema."""
    return {
        "match_id":     info.get("match_id", ""),
        "date":         info.get("date", ""),
        "matchday":     int(info.get("matchday", 0) or 0),
        "stage_name":   info.get("stage_name", ""),
        "match_status": info.get("match_status", ""),
        "home_id":      info.get("home_id", ""),
        "away_id":      info.get("away_id", ""),
        "home_team":    info.get("home_team", ""),
        "away_team":    info.get("away_team", ""),
        "home_score":   info.get("home_score"),
        "away_score":   info.get("away_score"),
        "file_name":    file_name,
    }


def _scan_matches(league: str, season: str) -> pd.DataFrame:
    """Parse matches.json + partidos/ into a flat, match_id-keyed DataFrame.

    This is the only place that does a full ``partidos/`` scan — and it runs
    once per (league, season, data-change), not per lookup.
    """
    rows: dict[str, dict] = {}

    # Pass 1: matches.json (season-wide, may lag the per-match files)
    mpath = jsons_dir(league, season) / "matches.json"
    if mpath.exists():
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
            matches = data.get("match", data) if isinstance(data, dict) else data
            for m in matches:
                info = parse_match_info(m)
                mid = info.get("match_id", "")
                if mid:
                    rows[mid] = _row_from_info(info, file_name="")
        except (json.JSONDecodeError, OSError, TypeError):
            pass  # a broken matches.json must not abort the index build

    # Pass 2: partidos/*.json (authoritative — overrides matches.json entries)
    pdir = partidos_dir(league, season)
    if pdir.exists():
        for f in sorted(pdir.glob("*.json")):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # skip a single corrupt file, keep building
            info = parse_match_info(raw)
            mid = info.get("match_id", "")
            if not mid:
                continue
            rows[mid] = _row_from_info(info, file_name=f.name)

    return pd.DataFrame(list(rows.values()), columns=INDEX_COLUMNS)


# ── Freshness policy ─────────────────────────────────────────────────────────

def _partidos_signature(league: str, season: str) -> tuple[int, float]:
    """Cheap fingerprint of ``partidos/``: ``(file_count, newest_mtime)``.

    One directory listing, no file reads — this is what makes the staleness
    check affordable on every lookup.
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return (0, 0.0)
    mtimes = [f.stat().st_mtime for f in pdir.iterdir() if f.suffix == ".json"]
    if not mtimes:
        return (0, 0.0)
    return (len(mtimes), max(mtimes))


def _is_stale(cached_sig: tuple[int, float], current_sig: tuple[int, float]) -> bool:
    """Decide whether the cached index must be rebuilt.

    This is the freshness POLICY KNOB — it trades data freshness against
    rebuild cost. Inputs are ``(file_count, newest_mtime)`` tuples from
    :func:`_partidos_signature`.

    Default policy: rebuild if the number of match files changed OR any file is
    newer than when the index was last built. That catches the two ways Opta
    data actually moves — new match drops (count rises) and corrections to
    existing files (mtime rises) — while costing only one directory stat.

    Trade-offs if you want to tune this:
      * Looser (e.g. count-only): misses in-place file corrections.
      * Stricter (e.g. per-file content hash): catches a delete+add that keeps
        the same count and an older mtime, but re-reads every file — which
        defeats the point of caching.
    """
    cached_count, cached_mtime = cached_sig
    current_count, current_mtime = current_sig
    return current_count != cached_count or current_mtime > cached_mtime


# ── Build / load ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _read_index_cached(parquet_path: str, signature: tuple) -> pd.DataFrame:
    """In-process cache of the Parquet read, keyed by file path + data signature.

    The ``signature`` in the key means a data change (new/edited match files)
    invalidates this automatically — no manual cache clearing needed.
    """
    return pd.read_parquet(parquet_path)


def build_match_index(league: str, season: str, force: bool = False) -> pd.DataFrame:
    """Return the match index DataFrame, (re)building the Parquet only if stale.

    Args:
        league: League folder name (e.g. "Mexico_Liga_MX").
        season: Season string (e.g. "2025-2026").
        force: Rebuild from source even if the cache looks fresh.
    """
    out = match_index_parquet(league, season)
    meta = out.with_suffix(".meta.json")
    current_sig = _partidos_signature(league, season)

    # Fast path: cache exists and is fresh → read Parquet (cached in-process).
    if not force and out.exists() and meta.exists():
        try:
            cached_sig = tuple(json.loads(meta.read_text()))
            if not _is_stale(cached_sig, current_sig):
                return _read_index_cached(str(out), current_sig)
        except (json.JSONDecodeError, OSError, ValueError):
            pass  # any cache-read problem → fall through and rebuild

    # Slow path: scan source, write Parquet + signature sidecar.
    df = _scan_matches(league, season)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    meta.write_text(json.dumps(list(current_sig)))
    return _read_index_cached(str(out), current_sig)


# ── Resolution (exact ID join, the whole point) ──────────────────────────────

def get_match_id(
    league: str,
    season: str,
    home_id: str,
    away_id: str,
    *,
    date=None,
    matchday=None,
) -> str:
    """Resolve a canonical ``match_id`` from team IDs — no fuzzy matching.

    A home/away pairing can recur within a season (Apertura + Clausura, league
    + cup), so when the ID match is ambiguous we narrow by ``date`` then
    ``matchday``, and finally prefer a match that has a file on disk.

    Returns "" when no match is found.
    """
    if not home_id or not away_id:
        return ""
    idx = build_match_index(league, season)
    if idx.empty:
        return ""

    cand = idx[(idx["home_id"] == home_id) & (idx["away_id"] == away_id)]
    if cand.empty:
        return ""

    if len(cand) > 1 and date is not None:
        day = str(date)[:10]  # normalise Timestamp or "2025-08-10Z" → "2025-08-10"
        narrowed = cand[cand["date"].astype(str).str[:10] == day]
        if not narrowed.empty:
            cand = narrowed

    if len(cand) > 1 and matchday is not None:
        try:
            narrowed = cand[cand["matchday"] == int(matchday)]
            if not narrowed.empty:
                cand = narrowed
        except (TypeError, ValueError):
            pass

    # Prefer a row backed by an actual partidos file (usable for match analysis).
    with_file = cand[cand["file_name"].astype(str) != ""]
    if not with_file.empty:
        cand = with_file

    return str(cand.iloc[0]["match_id"])


if __name__ == "__main__":
    # Warm the index for the default competition without launching Streamlit.
    from config import DEFAULT_LEAGUE, DEFAULT_SEASON

    df = build_match_index(DEFAULT_LEAGUE, DEFAULT_SEASON, force=True)
    print(f"Built match index: {len(df)} matches "
          f"({(df['file_name'] != '').sum()} with on-disk files) "
          f"→ {match_index_parquet(DEFAULT_LEAGUE, DEFAULT_SEASON)}")
