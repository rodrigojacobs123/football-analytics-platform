# DATA ARCHITECT REPORT

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-24 (14:54 run)
**Author:** Principal Data Architect — automated 3-day improvement cycle
**Scope:** Architecture review of a single-process Streamlit app reading flat Opta JSON across 21+ North-American/CONCACAF competition folders. Layers: `data → processing → viz → components → pages`.

> **Delta since the last architect run (2026-06-21 09:10).** I verified the tree this cycle. The prior report's five headline recommendations — silver Parquet event layer, DuckDB query engine, medallion bronze/silver/gold, a headless build CLI, and a versioned schema module — **have not shipped.** What *did* change is purely analytical: two new modules (`processing/buildup_play.py`, `viz/buildup.py`) wired directly into `2_Pre_Match_Analysis` and `3_Post_Match_Analysis`. `processing/` is now 29 modules; the nav holds 11 pages. The architecture is therefore **unchanged in substance** since 06-21, and this report does *not* re-pad the same phased plan. Instead it (a) credits the standing recommendations as still-correct and now de-risked, (b) surfaces **three concrete, previously-unflagged risks** the new code and a fresh dependency audit expose, and (c) deepens the Streamlit-layer and cross-provider-schema thinking the earlier runs only touched.

---

## 0. Executive Summary

The platform is still a **well-layered analytical monolith** on a raw-file lake, and that layering remains its decisive asset — every evolution below is non-destructive because of it. Three cycles of analyst reports have grown `processing/` to 29 modules; the intellectual product now rivals a mid-tier data vendor. **The gap has not moved: it is entirely in how data is *stored and served*, not in what is computed.**

This cycle's sharpest finding is not strategic but operational and immediate: **the one persistence tier the platform already depends on — the Parquet match index — rests on an undeclared dependency.** `data/match_index.py` calls `df.to_parquet()` / `pd.read_parquet()`, which require `pyarrow`. It works on this machine (pyarrow 23.0.1 is installed) but `requirements.txt` declares only `streamlit, pandas, numpy, plotly, mplsoccer, scipy, scikit-learn, matplotlib, seaborn, beautifulsoup4, requests`. A clean `pip install -r requirements.txt` on a fresh box would **silently omit pyarrow** (pandas 2.x does not hard-require it), and the match index would throw at first write. Every future evolution in this report rests on Parquet I/O — so this one-line fix is the literal precondition for the roadmap, not a footnote.

Framed as a club would: the system is a strong analyst's workbench whose **storage engine is still nested JSON parsed on the request hot path**. The standing move — *persist a silver Parquet event layer and query it with in-process DuckDB* — remains the highest-leverage single change and is now blocked only by inertia plus a missing `requirements.txt` line. This report's job is to remove the excuses.

---

## 1. Current Architecture Strengths

What the layered Streamlit approach gets right (re-verified this cycle, not assumed):

1. **One-directional layer dependency holds even under new code.** The two new modules landed in the right places — analytics in `processing/buildup_play.py`, rendering in `viz/buildup.py`, consumed by pages. No page parses JSON; no `processing/` module calls Streamlit. The discipline survived a feature addition unsupervised, which is the real test of an architecture.

2. **The match index is a genuine persistence tier and the template for everything next.** `match_index.py` is a signature-gated, ID-keyed Parquet artifact with an in-process cache keyed by `(path, signature)` so staleness self-invalidates. This *is* the bronze→indexed-table lakehouse pattern, hand-built correctly for the access path that needed it most. Every Phase-1 step below is "do this again for events."

3. **Opta semantics centralized as a schema contract in waiting.** `config.py` encodes the gotchas (shots {13,14,15,16}, xG qual 395, formation qual 130, penalty qual 9 *not* 22, goalmouth z=19 = "not recorded") with comments tracing real past bugs. Vendors like StatsBomb treat the event spec *as the product*; this project already treats it as a first-class module — it just isn't *enforced* yet (Risk #4).

