# DATA ARCHITECT REPORT

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-21
**Author:** Principal Data Architect (automated 3-day improvement cycle)
**Scope:** Architecture review of a single-process Streamlit app reading ~47 GB of flat Opta JSON across 21+ competition folders (Liga MX, MLS, USL, CONCACAF, Canadian PL, plus youth/qualifier comps).

---

## 0. Executive Summary

The platform is a **well-layered analytical monolith**: a clean `data → processing → viz → components → pages` separation that most Streamlit projects never achieve, sitting on top of a raw-file data lake. That layering is the project's biggest asset and should be preserved through every evolution below.

The central architectural tension is this: **the presentation layer (Streamlit, in-process Python cache) and the storage layer (47 GB of flat JSON parsed with `json.load`) are now mismatched in scale.** The code is correct, but two patterns — full-tree globbing of `partidos/*.json` and fuzzy string-based match-ID resolution — will not survive growth in competitions, seasons, or concurrent users. The thesis-grade goal should be to **decouple storage from presentation by introducing a columnar query layer (Parquet + DuckDB)** without rewriting the analytics, and to **make caching durable**. Everything else is incremental.

This report frames recommendations as a club would: *what does the next version look like if a Premier League analytics department adopted it?*

---

## 1. Current Architecture Strengths

What the layered Streamlit approach gets right:

1. **Strict layer separation with enforced direction of dependency.** `pages/` never parse JSON directly — they call `data.loader`, which calls `data.paths`, which builds paths but does no I/O. `processing/` functions take DataFrames in and return DataFrames/dicts out with **zero Streamlit calls**. This is the discipline that makes the codebase testable and portable. It is also exactly the boundary you need to swap the storage engine underneath without touching analytics — a rare gift in a research codebase.

2. **Centralized domain constants.** Opta `typeId`/qualifier semantics (shots = {13,14,15,16}, xG = qual 395, formation = qual 130, penalty = qual 9) live in `config.py` with comments documenting real past bugs. This is institutional knowledge captured *in code* — the single most valuable defense against the "easy to get wrong" Opta conventions. Professional providers (StatsBomb, Opta) treat their spec as the product; this project treats its spec as a first-class module, which is correct.

3. **Caching at the right seam.** Every loader is wrapped in `@st.cache_data(ttl=3600)`. The cache boundary is the I/O boundary, not scattered through pages — so cache policy is changeable in one layer.

4. **Explicit navigation over magic discovery.** `app.py` uses `st.navigation` with a hand-curated page list rather than Streamlit's auto-discovery of `pages/`. This means the numeric file prefixes are sort hints, not routing, and dropping a file in `pages/` does **not** silently ship it. For a platform that gates pages by competition (`AME_LEAGUES`), explicit registration is the right call and aligns with current Streamlit best practice (`st.navigation` is the documented preferred method over the `pages/` directory).

5. **Entity-by-ID discipline.** Club América is referenced by `AME_TEAM_ID`, not name, because names vary across feeds. This is the correct modeling instinct and the foundation any future star/dimensional schema would build on.

6. **Minimum-sample guards as a product principle.** `MIN_APPEARANCES_FOR_RATING`, `MIN_MATCHES_FOR_PREDICTION` — early-season noise is acknowledged in the architecture, not bolted on. Professional recruitment tools live and die on this.

7. **Pure-pandas processing = trivially portable.** Because `processing/` has no framework coupling, every analytic (xG, Elo, Poisson, pass networks, play-style, archetypes, xT, xDef) could be lifted into a batch job, a notebook, or an API tomorrow with no rewrite.

---

## 2. Critical Architectural Risks

What breaks at scale or under new requirements. Ordered by severity.

### R1 — Full-tree JSON globbing on the hot path *(severity: critical)*
`load_player_events_season()` ([data/loader.py:264](../data/loader.py)) does `for f in sorted(p_dir.glob("*.json"))` and re-parses **every match file in the competition** to extract one player's events. `load_all_season_results()` ([data/loader.py:367](../data/loader.py)) similarly iterates all of `partidos/` on a cache miss. Against a 47 GB tree this is O(matches × events_per_match) disk + parse per cold call. Today it is survivable only because `@st.cache_data` warms the result. The moment the cache is cold (restart, deploy, eviction, a new player/season), the user waits tens of seconds to minutes, and concurrent users each pay it independently. **This is the defining scalability ceiling of the platform.**

