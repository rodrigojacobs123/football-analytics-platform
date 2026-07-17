# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-07-17 (final consolidation, cycle 8) — **supersedes** the two earlier same-day drafts (`manager_sprint_review_2026-07-17.md`, `..._rerun.md`)
**Author:** Analytics Engineering Manager (automated consolidation run)
**Inputs consolidated:**
- Data Analyst — `reports/data_analyst_report_2026-07-17_0643.md` (cycle 8: 5 new metrics + 3 viz upgrades)
- Data Engineer — `reports/data_engineer_brief_2026-06-25.md` (P0–P3: silver hot-path, DuckDB, **tests+CI**, gold marts, schema module)
- Data Architect — `reports/data_architect_report_2026-06-25_0715.md` (governance risk + storage evolution + domain data-products)
- Prior same-day approvals — `manager_sprint_review_2026-07-17.md` and `..._rerun.md`

> **Why a third pass exists.** Two consolidations already ran today. Both correctly led with the untracked-files governance risk, and the rerun's whole point was that the #1 Must-Have *had not been actioned between passes.* I re-verified the tree independently (grep/`git status`, not report claims) and **ratify their lead call — it still holds.** I add exactly **one decisive amendment** they both under-weighted, backed by the tree: **there is still no `tests/` directory at all** — 47 processing modules and the entire silver derivation have *zero* automated verification. For a thesis about to be defended, that is the single largest *credibility* exposure, and it gets promoted into the immediate sprint. This document is decisive and self-contained; treat it as the authoritative cycle-8 approval.

---

## 0. State of the board — verified against the working tree (2026-07-17)

| Item | Tree reality | Read |
|---|---|---|
| **Untracked production code** | **33 files `??`** — 28 in `processing/`+`viz/`, plus the whole silver slice (`data/build.py`, `data/match_index.py`, `data/silver_events.py`) | Data-loss cliff; **3rd cycle** this appears; count grew, not shrank |
| **`tests/` directory** | ❌ **does not exist** | 47 modules + silver derivation have zero regression coverage |
| **Cycle-8 Analyst #1 — Bench-Impact** | ⚠️ `processing/bench_impact.py` **exists (361 lines) but no page imports it** | Built-but-orphaned — needs *wiring + verify*, not a rebuild |
| **Cycle-8 Analyst #2 — Press-Value (exPress)** | ✅ genuinely new (`press_value.py` missing) | Real proposal; thin layer over shipped `xdef.py` |
| **Cycle-8 Analyst #3 — Free-Kick phases** | ✅ new (no `free_kick` branch in `set_pieces.py`) | Real; extends the corner engine |
| **Cycle-8 Analyst #4 — Rest-Defense** | ✅ new (no `rest_defen*` module) | Real; companion to shipped `transitions.py` |
| **Cycle-8 Analyst #5 — xShotDanger** | ✅ new (`shot_danger.py` missing) | Real; additive over `xg.py` |
| **Engineer P1 — DuckDB query layer** | ❌ `data/query.py` **missing** (`duckdb>=1.0` declared) | Half-wired dependency |
| **Engineer P0 — silver hot-path migration** | ⚠️ silver layer exists; most `processing/` still `json.loads` per call | Standing perf item |

**Verdict:** Unlike cycle 7 (where every "new" metric was already on disk), **cycle 8's proposals are genuinely new** — the analyst pipeline is healthy. But the *foundation* is not: a third of the codebase is uncommitted, nothing is tested, and one already-built feature (`bench_impact`) is stranded unwired. MoSCoW discipline caps Must-Have effort at 60% of a project to stay predictable ([Agile Business Consortium](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html)); I size the immediate sprint to ~2.5 dev-days under that cap, spent on foundation + the one nearly-free feature.

---

## 1. Decision context

