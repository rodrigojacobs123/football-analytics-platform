# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM) — Streamlit / Pandas / Plotly / mplsoccer, Opta F24 event data across 77 competitions
**Prepared by:** Analytics Engineering Manager (autonomous 3-day cycle run)
**Date:** 2026-06-21
**Inputs consolidated:** Data Analyst (metrics & viz), Data Engineer (performance & storage), Data Architect (roadmap & data model)
**Prioritization framework:** MoSCoW within a fixed timebox ([Agile Business Consortium](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html), [Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)), filtered through one hard constraint — *single-developer thesis project on a finite defense clock.* Effort that doesn't show up in the writeup or the live demo is deprioritized regardless of technical merit. DSDM guidance: keep Must-Have effort ≤60% of the timebox; this plan does.

---

## EXECUTIVE SUMMARY — what the code audit changed

I re-audited the live repo before approving anything. **The previous cycle's headline asks are now shipped**, which retires them and exposes a sharper, smaller set of high-ROI moves:

| Item from prior reviews | Verified state today (`grep`/`git status`) | Verdict |
|---|---|---|
| Surface xT in the UI | **Done** — xT now imported by **6 pages** (Home, Pre-Match, Post-Match, Tactics, Scouting, Player Intelligence) | ✅ Retired |
| Surface orphaned `pressure.py` | **Done** — now imported by Tactics + Post-Match | ✅ Retired |
| Integrate Corner Defense + Archetypes pages | **Done** — pages `13`/`14` registered in `app.py` nav (lines 27–28) | ✅ Integrated, **not committed** |
| xDEF (defensive threat reduction) | **Newly built** — `processing/xdef.py` (7 KB; `defensive_actions_xdef`, `xdef_summary`) but imported by **zero pages** | 🔶 **Orphaned — surface it** |
| Whole new feature tree | `xdef.py`, `corner_defense.py`, `archetypes.py`, `tactical_positions.py`, `plotly_pitch.py`, pages `13`/`14` are **all untracked** | ⚠️ **Top risk — commit it** |

**The headline:** the developer is executing fast — last cycle's recommendations are largely live. But that speed created two precise problems this sprint must close: (1) `xdef.py` is built-but-unwired (the cheapest high-impact win available), and (2) `app.py` already references untracked page files, so the working tree is one bad commit away from a **broken-on-clone demo**. This sprint is therefore *finish, wire, and commit* — not *build new*. That matches the industry signal that 2025-era dashboards win on **advanced metrics surfaced with context and scenario filtering**, not on raw model count ([Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/), [Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/)), and the Streamlit reality that features only stay fast with intentional caching ([Towards Data Science](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/)).

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