### R2 — In-process, non-durable cache *(severity: high)*
`@st.cache_data(ttl=3600)` is per-process, in-memory, and lost on every restart. There is no shared cache across replicas and no warm state after deploy. A single analyst is fine; a club deployment with 2 replicas behind a load balancer doubles all compute and shares nothing. This is the difference between "a thesis demo" and "a service."

### R3 — Fuzzy match-ID resolution will not generalize *(severity: high)*
`_find_match_id_for_row` → `_team_name_match` → `_short_team_name` ([data/loader.py:500–595](../data/loader.py)) resolves matches by hardcoded Liga-MX name mappings (`"CF América" → "América"`) and `first_word[:3]` heuristics. This is brittle correctness debt: it silently mis-resolves or fails to resolve matches in MLS, USL, and CONCACAF where the name dictionary doesn't apply. **Identity should come from IDs in a join table, never from string similarity.**

### R4 — Whole-file reads, no projection or predicate pushdown *(severity: high)*
`_load_json` reads an entire file into memory and parses it fully, even when a page needs three columns of shots. JSON has no columnar projection — every shot-map query pays the cost of parsing passes, tackles, carries, and qualifiers it discards. This is the textbook case the industry solves with Parquet (columnar, compressed, predicate/projection pushdown). DuckDB-over-Parquet benchmarks show ~17× over pandas and the gap widens with size.

### R5 — No schema contract / no validation layer *(severity: medium)*
Opta feeds drift (new qualifiers, renamed stages, `matches.json` lagging `partidos/` — already worked around with a two-pass loader). There is no schema enforcement, no contract test, and no "bronze→silver" validation step. A malformed feed degrades silently (the `except: continue` in the glob loops swallows parse errors entirely — bad files become invisible, not loud).

### R6 — `processing/` growth without a registry *(severity: medium)*
24 processing modules and 11 pages, several added recently (`archetypes`, `corner_defense`, `tactical_positions`, `xdef`, `gap_analysis`). There's no manifest tying *metric → producing module → consuming page → required inputs*. As the metric catalog grows toward a club's expectations, "which page breaks if I change xG?" becomes unanswerable without grep.

### R7 — Single-process compute on the request thread *(severity: medium)*
All analytics run synchronously inside the Streamlit rerun. A heavy season-wide aggregation blocks the user's interaction. There is no batch/precompute tier — every expensive number is computed on demand, live, in the UI process.

### R8 — Multi-tenancy and access control are absent *(severity: low today, blocking for club use)*
No auth, no per-user state isolation beyond Streamlit session_state, no row-level scoping (e.g., scouts who may only see certain competitions). Fine for a TFM; a hard gate for any real club deployment.

---

## 3. Recommended Architectural Evolutions (Phased)

### Phase 1 — Quick wins (days, no infra, preserve the monolith)

- **P1.1 Kill silent failure.** Replace bare `except: continue` in the glob loops with structured logging (count + filename of bad files, surfaced on the Data Sources page). Invisible data loss is the worst kind.
- **P1.2 Build a match index once, resolve by ID.** Generate a single `match_index.parquet` per league/season (match_id, date, stage, home_id, away_id, scores, file_path) from `matches.json` + `partidos/` filenames **once**, and have `load_*` resolve via this table. Deletes R3's fuzzy matching outright and removes the per-call glob in `load_all_season_results` (R1 partial).
- **P1.3 Disk-backed cache for the expensive loaders.** Wrap `load_player_events_season` / season aggregations with a persistent cache (joblib `Memory`, or write results to `cache/*.parquet` keyed by inputs). Survives restarts; first analyst warms it for everyone (R2 partial).
- **P1.4 Add `st.cache_resource` for read-only singletons** (name maps, the match index) so they're shared, not recomputed per session.
- **P1.5 Processing manifest.** A small `processing/registry.py` dict: `metric → (module, inputs, pages)`. Cheap insurance against R6; also auto-documents the platform for the thesis.

