# DATA ARCHITECT REPORT

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-25 (07:15 run)
**Author:** Principal Data Architect — automated 3-day improvement cycle
**Scope:** Architecture review of a single-process Streamlit app reading flat Opta JSON across 21+ North-American/CONCACAF competition folders. Layers: `data → processing → viz → components → pages`.

> **Delta since the last architect run (2026-06-24 14:54).** I re-verified the tree this cycle, and for the first time in three cycles the recommendations *moved*. **Two of the three "new" risks I raised last run shipped fixes — exactly as scoped:**
> 1. `pyarrow>=14.0` is now in `requirements.txt`, carrying the verbatim comment from the last report ("Parquet engine for data/match_index.py — pandas 2.x does NOT pull this in"). Risk #1 (undeclared Parquet dependency) is **retired.**
> 2. A new `nav.py` module now holds `PAGE_SPECS` as the single page registry; `app.py` builds `st.navigation` from it and `11_Data_Sources` renders it. The docstring quotes my own finding back ("the task brief said 8 pages, CLAUDE.md said 11, app.py shipped 11"). Risk #3 (registry drift) is **retired** — and, notably, `build_pages()` imports Streamlit *lazily* "so this module stays importable in … a future headless build CLI," meaning the Phase-2 keystone has been deliberately pre-wired.
>
> What did **not** move is the storage engine. The three standing High-severity risks (per-event season scans, volatile per-process cache, JSON-as-query-engine) remain verbatim. Meanwhile `processing/` grew **29 → 37 modules** (+9: `attack_play`, `buildup_play`, `discipline`, `game_state`, `gk_value`, `player_threats`, `team_shape`, `wide_play`, `xg_chain`) plus two new `viz/` modules. The analytical surface widened again on top of an unchanged storage floor.

---

## 0. Executive Summary

The narrative of the last three cycles was "the roadmap is right; execution hasn't started." **That narrative is now disproven in the project's favour.** The two cheapest items I flagged last cycle were implemented precisely and with the reasoning preserved in code comments. The team can and does execute architectural recommendations. So the remaining gap is no longer a question of *capability* — it is a question of *size*: the storage work is being deferred because it is the biggest single item, not because it is hard to land.

This reframes my job. I will not re-pad the silver/DuckDB/medallion plan a fourth time — it is endorsed, unchanged, and the team has shown it will execute scoped work. Instead this cycle: (a) credits the two retired risks and shows how `nav.py` accidentally laid Phase-2 groundwork; (b) raises **one new High-severity governance risk the prior reports missed** — a large body of live analytics is *not under version control*; (c) makes the **domain-product boundary concrete** now that 37 modules give enough signal to name the data products; and (d) quantifies the widening analytics-vs-storage gap so the silver layer stops being abstract.

The sharpest *immediate* finding is not strategic: **9 of the 37 `processing/` modules — and 2 of the `viz/` modules — are untracked in git (`??` status).** A meaningful fraction of the platform's intellectual product (build-up play, GK valuation, game-state splits, player threat, team shape, wide play, xG chain) exists only in the working tree. One `rm -rf` or a bad `git clean` and it is gone, unreviewed and unrecoverable. That is a bigger near-term exposure than any storage-layer latency, and it is one `git add` away from fixed.

---

## 1. Current Architecture Strengths

Re-verified this cycle, not assumed:

1. **Recommendations are executable, and the layering survives growth.** Nine new analytics modules landed in `processing/`, two renderers in `viz/`, consumed by pages — none parsing JSON, none calling Streamlit. The one-directional layer dependency held through a +30% expansion of the analytics surface, unsupervised. That is the strongest possible evidence the architecture is sound.

2. **The single-registry pattern is now real, and forward-compatible.** `nav.py:PAGE_SPECS` is the sole page list; `app.py` and `11_Data_Sources` both consume it, so documentation cannot drift from what ships. Critically, `build_pages()` imports `streamlit` lazily *by design* so `nav.py` stays importable headless. The team didn't just fix the drift — they fixed it in a way that **pre-stages the headless build CLI** (Phase 2). This is the first piece of the storage roadmap to land, even if incidentally.

