# DATA ARCHITECT REPORT

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-21 (09:10 run)
**Author:** Principal Data Architect — automated 3-day improvement cycle
**Scope:** Architecture review of a single-process Streamlit app reading ~47 GB of flat Opta JSON (~31,900 files) across 21+ competition folders (Liga MX, MLS, USL, CONCACAF, Canadian PL, plus youth/qualifier comps).

> **Context vs. prior run.** The previous architect report (`data_architect_report_2026-06-21.md`) flagged two top risks: full-tree `partidos/*.json` globbing and fuzzy string-based match resolution. **Both are now partially mitigated** — `data/match_index.py` introduces a durable, `match_id`-keyed Parquet index with a `(file_count, newest_mtime)` staleness fingerprint, replacing fuzzy resolution and confining the full scan to one rebuild path. This report credits that progress and re-bases the recommendations on the *current* tree, then pushes further: from "make storage survive growth" to "design the columnar query layer and feature store a Premier League department would adopt."

---

## 0. Executive Summary

The platform remains a **well-layered analytical monolith** — a clean `data → processing → viz → components → pages` separation sitting on a raw-file data lake. That layering is still the single biggest asset and the seam that makes every evolution below non-destructive.

The architectural center of gravity has shifted. With `match_index.py` in place, *match discovery* is no longer the bottleneck — **per-event analytics over `partidos/` is.** Functions like `load_player_events_season()` (`data/loader.py:265`) still scan and `json.loads` every match file in a season to extract one player's events. That is an O(matches × events) full-lake parse executed inside a request, cached only in volatile process memory (`@st.cache_data`). The thesis-grade next step is to **materialize a columnar event layer (Parquet, partitioned by league/season) and query it with DuckDB**, so player/team/season slices become predicate-pushdown scans instead of full-tree JSON parses. The `processing/` layer is pure pandas with zero Streamlit coupling, so this swap happens *underneath* the analytics with no rewrite.

Framed as a club would: the current system is a strong analyst's workbench. The next version is a **governed feature platform** — a bronze/silver/gold lakehouse feeding both the Streamlit UI and (eventually) an API, with the Opta semantics in `config.py` promoted to a versioned schema contract.

---

## 1. Current Architecture Strengths

What the layered Streamlit approach gets right:

1. **Enforced layer separation with one-directional dependency.** `pages/` never parse JSON; they call `data.loader` → `data.paths` (path-building, no I/O) → analytics in `processing/` that take DataFrames in and return DataFrames/dicts out with **zero Streamlit calls**. This is the discipline that lets the storage engine be swapped without touching analytics — rare in a research codebase.

2. **The match index is now a real persistence tier.** `match_index.py` is the architectural highlight since the last review: a Parquet artifact, ID-keyed, rebuilt only when a cheap `partidos/` signature changes, with an in-process cache keyed by `(path, signature)` so staleness invalidates automatically. This is exactly the bronze-layer pattern (raw → indexed table) that lakehouse designs prescribe — built by hand, correctly, for the one access path that needed it most.

3. **Centralized domain constants as a schema contract in waiting.** Opta `typeId`/qualifier semantics (shots = {13,14,15,16}, xG = qual 395, formation = qual 130, penalty = qual 9 *not* 22) live in `config.py` with comments documenting real past bugs. Providers like StatsBomb treat their event spec *as the product*; this project already treats its spec as a first-class module.

4. **Caching at the I/O seam, not scattered.** Every loader is `@st.cache_data(ttl=3600)`. Cache policy is changeable in one layer — the precondition for making it durable later (§5).

5. **Explicit navigation over magic discovery.** `app.py` uses `st.navigation` with a hand-curated `st.Page` list — the current Streamlit-documented best practice — so numeric file prefixes are sort hints, not routing, and dropping a file in `pages/` does not silently ship it. Critical for a platform that gates pages by competition (`AME_LEAGUES`). The dynamic-page idiom (append pages to the `st.navigation` list based on a check) is the same mechanism you'd use for role-based access later.

6. **Entity-by-ID discipline.** Club América is referenced by `AME_TEAM_ID`, never by name — the correct modeling instinct and the foundation of any future dimensional schema. `AME_TEAM_FOLDER` is used only for filesystem paths.

7. **Minimum-sample guards as a product principle.** `MIN_APPEARANCES_FOR_RATING`, `MIN_MATCHES_FOR_PREDICTION` — early-season noise is acknowledged in the architecture. Professional recruitment tools live or die on this.

8. **Analytics breadth already matches a mid-tier provider.** 28 modules in `processing/` (xG/xGOT, xT, xDEF, Elo, Poisson, PPDA/pressure, sequences, formations, pass networks, play-style, archetypes, set pieces, corner defense). The intellectual product is dense; the gap is purely in *how* it's stored and served.