### Phase 2 — Medium-term (the storage decoupling — highest ROI)

This is the centerpiece. **Introduce a Parquet "silver" layer and query it with DuckDB, behind the existing `data.loader` API so pages don't change.**

- **P2.1 ETL: JSON → Parquet (medallion pattern).**
  - *Bronze:* the raw `partidos/*.json` as-is (already have it).
  - *Silver:* one ETL pass (a script, then a scheduled job) flattens events into partitioned columnar tables — `events/`, `shots/`, `passes/`, `lineups/`, `match_index/` — partitioned by `league/season`. This is exactly StatsBomb's own conceptual split (competitions/matches/events as separate, ID-joined entities) made physical.
  - *Gold:* precomputed aggregates the UI reads directly (player-season event rollups, team xG-for/against, Elo history) — moves R7's live compute to batch.
- **P2.2 DuckDB as the query engine.** `data.loader` keeps the same function signatures but internally runs `SELECT ... FROM 'silver/shots/league=.../season=.../*.parquet' WHERE player_id = ?`. Projection + predicate pushdown means `load_player_events_season` reads **only that player's rows from only the columns needed** — turning R1's full-tree scan into a sub-second indexed-style query, with no Streamlit, no pandas-glob, no 47 GB re-parse. DuckDB is embedded (no server), which preserves the "no DB to operate" simplicity that makes this project pleasant.
- **P2.3 Schema contract + validation in the ETL.** Validate qualifier presence, coordinate ranges (0–100), stage-name normalization at the bronze→silver boundary using the `config.py` constants as the canonical spec. Feeds drift loudly, once, in the pipeline — not silently, repeatedly, in the UI.
- **P2.4 Incremental ETL.** Only reprocess match files newer than the last Parquet write (mtime or a manifest). Daily Opta drops become minutes, not a full rebuild.

> Net effect of Phase 2: the app stays a single Streamlit process with the same layers and the same page code, but the storage layer becomes a columnar lakehouse. Risks R1, R4, R5, R7 are structurally resolved, not patched.

### Phase 3 — Long-term vision (the "Premier League club" version)

- **P3.1 Split compute from presentation.** Promote `processing/` into a thin internal **analytics service / API** (FastAPI) that the Streamlit app *consumes*. Because `processing/` is already framework-free, this is a packaging change, not a rewrite. Enables caching, horizontal scale, scheduled precompute, and reuse by other clients (a video tool, a mobile scout app, R/Python notebooks).
- **P3.2 Domain-oriented data products (data-mesh thinking, right-sized).** Treat *Recruitment*, *Opposition Analysis*, *Medical/Availability*, *Match Performance* as data-product domains, each owning its gold tables with a documented contract. Don't adopt full data-mesh org overhead (overkill for one team) — adopt the *principle*: data as a product, with contracts and ownership, so domains evolve independently.
- **P3.3 Real-time ingestion path (only if live use is a goal).** The industry pattern for live football is Kafka/Kinesis → Flink/Spark Streaming → low-latency store, ingesting 25 Hz tracking + event feeds (cf. Bundesliga Match Facts on Amazon MSK, Hawk-Eye on Flink+MSK). This is a **separate pipeline** feeding the same gold layer — not a rewrite of the batch path. Scope it only if the platform must show in-match win-probability/momentum; for post-match analysis the batch lakehouse is sufficient and far cheaper.
- **P3.4 Multi-tenancy + governance.** Auth, per-role competition scoping, audit. Required before any external user touches it.
- **P3.5 Add tracking/360 data dimension.** The single biggest analytical leap available to clubs is positional/tracking data (SkillCorner, StatsBomb 360 — body coordinates, off-ball runs, pressure context). The schema should be designed now to accommodate an `x,y,frame` tracking table even before the data is licensed.

---

## 4. New Page / Feature Opportunities

Benchmarked against what StatsBomb, Wyscout, SkillCorner, and club analytics departments ship that this platform doesn't yet:

