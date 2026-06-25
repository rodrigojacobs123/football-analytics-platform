# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-24 (consolidation run, cycle 5)
**Author:** Analytics Engineering Manager (automated consolidation run)
**Inputs reviewed:**
- `reports/data_analyst_report_2026-06-21_0911.md` (Analyst cycle 4 — newest)
- `reports/data_architect_report_2026-06-21_0910.md` (Architect, 09:10 run)
- *Data Engineer:* no standalone report filed this cycle. Engineering scope (hot-path parsing, caching durability, Parquet/DuckDB) is carried inside the Architect's risk register (R1–R7) and Phase-1 quick wins; I attribute those items to **"Engineering/Architecture"** below.
- Prior approvals: `reports/manager_sprint_review_2026-06-21.md`

> **Correction note.** This report corrects an earlier same-day draft that recorded xGChain/xGBuildup as "shipped." On verification that was wrong — see §0. The delivery verdict, the Immediate sprint, and the success metrics below are re-based on the true tree state.

---

## 0. State of the board — what the last sprint *actually* shipped (verified)

I diffed the working tree against the three Must-Haves approved on 2026-06-21 **before** approving anything new. Don't approve what's already built — and don't credit what isn't:

| Last sprint's Must-Have | Status | Evidence |
|---|---|---|
| **#3 Match index + ID resolution** | ✅ **Shipped** | `data/match_index.py` present; Architect §1.2 credits it as the new persistence tier. |
| **#1 xGChain / xGBuildup** | ❌ **NOT shipped** | No `processing/xg_chain.py`. The new `processing/buildup_play.py` is a *different* metric — its own docstring says "Build-up / playing-out-from-the-back analysis… **Distinct from `goal_buildup.py`**", channel×style exit-pass distribution. It does **not** credit shot-xG to possession participants. This was **unplanned scope**, not the approved deliverable. |
| **#2 xT momentum-flow chart** | ❌ **NOT shipped** | `grep momentum viz/*.py` → 0 hits. Now deferred **four** consecutive cycles. |

**Verdict: 1 of 3 Must-Haves delivered (33%), plus one unplanned build-up module.** That is a *failed* sprint by the DSDM rule I set last cycle, and the root cause is mine: I over-loaded a single-developer timebox and let scope drift into unplanned build-up work. The corrective this cycle is structural — **fewer items, all carry-overs first, all model-free, the two cheapest under half a day each.** ([Agile Business Consortium — MoSCoW/DSDM 60% cap](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html))

Both missed Must-Haves (momentum, xGChain) **roll to the front of this sprint.** None of the cycle-4 net-new proposals (`game_state.py`, `team_shape.py`, `action_value.py`) exist yet — confirmed against [[implemented-analytics-metrics]].

---

## 1. Decision context (why these calls)