4. **Explicit `st.navigation` over magic discovery.** `app.py` hand-curates 11 `st.Page` entries. The numeric prefixes (note the 5/7/8 gaps from deleted pages) are sort hints, not routing — dropping a file in `pages/` does not silently ship it. This is exactly the mechanism future role-based / competition-gated access would reuse.

5. **Entity-by-ID discipline and minimum-sample guards.** Club América is `AME_TEAM_ID`, never a name; ratings respect `MIN_APPEARANCES_FOR_RATING` and `MIN_MATCHES_FOR_PREDICTION`. These are the two instincts that separate a recruitment-grade platform from a notebook, and they are already load-bearing.

6. **Caching concentrated at the I/O seam.** Every loader is `@st.cache_data(ttl=3600)`; cache policy is one layer, changeable in one place — the precondition for making it durable later.

---

## 2. Critical Architectural Risks

The three High-severity risks from 06-21 (per-event season scans, volatile per-process cache, JSON-as-query-engine) **all still stand verbatim** — nothing was done to retire them, so I will not re-prosecute them here; treat §3 of the 06-21 report as still in force. This cycle adds **three risks those reports did not name**, surfaced by the new code and a dependency audit:

1. **Undeclared Parquet dependency under the only persistence tier.** *(NEW — Severity: High, trivial fix.)* `match_index.py` reads/writes Parquet; `requirements.txt` omits `pyarrow` (and `fastparquet`). It runs here only because pyarrow 23.0.1 happens to be installed. A fresh environment — a grader reproducing the TFM, a teammate, a container build — would install per the manifest and crash on first index write with an opaque `ImportError: ... pyarrow`. The entire storage roadmap (silver/gold Parquet) widens this exposure. **Fix: add `pyarrow>=14.0` to `requirements.txt` today.** Everything else in this report is downstream of that line being present.

2. **New analytics are wired straight into pages with no shared cache boundary.** *(NEW — Severity: Medium.)* `buildup_play.py` is imported by both `2_Pre_Match_Analysis` and `3_Post_Match_Analysis`. If its entry points are invoked inside the page body (not behind a `@st.cache_data` loader), the build-up computation re-runs on every widget interaction and is recomputed independently per page — the same event frame parsed twice for two views of one match. As `processing/` grows past 29 modules, "analytics called directly from pages without a caching seam" becomes the dominant source of silent latency. **The architectural rule to codify: pages call cached loaders, never raw `processing.*` entry points on the hot path.** Audit the two new imports against this rule.

3. **No single source of truth for the page registry, and it has already drifted.** *(NEW — Severity: Low-Medium.)* Three artifacts describe the page set and *disagree*: the scheduled-task brief says "8 pages," `CLAUDE.md` lists 11 in its table, and `app.py` registers 11 `st.Page` objects — with prefix gaps (5/7/8) marking deleted pages whose numbering was never reclaimed. Today this is cosmetic. The moment pages are gated by competition or role (the stated Phase-3 direction), an out-of-sync registry becomes an access-control correctness bug. **Make `app.py`'s `st.navigation` list the sole registry, and have `11_Data_Sources` render it** so docs can't drift from reality.

4. **Compute is still welded to presentation.** *(Carried, re-affirmed — Severity: Medium.)* Analytics only execute inside a Streamlit request. There is still no path to scheduled pre-computation, batch backfill, or an API. The pure-pandas `processing/` layer *can* support all three; nothing exercises it outside the app. This is why the headless build CLI (§3) keeps recurring — it is the keystone that unlocks scheduling, the API, and offline correctness testing simultaneously.

5. **No ingestion contract / schema validation.** *(Carried — Severity: Medium-High.)* `config.py` documents Opta semantics but nothing validates incoming files against it. A renamed qualifier or coordinate-system shift surfaces as a wrong number deep in a page, not a load-time failure. With four+ seasons per league now spanning 2015–2026, the odds that the Opta spec drifted somewhere across that range are not negligible — and no test would catch it.