| Opportunity | What it adds | Builds on existing |
|---|---|---|
| **Recruitment / Scouting Shortlist Builder** | Multi-criteria player search across *all* competitions with similarity ("find players like X"), filters, exportable longlists. This is the #1 commercial use of StatsBomb/Wyscout. | `archetypes.py`, `player_ratings.py`, `play_style.py` already produce the feature vectors. |
| **Opposition Report Generator** | One-click pre-match dossier (formation tendencies, set-piece routines, pressing triggers, danger players) — the artifact coaches actually receive. | `formations.py`, `set_pieces.py`, `pressure.py`, `corner_defense.py` already exist; this *composes* them into a PDF/deck. |
| **Player Development / Trajectory** | Multi-season progression curves, age-vs-output, percentile evolution. | Needs the season-history dimension (see §5); analytics already exist. |
| **Squad Availability & Load (real, not synthetic)** | Today's `injuries_synthetic.py` is a placeholder. Clubs link GPS/load to availability (cf. Axon Perform, Catapult). A real availability model + minutes-management view is high value. | Replace synthetic source; keep the timeline UI. |
| **Set-Piece Designer / Threat Map** | Beyond corner *defense* — attacking routine library and expected-threat-by-zone. Midtjylland-style edge. | `set_pieces.py`, `xt.py`. |
| **Match Momentum / Win-Probability timeline** | Now standard fan- and analyst-facing (Bundesliga Match Facts). | `xg.py` race chart already half-way there; add a win-prob model. |
| **Comparison Workspace** | Save/compare arbitrary player or team sets side-by-side (the "Comparisonator" pattern). | Radar/pizza viz already built. |
| **Natural-language query layer** | "Show me América's xG conceded from corners this Apertura." DuckDB-backed (Phase 2) makes a text→SQL layer genuinely feasible. | Lands cleanly once Parquet/DuckDB exists. |

---

## 5. Data Model Improvement — Evolving the Flat JSON

The flat JSON tree is a fine *bronze* (raw, immutable, replayable) layer. The improvement is to **layer a modeled silver/gold schema on top of it**, not to throw it away.

**Today (implicit, file-system-as-schema):**
```
<League>/<Season>/partidos/<n_Home_Away_matchid>.json   # everything, nested, re-parsed each read
```
Identity is encoded in *filenames* and recovered by *string matching* (R3). There is no season-spanning entity; cross-season trends require re-globbing.

**Target — a star/dimensional schema materialized as partitioned Parquet:**

*Dimensions (slowly-changing, ID-keyed):*
- `dim_team` (team_id, names/aliases ← solves the name-variance problem once), `dim_player`, `dim_manager`, `dim_competition`, `dim_season`, `dim_venue`.

*Facts (partitioned by `league/season`, columnar):*
- `fact_event` — the flattened event grain (one row per Opta event: match_id, player_id, team_id, typeId, x, y, end_x, end_y, period, minute, outcome + promoted qualifier columns: xg, is_penalty, is_header, zone, pass_len, angle). This single table replaces the per-player full-tree scan with a `WHERE player_id=...` pushdown.
- `fact_shot`, `fact_pass`, `fact_lineup`, `fact_match` (the match index — the canonical join key, replacing fuzzy resolution).

*Gold rollups (precomputed):*
- `agg_player_season`, `agg_team_season`, `elo_history`, `xg_for_against` — what pages read directly.

**Key modeling decisions to make explicit (these are genuine trade-offs, not boilerplate):**

1. **Qualifier handling — promote vs. preserve.** Hot qualifiers (xG=395, formation=130, penalty=9) become typed columns; the long tail stays in a `qualifiers` MAP/JSON column so nothing is lost. *Trade-off:* every promoted qualifier is a faster query but a wider table and an ETL contract to maintain. Promote only what pages actually filter on (the manifest from P1.5 tells you which).
2. **Partitioning grain.** `league/season` matches every current access pattern and keeps file counts sane. Going finer (per matchday) speeds single-match reads but explodes small-file count — premature until match-level latency is proven a problem.
3. **Coordinate normalization stays 0–100** to keep `viz/pitch.py` (mplsoccer) untouched — the model serves the existing viz contract, not the other way around.
4. **Alias table is the antidote to R3.** `dim_team` carrying every feed spelling of a name, joined by `team_id`, retires `_short_team_name`'s hardcoded dictionary permanently and generalizes to all 21 competitions for free.
5. **Schema versioning.** Stamp each Parquet write with a schema version so feed drift is a migration, not a silent break.

