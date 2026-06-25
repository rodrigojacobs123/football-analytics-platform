# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-25 (consolidation run, cycle 6)
**Author:** Analytics Engineering Manager (automated consolidation run)
**Inputs reviewed:**
- `reports/data_analyst_report_2026-06-24_1511.md` (Analyst cycle 5 — newest)
- `reports/data_architect_report_2026-06-24_1454.md` (Architect, 14:54 run)
- *Data Engineer:* no standalone report filed again this cycle. Engineering scope (hot-path parsing, caching durability, Parquet/DuckDB, dependency hygiene) is carried inside the Architect's risk register and Phase-1 quick wins; I attribute those items to **"Engineering/Architecture"** below. **This is now the second consecutive cycle with no engineering report — flagged in Risks.**
- Prior approvals: `reports/manager_sprint_review_2026-06-24.md`

> **This is the inverse of last cycle.** Cycle 5 delivered 33% (a failed sprint). Cycle 6 delivered **everything on the board plus five unplanned modules** (verified below). That changes the manager's job completely: the constraint is no longer *velocity*, it is **consolidating a windfall before it becomes unreproducible, unverified, slow tech debt.** This sprint is deliberately a **hardening sprint**, not a feature sprint.

---

## 0. State of the board — what the last sprint *actually* shipped (verified against the tree)

I diffed the working tree before approving anything. Every claim below was grep/`wc`-verified this run, not assumed:

| Cycle-5 commitment | Status | Evidence |
|---|---|---|
| **Immediate #1 — xT momentum-flow chart** | ✅ **Shipped** | `viz/charts.py:214` `momentum_chart()`, reads `processing.xt.compute_xt_momentum`. The Must-Have deferred **4×** is finally rendered. |
| **Immediate #2 — `game_state.py`** | ✅ **Shipped & wired** | `processing/game_state.py` (231 lines); imported in `1_Home` and `2_Pre_Match_Analysis`. |
| **Immediate #3 — `xg_chain.py`** | ✅ **Shipped & wired** | `processing/xg_chain.py` (224 lines); imported in `6_Player_Scouting`. |
| Analyst cycle-5 #1 — **GVM goalkeeper model** | ✅ **Shipped & wired** (unplanned-early) | `processing/gk_value.py` (355 lines) + `viz`; wired into `2_Pre_Match` and `6_Player_Scouting`. |
| Analyst cycle-5 #3 — **crossing / cutback xV** | ✅ **Shipped & wired** | `processing/wide_play.py` (269 lines); wired into `4_Tactics`. |
| Analyst cycle-5 #4 — **MOU / xPts manager index** | ✅ **Shipped & wired** | `processing/manager_stats.py:354` MOU block (`match_expected_points`, Poisson xPts vs actual); `12_Manager_Profiles`. |
| Architect #1 risk — **`pyarrow` undeclared** | ✅ **Fixed** | `requirements.txt` now carries `pyarrow>=14.0` with the explanatory comment. The "literal precondition for the roadmap" is retired. |
| *Unplanned extras* | ✅ Shipped | `processing/attack_play.py` (+`viz/attack_play.py`), `processing/player_threats.py`, prior `buildup_play.py` — final-third connection + squad threat indices, wired into Pre/Post-Match. |

**Verdict: 3 of 3 Must-Haves delivered (100%) + 3 of 5 Analyst cycle-5 proposals + the Architect's one true bug, plus 3 unplanned modules.** `processing/` grew **30 → 35 modules** in one window. This is a *passed* sprint by every success metric I set, and the velocity flag from cycle 5 is **cleared.**

**What did NOT ship from Analyst cycle 5 (the only open net-new metrics):**
- **#2 Substitution / bench-impact model** — no module; `tactical_positions.py` references subs only positionally (`until_first_sub`). *The single unshipped HIGH-priority item.*
- **#5 Counter-attack / transition conversion value layer** — `attack_play.py` covers final-third *connection*, not transition *conversion*. Still open.