### 1. Wire the orphaned `xdef.py` into the UI — *MUST-HAVE, flagship of this cycle*
- **What it is:** `processing/xdef.py` already computes Expected Defensive Threat Reduction (the defensive mirror of xT) via the Karun-grid flip `xt_value(100 − x, y)`. It reaches no page. Surface it: add a "Defensive Threat Denied (per 90)" leaderboard on **Player Scouting** and fold `xdef_summary` into the count-based **`DEF`** attribute in `processing/player_ratings.py`.
- **Proposed conceptually by:** Data Analyst (xDEF was their #1 HIGH item; defensive action-valuation is the clearest 2025 industry gap — StatsBomb OBV-defensive, the *Journal of Big Data* 2025 valuation paper).
- **Effort:** **Low (~0.5–1 day).** The hard part (grid reuse, coordinate flip, defensive-event extraction) is written. This is a leaderboard table + one rating-block edit + a caption.
- **Expected user impact:** **High.** Turns "made a tackle" into "denied 0.018 of threat in a dangerous zone." It's the headline modern-analytics differentiator an examiner looks for, and it makes the `DEF` rating defensible rather than count-based.
- **Implementation notes:** Confirm the module's `100 − x` flip against one known deep defensive action before trusting the board (the repo has a documented coordinate-convention bug history — `CLAUDE.md`). Enforce `MIN_MINUTES_FOR_RATING`; a sub's one clearance must not top the chart. Add a one-line methodology caption (Opta-approximated, cite Lamberts). Go through `data.loader` — no direct JSON parse in the page.

### 2. Commit & verify the untracked feature tree — *MUST-HAVE (de-risk), do this first*
- **What it is:** Smoke-test then **commit in logical chunks**: `xdef.py`, `corner_defense.py`, `archetypes.py`, `tactical_positions.py`, `plotly_pitch.py`, and pages `13_Corner_Defense` / `14_Player_Intelligence`. `app.py` is modified to reference pages 13/14, but those page files are untracked — a commit of `app.py` without them yields a **broken nav on any fresh checkout**.
- **Proposed conceptually by:** Data Architect (integration/new-page hygiene) + Data Engineer (repo health).
- **Effort:** **Low–Medium (~0.5–1 day).** Cost is a click-through of each page on real match data and fixing any breakage, then staged commits.
- **Expected user impact:** **High (risk elimination).** Uncommitted demo code is the single largest threat to the defense; this converts ~7 unversioned files into safe, demonstrable features.
- **Implementation notes:** Commit `app.py` and its referenced page files **in the same commit** so nav never points at a missing file. Verify each new page renders end-to-end before staging. Keep `.streamlit/` and any Parquet artifacts out via `.gitignore`.

### 3. Profile & cache the Post-Match Analysis hot path — *MUST-HAVE (engineering)*
- **What it is:** `pages/3_Post_Match_Analysis.py` is the heaviest page and loads per-match `partidos/*.json`. Time a cold load, confirm `event_parser` outputs are memoized on `match_id`, add `@st.cache_data` to any transform that re-runs on every interaction.
- **Proposed conceptually by:** Data Engineer (caching strategy / Streamlit performance).
- **Effort:** **Low (~0.5 day).** Caching infra exists (`@st.cache_data(ttl=3600)` is pervasive in `data/loader.py`); this is coverage auditing, not new plumbing.
- **Expected user impact:** **Medium–High.** Streamlit re-runs the whole script on every interaction; uncached per-match parsing is the classic latency trap ([Towards Data Science](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/), [Streamlit scaling lessons](https://medium.com/@hadiyolworld007/streamlit-apps-that-scale-lessons-from-real-projects-8237f1ae6729)). A snappy defense demo matters.
- **Implementation notes:** Cache keyed on `match_id`, not on a parsed DataFrame object. Capture a before/after timing in the commit message — it becomes a measurable performance line in the dissertation.

> Must-Have effort this cycle ≈ 1.5–2.5 dev-days against a 3-day timebox — comfortably within the DSDM ≤60% rule, leaving slack for the inevitable coordinate/edge-case debugging.

---

## 🔜 APPROVED FOR NEXT SPRINT (Days 4–9)

### 4. Progressive carries from events + packing proxy — *SHOULD-HAVE*
- **What it is:** Add `extract_carries()` to `data/event_parser.py` and a `processing/progression.py` for progressive carries (≥~5 normalized units toward goal or into the box) plus the event-data **packing proxy** (line-breaking passes / between-the-lines receptions). Replaces the CSV-sourced carry columns with a single event-derived source of truth.
- **Proposed conceptually by:** Data Analyst (metrics #3 & #4).
- **Effort:** **Medium (~1–1.5 days).** Reuses take-on/touch extraction already imported in `xt.py`; mostly thresholding + aggregation + a leaderboard.
- **Expected user impact:** **High.** Completes the modern on-ball-value triad (xT + xDEF + progression) and unlocks per-match carry maps on Post-Match/Tactics.
- **Implementation notes:** Define the "progressive" threshold **once** in `config.py` and cite the convention (Opta/StatsBomb ≈5 m). True packing needs tracking data we don't have — label the proxy honestly.

### 5. Single Parquet conversion of the season hot path (`matches.json`) — *SHOULD-HAVE*
- **What it is:** Write-through Parquet cache for the season-wide `jsons/matches.json` (read by Home/Tactics/Scouting); `data/loader.py` prefers the Parquet artifact when present, JSON stays source-of-truth + fallback.
- **Proposed conceptually by:** Data Engineer (columnar/storage move).
- **Effort:** **Medium (~1.5 days).** New helper in `data/paths.py` + write-through in `data/loader.py`; careful cache-key + fallback.
- **Expected user impact:** **Medium.** Faster cold loads and a smoother demo. Caching already hides most repeat-load latency, so this is optimization, not rescue — hence next sprint.
- **Implementation notes:** **Parquet only — no DuckDB engine** (see Rejected). Scope to `matches.json`; leave `partidos/*.json` on JSON. Key the cache on source mtime; add the artifact to `.gitignore`. Measure cold-load before/after for the thesis.

### 6. Two high-recognition viz upgrades over existing metrics — *SHOULD-HAVE*
- **What it is:** (a) **PPDA × defensive-line-height quadrant scatter** (teams plotted, América in yellow, pressing-profile quadrants) and (b) **xT/momentum-flow area chart** on Post-Match (cumulative net-threat swing, like the xG race but for territory).
- **Proposed conceptually by:** Data Analyst (viz upgrades #1 & #3).
- **Effort:** **Medium (~1 day total).** Pure `viz/charts.py` / `viz/plotly_pitch.py` assembly — both axes/inputs already computed in `formations.py`, `pressure.py`, `xt.py`.
- **Expected user impact:** **Medium–High.** The quadrant scatter is *the* signature 2025 pressing-profile chart; momentum flow is the canonical match-narrative viz. Highest value-per-hour visuals available.
- **Implementation notes:** Reuse the dark América palette; no new theming. Label the static metrics' caveats per the literature.

---

## 📋 BACKLOG (Approved but deferred)

- **VAEP / unified action-value model (`processing/action_value.py`).** Conceptually the industry standard (OBV/VAEP), but an ML model needing labelled scoring/conceding outcomes and validation. **Deferred:** xT + the now-surfaced xDEF cover possession value for the thesis at a fraction of the cost; gate any build on the feasibility spike below.
- **Build-up disruption rate + counter-press regain (≤5 s) in `pressure.py`.** Two extra keys on an existing bundle. **Deferred:** real but marginal next to wiring xDEF and shipping progression.
- **Voronoi / static pitch-control snapshot on Tactics.** Honest event-data approximation of pitch ownership. **Deferred:** polish; reuses `tactical_positions.py` positions but lower narrative priority than the metric triad.
- **Advanced "scenario" filtering on Player Scouting** (minutes / position / competition / home-away). Strong demo moment ([Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/)). **Deferred:** valuable but competes for the same hours as surfacing built analytics; promote next cycle.
- **`partidos/*.json` → Parquet.** **Deferred:** per-match files load on-demand; revisit only if per-match pages feel slow after #5.
- **DuckDB query layer.** **Deferred:** dataset isn't large enough to justify the dependency; Parquet captures most of the win.

**Why deferred, in one line:** each is either blocked by data the Opta F24 feed lacks (tracking), or it competes for the same single-developer hours as higher-ROI "surface / finish what's already built" work.

---

## ❌ REJECTED / NEEDS MORE RESEARCH

- **Full migration to Parquet/DuckDB as the *primary* store this term.** **REJECTED.** Rewriting `data/loader.py`'s entire I/O layer mid-thesis, with no test suite, is high-risk; the incremental Parquet cache (#5) captures most of the benefit safely.
- **VAEP production model before a timeboxed feasibility spike.** **NEEDS MORE RESEARCH.** No evidence yet it beats the shipped xT/xDEF for thesis purposes. Approve only a **2-day hard-capped spike → 1-page go/no-go memo**, not an implementation.
- **Dynamic xT (DxT) / off-ball-adjusted threat.** **NEEDS MORE RESEARCH / out of reach.** Requires positional/tracking data the F24 feed doesn't carry.
- **Bespoke xG model from scratch.** **REJECTED for the sprint.** xG already lives in Opta qualifier 395; re-deriving risks *worse* numbers than the provider. Only justified if the thesis explicitly requires a self-built-model section.
- **Real-time / live ingestion, migrating off Streamlit, multi-user/auth/deployment hardening.** **REJECTED.** No live feed in scope; massive rewrites with zero analytical value; single-user thesis demo. All are scope creep against the defense clock.

---

## ⚠️ RISK FLAGS

1. **Broken-on-clone risk (NEW, top priority).** `app.py` references pages `13`/`14` that are **untracked**. Any commit of `app.py` without those files breaks the nav on a fresh checkout. *Mitigation: Immediate item #2 — commit `app.py` and its page files atomically.*
2. **Uncommitted feature sprawl.** ~7 new feature files + ~45 modified files are unversioned. Work that isn't committed isn't safe. *Mitigation: staged commits before any new work begins.*
3. **No test suite, no linter.** Every refactor (caching, Parquet) is unguarded. *Mitigation: keep changes small; verify each page renders in the running app before committing; add smoke assertions on `xdef.py`/`pressure.py` outputs.*
4. **Coordinate / qualifier convention bugs.** Documented history (penalty Q9-vs-Q22, formation Q130-vs-row-count). xDEF's `100 − x` flip and progressive thresholds both depend on axis orientation. *Mitigation: verify against a known event before trusting any new metric.*
5. **Methodology labelling.** `pressure.py` and `xdef.py` are Opta *approximations* of StatsBomb-native events. Surfacing without a caption is examiner-bait. *Mitigation: a one-line methodology caption on every approximated metric.*
6. **Early-season sample noise.** Default season `2025-2026` is thin; new leaderboards (xDEF-p90, progression) are volatile. *Mitigation: honor `MIN_*` guards; show "low sample" over a misleading number.*
7. **Feature-vs-stability tension.** Every new page is live demo surface that can break ([Logiciel on tech-debt tradeoff](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)). *Mitigation: freeze the feature list after Days 4–9; reserve the run-up to defense for hardening, not new metrics.*

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

1. **xDEF is live and validated.** `grep -rl xdef pages/` returns **≥1** page, and one hand-checked "threat denied" value (a known deep defensive action) matches the flipped Karun grid within tolerance. *Binary: shipped & spot-checked, or not.*
2. **Zero untracked feature files + clean cold start.** `git status` shows no untracked feature code, and `streamlit run app.py` cold-starts with **all 14 registered nav pages rendering without import/runtime error** (closes Risk #1 and #2). *Verifiable by a clean click-through of the running app.*
3. **Post-Match load time −≥30%.** End-to-end load of a single match drops by at least 30% after the caching audit (#3), captured as a before/after timing in the commit message.

---

*Prioritization is deliberately ruthless: the developer already shipped last cycle's headline metrics, so this sprint's job is to **wire the one built-but-orphaned metric (xDEF), make the in-flight work safe by committing it, and keep the demo fast** — then defer every model/storage deepening that costs more than it demonstrates before the defense.*

### Sources
- [MoSCoW Prioritisation — Agile Business Consortium (DSDM)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html)
- [MoSCoW method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)
- [Feature prioritization: RICE, MoSCoW, Kano — Plane](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained)
- [Top Websites for Football Stats & Player Analytics 2025 — Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/)
- [How Football Clubs Use Data Analytics — Sportmonks](https://www.sportmonks.com/blogs/how-football-clubs-use-data-analytics-to-improve-performance/)
- [Analyzing Data Analytics in EPL Team Strategies — World Football Index](https://worldfootballindex.com/2025/04/analyzing-the-role-of-data-analytics-in-english-premier-league-team-strategies/)
- [Technical Debt vs Feature Development — Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)
- [Optimize Streamlit Deployment — Towards Data Science](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/)
- [Streamlit Apps That Scale: Lessons From Real Projects — Medium](https://medium.com/@hadiyolworld007/streamlit-apps-that-scale-lessons-from-real-projects-8237f1ae6729)