---

## 6. Sequenced Recommendation

1. **This sprint (P1):** loud error handling, a real `match_index.parquet`, ID-based resolution, disk-backed cache. Low risk, immediately removes the worst correctness (R3) and cold-start (R1/R2) pain.
2. **Next (P2):** the JSON→Parquet ETL + DuckDB query layer behind `data.loader`. This is the keystone — it resolves R1/R4/R5/R7 structurally and unlocks the NLQ and cross-season features. Highest ROI of anything in this report.
3. **Later (P3):** carve `processing/` into an API, add domain data products, multi-tenancy, and (only if live is a goal) a streaming path — plus design the schema for tracking/360 data now.

**One-line thesis framing:** *The platform is already correctly layered in code; the next version's job is to make the storage layer as well-architected as the application layer — by introducing a columnar lakehouse (Parquet + DuckDB) behind the existing loader API, so the analytics never change but the platform stops re-reading 47 GB of JSON to answer a single question.*

---

## Sources

- [How Big Data Analytics Improve Football Performance — B-Eye](https://b-eye.com/blog/how-big-data-analytics-improve-football-performance/)
- [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [How Football Clubs Use Data Analytics — Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/)
- [Streamlit Multipage Apps — Overview](https://docs.streamlit.io/develop/concepts/multipage-apps/overview) · [st.navigation concepts](https://docs.streamlit.io/develop/concepts/multipage-apps)
- [What is a Data Lakehouse? — MotherDuck](https://motherduck.com/learn/what-is-a-data-lakehouse/) · [Data Lakehouse Explained — Analytics8](https://www.analytics8.com/blog/data-lakehouse-explained-building-a-modern-and-scalable-data-architecture/) · [What is a Data Lakehouse — Databricks](https://databricks.com/glossary/data-lakehouse)
- [Parquet in Data Lake Architectures — Dremio/Medium](https://medium.com/data-engineering-with-dremio/all-about-parquet-part-09-parquet-in-data-lake-architectures-b6bbfff0a0ce)
- [Real-Time Sports Analytics with Kafka and Flink — IJARCSE](https://ijarcse.org/index.php/ijarcse/article/view/118)
- [Hawk-Eye Innovations: Real-Time Sports Data with Flink and Amazon MSK — AWS](https://aws.amazon.com/blogs/media/hawk-eye-innovations-powers-real-time-sports-data-with-flink-and-amazon-msk/)
- [Bundesliga Match Fact: Match Momentum — AWS](https://aws.amazon.com/blogs/media/bundesliga-match-fact-match-momentum-revealing-the-games-invisible-pulse/)
- [StatsBomb Open Data (schema/structure) — GitHub](https://github.com/statsbomb/open-data) · [Hudl StatsBomb Aggregated API](https://statsbomb.com/articles/soccer/learn-more-about-the-statsbomb-iq-api/) · [StatsBomb Live Data API Reference](https://live-data-api-guide.statsbomb.com/api-reference/)
- [How to Move Beyond a Monolithic Data Lake to a Distributed Data Mesh — Martin Fowler](https://martinfowler.com/articles/data-monolith-to-mesh.html) · [The 4 Principles of Data Mesh — dbt Labs](https://www.getdbt.com/blog/the-four-principles-of-data-mesh)
- [DuckDB vs Polars on Massive Parquet — codecentric](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data) · [Modern Data Analytics Stack with Python, Parquet, DuckDB — KDnuggets](https://www.kdnuggets.com/building-your-modern-data-analytics-stack-with-python-parquet-and-duckdb)
- [Tools Every Football Analyst Should Know — Liam Henshaw](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know) · [SkillCorner — Football](https://skillcorner.com/sports/football) · [Axon Perform — Football Analytics](https://www.axonperform.com/football-analytics)