**Two High-severity Architect items also remain open and now matter more, not less, because of the windfall:**
- The **silver Parquet event layer** (deferred two cycles) — still not built.
- The **cache boundary** the Architect named as Risk #2 ("analytics wired straight into pages with no shared cache loader") is **now realized at scale**: 7 new `processing/` modules are imported directly by pages. Streamlit redraws the scene from scratch on every widget change ([Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching), [SoftwareMill](https://softwaremill.com/pros-and-cons-of-using-streamlit-for-simple-demo-apps/)) — so an uncached `processing.*` call on the hot path recomputes per interaction, per page. This is the dominant *new* latency exposure.

---

## 1. Decision context (why this is a hardening sprint)

1. **The metric backlog is now largely drained.** xT, xGOT, xDEF, PPDA, field-tilt, sequences, game-state, xGChain, GVM, crossing-xV, MOU, momentum, attack-connection, player-threats all ship. The Analyst's own cycle-5 summary says the attacking-event vein is "saturated." When the feature backlog thins, the highest-leverage work shifts to **making what shipped correct, fast, and reproducible** — not bolting on metric #36.
2. **Tech debt is a feedback loop, not a tax.** Industry consensus is to spend **10–30% of capacity** on hardening *continuously*, using each PR to pay a little down ([CTO Magazine](https://ctomagazine.com/tech-debt-vs-feature-velocity-balance/), [Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff), [Metamindz](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize)). This cycle the ratio inverts deliberately: a five-module windfall landed *uncommitted, unverified, and uncached* — clearing that is the right-sized debt payment, and it directly protects velocity going forward.
3. **The 2025/26 dashboard standard rewards trustworthy narratives, not metric count** ([Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/), [Liam Henshaw 2026](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know)). A GVM or MOU number that is *wrong* (un-spot-checked) or *slow* (uncached) is worse than no number for a thesis a reviewer will probe. Correctness + responsiveness is the feature now.
4. **Capacity is still ~2 dev-days of real throughput per 3-day window**, and the MoSCoW 60% Must-Have cap holds ([Agile Business Consortium](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html), [Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)). Cycle 6 *over*-delivered, but I will not bank on that repeating — the plan is sized for the conservative number.
5. **Don't out-engineer the thesis.** Top PL clubs run 6+ analysts at £1–5M/yr ([World Football Index](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/)); they also clean as they ship. A one-person TFM that just produced five unverified modules in three days is exactly the case where a consolidation sprint pays for itself.

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

> Theme: **bank the windfall — make it reproducible, fast, and correct, then add the one HIGH metric still owed.** Two hardening items + one feature. ~2.25 dev-days, under the 60% cap.

### 1. Checkpoint & verify the working tree — commit the 18 uncommitted analytics files — *Engineering/Architecture (git-hygiene risk, now critical)*
- **What:** Commit (in coherent, page-scoped commits) the 18 uncommitted/untracked analytics files — `processing/{game_state, xg_chain, gk_value, wide_play, attack_play, player_threats, buildup_play}.py`, `viz/{attack_play, buildup}.py`, the momentum addition to `viz/charts.py`, the MOU edit to `manager_stats.py`, and the touched pages. As part of the commit, **verify each new module carries its `AME_LEAGUES` page guard, `MIN_APPEARANCES_FOR_RATING` / `MIN_MATCHES_FOR_PREDICTION` thresholds, and the required "event-data approximation" labels.**
- **Proposed by (conceptually):** Engineering/Architecture (last cycle's process gate, now a first-class deliverable).
- **Effort:** **~0.5 day.**
- **User impact:** **HIGH (defensibility).** A thesis built on five modules that exist only in one machine's working tree is not reproducible — a grader reproducing the repo gets nothing of this cycle's work. This makes the whole windfall real. It is also the precondition for the cache audit below (you cannot safely refactor an uncommitted file).
- **Implementation notes:** Last cycle this was a "gate"; it was not met (the tree is still dirty), which is *why* the volume is now 18 files. **This ships first and is non-negotiable.** One commit per page-cluster keeps the thesis git history legible.

### 2. Cache-boundary hardening of the 7 page-wired modules — *Engineering/Architecture (Architect Risk #2, now realized)*
- **What:** Audit every direct `processing.*` import in `2_Pre_Match`, `3_Post_Match`, `4_Tactics`, `6_Player_Scouting`, `12_Manager_Profiles`. Wrap each entry point in a `@st.cache_data(ttl=3600)` loader keyed on `(match_id / team_id, season)`, so the build-up, GVM, wide-play, attack-play, player-threats, game-state, and xGChain computations run **once per input, not once per widget interaction per page.** Codify the rule the Architect asked for: *pages call cached loaders, never raw `processing.*` on the hot path.*
- **Proposed by:** Data Architect (Phase-1 quick win / Risk #2).
- **Effort:** **~0.75 day.**
- **User impact:** **MEDIUM-HIGH.** Streamlit reruns the whole script on every interaction; five of these modules parse event frames. Today a single dropdown change on Pre-Match can recompute GVM + attack-play + player-threats + game-state from scratch. Caching at the seam is the single biggest responsiveness win available without touching storage, and it directly answers the framework's known weakness ([Streamlit caching docs](https://docs.streamlit.io/develop/concepts/architecture/caching)).
- **Implementation notes:** No page-layout changes, no `processing/` logic changes — only a loader wrapper at the import seam. Spot-measure one page's interaction latency before/after to confirm the recompute is gone. This is the natural "clean as you ship" payment for the five modules just merged.

### 3. Substitution / bench-impact model (`processing/substitution_impact.py`) → `12_Manager_Profiles` + `14_Player_Intelligence` — *Analyst cycle-5 #2, the one unshipped HIGH*
- **What:** Quantify each player's effect *as a substitution event*: build on-pitch intervals from line-ups + sub events (`typeId 18` off / `19` on), attribute team xG/xT accumulated per interval, and compute **on↔off swing** (team xT-rate while on vs off) plus a **bench-impact** number conditioned on game-state.
- **Proposed by:** Data Analyst (cycle 5, metric #2, Priority HIGH).
- **Effort:** **~1 day.** Pure pandas; **pairs directly with the now-shipped `game_state.py`** (conditioning a sub on chasing/level/leading is the cycle-4 tagger reused) and the now-shipped MOU layer on the same page.
- **User impact:** **HIGH.** `12_Manager_Profiles` just gained MOU/xPts; "do this coach's subs move the needle?" is the natural companion question and the page has no bench analytics. Also lights up a "super-sub / impact-sub" badge on Player Intelligence.
- **Implementation notes:** Bench minutes are the thinnest sample in the app — **aggregate across the season, respect `MIN_MATCHES_FOR_PREDICTION`, and show confidence; never trust a single-match split.** Ship with a 1-match spot-check (an interval's attributed xT reconciles to the events inside it) as part of the deliverable. Per [[def-rating-is-league-percentile]], surface as its own number, not blended into FC ratings.

> **Capacity check:** 0.5 + 0.75 + 1.0 = **~2.25 dev-days** against a 3-day window — under the 60% cap with slack. Items 1 and 2 are the certain hardening wins and **must** land; item 3 is the designated drop if anything slips.

---

## ✅ APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. Silver Parquet event layer at the loader seam (`silver/events/<league>/<season>/<match_id>.parquet`) — *Engineering/Architecture (Phase-1, deferred 2×, now unblocked)*
- **What:** Run `event_parser.py` once per match in a signature-gated build step → columnar Parquet. `load_player_events_season()` (`data/loader.py:265`) then scans typed columns with a `player_id` predicate instead of `json.loads`-ing every match. Mirror the proven `match_index.py` signature-gated rebuild pattern.
- **Proposed by:** Data Architect (Phase-1 top recommendation).
- **Effort:** **~1.5–2 days.** Reuses an existing in-tree pattern; **`pyarrow` is now declared, so the precondition is finally met.**
- **User impact:** **MEDIUM-HIGH.** Retires the three standing High risks (cold-start full-tree glob, volatile per-process cache, JSON-as-query-engine) for the heaviest access path, and survives restart/redeploy. The honest, right-sized slice of the lakehouse vision — *not* DuckDB/medallion. Per §5 of the Architect report, model the silver schema **provider-neutral** (semantic `action` column + raw `opta_type_id`) and **bake in the gotchas** (`goalmouth_z` NULL when raw z==19 per [[goalmouth-z-placeholder]]; `is_penalty` from qualifier 9 not 22) so no future consumer can re-introduce them.
- **Implementation notes:** Wrap at the loader seam — pages and `processing/` untouched. Tag each artifact with the source `partidos/` signature for self-invalidation.

### 2. Counter-attack / transition conversion value layer (`processing/transition_value.py`) → `4_Tactics` + `2_Pre_Match` — *Analyst cycle-5 #5*
- **What:** A conversion layer on the existing sequence/phase detection: per team per 90 — counters initiated (fast, direct, forward sequences from an own-half regain), their shot & xG conversion, and the defensive mirror (transitions conceded, xG conceded). Report settled-vs-transition xG side by side.
- **Proposed by:** Data Analyst (cycle 5, metric #5).
- **Effort:** **~1 day.** Arithmetic over already-built `sequences.py` + `game_phases.py` + `extract_shots()`; no new model.
- **User impact:** **MEDIUM-HIGH.** Answers a concrete coaching question for América ("how dangerous on the break, how exposed to it?") and completes the cycle-5 metric set. **Honesty note:** ship the event-data sequence version; flag full Dynamic xT (off-ball) as tracking-only future work.

### 3. Governance bundle: self-documenting nav registry + load-time schema assertion + `processing/` manifest — *Architect Phase-1 governance*
- **What:** (a) Have `11_Data_Sources` render the live `st.navigation` registry (count + titles + paths) so docs can't drift. (b) Add a load-time assertion in `event_parser.py` that the `config.py` qualifier IDs actually appear in a sampled event per season; warn on absence. (c) A one-page metric→module→page manifest.
- **Proposed by:** Data Architect (Phase-1 / governance; Risks #3–#6).
- **Effort:** **~1 day combined.** No user-facing surface; pure thesis-defensibility + drift insurance — cheap value against a `processing/` layer that just jumped to 35 modules.
- **User impact:** **MEDIUM.** Retires the page-registry-drift risk, the silent-feed-drift risk across 2015–2026 seasons, and makes "which page breaks if I change xG?" answerable — the metric-sprawl flag that climbs every cycle.

> **Capacity check:** ~3.5–4.5 dev-days across a 6-day window. Item 1 (Parquet) is the centrepiece and the designated keep; items 2–3 are independent and either can roll to backlog without blocking item 1.

---

## 📋 BACKLOG (Approved but deferred)

| Item | Source | Why deferred |
|---|---|---|
| **VAEP / OBV unified action value (model-free fallback)** | Analyst (carry-over) | *Top of backlog.* The clearest 2025/26 throughline and a thesis centrepiece (~2–3 days), nets the already-built `xt`/`xdef`/`xgot`/`sequences`. **Promote once the consolidation + Parquet land** — it should sit on the silver layer, not raw JSON. Own column, never blended into FC ratings ([[def-rating-is-league-percentile]]). |
| **Aerial duel win-probability model (HOPS-style)** | Analyst (cycle 4 #3) | Real bias fix in `player_ratings.py`, but ~2 days of model work behind the cheap reuse wins. Must guard `goalmouth_z=19` ([[goalmouth-z-placeholder]]). |
| **Expected Pass (xP) + Passes Above Expected (PAx)** | Analyst (carry-over) | Needs a *trained* model; upstream blocker for pass risk/reward. Promote after VAEP fallback proves the action-value layer pays. |
| **Pass risk/reward decomposition** | Analyst (cycle 4 #4) | Needs `P(complete)` from xP first; pure arithmetic afterward. |
| **Team-shape compactness / width / hull + Tactics overlay** | Analyst (cycle 4 #1 + viz) | ~1.5 days; `scipy` hull. Label as **event-location hull**, not pitch control. Slot after governance bundle frees a tactics slot. |
| **Line-breaking passes / packing proxy + `extract_carries()`** | Analyst (carry-overs) | Approximable from team-shape line-height; new event-parser work. Good, not urgent. |
| **Pass sonars → `4_Tactics`** | Analyst (cycle 4 viz #2) | Net-new tactics surface, no correctness payoff. |
| **Attacking set-piece xG + Set-Piece Intelligence page** | Analyst + Architect §4 | Set pieces ≈23% of goals; `set_pieces.py` exists but only corner *defense* shows. Discrete model + page. |
| **Recruitment / Player-Similarity & Shortlist workspace** | Architect §4 | The highest-value *new page* for a club; `find_similar_players` already exists (`player_profile.py:360`). Cross-competition scan is responsive **only after** the silver Parquet layer (Next #1) — strong promote candidate once that's in. |
| **Opposition Dossier PDF generator** | Architect §4 | Composes `formations`/`pressure`/`buildup_play`/`set_pieces` into the artifact analysts hand coaches. Multi-day net-new; sequence after the metric layer settles. |

---

## ❌ REJECTED / NEEDS MORE RESEARCH

| Item | Source | Ruling |
|---|---|---|
| **Full DuckDB lakehouse — medallion bronze/silver/gold + headless build CLI** | Architect (Phase 2) | **Not now.** Right architecture and the right *future-work chapter*; a multi-week query-engine rewrite against ~47 GB is disproportionate for one developer. The approved silver-Parquet slice (Next #1) captures the latency win at the loader seam without the DuckDB/medallion commitment. |
| **FastAPI service split · multi-tenant/role auth · Kafka/Flink streaming** | Architect (Phase 3) | **Rejected for TFM scope.** PL-department infrastructure (£1–5M/yr, 6+ analysts — [World Football Index](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/)). No real users, no live feed. Keep as the "if a PL club adopted this" north-star paragraph. |
| **Trained `P(score\|state)` VAEP / xP models** | Analyst | **Deferred to season-end, not approved.** Ship the model-free fallbacks first; train only once more matches accumulate and early-season noise subsides. |
| **TacticAI-style GNN corner setups · Dynamic xT (off-ball) · pitch control / Voronoi · pressing-intensity via velocities** | Analyst (flagged honestly) | **Rejected (tracking-data-impossible).** All require positional/freeze-frame data we don't license. One honest "future work with tracking data" note beats a faked event-data version — and protects academic integrity. |
| **Generative "matches as language" transformers (ScoutGPT-style)** | Analyst (emerging) | **Needs more research / out of scope.** Frontier research direction, not a near-term TFM build. Note as direction only. |
| **Replace `injuries_synthetic.py` with a real availability/load model** | Architect §4 | **Needs more research.** Requires GPS/biometric load data the project lacks. Keep the synthetic placeholder + timeline UI. |

---

## ⚠️ RISK FLAGS (monitor)

1. **🔴 Git hygiene — 18 uncommitted analytics files (NEW top risk).** Five modules and a momentum chart exist only in the working tree. Until Immediate #1 lands, **this cycle's entire output is at risk of loss and is not reproducible for the thesis.** This was last cycle's unmet "gate"; it is now a first-class deliverable because the volume tripled.
2. **🔴 Cache boundary realized at scale (Architect Risk #2).** 7 `processing/` modules are imported directly by pages with no shared cache loader. Streamlit redraws from scratch on every interaction → repeated full recomputation. Mitigated by Immediate #2; until then, treat page latency as degrading with each module added.
3. **🟠 Correctness debt — five modules shipped fast, none spot-checked on record.** GVM weights, MOU xPts summation, xGChain double-counting, crossing→shot linkage windows, and attack-play channel assignment all merged without a recorded 1-match validation. A *wrong* headline number is worse than none for a thesis a reviewer will probe. **Action: a 1-match spot-check per new module, retrofitted during the commit pass (Immediate #1).**
4. **🟠 No Data Engineer report — 2 cycles running.** Engineering judgement is being inferred entirely from the Architect's risk register. If a dedicated engineering perspective exists, it should file; if not, acknowledge in the thesis that engineering and architecture are one role here.
5. **🟠 Cold-start glob + volatile per-process cache (R1/R2).** The defining scalability ceiling; `load_player_events_season()` re-parses every JSON on a cache miss. Mitigated only by Next-Sprint #1 (silver Parquet) — now genuinely unblocked since `pyarrow` is declared.
6. **🟡 Metric sprawl — 35 `processing/` modules, no registry.** Up from 30 in one cycle. "Which page breaks if I change xG?" is still grep-only. Governance bundle (Next #3) addresses it; the count climbs every cycle.
7. **🟡 FC-rating blending constraint** ([[def-rating-is-league-percentile]]). Event-derived team-only metrics (xGChain, GVM distribution-xT, substitution swing) cannot fold into FC PAC/SHO/DEF without a league-wide scan. Verify the shipped GVM and xGChain kept their own columns.
8. **🟡 Goalmouth z=19 placeholder** ([[goalmouth-z-placeholder]]). Qualifier 103 uses z=19 as "height not recorded" on ~40% of on-target shots — **verify the shipped `gk_value.py` / `xgot.py` shot-stopping guards it**, since GVM leans on xGOT.
9. **🟡 Game-state bucket starvation.** The now-shipped `game_state.py` splits shrink samples fast; the substitution model (Immediate #3) conditions on the same buckets — enforce `MIN_MATCHES_FOR_PREDICTION` and grey out thin states.
10. **🟡 Event-data honesty labels.** Every shipped approximation (build-up, attack-play, wide-play, future hull/transition) must be labelled an *event-data approximation*, never tracking-derived. A TFM reviewer will probe this — verify during the commit pass.

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

Measured at the close of the 3-day Immediate window:

1. **Working tree banked & guarded (the real lesson of cycles 5–6).** `git status` shows **zero uncommitted analytics files**; the five new modules + momentum chart + MOU edit are committed in coherent, page-scoped commits. A spot inspection confirms each new module carries its `AME_LEAGUES` guard, the minimum-sample thresholds, and an event-data-approximation label. **The thesis is reproducible from a clean clone.**
2. **Cache boundary closed and measured.** Every `processing.*` entry point used by a page sits behind a `@st.cache_data` loader keyed on its match/team input. A before/after measurement on one page (e.g. change the match dropdown on `2_Pre_Match`) confirms the heavy modules **do not recompute** on a second interaction — load time is flat, not re-incurred.
3. **Substitution model live, conditioned, and spot-checked (stretch).** `processing/substitution_impact.py` exists; on↔off swing renders on `12_Manager_Profiles` with states below `MIN_MATCHES_FOR_PREDICTION` greyed; a 1-match spot-check confirms an on-pitch interval's attributed xT reconciles to the events inside it (no leakage across sub boundaries).

**Sprint passes** if Metrics 1 and 2 (the two hardening wins) land with no page-load regression. Metric 3 is the stretch — if it slips it rolls to the front of Days 4–9, but **the windfall must be banked and cached this cycle.** Shipping five modules and then losing or slowing them is the failure mode this sprint exists to prevent.

---

## Sources

**Prioritization & process**
- [Agile Business Consortium — MoSCoW Prioritisation (DSDM, 60% Must-Have cap)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html) · [MoSCoW method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method) · [ProductPlan — MoSCoW](https://www.productplan.com/glossary/moscow-prioritization) · [IIA — A Framework for Prioritizing Analytics Efforts](https://iianalytics.com/community/blog/a-framework-for-prioritizing-analytics-efforts)
- [CTO Magazine — Tech Debt vs Feature Velocity](https://ctomagazine.com/tech-debt-vs-feature-velocity-balance/) · [Logiciel — Technical Debt vs Feature Development](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff) · [Metamindz — Tech Debt vs Feature Development](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize)

**Streamlit / engineering**
- [Streamlit — Caching overview](https://docs.streamlit.io/develop/concepts/architecture/caching) · [SoftwareMill — Pros and cons of Streamlit](https://softwaremill.com/pros-and-cons-of-using-streamlit-for-simple-demo-apps/) · [DigitalDefynd — Pros & cons of Streamlit 2026](https://digitaldefynd.com/IQ/pros-cons-of-streamlit/)

**Football analytics standard & club context**
- [Sportmonks — How Football Clubs Use Data Analytics](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/) · [Liam Henshaw — Tools Every Football Analyst Should Know (2026)](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know) · [World Football Index — Data Analytics in the EPL](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/) · [Premier League — Kitman Labs Football Intelligence Platform](https://www.premierleague.com/en/news/3750826) · [Sky Sports — AI in football (PLAIER)](https://www.skysports.com/football/news/11095/13302459/ai-revolution-in-football-how-plaier-is-helping-premier-league-clubs-make-better-decisions)

**Internal inputs:** `reports/data_analyst_report_2026-06-24_1511.md`, `reports/data_architect_report_2026-06-24_1454.md`, `reports/manager_sprint_review_2026-06-24.md`; memory notes [[implemented-analytics-metrics]], [[def-rating-is-league-percentile]], [[goalmouth-z-placeholder]], [[formation-position-mapping]].