---

## 2. Critical Architectural Risks

What breaks at scale or with new requirements:

1. **Per-event season scans are the new bottleneck.** `load_player_events_season()` (`data/loader.py:265`) globs `partidos/*.json` and `json.loads` every file to extract one player. For a Liga MX season that is hundreds of multi-MB files parsed per call. The match *index* is solved; the match *events* are not. This is the dominant latency and memory risk and the clearest candidate for the columnar layer in §3/§5.
   *Severity: High.*

2. **Cache durability is volatile and per-process.** `@st.cache_data` lives in the Streamlit process. A restart, a redeploy, or a second worker means cold re-parses of 47 GB. There is no on-disk derived-data tier except the match index. As competitions and seasons grow, "first hit after deploy" becomes minutes.
   *Severity: High.*

3. **JSON is the query engine.** Every analytic re-derives flat frames from nested Opta JSON at request time via `event_parser.py`. The parse logic is correct and centralized, but it runs on the hot path. There is no silver layer (cleaned, typed, flattened events) persisted anywhere — so the same parse cost is paid on every cache miss, forever.
   *Severity: High.*

4. **No schema versioning or validation contract.** `config.py` encodes Opta semantics, but nothing *validates* incoming files against it. A feed change (a renamed qualifier, a new `typeId`, a coordinate-system shift) would surface as a silent wrong number deep in a page, not as a load-time failure. Professional platforms gate ingestion behind schema checks (StatsBomb ships JSON/XML/CSV against a published spec).
   *Severity: Medium-High.*