3. **The match index remains the proven persistence template.** `data/match_index.py` is still the only durable tier: signature-gated, ID-keyed Parquet with `(path, signature)` cache invalidation. With `pyarrow` now declared, it is no longer resting on an undeclared dependency. Every Phase-1 storage step is "do this again for events."

4. **Opta semantics stay centralized as a schema-contract-in-waiting.** `config.py` still encodes the gotchas with bug-traced comments (shots {13,14,15,16}, xG qual 395, formation qual 130, penalty qual 9 ≠ 22, goalmouth z=19 = "not recorded"). The contract is documented; it is still not *enforced* at load time (Risk #5, carried).

5. **Caching concentrated at the I/O seam, and the new code respects it.** Post-Match parses each match behind `@st.cache_data(ttl=3600)` (`pages/3_Post_Match_Analysis.py:59`); the new `plot_attack` / `extract_goal_buildups` calls operate on that *already-cached* `events` frame rather than re-reading JSON. So last cycle's Risk #2 (per-page recompute) is **materially mitigated** for the match-level path — the new analytics ride the cached frame instead of forking their own parse.

---

## 2. Critical Architectural Risks

The three standing **High-severity** risks from 06-21 are unchanged and I will not re-prosecute them — `data/loader.py:317` still does `json.loads(f.read_text())` on the per-player season-scan hot path; treat §3 of the 06-21 report as still in force. Of last cycle's three *new* risks, two are retired (pyarrow, nav drift) and one (per-page recompute) is mitigated. This cycle raises **one genuinely new risk** and re-affirms the two structural carries:

1. **A large body of live analytics is not under version control.** *(NEW — Severity: High, trivial fix.)* `git status` shows **9 `processing/` modules and 2 `viz/` modules as untracked (`??`):** `attack_play`, `buildup_play`, `discipline`, `game_state`, `gk_value`, `player_threats`, `team_shape`, `wide_play`, `xg_chain`, plus `viz/attack_play`, `viz/buildup`. These are *imported by shipped pages* (Pre-Match and Post-Match both `from viz.attack_play import …`) — they are not experiments, they are production. Yet they have no commit, no history, no review, no diff. Consequences: (a) **data loss** — a `git clean -fd`, a discarded worktree, or a fresh clone loses them silently; (b) **no provenance** — when `gk_value` produces a wrong number there is no blame/history to bisect; (c) **CI/test impossibility** — you cannot gate untracked files. This is the single highest-exposure, lowest-effort fix in the report. **Commit the 11 files today**, before any of them grows further.

2. **Compute is still welded to presentation — but the wedge is now in place to split it.** *(Carried, re-affirmed — Severity: Medium.)* Analytics still only execute inside a Streamlit request; no scheduled pre-compute, batch backfill, or API. *However*, `nav.py`'s deliberate headless-importability is the first crack in that weld. The keystone — a `python -m data.build` CLI running the `processing/` modules outside Streamlit — is now a smaller lift than it was, because import discipline already anticipates it. This risk is downgraded from "no path exists" to "the path is half-built; finish it."

3. **No ingestion contract / schema validation, now spanning 37 consumers.** *(Carried — Severity: Medium-High.)* `config.py` documents Opta semantics; nothing validates incoming files against them. With seasons spanning 2015–2026 and **37 processing modules** each trusting the feed's shape, a renamed qualifier or coordinate shift surfaces as a wrong number deep in a page, never as a load-time failure. Every new module added without a load-time assertion widens this blast radius. The +9 modules this cycle each added a new way for silent feed-drift to manifest.

4. **The analytics-vs-storage gap is widening measurably.** *(NEW framing — Severity: Medium.)* Three cycles ago `processing/` had ~25 modules on a JSON file lake; today it has 37. **Every one of those 37 modules ultimately consumes an event frame parsed from nested JSON on the request hot path.** The intellectual product now rivals a mid-tier vendor while the storage substrate is still "parse the file each time." A cross-competition query (e.g. "GK value across all 21 leagues," which `gk_value.py` could in principle compute) is *un-serveable* responsively today not for lack of analytics but because there is no columnar layer to scan. The gap is no longer a abstract risk — it is the concrete ceiling on the highest-value new features (§4).

---

## 3. Recommended Architectural Evolutions (Phased)

The phased plan is endorsed unchanged; I restate only what shifted now that the team has proven it executes scoped work. **The discipline this cycle: every Phase-1 item is sized to be un-deferrable, and ordered so the governance bleak is plugged first.**

### Phase 1 — Quick wins (hours-to-days, no new infra)

- **Commit the 11 untracked modules.** `git add processing/{attack_play,buildup_play,discipline,game_state,gk_value,player_threats,team_shape,wide_play,xg_chain}.py viz/{attack_play,buildup}.py` and commit. Retires the new High-severity governance risk. *Do this first — it is the only true data-loss exposure in the report.*
- **Add a load-time schema assertion in `event_parser.py`.** Assert the `config.py` qualifier IDs actually appear in a sampled event per season; warn on absence. Cheap insurance against 2015–2026 feed drift across now-37 consumers (Risk #3).
- **Ship the silver Parquet event layer, partitioned `league/season`** — the standing top recommendation, now a genuine quick win: the `match_index.py` pattern is proven *and* `pyarrow` is finally declared. Mirror it: signature-gated, rebuild-on-drift, `events/<league>/<season>/<match_id>.parquet`. Then `load_player_events_season()` (`data/loader.py:287`) scans columnar files with a `player_id` predicate instead of `json.loads`-ing every match at line 317. This single step retires the three standing High risks for the heaviest path.

### Phase 2 — Medium-term (the keystone is half-built; finish it)

- **Extract the headless build CLI (`python -m data.build --league … --season …`).** Promoted to the *front* of Phase 2 this cycle because `nav.py` already proved the codebase can be imported headless. The CLI runs bronze→silver→gold outside Streamlit, and — equally important — gives the 37 `processing/` modules their **first test harness**, which untracked files (Risk #1) currently make impossible anyway. This is the keystone that simultaneously unlocks scheduling, the future API, offline correctness tests, and CI gating.
- **DuckDB as the in-process query layer over the Parquet lake** — Hive-partition pruning + predicate pushdown, no new service. `data/loader.py` becomes a thin SQL emitter; `processing/` still receives DataFrames.
- **Formalize medallion bronze/silver/gold** — bronze = raw Opta JSON (never mutated); silver = typed flattened events + ID-keyed dimensions; gold = pre-aggregated marts (season ratings, team xG tables, Elo histories, and now GK-value / team-shape / xG-chain marts from the +9 modules).
- **Promote `config.py` Opta semantics to a versioned `schema/opta_v1.py`** with a validator, tagging each ingested season with the schema version it parsed under — turning Risk #3's silent break into a versioned event.

### Phase 3 — Long-term vision (the club-grade platform)

- **Serve gold marts through a thin FastAPI layer** so Streamlit becomes *one* consumer alongside a future React UI and the club's own data scientists — the way StatsBomb/Wyscout expose data and APIs to clubs.
- **Adopt a provider-neutral event contract (UIED-style).** The industry's Unified and Integrated Event Data format normalizes StatsBomb / Wyscout / Opta / DataStadium into one schema. Model the silver layer to a provider-neutral `action` vocabulary now so a second feed (e.g. Wyscout video tags alongside Opta events) drops in without rewriting any of the 37 modules. (§5.)
- **Incremental-batch ingestion as the realistic streaming target.** Process new matches as they land; reserve true streaming (Kafka/MSK + Flink — the Hawk-Eye / AWS pattern, sub-second event-to-screen) as the explicit "if a PL club adopted this" north star — scoped, not over-built.
- **Domain-oriented data products (lightweight data-mesh framing).** The 37 modules now cluster cleanly enough to *name* the domains — see §4. Formalizing the boundary is mostly naming and a mart-ownership contract, not rearchitecting.

---

## 4. New Page / Feature Opportunities

The +9 modules this cycle make the **domain boundaries concrete** for the first time. Below, the existing 37 modules are grouped into the five data-product domains a club platform (Hudl StatsBomb + Wyscout, SAP Sports One, Second Spectrum, Kitman Labs) would recognize — and the page each domain is missing:

| Domain | Modules already shipped (selected) | Missing page / feature | Why it's the gap |
|---|---|---|---|
| **Recruitment** | `player_ratings`, `archetypes`, `player_profile`, `player_threats`, `gk_value` | **Player Similarity & Shortlist** — "find players like X across all 21 competitions" | StatsBomb's core club workflow. The cross-league scan it needs is exactly what silver/DuckDB unlocks and what JSON-parsing makes un-serveable today. `gk_value` notably enables a *goalkeeper* shortlist most platforms under-serve. |
| **Opposition analysis** | `formations`, `team_shape`, `wide_play`, `pressure`(PPDA), `goal_buildup`, `buildup_play`, `attack_play`, `set_pieces` | **One-click Opposition Dossier** (exportable PDF) | The new `buildup_play` + `attack_play` + `team_shape` are now the missing two-thirds of an opponent report; compose them with pressing/shape into the artifact analysts hand coaches. |
| **Match analysis** | `game_phases`, `game_state`, `sequences`, `xg_chain`, `match_ratings` | **Live Match Momentum** (read-only, batch source) | `game_state` (state-dependent splits) + `xg_chain` (possession value) are exactly the momentum primitives; showcases the streaming north-star from a batch source without building streaming infra. |
| **Set-piece** | `set_pieces` (only *corner defense* surfaced via `13_Corner_Defense`) | **Attacking Set-Piece Intelligence** | Top marginal-gains area for clubs; analytics exist and aren't shown. |
| **Discipline / risk** | `discipline` (NEW), `injuries_synthetic` | **Squad Availability & Discipline Risk** | `discipline` (cards/suspension exposure) + synthetic load is a natural medical/availability data-product the platform doesn't surface yet. |

The throughline is unchanged and now sharper: **nearly every high-value new page is already computable** — the +9 modules this cycle added the *last missing analytics* for three of the five domains. The sole blocker is the storage layer's inability to serve cross-competition slices responsively.

---

## 5. Data Model Improvement — Evolving the Flat JSON

The medallion target (bronze JSON untouched → silver Parquet events + dimensions → gold marts) and the provider-neutral `action` column are endorsed unchanged from the 06-24 report. This cycle adds one refinement the +9 modules expose:

**Make the silver schema carry the columns the new modules recompute per request.** Modules like `game_state` (score-state at event time), `xg_chain` (possession-chain id + value), and `team_shape` (per-event team centroid/width) all derive *contextual* fields by re-walking the event stream every time they run. These are precisely the fields that belong **materialized once in the silver layer**, not recomputed in 9 places:

```
silver/events.parquet  (partitioned by league/season)
  match_id, team_id, player_id, period, minute, second,
  action,            # provider-neutral: 'shot','pass','tackle',...  (UIED)
  opta_type_id,      # raw 13/14/15/16/... retained for lineage
  x, y,              # normalised 0–100
  xg, formation, outcome, is_penalty, goalmouth_z,   # exploded hot qualifiers (typed)
  -- contextual fields the +9 modules currently recompute, materialized once:
  score_state,       # +1/0/-1 from team's perspective at event time  (feeds game_state)
  possession_id,     # chain id                                        (feeds xg_chain, sequences)
  team_centroid_x, team_centroid_y, team_width,      # (feeds team_shape, wide_play)
  qualifiers,        # full nested array for the long tail
  schema_version, source_signature                   # lineage + drift detection
```

This is the model-level expression of the §2 "widening gap" finding: as the analytics layer grows, the cost of *not* materializing context compounds linearly with the number of modules. Materializing `score_state` / `possession_id` / centroids once turns nine independent stream-walks into nine columnar reads.

**Codify the known gotchas into the schema, not into 37 consumers.** Still the highest correctness-per-line change: materialize `goalmouth_z` as **NULL when raw z==19** ("height not recorded," ~40% of on-target shots) and `is_penalty` from qualifier **9** (not 22) once at parse time. With 37 modules now trusting the feed, enforcing these in storage means no new module can re-introduce the bug — the bad sentinel never reaches it.

**Migration stays non-destructive.** Bronze JSON is never deleted; silver/gold rebuild from it via the build CLI. If a derived file is wrong, delete and rebuild — the exact contract `match_index.py` already honors.

---

## 6. Closing — What the Next Version Looks Like

This is the first cycle where the recommendations moved, and they moved *exactly as written* — pyarrow with the verbatim comment, the single registry quoting my own finding back, and `nav.py` quietly pre-wiring the headless future. The honest read flips: **the team executes scoped architectural work reliably; the only thing standing between this and a club-grade platform is sequencing the storage work into bites it can't defer.** So, deliberately small and ordered to plug the leak first:

1. **`git add` the 11 untracked modules** — the only true data-loss exposure in the report, and one command.
2. **Ship the silver Parquet event layer**, reusing `match_index.py`'s proven signature-gated pattern (now that `pyarrow` is declared) — retiring the three standing High-severity risks for the heaviest access path.
3. **Extract the headless build CLI** — `nav.py` already proved the codebase imports headless; this gives the 37 modules their first test harness and unlocks scheduling, the API, and CI simultaneously.
4. Then **DuckDB → medallion → gold-mart API → provider-neutral silver**, exactly as scoped — confident now that scoped work gets done.

The layered design earned the right to evolve storage without rewriting analytics, and this cycle proved the team will take the steps. If a Premier League department adopted this codebase tomorrow, they would commit those 11 files, build the silver layer, and find — as I did — that the analytics to fill three more domains are already written, just waiting for a storage engine that can serve them.

---

## Sources

- [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [Top 5 Football Data Analytics Tools for Clubs & Agents — Comparisonator](https://comparisonator.com/blog/top-5-football-data-analytics-tools-for-clubs-agents)
- [Global Football Software Market Outlook 2025-2032 — IntelMarketResearch](https://www.intelmarketresearch.com/Global-Football-Analysis%20-922)
- [Define multipage apps with st.Page and st.navigation — Streamlit Docs](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [Overview of multipage apps — Streamlit Docs](https://docs.streamlit.io/develop/concepts/multipage-apps/overview)
- [The Lakehouse in Football Analytics — Eyedle](https://eyedle.ai/the-lakehouse-in-football-analytics/)
- [LaLiga uses the Databricks Lakehouse platform — Digitalisation World](https://digitalisationworld.com/news/63327/laliga-uses-the-databricks-lakehouse-platform-to-analyse-competitions-and-create-data-driven-sports)
- [The Rise of Sports Intelligence: How the Lakehouse Turns Tracking Data into Competitive Advantage — Databricks Blog](https://www.databricks.com/blog/rise-sports-intelligence-how-lakehouse-turns-tracking-data-competitive-advantage)
- [Databricks lakehouse a secret weapon for WNBA's Fever — TechTarget](https://www.techtarget.com/searchbusinessanalytics/feature/Databricks-lakehouse-a-secret-weapon-for-WNBAs-Fever)
- [Hawk-Eye Innovations Powers Real-Time Sports Data with Flink and Amazon MSK — AWS](https://aws.amazon.com/blogs/media/hawk-eye-innovations-powers-real-time-sports-data-with-flink-and-amazon-msk/)
- [Using Kafka, ksqlDB, and Quarkus for Real-Time Sports Tracking — Confluent](https://www.confluent.io/blog/using-kafka-ksqldb-quarkus-for-real-time-sports-tracking/)
- [How to Architect a Scalable, Low-Latency Sports Data Pipeline — Data Sports Group / Medium](https://medium.com/@marketing_25315/how-to-architect-a-scalable-low-latency-sports-data-pipeline-for-real-time-apps-385b18246fd8)
- [OpenSTARLab: Open Approach for Spatio-Temporal Agent Data Analysis in Soccer (UIED format) — arXiv](https://arxiv.org/html/2502.02785v2)
- [Hudl StatsBomb — The World's Most Advanced Football Data](https://www.hudl.com/en_gb/products/statsbomb)
- [Introducing the New Hudl StatsBomb with Wyscout Video — Hudl](https://www.hudl.com/blog/hudl-statsbomb-video-wyscout)
- [The tools every football analyst should know in 2026 — Liam Henshaw](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know)
- [Sports Data Integration API — Kitman Labs](https://www.kitmanlabs.com/platform/analytics/)
- [Data Analytics in Sports: Use-Cases, Examples, and Costs — Appinventiv](https://appinventiv.com/blog/data-analytics-in-the-sports-industry/)
- [Data Mesh Architecture](https://www.datamesh-architecture.com/)