1. **Untested data pipelines fail *silently* — the worst case for a thesis defense.** "The challenge is not code correctness — it's data correctness," and golden-file regression tests are "one of the highest-ROI investments in any engineering programme" ([Datafold](https://www.datafold.com/blog/automated-regression-testing-data-quality/), [Harness](https://www.harness.io/blog/regression-testing-in-ci-cd-deliver-faster-without-the-fear)). A wrong, un-spot-checked GVM/VAEP number in front of an examiner is worse than no number.
2. **The untracked-files leak is a *process* failure, not a one-off.** It has appeared three cycles running and the count grew to 33. Pay debt continuously, not after an outage ([Metamindz](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize), [Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)).
3. **The metric backlog is near-saturated; the marginal *test* beats the marginal metric.** "If your MVP has 10+ features you're building too much" — cut to essentials ([Aalpha](https://www.aalpha.net/blog/how-to-prioritize-mvp-features/), [Net Solutions](https://www.netsolutions.com/hub/minimum-viable-product/prioritize-features/)). This platform has ~47 modules; correctness and reproducibility are the features now.
4. **The highest-value *new* pages are storage-gated, not analytics-gated.** Cross-competition recruitment/opposition workflows need DuckDB over the silver lake — "a vectorized, columnar SQL engine … fewer bytes over the wire," faster than reading Parquet directly ([DuckDB+Streamlit](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit)). That's the next-sprint unlock, after the foundation is committed and tested.
5. **Don't out-engineer the thesis.** PL clubs run 6-analyst departments at £1–5M/yr and still clean as they ship ([World Football Index](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/), [AnalyiSport](https://analyisport.com/insights/how-are-the-leading-premier-league-clubs-investing-in-data-analysis/)). A one-person TFM that keeps producing uncommitted, untested modules is the exact case a consolidation sprint is for.

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

> Theme: **make the foundation real — commit it, test it, wire the one stranded feature.** ~2.5 dev-days, under the 60% cap.

### 1. Commit the 33 untracked production files + add a load-time schema assertion — *Architecture/Engineering (governance, MUST-HAVE)*
- **What:** In coherent, page/layer-scoped commits, commit every untracked module — the 28 `processing/`+`viz/` files (incl. `bench_impact`, `expected_pass`, `carries`, `action_value`, `transitions`, `aerials`, `viz/sonar`, …) **and the silver slice** (`data/build.py`, `data/match_index.py`, `data/silver_events.py`). As you commit, verify each new module carries its `AME_LEAGUES` page guard, `MIN_APPEARANCES_FOR_RATING` / `MIN_MATCHES_FOR_PREDICTION` thresholds, and "event-data approximation" honesty labels (e.g. "line-break carries (event proxy)", never "packing"). Add the architect's cheap load-time assertion in `event_parser.py` that the `config.py` qualifier IDs actually appear in a sampled event per season (warn on absence).
- **Proposed by:** Data Architect (Risk #1 — "the single highest-exposure, lowest-effort fix in the report").
- **Effort:** **~0.5 day.**
- **User impact:** **HIGH (defensibility).** A thesis whose last several cycles exist only in one working tree is not reproducible — a grader who clones gets none of it, and one `git clean -fd` erases a third of the platform, unrecoverable. It is also a precondition for items #2 and #3 (you cannot gate or golden-file untracked files). **Ships first, non-negotiable.**

### 2. Golden-file test suite + CI on the silver build pipeline — *Data Engineer (P1, MUST-HAVE — my promotion)*
- **What:** Create `tests/` (pytest): (a) silver row derivations — `xg`, `is_penalty` (qualifier **9**, not 22), goalmouth `z=19`→NULL guard, action-vocabulary mapping; (b) a **golden-file check that silver output equals the legacy JSON scan for one fixture match**; (c) the freshness/staleness signature logic. Wire `python -m data.build --max-files 3` + `pytest` into a GitHub Actions workflow that **fails on drift**.
- **Proposed by:** Data Engineer (P1 — "there is no test suite today; the build CLI is the natural harness"). *Neither same-day draft placed this in the immediate sprint; the tree proves it is still absent, so I promote it.*
- **Effort:** **~1 day.**
- **User impact:** **HIGH (correctness + credibility).** 47 modules + the silver derivation currently have zero automated checks; golden tests give "confidence in every ETL refresh with no guessing whether updates broke anything" ([Golden Tests — Medium](https://medium.com/@nidhipandya1606/golden-tests-how-a-small-set-of-real-inputs-helped-me-keep-a-data-driven-api-correct-through-0926b6384e9f)). Keep the merge suite **< 15 min** or it gets bypassed ([SunnyData](https://www.sunnydata.ai/blog/cicd-best-practices-data-projects-validation-testing)) — the 3-file cap enforces that.
- **Implementation notes:** Start narrow — one fixture, the derivations the memory files already document as *real historical bugs* (penalty q9, goalmouth z=19, formation q130). Chase the golden fixture, not coverage %.

### 3. Wire + verify the stranded Bench-Impact feature (module + ribbon) — *Data Analyst cycle-8 #1 (SHOULD-HAVE, nearly free)*
- **What:** `processing/bench_impact.py` exists (361 lines) but **no page imports it.** Wire it into Post-Match behind a `@st.cache_data(ttl=3600)` loader keyed on `(match_id, season)`, add the substitution-impact ribbon (Plotly horizontal bars keyed to sub/red-card interval boundaries — no new dependency), confirm the `MIN_MINUTES` guard fires, and **verify the ribbon in the actual app render, not a headless stub** (cycle 7 proved `mplsoccer.arrows()` passes stubbed `st.pyplot` but ValueErrors in-app).
- **Proposed by:** Data Analyst (cycle 8 #1 + Viz #1 — the longest-open item, flagged unbuilt in cycles 5–7).
- **Effort:** **~0.75 day.**
- **User impact:** **MEDIUM-HIGH.** Answers "which subs change games / who are we carrying" — directly actionable for América's rotation. The analytics are already written; this is pure integration, converting sunk build cost into a visible, defensible feature. No new metric risk.

---

## ✅ APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. DuckDB query layer (`data/query.py`) + one cross-competition aggregate — *Data Engineer P1 / Architect Phase 2*
- **What:** Build the missing `data/query.py` — a thin `con()`/`sql()` helper over the silver Parquet with Hive `league/season` partition pruning + predicate pushdown; prove it by re-implementing one cross-competition aggregate (e.g. player action-value across all comps). DuckDB stays inside `data/`; `processing/` still receives DataFrames.
- **Effort:** **~1 day.** **Impact: HIGH** — the storage key to every cross-league feature; `duckdb>=1.0` is already declared, only the query layer is missing.

### 2. Player-Level Pressing Value (exPress-style) — *Data Analyst cycle-8 #2*
- **What:** Per-player press value = xT denied (reuse the shipped `xdef.py` per-action engine) + a share of 5-second regains (`pressure.pressure_regains_5s`), attributed to the presser, then **league-percentile-ranked** (mandatory per the DEF-rating-is-a-percentile rule). New `processing/press_value.py` + press-value heat map; wired into Player Scouting beside the xDEF bar.
- **Effort:** **~1 day.** **Impact: HIGH** — engine is ~80% built; distinguishes genuine ball-winners from high-volume runners. Label it the *event proxy*, not velocity-based intensity.

### 3. Free-Kick routine phases + direct-FK xG — *Data Analyst cycle-8 #3*
- **What:** Extend `set_pieces.compute_set_piece_phase_value` with a `free_kick` branch (direct-FK xG/conversion; indirect first-vs-second-phase). Add the FK qualifier constant to `config.py` (**don't hardcode**), and **reuse the cycle-6 delivery-contact anchor fix** (`FIRST_CONTACT_SECS=6`) — anchoring on the award timestamp mis-binned 99.7% of xG.
- **Effort:** **~0.75 day.** **Impact: MEDIUM-HIGH** — smallest lift, engine exists, ~25% of non-penalty goals are set pieces.

---

## 🗂️ BACKLOG (Approved but deferred)

- **Silver hot-path migration for the ~5 heaviest `processing/` modules** (Engineer P0) — real warm-cache latency win, but sequence it *after* item #2's tests exist so migration is diff-verifiable (prove byte-stable output). *Both prior drafts put this immediate; I defer it one slot behind the test harness that makes it safe.*
- **Rest-Defense / Counter-Vulnerability index** (Analyst #4) & **xShotDanger context multiplier** (Analyst #5) — genuinely new, proxy-flagged, additive over `transitions.py` / `xg.py`. *Deferred:* MEDIUM value, land when foundation is solid.
- **Gold medallion marts** (Engineer P2) — pre-aggregate season rollups; build through the DuckDB engine once it lands.
- **Versioned schema module** `data/schema.py` + `SCHEMA_VERSION` (Engineer P2) — the golden-file suite covers the near-term correctness gap more cheaply; formalize once tests protect it.
- **Player Similarity & Shortlist page** and **Opposition Dossier (PDF)** (Architect §4) — high club value, storage-gated; follow the DuckDB layer.
- **`st.stop()` refactor in `14_Player_Intelligence.py` + single-option Club selector cleanup** (Engineer P3) — low-impact code health; fold into a future PR.

---

## ⛔ REJECTED / NEEDS MORE RESEARCH

- **Voronoi / pitch-*control* overlay (Analyst Viz #2).** *Needs care — do not ship as "control."* True pitch control needs tracking + velocities; a Voronoi over average event positions is a *territory approximation* only. Allowed **only** if labelled an event approximation; otherwise it misrepresents. Lower priority than the foundation regardless.
- **GNN / TacticAI set pieces, DxT off-ball xT, cover-shadows, space-at-transition.** *Rejected for this stack.* All **tracking-gated** — the analyst themselves bucket these as un-fakeable from Opta events. Building them would violate the platform's tracking-vs-event honesty rule.
- **Generative/LLM scouting (ScoutGPT, EventGPT), FastAPI+React serving, Kafka/Flink streaming.** *Rejected / horizon-only.* Out-engineering a single-author TFM; the architect already scopes streaming and the API as explicit "if a PL club adopted this" north stars. No real-time source exists.
- **OBV/VAEP (`action_value.py`) as a headline thesis number *before validation*.** *Needs evidence.* Built, but VAEP is attacker-biased and vulnerable to next-goal label leakage ([Hudl OBV](https://www.hudl.com/blog/statsbomb-on-ball-value), [VAEP — ResearchGate](https://www.researchgate.net/publication/342798789_VAEP_An_Objective_Approach_to_Valuing_On-the-Ball_Actions_in_Soccer_Extended_Abstract)). Do not present as authoritative until item #2's suite spot-checks its label window.

---

## ⚠️ RISK FLAGS

1. **The untracked-files leak is now a chronic process failure.** Three cycles, count grew to 33, and it went *unactioned between two same-day manager passes.* Beyond immediate #1: adopt commit-per-module-as-built, and let the new CI (immediate #2) refuse to run against a dirty tree so the gap self-surfaces.
2. **Zero test coverage against 47 modules + the silver derivation** — until immediate #2 lands, every number in the app is unverified. Top thesis-defense credibility exposure.
3. **Built-but-orphaned features.** `bench_impact.py` (361 lines) is imported by no page. Modules are being *written* faster than they are *wired and committed* — audit for other stranded code during immediate #1/#3.
4. **DuckDB declared but query layer never built** — `duckdb>=1.0` in `requirements.txt` with no `data/query.py` reads as "done" but isn't. Next-sprint #1 closes it.
5. **Engineering still has no standalone report** — its scope arrives as an architect-authored brief. A coordination blur for a single dev wearing three hats; watch that storage/test work doesn't fall between owners.
6. **Thesis deadline proximity** — scope discipline is paramount; this is precisely why the sprint refuses new metrics and spends the window committing, testing, and wiring what exists.

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

Measured at the end of the 3-day immediate window:

1. **Clean tree, full provenance.** `git status --porcelain | grep -E '^\?\?' | grep '\.py'` returns **0 lines** — all 33 files committed in coherent, page/layer-scoped commits; the load-time schema assertion is present in `event_parser.py`. *(Immediate #1.)*
2. **Green, drift-proof CI.** `pytest` passes locally and in GitHub Actions; the suite includes a golden-file assertion (silver == legacy JSON scan for ≥1 fixture) and explicit `is_penalty` (q9), goalmouth `z=19`→NULL, and `xg` checks; **CI turns red when a derivation is perturbed** (prove it once). Merge suite runs **< 15 min**. *(Immediate #2.)*
3. **Bench-Impact live and correct.** `bench_impact.py` is imported by Post-Match behind a `@st.cache_data` loader; the substitution ribbon renders **in the running app** (not a headless stub); the `MIN_MINUTES` guard is verified on a low-minute player. *(Immediate #3.)*

---

### Sources
- [MoSCoW Prioritisation — Agile Business Consortium (60% cap)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html) · [MVP feature prioritization — Aalpha](https://www.aalpha.net/blog/how-to-prioritize-mvp-features/) · [Net Solutions](https://www.netsolutions.com/hub/minimum-viable-product/prioritize-features/)
- [Technical Debt vs Feature Development — Metamindz](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize) · [Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)
- [Regression Testing in CI/CD — Harness](https://www.harness.io/blog/regression-testing-in-ci-cd-deliver-faster-without-the-fear) · [Automated regression testing for data quality — Datafold](https://www.datafold.com/blog/automated-regression-testing-data-quality/) · [Golden Tests — Medium](https://medium.com/@nidhipandya1606/golden-tests-how-a-small-set-of-real-inputs-helped-me-keep-a-data-driven-api-correct-through-0926b6384e9f) · [CI/CD best practices for data projects — SunnyData](https://www.sunnydata.ai/blog/cicd-best-practices-data-projects-validation-testing)
- [Streamlit caching overview](https://docs.streamlit.io/develop/concepts/architecture/caching) · [Using DuckDB in Streamlit — DuckDB](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit)
- [On-Ball Value (OBV) — Hudl/StatsBomb](https://www.hudl.com/blog/statsbomb-on-ball-value) · [VAEP — ResearchGate](https://www.researchgate.net/publication/342798789_VAEP_An_Objective_Approach_to_Valuing_On-the-Ball_Actions_in_Soccer_Extended_Abstract) · [Substitute Interval Model — Marc Lamberts](https://marclamberts.medium.com/substitute-interval-model-quantifying-the-change-in-win-probability-when-a-player-is-on-or-off-the-031d671f07d5) · [Soccer Analytics Review 2025 — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [Data analytics in EPL — World Football Index](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/) · [PL club data investment — AnalyiSport](https://analyisport.com/insights/how-are-the-leading-premier-league-clubs-investing-in-data-analysis/) · [Top 5 football data tools for clubs — Comparisonator](https://comparisonator.com/blog/top-5-football-data-analytics-tools-for-clubs-agents)