5. **Single-process concurrency ceiling.** One Streamlit process = one Python GIL serving all users. Fine for a thesis demo and a single analyst; a club analytics department with 5–10 concurrent users hitting `partidos/` scans will queue behind each other. There is no horizontal scaling story.
   *Severity: Medium (low today, high the moment it's multi-user).*

6. **Coupling of compute to presentation.** Because analytics only run inside the Streamlit request, there is no path to (a) scheduled pre-computation, (b) an API for a future React front end or club data team, or (c) batch backfills. The pure-pandas `processing/` layer *can* support all three — but nothing exercises it outside the app yet.
   *Severity: Medium.*

7. **Operational blind spots.** No structured logging, no load-time metrics, no data-freshness dashboard beyond `11_Data_Sources`. When a season's `matches.json` lags `partidos/` (a real case handled in `load_all_season_results`), there's no alert — only correct-by-construction reconciliation code. At club scale you need observability, not just correctness.
   *Severity: Low-Medium.*

---

## 3. Recommended Architectural Evolutions (Phased)

### Phase 1 — Quick wins (days, no new infra)

- **Persist a silver event layer to Parquet, partitioned by `league/season`.** Run `event_parser.py` once per match in a build step (mirror the `match_index.py` pattern: signature-gated rebuild). Store `events/<league>/<season>/<match_id>.parquet`. `load_player_events_season()` then reads columnar files with a `player_id` predicate instead of parsing JSON. Expected: season-scan latency drops from "parse hundreds of JSON files" to "scan a few hundred MB of typed columns." **Reuses the exact durability pattern already proven in `match_index.py`.**
- **Add `@st.cache_resource` for shared, read-only artifacts** (the match index DataFrame, name maps) so they survive across sessions in one process — distinct from per-session `@st.cache_data`.
- **Generalize the `match_index.py` signature trick into a tiny `derived/` cache helper** so any expensive aggregate (season tables, leaderboards) can be memoized to disk with automatic staleness. One module, reused everywhere.
- **Add a load-time schema assertion** in `event_parser.py`: assert the qualifier IDs in `config.py` actually appear in a sampled file; log a warning if a season's events lack expected qualifiers. Cheap insurance against silent feed drift (Risk #4).

### Phase 2 — Medium-term (a real query engine + ingestion)

- **Introduce DuckDB as the query layer over the Parquet lake.** DuckDB natively reads partitioned Parquet with Hive partitioning and `union_by_name`, supports predicate pushdown and partition pruning, and runs in-process — *no new service, no cluster*. `data/loader.py` becomes a thin SQL-emitting layer; `processing/` still receives DataFrames. This is the highest-leverage single change: it turns "parse 47 GB of JSON" into "SQL over columnar storage" while preserving the entire layered design.
- **Formalize a medallion (bronze → silver → gold) layout.** Bronze = raw Opta JSON (untouched, the source of truth). Silver = typed, flattened Parquet events + dimension tables (teams, players, matches, managers) keyed by ID. Gold = pre-aggregated marts (season player ratings, team xG tables, Elo histories) refreshed on a schedule. Pages read gold; explorers read silver; nobody reads bronze on the hot path.
- **Promote `config.py` Opta semantics to a versioned schema module** (`schema/opta_v1.py`) with explicit `typeId`/qualifier enums and a validator. Tag each ingested season with the schema version it parsed under — so a future feed change is a new version, not a silent break.
- **Extract a headless build CLI** (`python -m data.build --league ... --season ...`) that runs the bronze→silver→gold refresh outside Streamlit. This decouples compute from presentation (Risk #6) and is the seedbed for scheduling and an API.

### Phase 3 — Long-term vision (the club-grade platform)

- **Serve gold marts through a thin API** (FastAPI) so the Streamlit UI, a future React front end, and the club's own data scientists (Python/R, the way StatsBomb/Wyscout expose data) all consume the same governed tables. Streamlit becomes *one* consumer, not *the* system.
- **Move to a scheduled/event-driven ingestion pipeline.** Today data lands as flat files. A club ingesting live Opta/Second Spectrum feeds needs an event-streaming path (Kafka/MSK + a stream processor like Flink) for live win-probability, momentum, and pressing-trigger detection — the pattern AWS documents for Bundesliga Match Facts (25 Hz positional + event data) and Hawk-Eye (480 msg/s). For this TFM, the realistic Phase-3 target is **incremental batch** (process new matches as they land) rather than true streaming — full streaming is the "if a PL club adopted this" north star, scoped explicitly so it isn't over-built.
- **Domain-oriented data products (lightweight data-mesh framing).** As the analytics surface grows, treat *recruitment*, *opposition analysis*, *medical/load*, and *match analysis* as domains, each owning its gold marts behind a clear contract. This is the data-mesh principle (domain ownership + data-as-a-product) applied at a sensible scale — not literal microservices, which this project does not need.
- **Multi-tenant / role-aware access** using the dynamic-`st.navigation` mechanism already in place (append pages per role), backed by API-level authorization once the API exists.

---

## 4. New Page / Feature Opportunities

Based on what professional club platforms (Hudl StatsBomb + Wyscout, SAP Sports One, Second Spectrum) offer that this one doesn't yet:

1. **Recruitment / Player Comparison workspace.** StatsBomb's core club workflow is *similarity search and shortlisting*. The platform already has `archetypes.py`, `player_ratings.py`, and `player_profile.py` — wire them into a "find players like X across all 21 competitions" page with radar overlays and percentile bars. The cross-league scan this needs is *exactly* the use case the Parquet/DuckDB layer (§3) unlocks.
2. **Set-Piece Intelligence page.** `set_pieces.py` and `corner_defense.py` exist but only corner *defense* is surfaced (`13_Corner_Defense`). Clubs treat attacking set pieces as a top marginal-gains area — add routines, delivery zones, and first-contact maps.
3. **Opposition Report generator.** A one-click "next opponent" dossier composing existing modules (formations, pressing/PPDA from `pressure.py`, build-up from `goal_buildup.py`, set-piece tendencies) into an exportable PDF — the deliverable analysts actually hand to coaches.
4. **Physical / Load layer.** Every club platform integrates GPS/biometric load. The synthetic `injuries_synthetic.py` is a placeholder; a "Workload & Availability" page (even synthetic) demonstrates the medical domain and is a natural data-product boundary for §3 Phase 3.
5. **Live Match Momentum (read-only demo).** A post-match "momentum" timeline (xG flow + possession + pressing intensity) showcases the streaming north-star from a batch source, using `game_phases.py` + `sequences.py`.
6. **Cross-competition Scouting Leaderboard.** A governed gold mart of season player ratings across all leagues — impossible to serve responsively today (full-lake scan), trivial once silver/gold exist.

---

## 5. Data Model Improvement — Evolving the Flat JSON

The flat-JSON store is the right *bronze* layer (cheap, immutable, the source of truth) but the wrong *query* layer. Evolution path, preserving every existing access pattern:

**Today**
```
testeo_ligas_norteamerica/<League>/<Season>/
├── jsons/matches.json, standings.json, squads.json …
└── partidos/<match_id>.json        # parsed at request time, every time
```

**Target — medallion layout (additive; bronze stays untouched)**
```
<League>/<Season>/
├── partidos/*.json                      # BRONZE: raw Opta, source of truth
├── _index/match_index.parquet           # already exists (match_index.py)
├── silver/
│   ├── events.parquet (partitioned)     # flattened, typed events — schema_version tagged
│   ├── dim_players.parquet              # ID-keyed player dimension
│   ├── dim_teams.parquet                # ID-keyed team dimension
│   └── dim_matches.parquet              # match dimension + result reconciliation
└── gold/
    ├── player_season_ratings.parquet    # pre-aggregated marts the pages read
    ├── team_xg_tables.parquet
    └── elo_history.parquet
```

**Schema principles**
- **Star schema over the flat dump.** A central `fact_events` (one row per Opta event, columns for `match_id`, `team_id`, `player_id`, `typeId`, `x`, `y`, `minute`, plus exploded common qualifiers like `xg`, `formation`, `outcome`) joined to `dim_players` / `dim_teams` / `dim_matches`. Everything keyed by Opta IDs — the entity-by-ID discipline already in `config.py` generalizes directly.
- **Explode the hot qualifiers into typed columns; keep the rest as a struct.** xG (395), formation (130), penalty (9), goalmouth coords — promote to first-class columns so analytics stop walking the qualifier list. Retain the full qualifier array as a nested column for the long tail. This is the single biggest correctness *and* speed win, and it codifies the Opta gotchas (penalty = 9 not 22; goalmouth z=19 = "not recorded", per the project's own memory) into the schema rather than into every consumer.
- **Tag every silver/gold artifact with `schema_version` + source `partidos/` signature.** Reuses the `match_index.py` staleness model; makes feed drift a versioned event, not a silent bug.
- **Partition by `league` then `season`.** Matches the directory truth, gives DuckDB partition pruning for free, and keeps the "never glob all leagues without reason" guardrail from CLAUDE.md enforceable at the storage layer (a query *names* its partition).

**Migration is non-destructive.** Bronze JSON is never deleted. Silver/gold are derived, rebuildable artifacts produced by the headless build CLI (§3 Phase 2). If a derived file is ever wrong, delete it and rebuild from bronze — the same contract `match_index.py` already honors.

---

## 6. Closing — What the Next Version Looks Like

If a Premier League analytics department adopted this codebase, they would keep the layered design and the `config.py` schema discipline untouched — those are already professional-grade. They would:

1. Persist a **silver Parquet event layer** so analytics stop parsing JSON on the hot path (Phase 1).
2. Drop **DuckDB** in as the query engine — no new service, full SQL over columnar storage, `processing/` unchanged (Phase 2).
3. Formalize **medallion bronze/silver/gold** with a versioned Opta schema contract (Phase 2).
4. Extract a **headless build CLI**, then a **gold-mart API**, so Streamlit is one consumer among several (Phase 2→3).
5. Reserve **streaming** (Kafka/Flink) as the explicit north star for live data, scoped as incremental-batch for the TFM (Phase 3).

The throughline: the project's layering already earns the right to evolve storage without rewriting analytics. The single most valuable next move is the **silver Parquet layer + DuckDB** — it directly retires the three High-severity risks (§2.1–2.3) and unlocks the cross-competition recruitment features (§4) that distinguish a club platform from an analyst's notebook.

---

## Sources

- [Football Performance Analytics — b-eye](https://b-eye.com/blog/how-big-data-analytics-improve-football-performance/)
- [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [Data analytics in the football industry (survey) — PubMed](https://pubmed.ncbi.nlm.nih.gov/38745403/)
- [Define multipage apps with st.Page and st.navigation — Streamlit Docs](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [st.navigation — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)
- [DuckDB Medallion Architecture: A Complete Local Lakehouse Guide — Medium](https://medium.com/@datatomas/duckdb-medallion-architecture-a-complete-local-lakehouse-guide-0f1944b6bcdf)
- [What is a Data Lakehouse? — MotherDuck](https://motherduck.com/learn/what-is-a-data-lakehouse/)
- [Introducing DuckLake — endjin](https://endjin.com/blog/introducing-ducklake-lakehouse-architecture-reimagined-modern-era)
- [Hawk-Eye Innovations Powers Real-Time Sports Data with Flink and Amazon MSK — AWS](https://aws.amazon.com/blogs/media/hawk-eye-innovations-powers-real-time-sports-data-with-flink-and-amazon-msk/)
- [Bundesliga Match Fact: Match Momentum — AWS](https://aws.amazon.com/blogs/media/bundesliga-match-fact-match-momentum-revealing-the-games-invisible-pulse/)
- [How to Architect a Scalable, Low-Latency Sports Data Pipeline — Data Sports Group / Medium](https://medium.com/@marketing_25315/how-to-architect-a-scalable-low-latency-sports-data-pipeline-for-real-time-apps-385b18246fd8)
- [Hudl StatsBomb — The World's Most Advanced Football Data](https://www.hudl.com/en_gb/products/statsbomb)
- [Introducing the New Hudl Statsbomb with Wyscout Video](https://www.hudl.com/blog/hudl-statsbomb-video-wyscout)
- [AI-Powered Football Match Analysis: SAP Sports One on AWS — AWS](https://aws.amazon.com/blogs/awsforsap/ai-powered-football-match-analysis-sap-sports-one-on-aws/)
- [The 4 principles of data mesh — dbt Labs](https://www.getdbt.com/blog/the-four-principles-of-data-mesh)
- [Data Mesh Architecture](https://www.datamesh-architecture.com/)
