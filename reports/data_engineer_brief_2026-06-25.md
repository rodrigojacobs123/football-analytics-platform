# Data Engineer Brief — Club América Analytics Platform

**Date:** 2026-06-25
**From:** Principal Data Architect (automated review cycle)
**To:** Data Engineer
**Branch with work-in-progress:** `architect/storage-foundation`

You are picking up a single-process Streamlit football-analytics platform that reads flat Opta
JSON for Club América across 22 North-American / CONCACAF competitions. Layers are
`data/ → processing/ → viz/ → components/ → pages/` (see `CLAUDE.md` for the full contract — read it
first; it is authoritative and overrides assumptions). There is no database and no API: analytics
are pure-pandas functions that run inside a Streamlit request.

Three architecture-review cycles concluded the analytics engine is strong (37 `processing/` modules)
but the **storage engine is the bottleneck** — nested JSON parsed on the request hot path. A first
slice of the fix already landed on the branch above. Your job is to finish it and harden it.

---

## What is already done (on `architect/storage-foundation` — review these first)

1. **Silver Parquet event layer** — `data/silver_events.py`. Flattens all events for a league/season
   into one columnar Parquet under `CACHE_ROOT/silver_events/`, signature-gated like the existing
   `data/match_index.py`. Carries a provider-neutral `action` column + raw `type_id`, and guards the
   goalmouth `z=19` "not recorded" sentinel and `is_penalty` (qualifier 9) at the storage edge.
2. **Headless build CLI** — `data/build.py` (`python -m data.build [--league --season --all-seasons --force --max-files N]`).
3. **Loader fast path** — `data/loader.py:load_player_events_season` now reads silver first, falls back
   to the JSON scan. Verified output-identical to the old scan; cold read 0.10s vs 6.2s, 698 MB → 5.9 MB.
4. **Governance** — 11 previously-untracked analytics modules committed.
5. **Bug fix** — `pages/14_Player_Intelligence.py` no longer blanks on non-América competitions.
6. **Branding** — removed the leftover Manchester United theme; the platform is Club América only.

Do **not** redo these. Build on them.

---

## Your tasks, in priority order

Each task lists the concrete change and its **acceptance criteria (AC)**. Respect the layer rules in
`CLAUDE.md`: pages never parse JSON, `processing/` never imports Streamlit, build paths via
`data/paths.py`, reference Club América by `AME_TEAM_ID` not name, honour the minimum-sample guards.

### P0 — Extend the silver layer to the other hot paths
Right now only `load_player_events_season` reads silver. The ~30 `processing/` modules that do
`raw.get("liveData", {}).get("event", [])` per match (grep for it — `xt.py`, `pressure.py`, `xdef.py`,
`gk_value.py`, `team_shape.py`, `wide_play.py`, `xg_chain.py`, `game_state.py`, `sequences.py`,
`manager_stats.py`, …) still parse JSON every call.
- Add a cached `load_events_for_match(league, season, match_id)` and/or a season-level silver reader to
  `data/loader.py` that serves from `data/silver_events.py`, and migrate the heaviest consumers to it.
- **AC:** at least the 5 heaviest modules read silver; a match-analysis page render does **zero** raw
  `json.loads` of `partidos/*` on a warm cache (verify by instrumenting/logging). Outputs unchanged
  (diff a Post-Match page before/after for one match).

### P1 — DuckDB query layer over the Parquet lake
Introduce DuckDB as the in-process query engine over the silver Parquet (no new service).
- Add `data/query.py` exposing a thin `con()` / `sql()` helper that reads the silver Parquet via
  DuckDB with Hive-style `league/season` partition pruning and predicate pushdown.
- Re-implement one cross-competition aggregate through it (e.g. "all shots for player X across all
  competitions") to prove the path.
- Add `duckdb>=1.0` to `requirements.txt`. **AC:** a cross-season query returns correct results and is
  faster than the per-file scan; `processing/` still receives DataFrames (DuckDB stays inside `data/`).

### P1 — Tests + CI on the build pipeline
There is **no test suite** today. The build CLI is the natural harness.
- Add `tests/` with pytest covering: silver row derivations (xg, is_penalty, goalmouth_z guard,
  action mapping), the freshness/staleness logic, and a golden-file check that silver output equals the
  legacy JSON scan for one fixture match.
- Wire `python -m data.build --max-files 3` + `pytest` into a CI workflow (GitHub Actions).
- **AC:** `pytest` green locally and in CI; CI fails if silver output drifts from the golden fixture.

### P2 — Medallion gold marts
Pre-aggregate the expensive season-wide rollups the pages recompute every load.
- Add a `gold/` tier (build step in `data/build.py`) materialising: season player ratings, team xG
  tables, Elo histories, and the GK-value / team-shape / xG-chain season marts. Pages read the mart.
- **AC:** Home / Scouting / Player-Intelligence read a gold mart instead of recomputing; first-paint
  latency measurably lower on a cold process.

### P2 — Versioned schema module
- Promote the Opta semantics in `config.py` + `event_parser.validate_event_schema` into
  `data/schema.py` (or `schema/opta_v1.py`) with an explicit `SCHEMA_VERSION`, and tag each ingested
  season with the version it parsed under (the silver `meta.json` already carries `schema_version` —
  extend that). **AC:** a feed-drift (missing qualifier) surfaces as a versioned, logged warning at
  build time, not a wrong number in a page.

### P3 — Code-health follow-ups
- `pages/14_Player_Intelligence.py` still uses `st.stop()` inside a `with tab:` block (now unreachable
  with data, but an anti-pattern — it halts every tab). Refactor Tab 2 to guard its body with a
  conditional instead of `st.stop()` so a future empty-data case can't blank sibling tabs.
- Consider whether the single-option "Club" selector in `components/sidebar.py` should stay now that
  there is only one theme.

---

## Constraints & definition of done
- Everything must remain **non-destructive**: bronze JSON under `testeo_ligas_norteamerica/` is the
  source of truth and is never written to; silver/gold live under `CACHE_ROOT` and are rebuildable.
- Never glob across all leagues without an explicit reason (the data tree is ~tens of GB).
- Each task ships behind its AC, with the app still running (`streamlit run app.py`) and the existing
  pages visually unchanged unless the task says otherwise.
- Open one PR per priority tier off `architect/storage-foundation`; keep `processing/` outputs
  byte-stable where a task claims "no behaviour change" (prove it with a before/after diff).