---

## 3. Recommended Architectural Evolutions (Phased)

The phased plan from 06-21 is correct and I am **not restating it line-by-line.** What follows is *re-prioritized for the fact that nothing shipped*, with the new risks folded in. The discipline this cycle: make Phase 1 small enough that it cannot be deferred again.

### Phase 1 — Quick wins (hours-to-days, no new infra)

- **Declare the Parquet engine.** Add `pyarrow>=14.0` to `requirements.txt`. One line; retires Risk #1 and unblocks every storage step. *Do this first, independent of everything else.*
- **Add the "pages call cached loaders only" rule and enforce it on the two new imports.** Wrap the `buildup_play` entry points in a `@st.cache_data` loader (key on `match_id`), so Pre-Match and Post-Match share one cached build-up frame instead of recomputing per page. Retires Risk #2 and sets the pattern for module #30.
- **Make the nav list self-documenting.** Have `11_Data_Sources` print the live `st.navigation` registry (count + titles + file paths). Retires Risk #3 and gives a free "what ships" audit.
- **Persist a silver event layer to Parquet, partitioned `league/season`** — the standing top recommendation, now genuinely a quick win because the pattern already exists. Mirror `match_index.py`: signature-gated, rebuild-on-drift, write `events/<league>/<season>/<match_id>.parquet`. `load_player_events_season()` (`data/loader.py:265`) then scans columnar files with a `player_id` predicate instead of `json.loads`-ing every match. This single step retires the three standing High risks (per-event scans, volatile cache, JSON-as-engine) for the heaviest access path.
- **Add a load-time schema assertion** in `event_parser.py`: assert the `config.py` qualifier IDs actually appear in a sampled event per season; warn on absence. Cheap insurance against the 2015–2026 feed-drift exposure (Risk #5).

### Phase 2 — Medium-term (a real query engine + ingestion)

Unchanged in direction from 06-21, summarized so this report is self-contained:
- **DuckDB as the in-process query layer over the Parquet lake** — Hive-partition pruning + predicate pushdown, no new service. `data/loader.py` becomes a thin SQL emitter; `processing/` still receives DataFrames.
- **Formalize medallion bronze/silver/gold** — bronze = raw Opta JSON (source of truth, never mutated); silver = typed flattened events + ID-keyed dimensions; gold = pre-aggregated marts (season ratings, team xG tables, Elo histories) the pages read.
- **Promote `config.py` Opta semantics to a versioned `schema/opta_v1.py`** with a validator, and tag each ingested season with the schema version it parsed under — turning Risk #5's silent break into a versioned event.
- **Extract a headless build CLI** (`python -m data.build --league … --season …`) running bronze→silver→gold outside Streamlit. This is the keystone that retires Risk #4 and enables offline correctness tests for the 29 `processing/` modules — which today have no test harness at all.

### Phase 3 — Long-term vision (the club-grade platform)

- **Serve gold marts through a thin FastAPI layer** so Streamlit becomes *one* consumer alongside a future React UI and the club's own data scientists (the way StatsBomb/Wyscout expose data to clubs).
- **Adopt a cross-provider event contract (UIED-style).** The industry is converging on a **Unified and Integrated Event Data** format that normalizes StatsBomb / Wyscout / Opta / DataStadium into one schema. Even single-source today, modeling the silver layer to a *provider-neutral* event contract is the move that lets the platform ingest a second feed (e.g. Wyscout video tags alongside Opta events) without rewriting analytics. See §5.
- **Incremental-batch ingestion as the realistic streaming target.** Process new matches as they land; reserve true streaming (Kafka/MSK + Flink, the AWS Bundesliga/Hawk-Eye pattern, sub-100ms event-to-screen) as the explicit "if a PL club adopted this" north star — scoped, not over-built.
- **Domain-oriented data products (lightweight data-mesh framing).** Treat *recruitment*, *opposition analysis*, *medical/load*, and *match analysis* as domains, each owning its gold marts behind a contract. The current `processing/` modules already cluster this way (see §4) — formalizing the boundary is mostly naming, not rearchitecting.

---

## 4. New Page / Feature Opportunities

Based on what professional club platforms (Hudl StatsBomb + Wyscout, SAP Sports One, Second Spectrum, Kitman Labs) offer that this one doesn't yet. I've grouped them by the **domain boundary** they'd anchor — pre-staging the data-mesh framing of §3 Phase 3:

| Domain | New page | Built from (already exists) | Why it's the gap |
|---|---|---|---|
| **Recruitment** | **Player Similarity & Shortlist** workspace — "find players like X across all 21 competitions" | `archetypes.py`, `player_ratings.py`, `player_profile.py` | StatsBomb's *core* club workflow is similarity search + shortlisting. The cross-league scan it needs is exactly what the silver/DuckDB layer unlocks — impossible to serve responsively today. |
| **Opposition analysis** | **One-click Opposition Dossier** (exportable PDF) | `formations.py`, `pressure.py` (PPDA), `goal_buildup.py` + new `buildup_play.py`, `set_pieces.py` | The new build-up module is the missing half of an opponent report; this composes it with pressing/shape into the artifact analysts actually hand coaches. |
| **Set-piece** | **Attacking Set-Piece Intelligence** | `set_pieces.py` (exists, only *corner defense* is surfaced via `13_Corner_Defense`) | Clubs treat attacking set pieces as a top marginal-gains area; the analytics already exist and aren't shown. |
| **Medical / load** | **Workload & Availability** | `injuries_synthetic.py` | Every club platform integrates GPS/biometric load. Even synthetic, this demonstrates the medical domain and is a natural data-product boundary. |
| **Match analysis** | **Live Match Momentum** (read-only, batch source) | `game_phases.py`, `sequences.py`, xG flow | Showcases the streaming north-star from a batch source without building the streaming infra. |

The throughline: nearly every high-value new page is **already computable** — the blocker is the storage layer's inability to serve cross-competition slices responsively, not missing analytics.

---

## 5. Data Model Improvement — Evolving the Flat JSON

The 06-21 report laid out the medallion target layout (bronze JSON untouched → silver Parquet events + dimensions → gold marts) and the star-schema / explode-hot-qualifiers principles. **That target is still correct and I endorse it without change.** This cycle adds the two refinements that the new code and the cross-provider research expose:

**(a) Model the silver event contract as provider-neutral from day one.** The industry's UIED convergence (StatsBomb / Wyscout / Opta normalized to one schema) is the signal: don't bake Opta `typeId` integers into the silver column names. Instead, the silver `fact_events` should carry a **semantic action column** (`action ∈ {pass, shot, tackle, carry, …}`) derived from Opta `typeId` at *parse* time, with the raw `typeId` retained alongside. This is a small change with a large payoff — it means a future Wyscout feed maps into the same `action` vocabulary instead of forking every `processing/` module on provider. The `config.py` mappings already do exactly this translation; the silver schema just persists the *output* of that mapping rather than the raw code.

```
silver/events.parquet  (partitioned by league/season)
  match_id, team_id, player_id, period, minute, second,
  action,            # provider-neutral: 'shot','pass','tackle',...  <-- the UIED idea
  opta_type_id,      # raw 13/14/15/16/... retained for lineage
  x, y,              # normalised 0–100
  xg, formation, outcome, is_penalty, goalmouth_z,   # exploded hot qualifiers (typed)
  qualifiers,        # full nested array for the long tail
  schema_version, source_signature                   # lineage + drift detection
```

**(b) Codify the known data-quality gotchas *into the schema*, not into every consumer.** The project's own memory records them: penalty = qualifier **9** not 22, and goalmouth **z=19 means "height not recorded"** on ~40% of on-target shots. Today every metric that touches shot placement must remember to guard z=19. In the silver layer, materialize a typed `goalmouth_z` that is **NULL when raw z==19**, and an `is_penalty` boolean computed once from qual 9. The gotcha is then enforced by the storage layer — a new analytic *cannot* re-introduce the bug because the bad sentinel never reaches it. This is the single highest correctness-per-line change in the model evolution, and it directly operationalizes two of the four entries in the project's memory.

**Migration stays non-destructive.** Bronze JSON is never deleted; silver/gold are rebuildable from it via the build CLI. If a derived file is ever wrong, delete and rebuild — the exact contract `match_index.py` already honors.

---

## 6. Closing — What the Next Version Looks Like

Three architect/analyst cycles have proven the analytics engine; the storage engine has not moved an inch. The honest read of this cycle is that the roadmap is right and **the obstacle is now execution, not design.** So the recommendation is deliberately small and sequenced to defeat deferral:

1. **Add `pyarrow>=14.0` to `requirements.txt`** — the one line the entire roadmap silently depends on, and the only true *bug* in this report.
2. **Wrap the new `buildup_play` calls in a shared cached loader** and write down the "pages call cached loaders, not raw `processing.*`" rule — before module #30 repeats the pattern.
3. **Ship the silver Parquet event layer**, reusing `match_index.py`'s proven signature-gated pattern — retiring the three standing High-severity risks for the heaviest access path.
4. Then, and only then, **DuckDB → medallion → build CLI → gold-mart API**, exactly as the 06-21 report scoped.

The layered design has already earned the right to evolve storage without rewriting analytics. What's missing is not another plan — it's the first three commits. If a Premier League department adopted this codebase tomorrow, those commits are precisely where they'd start, and the provider-neutral silver schema (§5) is the bet that lets them add a second data feed without touching a single `processing/` module.

---

## Sources

- [Football Performance Analytics — b-eye](https://b-eye.com/blog/how-big-data-analytics-improve-football-performance/)
- [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [Data analytics in the football industry (survey) — PubMed](https://pubmed.ncbi.nlm.nih.gov/38745403/)
- [How Football Clubs Use Data Analytics to Improve Performance — Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/)
- [Define multipage apps with st.Page and st.navigation — Streamlit Docs](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [How to Structure and Organise a Streamlit App — Towards Data Science](https://towardsdatascience.com/how-to-structure-and-organise-a-streamlit-app-e66b65ece369/)
- [The Lakehouse in Football Analytics — Eyedle](https://eyedle.ai/the-lakehouse-in-football-analytics/)
- [LaLiga uses the Databricks Lakehouse platform — Digitalisation World](https://digitalisationworld.com/news/63327/laliga-uses-the-databricks-lakehouse-platform-to-analyse-competitions-and-create-data-driven-sports)
- [The Rise of Sports Intelligence: How the Lakehouse Turns Tracking Data into Competitive Advantage — Databricks Blog](https://www.databricks.com/blog/rise-sports-intelligence-how-lakehouse-turns-tracking-data-competitive-advantage)
- [How to Architect a Scalable, Low-Latency Sports Data Pipeline — Data Sports Group / Medium](https://medium.com/@marketing_25315/how-to-architect-a-scalable-low-latency-sports-data-pipeline-for-real-time-apps-385b18246fd8)
- [OpenSTARLab: Open Approach for Spatio-Temporal Agent Data Analysis in Soccer (UIED format) — arXiv](https://arxiv.org/html/2502.02785v2)
- [Hudl StatsBomb — The World's Most Advanced Football Data](https://www.hudl.com/en_gb/products/statsbomb)
- [Introducing the New Hudl StatsBomb with Wyscout Video — Hudl](https://www.hudl.com/blog/hudl-statsbomb)
- [Sports Data Integration API — Kitman Labs](https://www.kitmanlabs.com/platform/sports-data-integration-api/)
- [Data Mesh Architecture](https://www.datamesh-architecture.com/)
- [The four principles of data mesh — dbt Labs](https://www.getdbt.com/blog/the-four-principles-of-data-mesh)
