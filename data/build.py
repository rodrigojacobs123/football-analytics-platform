from __future__ import annotations
"""Headless build CLI for the derived data tiers (match index + silver events).

Runs the bronze→silver pipeline *outside* Streamlit, so the cache artifacts the
app reads can be (re)built on a schedule, in CI, or by hand — without launching
a server. This is the keystone the architecture reviews kept asking for: it
decouples *computing* the data from *serving* it.

Usage
-----
    python -m data.build                       # default league/season
    python -m data.build --league MLS --season 2024-2025
    python -m data.build --all-seasons --league Mexico_Liga_MX
    python -m data.build --max-files 5         # smoke test (not persisted)
    python -m data.build --force               # rebuild even if fresh

By default it builds only the default competition. Building every league is
opt-in (``--all-seasons`` is per-league; there is deliberately no "all leagues"
flag — globbing the entire 47 GB tree must be an explicit, considered choice,
per the project's data conventions).

Exit code is non-zero if any (league, season) target failed, so CI can gate on
it.
"""

import argparse
import sys
import time

from config import DEFAULT_LEAGUE, DEFAULT_SEASON
from data.paths import list_seasons


def _build_one(league: str, season: str, *, force: bool, max_files: int | None) -> dict:
    """Build both derived tiers for one (league, season). Returns a summary."""
    # Imported here (not at module top) so a smoke test of one tier can't be
    # blocked by an import-time failure in the other.
    from data.match_index import build_match_index
    from data.silver_events import build_silver_events

    t0 = time.perf_counter()
    idx = build_match_index(league, season, force=force)
    events = build_silver_events(league, season, force=force, max_files=max_files)
    elapsed = time.perf_counter() - t0

    return {
        "league": league,
        "season": season,
        "matches": int(len(idx)),
        "with_files": int((idx["file_name"] != "").sum()) if not idx.empty else 0,
        "events": int(len(events)),
        "players": int(events["player_id"].nunique()) if not events.empty else 0,
        "seconds": round(elapsed, 1),
        "persisted": max_files is None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m data.build",
        description="Build the match index + silver event tiers headlessly.",
    )
    p.add_argument("--league", default=DEFAULT_LEAGUE, help="League folder name.")
    p.add_argument("--season", default=DEFAULT_SEASON, help="Season, e.g. 2025-2026.")
    p.add_argument("--all-seasons", action="store_true",
                   help="Build every season found for --league.")
    p.add_argument("--force", action="store_true",
                   help="Rebuild even if the cache looks fresh.")
    p.add_argument("--max-files", type=int, default=None, metavar="N",
                   help="Cap matches scanned for silver (smoke test; not persisted).")
    args = p.parse_args(argv)

    if args.all_seasons:
        seasons = list_seasons(args.league)
        if not seasons:
            print(f"No seasons found for league {args.league!r}.", file=sys.stderr)
            return 1
        targets = [(args.league, s) for s in seasons]
    else:
        targets = [(args.league, args.season)]

    failures = 0
    for league, season in targets:
        try:
            r = _build_one(league, season, force=args.force, max_files=args.max_files)
            tag = "" if r["persisted"] else "  (smoke, not persisted)"
            print(
                f"✓ {r['league']}/{r['season']}: "
                f"{r['matches']} matches ({r['with_files']} with files), "
                f"{r['events']:,} events over {r['players']} players "
                f"in {r['seconds']}s{tag}"
            )
        except Exception as exc:  # one target's failure must not abort the rest
            failures += 1
            print(f"✗ {league}/{season}: {type(exc).__name__}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