1. **Capacity is the binding constraint — and smaller than assumed.** Demonstrated throughput is ~1 meaningful item per 3-day window once context-switching and thesis writing are netted out. I budget this sprint at **~2 dev-days of new+carry-over work**, deliberately under the 60% Must-Have cap, with real slack. ([MoSCoW / DSDM](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html), [Wikipedia — MoSCoW](https://en.wikipedia.org/wiki/MoSCoW_method))
2. **The metric backlog is integrative reuse, not greenfield.** First-gen metrics (xT, xGOT, xDEF, PPDA, sequences, field-tilt) all ship. The remaining wins are cheap recombinations of existing frames — the Analyst's game-state split is ~40 lines of pandas. That asymmetry (large interpretive lift, near-zero cost) decides the top of the list.
3. **Don't out-engineer the thesis.** Top PL clubs run **6 analysts and £1–5M/yr** ([PremierLeagueNow](https://premierleaguenow.co.uk/2025/10/30/how-data-analytics-is-revolutionizing-player-recruitment-in-the-premier-league/), [AnalyiSport](https://analyisport.com/insights/how-are-the-leading-premier-league-clubs-investing-in-data-analysis/)) — not the comparison class for a one-person TFM. Industry consensus puts tech-debt paydown at **15–20% of capacity**, treating *blocking* debt as a feature and deferring low-friction debt — not a storage rewrite. ([Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff), [Metamindz](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize)) So we take the right-sized engineering slice (silver Parquet at the loader seam) and defer the full DuckDB lakehouse to the thesis's "future work" chapter.
4. **What "must-have" means here:** the 2025 dashboard standard is *distilling data into clear, comparable, context-adjusted narratives* — game-state splits, percentile comparison, momentum flow — **not** raw metric count ([Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/), [Liam Henshaw 2026 tools](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know)). Approvals favour making existing pages more decision-useful over net-new surface area.

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

> Theme: **clear the two missed carry-overs, plus the one ~40-line fresh win.** All three model-free, no new dependencies, **~2 dev-days total** — deliberately under-loaded so it lands this time.

### 1. xT / possession-value momentum-flow chart → `3_Post_Match_Analysis` (`viz/charts.py`) — *CARRY-OVER, missed 4×*
- **What:** Cumulative (or rolling ~3-min) **home xT − away xT** area chart across the 90 — América band in `AME_YELLOW`, opponent band below zero, goal markers overlaid. The "who was on top, when" companion to the existing xG race.
- **Proposed by (conceptually):** Data Analyst (viz #1 — recommended in **four** consecutive cycles, still unbuilt).
- **Effort:** **~0.5 day.** Pure `viz/charts.py` assembly over per-event xT already produced by `xt.py`; Plotly `fill='tozeroy'`, two traces split on sign. Zero new processing.
- **User impact:** **MEDIUM-HIGH** — highest visibility-per-hour on the board and a clean thesis figure; completes the Post-Match narrative and matches the 2025 "match momentum" pattern.
- **Implementation notes:** Reuse the dark América palette and the xG-race construction. **This ships first** — a four-times-deferred Must-Have missing a fifth time is not acceptable.

### 2. Game-state-adjusted xG / xT (`processing/game_state.py`) → `1_Home` + `2_Pre_Match_Analysis` — *NEW*
- **What:** Tag every event with the scoreline state at that moment — *losing / level / winning* — from a running step-function over goal events (`typeId==16`), then re-cut xG, xT, shots and field-tilt by state. Three columns, never one blended number.
- **Proposed by:** Data Analyst (cycle 4, metric #2, Priority HIGH — explicitly "ship first, highest payoff-to-effort").
- **Effort:** **~0.5 day.** ~40 lines of pure pandas: `tag_state()` + `groupby(state)`. No model, no new dependency, no new viz.
- **User impact:** **HIGH.** "América's xT *while level*" is a far more honest signal than a season aggregate that silently mixes regimes (leaders cede possession; chasers inflate xG vs. open defences). Lands as a 3-column table and immediately hardens Pre-Match form — exactly the context-adjustment the 2025/26 literature treats as baseline.
- **Implementation notes:** Build the running lead as a step function joined to each event by `(timeMin, timeSec)`; `state = sign(team_lead)`. Per-state buckets shrink fast — **respect `MIN_MATCHES_FOR_PREDICTION`** and grey out states below threshold rather than showing noise.

### 3. xGChain & xGBuildup (`processing/xg_chain.py`) → `6_Player_Scouting` — *CARRY-OVER (mis-credited last cycle)*
- **What:** Credit each shot-ending possession's xG to every player who touched the ball in it. `xGChain` = total; `xGBuildup` = excluding shooter + assister (isolates deep build-up contributors). Ship with the credit-bar in the same PR.
- **Proposed by:** Data Analyst (HIGH, carried from cycle 3 — **never actually built**; do not confuse with `buildup_play.py`).
- **Effort:** **~1 day.** Pure pandas over the already-built `sequences.py` + `extract_shots()`. No model, no new deps.
- **User impact:** **HIGH.** Surfaces América's unsung progressors — the most "recruitment-selling" view and exactly the percentile-comparison narrative the 2025 standard rewards (Impect-style "who builds the chance" is now a recruitment baseline). ([PremierLeagueNow](https://premierleaguenow.co.uk/2025/10/30/how-data-analytics-is-revolutionizing-player-recruitment-in-the-premier-league/))
- **Implementation notes:** Attach each shot's xG (`QUAL_XG=395`) to its sequence; sum per distinct `player_id`; per-90 with `MIN_APPEARANCES_FOR_RATING`. **Manual 1-match spot-check is part of the deliverable.** Per [[def-rating-is-league-percentile]], ship as its own columns — do not blend into FC PAC/SHO/… ratings.

> **Capacity check:** 0.5 + 0.5 + 1.0 = **~2 dev-days** against a 3-day window — well under the 60% cap, leaving slack for the git-hygiene cleanup (Risk #7). Items 1 and 2 are independent half-day wins; item 3 is the single full-day piece and is the designated drop if anything slips (the two cheap wins must not).

---

## ✅ APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. Team-shape: block compactness / width / surface + Tactics overlay (`processing/team_shape.py` + `4_Tactics`) — *NEW*
- **What:** Three shape numbers per team per phase — **vertical compactness** (`x.q90 − x.q10`), **width** (same on y), **hull surface** (`scipy.spatial.ConvexHull(...).volume`) — plus the paired overlay: hull polygon + line-height marker + width band, per half/phase. Line height already ships; the *spread* around it does not.
- **Proposed by:** Data Analyst (cycle 4, metric #1 HIGH **+** viz #3 — bundled; the viz is free once the numbers exist).
- **Effort:** **~1.5 days.** Reuses `pressure.py`'s defensive-action filter; only new dependency is `scipy` (likely already transitive).
- **User impact:** **HIGH.** Completes the pressing picture (PPDA + line height + *compactness*) and answers "is América defending as a unit or getting stretched?" — the most-cited team-shape family in 2025 tactical writing.
- **Implementation notes:** Trim with the 10–90 quantile band, not min/max. **Academic-honesty guard:** label the polygon an **event-location convex hull**, explicitly NOT pitch control / Voronoi (true pitch control needs all-22 tracking we don't license). This caveat retires the speculative "Voronoi" backlog item. `@st.cache_data(ttl=3600)` like the other loaders.

### 2. Silver Parquet event layer + durable cache at the loader seam — *Engineering/Architecture (R1/R2/R3)*
- **What:** Run `event_parser.py` once per match in a signature-gated build step → `silver/events/<league>/<season>/<match_id>.parquet`. `load_player_events_season()` then reads columnar files with a `player_id` predicate instead of `json.loads`-ing every file. Add `@st.cache_resource` for read-only singletons (match index, name maps).
- **Proposed by:** Data Architect / Engineering (Phase-1 quick wins).
- **Effort:** **~1.5–2 days.** **Reuses the exact `match_index.py` signature-gated rebuild pattern already proven in the tree** — that's why it's a quick win and not the lakehouse.
- **User impact:** **MEDIUM-HIGH.** Turns "parse hundreds of multi-MB JSON files per call" into "scan a few hundred MB of typed columns," and survives restarts/redeploys (today's `@st.cache_data` is volatile per-process). The honest, right-sized slice of the Architect's vision — most of the latency win without committing to DuckDB/medallion. ([Streamlit caching docs](https://docs.streamlit.io/develop/concepts/architecture/caching), [Optimizing Streamlit performance](https://medium.com/@psaimanohar/optimizing-streamlit-app-performance-with-caching-and-efficient-data-handling-39e2b5c3c72a))
- **Implementation notes:** Wrap at the existing loader seam — no page changes, `processing/` untouched. Tag each Parquet artifact with the source `partidos/` signature so staleness self-invalidates, exactly like the match index.

### 3. Defensibility bundle: possession-adjusted DEF rating + pizza-chart hardening — *Analyst (cheap, high value-per-effort)*
- **What:** (a) Apply the existing `PADJ_BASELINE` to the `DEF` rating in `player_ratings.py` (still on raw counts). (b) Harden `viz/pizza.py`: percentiles not raw counts, attack/defence slice grouping, usage+outcome mix.
- **Proposed by:** Data Analyst (both flagged "cheap, high value-per-effort").
- **Effort:** **~1 day combined** (~30 lines + a viz audit).
- **User impact:** **MEDIUM.** Strips América's high-possession bias from defensive ratings (honest cross-team scouting) and aligns the headline player chart with 2025 best practice — both directly improve thesis defensibility for low cost.
- **Implementation notes:** PAdj must respect [[def-rating-is-league-percentile]] — adjust the counts that *feed* the percentile, don't double-normalise.

> **Capacity check:** ~4–4.5 dev-days across a 6-day window — feasible with margin, unlike the prior over-loaded plan. **VAEP/OBV fallback and the aerial model are deliberately NOT here** (see backlog): they were "next sprint" last cycle and never got reached. Three cheap, certain wins beat half-finishing one centrepiece. If #3 slips, it rolls to backlog.

---

## 📋 BACKLOG (Approved but deferred)

| Item | Source | Why deferred |
|---|---|---|
| **VAEP / OBV unified action value (fallback mode, no trained model)** | Analyst (carry-over) | *Top of backlog.* The clearest 2025/26 throughline (StatsBomb OBV across 140+ comps) and a thesis centrepiece — but ~2–3 days, and the last two sprints couldn't clear half-day items. **Promote the moment momentum + game-state + xGChain land and velocity is proven.** Nets the already-built `xt.py`/`xdef.py`/`xgot.py`/`sequences.py`. Per [[def-rating-is-league-percentile]], ship as its own column, never blended into FC ratings. |
| **Aerial duel win-probability model (HOPS-style)** | Analyst (cycle 4 #3) | Real bias fix in `player_ratings.py` (raw win% punishes target men), persisted via the `xg_model.py` pattern — but model work (~2 days) waits behind the cheap reuse wins. The only cycle-4 residual with no upstream blocker. |
| **Expected Pass (xP) + Passes Above Expected (PAx)** | Analyst (carry-over) | Needs a *trained* model and is the **upstream blocker** for two other proposals below. Promote after VAEP fallback proves the action-value layer pays off. |
| **Pass risk/reward decomposition** | Analyst (cycle 4 #4) | `reward − risk` needs `P(complete)` from xP first. Pure arithmetic afterward — natural sequel, blocked until xP ships. |
| **Line-breaking passes (StatsBomb 360 binary spec)** | Analyst (cycle 4 #5) | Coach-legible and approximable from `team_shape.py` line-height (next sprint). Defer until the team-shape line is available per-minute; pairs with packing/carries. |
| **Pass sonars → `4_Tactics`** | Analyst (cycle 4 viz #2) | Richer than arrow maps but net-new tactics surface with no correctness payoff. Slot in once the team-shape overlay lands (same page, same data). |
| **Packing / line-break proxy + `extract_carries()`** | Analyst (carry-over) | New event-parser work + a clear "event-data approximation" label. Good, not urgent. |
| **Attacking set-piece xG + Set-Piece Intelligence page** | Analyst + Architect §4 | Set pieces ≈23% of goals; `set_pieces.py` exists but only corner *defense* is surfaced. High value, but a discrete new model + page. Build after the integrative layer settles. |
| **Recruitment / Player-Comparison workspace** | Architect §4 | The single highest-value *new page* for a club; feature vectors already exist (`archetypes.py`, `player_ratings.py`). Deferred because the cross-competition scan it needs is responsive **only after** the silver Parquet layer (Next #2) lands. Strong candidate once that's in. |
| **Opposition Report PDF generator** | Architect §4 | The deliverable analysts hand coaches; composes existing modules. Multi-day net-new; sequence after the metric layer is final. |
| **Load-time schema assertion + processing registry/manifest** | Architect (Phase-1 / governance) | Cheap insurance against feed drift (R4) and metric sprawl (R6); self-documents for the thesis. No user-facing value — slot into a low-energy day. |

---

## ❌ REJECTED / NEEDS MORE RESEARCH

| Item | Source | Ruling |
|---|---|---|
| **Full DuckDB lakehouse — medallion bronze/silver/gold + headless build CLI** | Architect (Phase 2) | **Not now.** Correct architecture and the right *future-work chapter*, but a multi-week query-engine rewrite against ~47 GB is disproportionate for a single developer who delivered 33% of last sprint. The approved silver-Parquet slice (Next #2) captures the practical latency win at the loader seam without the medallion/DuckDB commitment. |
| **FastAPI service split · multi-tenant/role auth · Kafka/Flink streaming** | Architect (Phase 3) | **Rejected for TFM scope.** PL-department infrastructure (£1–5M/yr, 6+ analysts). No real users, no live feed. Keep as the explicit "if a PL club adopted this" north-star paragraph — do not build. |
| **Trained `P(score \| state)` VAEP model** | Analyst | **Deferred to season-end, not approved.** Ship the model-free fallback first; train only once more matches accumulate and early-season noise subsides. |
| **True pitch control / Voronoi · pressing-intensity via velocities · ball receipts in space** | Analyst (flagged honestly) | **Rejected (event-data-impossible).** All require positional tracking we don't license. The approved convex-hull (Next #1) is the *event-location* hull and must be labelled as such — it is **not** pitch control. Keep the rest as a one-line "future work with tracking data" note. |
| **Replace `injuries_synthetic.py` with a real availability/load model** | Architect §4 | **Needs more research.** Requires GPS/biometric load data the project doesn't have. Keep the synthetic placeholder + timeline UI; revisit only if a data source appears. |

---

## ⚠️ RISK FLAGS (monitor)

1. **🔴 Velocity / scope-drift (top flag, NEW).** 1 of 3 Must-Haves delivered last sprint, plus an *unplanned* build-up module. The mitigation is in this plan (under-loaded sprint, carry-overs first, all items ≤1 day). If momentum + game-state don't both land in 3 days, the root cause is process, not metrics, and cycle 6 must cut to **one** Must-Have.
2. **🔴 Git hygiene — uncommitted work.** `processing/buildup_play.py` and `viz/buildup.py` are **untracked**; `data/event_parser.py`, `pages/2_*`, `pages/3_*`, `viz/phases.py` show uncommitted edits. Delivered work that isn't committed is at risk of loss and isn't reproducible for the thesis. **Action: commit or stash the working tree before any new work begins.** Also confirm the build-up module carries the `AME_LEAGUES` page guards and approximation labels.
3. **🟠 Match index shipped — verify the loaders use it.** Architect §0 calls fuzzy resolution only "*partially* mitigated." Confirm `load_*` paths resolve by `match_id` with a zeroed fuzzy-fallback counter across MLS/USL/CONCACAF, and that the loud-failure logging on `11_Data_Sources` was wired. Treat cross-competition numbers as suspect until instrumented.
4. **🟠 R1/R2 — cold-start full-tree glob + volatile per-process cache.** The defining scalability ceiling; `load_player_events_season()` parses every JSON on a cache miss → minutes of cold re-parse on restart/redeploy. Mitigated by Next-Sprint #2.
5. **🟡 Game-state bucket starvation.** Per-state splits (Immediate #2) shrink the sample fast — enforce `MIN_MATCHES_FOR_PREDICTION` and grey out thin states; don't render noise as signal.
6. **🟡 Convex-hull honesty.** Next-Sprint #1 must be labelled an *event-location hull*, never "pitch/space control." A TFM reviewer will probe this — mislabelling is an academic-integrity flag, not cosmetic.
7. **🟡 FC-rating blending constraint** ([[def-rating-is-league-percentile]]). Event-derived team-only metrics (xGChain, VAEP impact, `aerial_pax`) cannot fold into FC PAC/SHO/DEF without a league-wide scan. Applies to Immediate #3 and the backlogged VAEP/aerial work.
8. **🟡 Goalmouth z=19 placeholder** ([[goalmouth-z-placeholder]]). Qualifier 103 uses z=19 as "height not recorded" on ~40% of on-target shots — guard in any placement/aerial metric; verify shipped `xgot.py` already does.
9. **🟡 Metric sprawl without a registry (R6).** 30 modules in `processing/` now (was 24), no metric→module→page manifest. "Which page breaks if I change xG?" is still un-answerable without grep. Backlogged — but the count climbs each cycle.

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

Measured at the close of the 3-day Immediate window:

1. **Momentum chart renders without error** on `3_Post_Match_Analysis` for any selected match, on the same time axis as the existing xG race, with cumulative end-values reconciling to each side's total event-xT (±rounding). The four-times-deferred Must-Have is **verified rendered**, not just merged.
2. **Game-state segmentation live and correct.** `processing/game_state.py` exists; a 3-column *losing/level/winning* xG+xT table renders on `1_Home` and `2_Pre_Match_Analysis`. A 1-match spot-check confirms each event's state matches the running scoreline (a goal at minute *m* flips state for all later events) and the three per-state xG values sum to the blended match xG (nothing dropped/double-counted). States below `MIN_MATCHES_FOR_PREDICTION` are visibly greyed.
3. **xGChain/xGBuildup correct (stretch).** `processing/xg_chain.py` exists; per-90 xGChain and xGBuildup render on `6_Player_Scouting` (with the credit-bar) for every squad player above `MIN_APPEARANCES_FOR_RATING`; a 1-match spot-check confirms each shot's xG is credited to exactly the players in its sequence — no double-counting, shooter+assister correctly excluded from xGBuildup.

**Plus a process gate (the real lesson of last sprint):** the uncommitted tree (Risk #2) is **committed or stashed before any new work begins**.

**Sprint passes** if Metrics 1 and 2 (the two half-day wins) ship *and* the process gate is met, with no regression to page load. Metric 3 is the stretch — if it slips it rolls to the front of Days 4–9, but the two cheap wins must not. **Miss on Metric 1 or 2 = the velocity problem is unsolved, and cycle 6 cuts to a single Must-Have.**

---

## Sources

**Prioritization & process**
- [Agile Business Consortium — MoSCoW Prioritisation (DSDM)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html) · [What is MoSCoW Prioritization](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/) · [MoSCoW method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method) · [RICE/MoSCoW/Kano — Plane](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained)
- [Logiciel — Technical Debt vs Feature Development](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff) · [Metamindz — Tech Debt vs Feature Development](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize) · [Beyond the Backlog — Balancing Tech Debt](https://beyondthebacklog.com/2024/01/15/balancing-technical-debt/)

**Streamlit / engineering**
- [Streamlit — Caching overview](https://docs.streamlit.io/develop/concepts/architecture/caching) · [Optimizing Streamlit App Performance with Caching](https://medium.com/@psaimanohar/optimizing-streamlit-app-performance-with-caching-and-efficient-data-handling-39e2b5c3c72a) · [FAQ: improve performance with large data](https://discuss.streamlit.io/t/faq-how-to-improve-performance-of-apps-with-large-data/64007)

**Football analytics standard & club context**
- [Sportmonks — How Football Clubs Use Data Analytics](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/) · [Liam Henshaw — Tools Every Football Analyst Should Know (2026)](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know) · [Sports Data Campus — Big Data Tools for Football](https://english-programs.sportsdatacampus.com/big-data-tools-for-football/)
- [PremierLeagueNow — Data Analytics & Recruitment](https://premierleaguenow.co.uk/2025/10/30/how-data-analytics-is-revolutionizing-player-recruitment-in-the-premier-league/) · [AnalyiSport — How Leading PL Clubs Invest in Data](https://analyisport.com/insights/how-are-the-leading-premier-league-clubs-investing-in-data-analysis/) · [Sportblog — Premier League Data Revolution](https://www.sportblog-online.de/en/premier-league-data-revolution-tactical-analysts/)

**Internal inputs:** `reports/data_analyst_report_2026-06-21_0911.md`, `reports/data_architect_report_2026-06-21_0910.md`, `reports/manager_sprint_review_2026-06-21.md`; memory notes [[implemented-analytics-metrics]], [[def-rating-is-league-percentile]], [[goalmouth-z-placeholder]].
