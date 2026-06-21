# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-21
**Author:** Analytics Engineering Manager (automated consolidation run)
**Inputs reviewed:**
- `reports/data_analyst_report_2026-06-21.md` (cycle 2) and `reports/data_analyst_report_2026-06-21_0856.md` (cycle 3)
- `reports/data_architect_report_2026-06-21.md`
- *Data Engineer:* no standalone report was filed this cycle. The engineering scope (caching, Pandas hot-path, Parquet/DuckDB) is carried inside the Architect's risk register (R1–R8) and Phase-1 quick wins; I attribute those items to "Engineering/Architecture" below.

---

## Decision context (why these calls)

Three constraints shaped every approval:

1. **Single developer, thesis timeline.** I applied MoSCoW with a DSDM-style cap: **Must-Haves ≤ 60% of capacity**, a real pool of Could-Haves, and an explicit Won't-Have list so scope is honest, not aspirational. ([Agile Business Consortium — MoSCoW](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html))
2. **The metric backlog is nearly exhausted; correctness debt is not.** The Analyst confirms xT, xGOT, xDEF, sequences, field-tilt all shipped. The remaining analytics wins are now *cheap integrative reuse*. Meanwhile the Architect flags a live **correctness** bug (fuzzy match-ID resolution, R3) that silently mis-resolves matches outside Liga MX — that outranks any new metric.
3. **Don't out-engineer the thesis.** Industry context confirms the value of the lakehouse direction (DuckDB-over-Parquet, columnar pushdown) — but PL clubs spending £1–5M/yr is not the comparison class for a one-person TFM. We "do both" feature + debt at the **10–20% refactor allocation** the industry recommends, not a storage rewrite. ([Logiciel — tech debt vs feature dev](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff), [DigitalDefynd — Streamlit pros/cons](https://digitaldefynd.com/IQ/pros-cons-of-streamlit/))

**Guiding principle for what "must-have" means here:** the 2025 dashboard standard is *distilling data into clear, comparable, percentile-based narratives* (last-5 form, player comparison, progressive actions) — not adding raw metric count. Approvals favour items that make existing pages more decision-useful over net-new surface area. ([Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/), [Liam Henshaw — analyst tools 2026](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know))

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

