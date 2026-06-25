# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-06-24 (consolidation run, 14:55)
**Author:** Analytics Engineering Manager (automated 3-day consolidation)
**Inputs reviewed:**
- `reports/data_analyst_report_2026-06-21_0911.md` — Analyst cycle 4 (5 new metrics, 3 viz upgrades, carry-overs)
- `reports/data_architect_report_2026-06-21_0910.md` — Architect (medallion/Parquet/DuckDB roadmap, 6 page ideas, R1–R7 risk register)
- **Data Engineer: no standalone report filed this cycle.** Engineering scope (hot-path JSON parsing, cache durability, Parquet/DuckDB) is carried inside the Architect's risk register and Phase-1 quick wins. I attribute those items to **"Engineering/Architecture"** below and flag the missing report as a process risk (Risk #4).
- Prior approval baseline: `reports/manager_sprint_review_2026-06-24.md` (14:52 run)

> **Decision posture.** This is an approval document, not a survey. The developer is a single student with a finite thesis timebox, so prioritization is ruthless: I cap **Must-Have effort at ≤60%** of sprint capacity per DSDM, sequence dependencies explicitly, and refuse anything that can't be defended in a TFM. ([Agile Business Consortium — MoSCoW](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html))

---

## 0. State of the board — verified against the tree before approving

I re-ran the checks this cycle (never approve what already ships):

| Item | Status | Evidence (this run) |
|---|---|---|
| xGChain / xGBuildup | ✅ **Shipped** | `processing/buildup_play.py` + `viz/buildup.py` present |
| Match index + ID resolution | ✅ **Shipped** | `data/match_index.py` present; Architect credits it as the new persistence tier |
| **xT match-momentum chart** | ❌ **MISSED again** | `grep -rl momentum viz/ processing/` → 0 hits. Now slipped **four consecutive cycles** |
| `game_state.py`, `team_shape.py`, `pass_value.py` | 🟢 **Net-new** | none exist — all genuinely new this cycle |
| Silver Parquet / DuckDB layer | 🟢 **Net-new** | only `match_index.py` uses Parquet; no `silver/` dirs exist |

**Ruling:** the momentum chart was a Must-Have that missed its timebox four times. Under DSDM that does **not** get re-deferred — it returns at the **front** of this sprint. A metric this cheap (reuses `xt.py`) slipping four cycles is a planning-discipline failure, not a complexity problem.

---

## 1. Why these calls (prioritization logic)

Three signals from the research drive the ranking:

1. **The industry's MVP bar is "context-adjusted, real-time-feeling insight," not metric count.** The Premier League's flagship fan/club products lead with *Attacking Threat*, *Win Probability*, and *Average Position* — threat-flow and context-adjustment, exactly what the momentum chart and game-state metric deliver — over exotic new numbers. ([Oracle — Premier League](https://www.oracle.com/premier-league/), [SportsPro — PL tech stack](https://www.sportspro.com/commercial-guide/premier-league/data-analytics/tech-stack/))
2. **A clean dashboard beats a cluttered model.** 2025 club-platform guidance is explicit that a legible "last-5 / rolling-average / percentile" visual is worth more than another back-end model. Visualization debt is real debt here. ([Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/), [SportsDataCampus](https://english-programs.sportsdatacampus.com/big-data-tools-for-football/))
3. **Streamlit's single-process ceiling makes hot-path parsing a *time-boxed* debt, not optional.** The literature is blunt that Streamlit bakes latency in as data grows; allocate 10–20% of capacity to debt every sprint rather than a big-bang refactor. That funds one tight engineering item now and the silver layer next. ([Logiciel — tech debt vs features](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff), [DigitalDefynd — Streamlit pros/cons](https://digitaldefynd.com/IQ/pros-cons-of-streamlit/))

---

## APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

*Exactly 3. Combined effort ≈ 2 of 3 dev-days — deliberately under the 60% Must-Have cap, leaving contingency.*

### 1. Match-momentum chart (xT-flow) → `3_Post_Match_Analysis`
- **What:** Filled area chart of rolling (~3-min) **home xT − away xT** across the 90, shaded `AME_YELLOW` above zero / opponent colour below, goal markers overlaid. The PL "Attacking Threat / Match Momentum" pattern, built on data we already compute.
- **Proposed by:** Data Analyst (Viz #1, the long-running carry-over).
- **Effort:** **~0.5 day.** One `viz/charts.py` function (`momentum_chart(events)`); Plotly `fill='tozeroy'`, two sign-split traces; bucket existing per-event `xt.py` output by minute.
- **User impact:** **High / high-visibility.** Single most engaging plot on the page; directly mirrors the flagship PL fan-facing metric. Closes a four-cycle miss.
- **Implementation notes:** No new model, no new data path. Overlay goal events (`typeId==16`) as markers. This is the canary for our planning discipline — if it slips a fifth time, escalate the process, not the scope.

### 2. Game-state-adjusted xG / xT → `processing/game_state.py` + tables on `1_Home` & `2_Pre_Match_Analysis`
- **What:** Re-cut xG / xT / shots / field-tilt by **scoreline state** (losing / level / winning) at event time, surfaced as a 3-column table — never one blended number.
- **Proposed by:** Data Analyst (Metric #2, their own "ship first").
- **Effort:** **~1 day.** ~40-line pure-pandas tagger (running scoreline from `typeId==16` ordered by `timeMin/timeSec`, tag `state ∈ {-1,0,+1}`, `groupby(state)`). No model, no new viz.
- **User impact:** **High.** The strongest predictiveness win in the 2025 literature and a direct analogue of the PL's context-adjusted insight; makes Pre-Match form honest ("América's xT *while level*").
- **Implementation notes:** **Must respect `MIN_MATCHES_FOR_PREDICTION`** — per-state buckets shrink fast in thin early-season Liga MX samples; gate the table behind the guard and label low-n states. Add a reconciliation assert: Σ over states == season total.

### 3. Load-time schema assertion + `@st.cache_resource` for shared artifacts → `data/event_parser.py`, `data/loader.py`
- **What:** (a) Assert the `config.py` qualifier IDs actually appear in a sampled event file at load; log a warning on drift. (b) Move read-only shared artifacts (match-index DataFrame, name maps) to `@st.cache_resource` so they survive across sessions, not just per-session `@st.cache_data`.
- **Proposed by:** Engineering/Architecture (Architect Phase 1 quick wins; retires Risk #4 and partially Risk #2).
- **Effort:** **~0.5 day.** Localized to two existing files; no new infrastructure.
- **User impact:** **Medium but compounding.** Cheap insurance against a silent feed change surfacing as a wrong number deep in a page; trims cold-start re-parse after a redeploy. This is the sprint's 10–20% debt allocation — the disciplined alternative to a big-bang refactor.
- **Implementation notes:** Keep the assertion non-fatal (warn + continue) so a single odd file never blanks a page. This is the on-ramp to the silver layer approved below.

---

## APPROVED FOR NEXT SPRINT (Days 4–9)

*Exactly 3. Bigger items that need their own timebox.*

### 1. Team-shape geometry → `processing/team_shape.py` + compactness overlay on `4_Tactics`
- **What:** Vertical compactness, width, and convex-hull surface area of the defending block, by game-phase; rendered as a hull polygon + line-height marker + width band on Tactics.
- **Proposed by:** Data Analyst (Metric #1 + Viz #3, bundled — one module feeds the viz).
- **Effort:** **~1.5 days.** Reuse `pressure.py`'s defensive-action filter; `scipy.spatial.ConvexHull` for surface; mplsoccer overlay on the existing pitch.
- **User impact:** **High.** The most-cited 2025 team-shape family; completes the pressing picture alongside existing PPDA/line-height and gives coaches the legible "are we a unit or stretched?" read.
- **Implementation notes:** Trim outliers with the 10–90 quantile band, not min/max. **Honesty caveat for the TFM:** label it convex-hull of *event* locations — **not** pitch control (that needs all-22 tracking we don't have).

### 2. Silver Parquet event layer → `events/<league>/<season>/<match_id>.parquet` + build step
- **What:** Run `event_parser.py` once per match in a signature-gated build step (mirroring `match_index.py`), persist typed columnar events. `load_player_events_season()` then does predicate-pushdown scans instead of parsing hundreds of JSON files per call.
- **Proposed by:** Engineering/Architecture (Architect Phase 1, the highest-leverage single move — retires High-severity Risks R1–R3).
- **Effort:** **~2 days.** Reuses the exact durability/staleness pattern already proven in `match_index.py`; `processing/` is untouched (it still receives DataFrames).
- **User impact:** **High, structural.** Turns the dominant latency/memory risk into a columnar scan and is the precondition for the cross-competition recruitment features in the backlog.
- **Implementation notes:** Bronze JSON is never deleted — silver is a rebuildable derived artifact. Tag each file with the source `partidos/` signature so staleness self-invalidates. Defer DuckDB itself to the backlog — Parquet alone already retires the risks.

### 3. Pass-completion-probability (xP) model → `processing/` (carry-over, unblocks two backlog items)
- **What:** Logistic `P(complete | start, end, context)` over `extract_passes()`, persisted via the `xg_model.py` pattern.
- **Proposed by:** Data Analyst (carry-over; explicit prerequisite for Metric #4 pass risk/reward and Metric #5 line-breaking).
- **Effort:** **~1.5 days.** Self-contained model; no UI dependency.
- **User impact:** **Medium now, high as an enabler.** Feeds the PAx execution-residual into the `PAS` rating block and is the dependency gate for the next two analyst metrics.
- **Implementation notes:** Sequenced **before** #4/#5 deliberately — approving those without xP first would stall mid-sprint. Guard with `MIN_APPEARANCES_FOR_RATING`.

---

## BACKLOG (Approved but deferred)

Good ideas, correctly scoped, waiting on capacity or a dependency:

- **Pass risk/reward decomposition** (Analyst #4) — *deferred: hard-depends on the xP model above.* Pure arithmetic once xP lands.
- **Line-breaking passes** (Analyst #5) — *deferred: depends on both `team_shape.py` (for the defensive line) and xP.* Natural sequel once both ship.
- **Aerial win-probability model / HOPS-style** (Analyst #3) — *deferred: standalone model with real value, but no dependency forcing it early; queue behind xP.*
- **Pass sonars** (Analyst Viz #2) — *deferred: nice-to-have viz; the momentum chart delivers the high-visibility win this sprint already.*
- **VAEP/OBV unified action value** (carry-over) — *deferred: the field's convergence point and a strong TFM centerpiece, but a multi-day model; needs the silver layer underneath it to be responsive.*
- **Attacking set-piece xG + Set-Piece Intelligence page** (Analyst carry-over + Architect page #2) — *deferred: clear marginal-gains area; bundle the metric and the page together later.*
- **DuckDB query engine** (Architect Phase 2) — *deferred: real, but the silver Parquet layer captures most of the latency win first; add DuckDB only when cross-league queries become the bottleneck.*
- **Recruitment / Player-Comparison workspace** (Architect page #1) — *deferred: the flagship club workflow, but it needs the silver/DuckDB cross-competition scan to be responsive. Sequenced after the data layer.*
- **Opposition Report PDF generator** (Architect page #3) — *deferred: high coach value, composes existing modules; schedule once team-shape + momentum exist to feed it.*

---

## REJECTED / NEEDS MORE RESEARCH

Decisive no's — these would burn thesis time for little defensible return:

- **Streaming ingestion (Kafka/Flink/MSK).** ❌ **Rejected for the TFM.** Explicitly the Architect's "if a PL club adopted this" north star, not a build target. Single-developer batch data; streaming is pure over-engineering. Keep as a one-paragraph "future work" note only.
- **FastAPI gold-mart API + multi-tenant / role-aware access.** ❌ **Rejected now.** Premature for a single-user thesis demo. Revisit only if the project outlives the TFM and gains real concurrent users.
- **True pitch control / Voronoi / pressing-intensity via player velocities.** ❌ **Rejected — data does not exist.** All require all-22 positional tracking we do not have. Rendering a fake event-data version would be a methodological own-goal in a thesis. Document them honestly in `11_Data_Sources` as tracking-only future work.
- **Physical / Load page on `injuries_synthetic.py`.** ⚠️ **Needs more research before committing.** A synthetic-data medical page risks looking like a toy in a defense. Only worth building if it demonstrates a real data-product boundary; otherwise leave as the existing placeholder.
- **Data-mesh domain products.** ⚠️ **Conceptual only.** Sound framing for the written thesis, but there is nothing to *build* at single-app scale. Cite as design rationale, not a deliverable.

---

## RISK FLAGS

Monitor through the sprint:

1. **Chronic slippage on the momentum chart (4 cycles).** The cheapest high-value item kept losing its timebox. If it slips a fifth time, the problem is planning discipline, not engineering — escalate the process.
2. **No Data Engineer report filed this cycle.** Engineering health is visible only through the Architect's lens — a real blind spot on caching/performance ownership. Flag for the next cycle; engineering items here are inferred, not independently reported.
3. **Untracked work not committed.** `processing/buildup_play.py`, `viz/buildup.py` (and modified `event_parser.py`, the two analysis pages, `viz/phases.py`) are uncommitted. Shipped-but-uncommitted code is unprotected — commit before starting new work.
4. **Hot-path JSON parsing debt is still compounding** (Architect R1–R3). The silver layer is approved for next sprint precisely so this doesn't grow another cycle; if next sprint slips, latency on `partidos/` scans becomes the user-visible problem.
5. **Game-state bucket sparsity.** Per-state splits shrink fast in thin Liga MX early-season samples — the `MIN_MATCHES_FOR_PREDICTION` guard is mandatory, not optional, or the new table will surface noise as signal.
6. **Cache volatility on redeploy.** `@st.cache_resource` (immediate item #3) only partially mitigates; full durability waits on the silver layer.

---

## SUCCESS METRICS FOR THIS SPRINT

We will call the 3 immediate items done only when **all** of the following are objectively true:

1. **Momentum chart renders with proof.** `momentum_chart()` displays on `3_Post_Match_Analysis` with the zero-split shading and goal markers, verified on at least one real match in the running app (screenshot in the next report). *Binary: it renders or it doesn't.*
2. **Game-state table is correct and guarded.** The 3-column state table appears on `1_Home` and `2_Pre_Match_Analysis`; a reconciliation assert confirms **Σ(per-state metric) == season total** (±rounding); and states below `MIN_MATCHES_FOR_PREDICTION` are visibly flagged rather than shown as confident numbers.
3. **Schema guard fires and cache survives sessions.** A deliberately malformed/sampled file triggers the load-time warning (not a crash); and the match-index artifact is served from `@st.cache_resource` across two separate sessions without re-parsing (observable in load timing / logs).

All three must hold without any page parsing JSON directly — the `data → processing → viz → pages` layer separation stays intact (the architectural asset every evolution depends on).

---

*Consolidated from the Analyst (cycle 4) and Architect (09:10) reports; Data Engineer scope inferred from the Architect risk register in the absence of a filed report. Web context: MoSCoW/DSDM prioritization, 2025 PL/club-platform feature bars, and Streamlit performance-vs-features guidance — sourced inline above.*