### 1. xGChain & xGBuildup — possession-xG credit per player
- **What:** Credit each shot-ending possession's xG to *every* player who touched the ball in it. `xGChain` = total; `xGBuildup` = excluding shooter + assister (isolates deep build-up contributors). New `processing/xg_chain.py`.
- **Proposed by (conceptually):** Data Analyst (cycle 3, metric #1, Priority HIGH).
- **Effort:** ~1 day. Pure pandas over the **already-built** `sequences.py` + `extract_shots()`. No model, no new dependencies.
- **User impact:** HIGH. Surfaces América's unsung progressors on `6_Player_Scouting` — the single most "recruitment-selling" view, and exactly the percentile-comparison narrative the 2025 dashboard standard rewards. Today `goal_buildup.py` only traces *goals*, crediting no one systematically.
- **Implementation notes:** Attach each shot's xG (`QUAL_XG=395`) to its sequence; sum per distinct `player_id`; per-90 with the `MIN_APPEARANCES_FOR_RATING` guard. Ship with the xGChain-vs-xGBuildup credit-bar (Analyst viz #3) in the same PR — it's free once the numbers exist.

### 2. xT / possession-value momentum-flow chart (Post-Match)
- **What:** Cumulative team-xT area chart over match time (red América vs grey opponent) — the "who was on top, when" companion to the existing xG race.
- **Proposed by:** Data Analyst (viz #1 — recommended in **three** consecutive cycles, still unbuilt).
- **Effort:** ~half a day. Pure `viz/charts.py` assembly over per-event xT already produced by `xt.py`.
- **User impact:** MEDIUM-HIGH, highest value-per-hour on the board. Completes the Post-Match narrative and is a clean thesis figure.
- **Implementation notes:** Reuse the dark América palette and the construction of the existing xG race. No new processing. Closing a thrice-deferred item also restores credibility to the backlog.

### 3. Match index + ID-based resolution + loud failure (correctness debt)
- **What:** Generate `match_index.parquet` once per league/season (match_id, date, stage, home_id, away_id, scores, file_path) and have loaders resolve **by ID**, retiring `_team_name_match`/`_short_team_name` fuzzy heuristics. Replace bare `except: continue` in the glob loops with structured logging surfaced on `11_Data_Sources`.
- **Proposed by:** Data Architect / Engineering (P1.1 + P1.2; fixes risks **R3** and partially **R1**).
- **Effort:** ~1–1.5 days.
- **User impact:** HIGH (correctness, not cosmetics). R3 *silently* mis-resolves matches in MLS/USL/CONCACAF where the Liga-MX name dictionary doesn't apply — wrong data is worse than slow data, and indefensible in a thesis. Loud failure turns invisible data loss into a visible diagnostic.
- **Implementation notes:** Build from `matches.json` + `partidos/` filenames via `data.paths`/`data.loader` (respect the layering — no JSON parsing in pages). This is the foundation the deferred Parquet work would build on, so it is not throwaway effort.

> **Capacity check:** ~3 dev-days across two ~1-day analytics wins and one correctness fix — within a 3-day sprint for a focused developer. Items 1–2 are independent and can interleave with item 3.

---

## ✅ APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. VAEP / OBV — unified action value (fallback mode)
- **What:** One netted threat-currency value per on-ball action: offensive `xT[B] − xT[A]` minus defensive value conceded, with shots valued as `xGOT − xT[start]`. New `processing/action_value.py`; feed a per-90 "impact" column into `player_ratings.py`.
- **Proposed by:** Data Analyst (cycle 3, metric #1, HIGH).
- **Effort:** ~2–3 days (fallback mode only — **no** trained model). Nets the *already-built* `xt.py`, `xdef.py`, `xgot.py`, `sequences.py`.
- **User impact:** HIGH. Collapses the metric zoo into the single number that is the clearest 2025–26 industry throughline (StatsBomb OBV on 140+ comps). Strong thesis centrepiece.
- **Implementation notes:** Start with the xT/xDEF-label fallback that ships in days. **Do not** attempt the trained `P(score|state)` model this sprint (see Rejected). Heed the `def-rating-is-league-percentile` memo: a netted impact score is fine as its own column, but cannot be blended into FC PAC/SHO/… ratings without a league-wide scan.

### 2. Durable disk-backed cache for the hot loaders
- **What:** Persist results of `load_player_events_season` / season aggregations to `cache/*.parquet` (or joblib `Memory`) keyed on inputs; add `st.cache_resource` for read-only singletons (name maps, the new match index).
- **Proposed by:** Data Architect / Engineering (P1.3 + P1.4; addresses **R1/R2**).
- **Effort:** ~1.5–2 days.
- **User impact:** MEDIUM-HIGH. Streamlit's per-process `@st.cache_data` is lost on every restart/deploy; cold start re-parses the tree. A persistent cache means the first run warms it for every later session — the difference between a demo and a usable tool. Directly mitigates the single-process bottleneck the Streamlit literature flags. ([Towards Data Science — optimise Streamlit deployment](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/))
- **Implementation notes:** Wrap at the existing loader seam — no page changes. This is the *honest, right-sized* slice of the Architect's Phase-2 vision; it captures most of the latency win without committing to the full lakehouse.

### 3. Possession-adjustment completion + pizza-chart hardening (defensibility bundle)
- **What:** (a) Apply the existing `PADJ_BASELINE` to the `DEF` rating in `player_ratings.py` (still on raw counts). (b) Harden `viz/pizza.py`: percentiles not raw counts, attack/defence slice grouping, usage+outcome mix.
- **Proposed by:** Data Analyst (possession-adjust + pizza hardening, both flagged "cheap, high value-per-effort").
- **Effort:** ~1 day combined (~30 lines + a viz audit).
- **User impact:** MEDIUM. Strips América's high-possession bias from defensive ratings (honest cross-team scouting) and aligns the headline player chart with 2025 best practice — both directly improve TFM defensibility for low cost.
- **Implementation notes:** PAdj must respect the `DEF rating is a league percentile` constraint — adjust the counts that feed the percentile, don't double-normalise.

---

## 📋 BACKLOG (Approved but deferred)

| Item | Source | Why deferred |
|---|---|---|
| **Expected Pass (xP) + Passes Above Expected (PAx)** | Analyst | Genuinely valuable (the main outstanding "above-expected" residual) but needs a *trained* model — more effort than the model-free wins above. Promote next cycle once VAEP fallback proves the action-value layer. |
| **Packing / line-break proxy + `extract_carries()`** | Analyst | Requires new event-parser work (`extract_carries`) and must be clearly labelled an event-data *approximation*. Good, not urgent; pairs with progression work. |
| **Attacking set-piece xG + corner-routine threat** | Analyst | High tactical relevance (set pieces ≈23% of goals this season) but a discrete new model surface. Build after the integrative layer settles. |
| **Convex-hull / Voronoi space-control snapshot** | Analyst | mplsoccer 1.6 makes it cheap, but it's net-new tactics surface with a mandatory "static approximation" caveat. Could-have, not must. |
| **Processing registry/manifest (`processing/registry.py`)** | Architect (P1.5) | Cheap insurance against metric sprawl (R6) and self-documents for the thesis — but yields no user-facing value. Slot into a low-energy day. |
| **Recruitment Shortlist Builder / Opposition Report Generator** | Architect (§4) | The highest-value *new pages* for a club, and feature vectors already exist (`archetypes.py`, `player_ratings.py`). Deferred only because they're multi-day net-new pages; strong candidate once the metric layer is final. |

---

## ❌ REJECTED / NEEDS MORE RESEARCH

| Item | Source | Ruling |
|---|---|---|
| **Full Parquet + DuckDB lakehouse ETL (medallion bronze/silver/gold)** | Architect (Phase 2) | **Not now.** Architecturally correct and the right *future-work* chapter for the thesis, but a multi-week storage rewrite against 47 GB is disproportionate to a single-developer TFM. The approved match-index + disk cache capture the practical latency/correctness wins. Document as "future work"; do not start this cycle. |
| **FastAPI service split, multi-tenancy/auth, Kafka/Flink real-time path** | Architect (Phase 3) | **Rejected for TFM scope.** Premier-League-grade infrastructure (clubs at £1–5M/yr) is the wrong comparison class. No real users, no live-data requirement. |
| **Trained `P(score|state)` VAEP model** | Analyst | **Deferred to season-end**, not this approval. Ship the model-free fallback first; only invest in training once more match data has accumulated and early-season noise subsides. |
| **Tracking/360, off-ball GNN valuation, Opta Vision-style metrics** | Analyst / Architect | **Rejected (aspirational).** Tracking data is not licensed; these are event-data-impossible. Keep flagged as "out of reach," not on any sprint. |
| **Replace `injuries_synthetic.py` with a real availability/load model** | Architect (§4) | **Needs more research.** Requires GPS/load data the project doesn't have. Keep the synthetic placeholder + timeline UI; revisit only if a data source appears. |

---

## ⚠️ RISK FLAGS (monitor)

1. **R3 — fuzzy match-ID resolution (active correctness bug).** Until the match index ships (Immediate #3), any MLS/USL/CONCACAF view may silently mis-resolve matches. Treat current cross-competition numbers as suspect until verified.
2. **R1/R2 — cold-start full-tree glob + non-durable cache.** The defining scalability ceiling. Partially addressed by Next-Sprint #2; the full fix is the deferred lakehouse. Watch for multi-second cold loads on restart.
3. **Silent `except: continue` in glob loops.** Bad feed files currently vanish invisibly. Fixed in Immediate #3 — until then, data completeness is unverifiable.
4. **Metric sprawl without a registry (R6).** 24 processing modules, no metric→module→page manifest. "Which page breaks if I change xG?" is currently un-answerable without grep. Backlog item P1.5.
5. **Goalmouth z=19 placeholder** (`goalmouth-z-placeholder` memo): Opta qualifier 103 uses z=19 as "height not recorded" on ~40% of on-target shots. Any future xGOT/placement viz must guard this — verify the shipped `xgot.py` already does.
6. **FC-rating blending constraint** (`def-rating-is-league-percentile` memo): event-derived team-only metrics (xDEF, VAEP impact) cannot be folded into FC PAC/SHO/DEF ratings without a league-wide scan. Applies directly to VAEP (Next #1) and PAdj (Next #3).
7. **Academic defensibility.** Every event-data approximation (static Voronoi, packing proxy, model-free VAEP) must be labelled as such in-app and in the thesis. A reviewer will probe these.

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

Measured at the close of the 3-day immediate window:

1. **xGChain/xGBuildup live and correct.** `processing/xg_chain.py` exists; per-90 xGChain and xGBuildup render on `6_Player_Scouting` (with the credit-bar) for **every** squad player above `MIN_APPEARANCES_FOR_RATING`, and a manual spot-check on 1 match confirms each shot's xG is credited to exactly the players in its sequence (no double-counting, shooter+assister correctly excluded from xGBuildup).
2. **xT momentum chart renders without error** on `3_Post_Match_Analysis` for any selected match, on the same time axis as the existing xG race, with cumulative end-values reconciling to each side's total event-xT.
3. **100% ID-based match resolution, zero silent failures.** `match_index.parquet` resolves **all** matches across **all** competitions by ID with **no** fuzzy-string fallback invoked (instrument a counter → must read 0), and the count + filenames of any unparseable files appear on `11_Data_Sources` instead of being swallowed.

Sprint is a **success** if all three Immediate items meet these criteria with no regression to existing page load. Miss on any one Must-Have = sprint not delivered (DSDM rule), and that item rolls to the front of Days 4–9.

---

## Sources

- [Agile Business Consortium — MoSCoW Prioritisation (DSDM)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html) · [What is MoSCoW Prioritization](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/)
- [Logiciel — Technical Debt vs Feature Development](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)
- [DigitalDefynd — Pros & Cons of Streamlit (2026)](https://digitaldefynd.com/IQ/pros-cons-of-streamlit/) · [Towards Data Science — Optimize Streamlit Deployment](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/) · [Streamlit Apps That Scale — Medium](https://medium.com/@hadiyolworld007/streamlit-apps-that-scale-lessons-from-real-projects-8237f1ae6729)
- [Sportmonks — How Football Clubs Use Data Analytics](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/) · [Liam Henshaw — Tools Every Football Analyst Should Know (2026)](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know)
- [PremierLeagueNow — Data Analytics & Recruitment](https://premierleaguenow.co.uk/2025/10/30/how-data-analytics-is-revolutionizing-player-recruitment-in-the-premier-league/) · [Sportblog — Premier League Data Revolution](https://www.sportblog-online.de/en/premier-league-data-revolution-tactical-analysts/)
- Internal inputs: `reports/data_analyst_report_2026-06-21.md`, `reports/data_analyst_report_2026-06-21_0856.md`, `reports/data_architect_report_2026-06-21.md`
