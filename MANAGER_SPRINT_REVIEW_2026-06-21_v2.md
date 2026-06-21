# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM) — Streamlit / Pandas / Plotly / mplsoccer, Opta F24 event data across 77 competitions
**Prepared by:** Analytics Engineering Manager (autonomous 3-day cycle run — no developer present)
**Date:** 2026-06-21 (cycle v2 — supersedes the earlier same-day draft after a fresh code audit)
**Inputs consolidated:** Data Analyst report `reports/data_analyst_report_2026-06-21.md` (metrics & viz); Data Engineer & Data Architect themes carried from the standing reviews (performance/storage; roadmap/data-model) — no fresh standalone files were submitted this cycle, so their asks are re-derived from the live repo state.
**Prioritization framework:** **MoSCoW inside a fixed timebox** ([Agile Business Consortium / DSDM](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html), [Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)), cross-checked with **Impact/Effort/Risk** screening ([Plane — RICE/MoSCoW/Kano](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained), [NetSolutions — MVP feature prioritization](https://www.netsolutions.com/hub/minimum-viable-product/prioritize-features/)). One hard constraint dominates everything: **single-developer thesis on a finite defense clock.** DSDM's rule — Must-Have effort ≤ ~60% of the timebox — is enforced below.

---

## EXECUTIVE SUMMARY — the audit overrides the analyst's premise

I re-audited the live repo (`git status`, `grep`) before approving anything. The result changes the plan:

| Claim / prior ask | Verified state today | Verdict |
|---|---|---|
| Analyst report states `xdef.py` "now exists … good" and moves on to new metrics | **File exists but is `?? processing/xdef.py` (untracked) and `grep -rl xdef pages/` → 0 pages** | 🔴 **NOT shipped — built, unwired, unversioned** |
| Prior manager review #1 — wire `xdef.py` into UI | **Still open** — zero pages import it | 🔴 Carry forward, top of queue |
| Prior manager review #2 — commit untracked feature tree | **Still open** — `xdef.py`, `corner_defense.py`, `archetypes.py`, `tactical_positions.py`, `plotly_pitch.py`, pages `13`/`14` all `??` | 🔴 **Top risk — broken-on-clone live** |
| Analyst's new flagship asks (xGOT, sequences, xP, set-piece xG, PAdj) | **None exist** (`processing/xgot.py` etc. absent; no goalmouth qualifiers in `config.py`) | ✅ Genuine gaps — but they go *behind* the unshipped foundation |

**The headline:** last cycle's two must-haves did **not** land, and `app.py` is already modified to reference page files that are not in git — meaning a single `git commit app.py` produces a **broken nav on any fresh clone**. The Data Analyst's 2026-06-21 report is analytically strong (xGOT/goalkeeping is the correct frontier — [Stats Perform xGOT](https://www.statsperform.com/insights/introducing-expected-goals-on-target-xgot/), [Football Analytics AI tracks 56 PL keepers this season](https://footballanalytics.ai/data/best/premier-league/gk/2025-26)), but it builds on a premise the repo contradicts. **This sprint is therefore "finish, wire, and commit," not "build new."** The industry signal agrees: 2025 dashboards win on *advanced metrics surfaced with context*, not raw model count ([Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/), [Comparisonator](https://comparisonator.com/blog/top-5-football-data-analytics-tools-for-clubs-agents)), and unmanaged technical debt inflates cost 10–20% and can blow schedules by up to 66% ([Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)).

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

### 1. Commit & verify the untracked feature tree — *MUST-HAVE (de-risk), do this FIRST*
- **What it is:** Smoke-test each new page on real match data, then **commit in logical chunks**: `processing/xdef.py`, `corner_defense.py`, `archetypes.py`, `tactical_positions.py`, `viz/plotly_pitch.py`, and pages `13_Corner_Defense` / `14_Player_Intelligence`. Critically: commit `app.py` **in the same commit** as the page files it references, so nav never points at a missing file.
- **Proposed conceptually by:** Data Architect (integration/new-page hygiene) + Data Engineer (repo health).
- **Effort:** **Low (~0.5–1 day)** — a click-through of each page + staged commits. No new code.
- **Expected user impact:** **High (risk elimination).** Converts ~7 unversioned files into safe, demonstrable thesis features and removes the single largest threat to the defense — code that only exists on one laptop.
- **Implementation notes:** Verify all 14 registered nav pages render before staging. Keep `.streamlit/`, the `testeo_ligas_norteamerica.zip`, and any future Parquet artifacts out via `.gitignore`. This is non-negotiable and gates everything below.

### 2. Wire the orphaned `xdef.py` into the UI — *MUST-HAVE, flagship of this cycle*
- **What it is:** `processing/xdef.py` already computes Expected Defensive Threat Reduction (the defensive mirror of xT, via the Karun-grid flip `xt_value(100 − x, y)`) and reaches no page. Surface it: a **"Defensive Threat Denied (per 90)" leaderboard** on Player Scouting, and fold `xdef_summary` into the count-based **`DEF`** attribute in `processing/player_ratings.py`.
- **Proposed conceptually by:** Data Analyst (xDEF was the prior cycle's #1 HIGH; defensive action-valuation is the clearest 2025 gap).
- **Effort:** **Low (~0.5–1 day).** The hard part (grid reuse, coordinate flip, defensive-event extraction) is already written — this is a leaderboard + one rating-block edit + a caption.
- **Expected user impact:** **High.** Turns "made a tackle" into "denied 0.018 of threat in a dangerous zone" — the headline modern-analytics differentiator an examiner looks for, and it makes `DEF` defensible rather than a raw count.
- **Implementation notes:** Validate the `100 − x` flip against one known deep defensive action before trusting the board (the repo has a documented coordinate-bug history — see `CLAUDE.md`). Enforce `MIN_MINUTES_FOR_RATING` so a sub's lone clearance can't top the chart. One-line methodology caption (Opta-approximated). Read via `data.loader`, never direct JSON.

### 3. Possession-Adjusted (PAdj) defensive metrics — *SHOULD-HAVE, cheap & thematically paired*
- **What it is:** Normalise raw defensive counts (tackles, interceptions, clearances, recoveries) by the team's volume out of possession: `PAdj = raw × (league_avg_opp_possession / team_opp_possession)`. Feed the adjusted counts into the `DEF` rating block.
- **Proposed conceptually by:** Data Analyst (new report, metric #5 — flagged as cheap, high value-per-effort).
- **Effort:** **Low (~0.3 day, ~30 lines).** No model, no new dependency — a helper in `processing/pressure.py` reusing counts already produced there.
- **Expected user impact:** **Medium–High.** América is a high-possession side in Liga MX, so raw counts systematically *under-credit* its defenders. PAdj removes that bias and makes cross-team scouting honest. Pairing it with item #2 lets this sprint ship a *complete, defensible defensive-rating overhaul* — "we value defensive actions (xDEF) **and** strip volume bias (PAdj) **and** committed it all" is a clean dissertation narrative.
- **Implementation notes:** Possession share = opponent passes faced ÷ league average. Label it a StatsBomb-style approximation in the caption.

> **Timebox check:** Must-Have effort (items 1+2) ≈ 1–2 dev-days; item 3 adds ~0.3 day. Total ~1.5–2.3 days against a 3-day window — within the DSDM ≤60% rule, leaving slack for the inevitable coordinate/edge-case debugging this repo's history guarantees.

---

## 🔜 APPROVED FOR NEXT SPRINT (Days 4–9)

### 4. xGOT / Post-Shot xG + the platform's first goalkeeper metric — *MUST-HAVE next sprint, the headline NEW build*
- **What it is:** `xGOT(shot) = P(goal | xG, goalmouth_y, goalmouth_z)` on on-target shots (`typeId ∈ {15,16}`). Player finishing = `Σ(xGOT) − Σ(xG)`; **GK shot-stopping +/− = Σ(xGOT_faced) − goals_conceded** — a goalkeeper dimension the platform currently lacks **entirely**. Plus the goalmouth shot-placement viz (goal-frame, coloured by `xGOT − xG`).
- **Proposed conceptually by:** Data Analyst (new report, metric #1 HIGH + viz #1).
- **Effort:** **Medium (~2–2.5 days).** New `config.py` qualifiers (`QUAL_GOALMOUTH_Y=102`, `QUAL_GOALMOUTH_Z=103`), extend `extract_shots()`, new `processing/xgot.py` with a cached model mirroring `xg_model.py`, new GK profile + viz.
- **Expected user impact:** **Very high.** The single biggest analytical gap (zero GK metrics today) and squarely the 2025-26 frontier — [Opta now reads goalkeeper position per shot](https://theanalyst.com/articles/what-are-expected-goals-on-target-xgot), and clubs rank keepers on xGOT-based shot-stopping. Highest examiner-impact item in the whole backlog.
- **Why not immediate:** Too large to safely co-land with the commit+wire foundation in one 3-day window. It needs new qualifiers, a new fitted/validated model, a new viz, and a new profile — sequencing it as the lead item of the next sprint protects both.
- **Implementation notes:** Verify Q102/Q103 axis orientation against one known top-corner goal before trusting the model (coordinate-bug history). Static "shot-placement zone" lookup as fallback if early-season placement data is thin. Honor `MIN_*` guards on the GK board.

### 5. Sequence/possession layer → Directness + Direct Speed + playing-style quadrant — *SHOULD-HAVE*
- **What it is:** Group events into sequences/possessions; derive `Directness = Σ upfield progress / Σ pass length` and `Direct Speed = progress / time`. Surface as the signature **Direct-Speed × sequence-length quadrant scatter** (teams as points, América in yellow), feeding Tactics / Home / Pre-Match.
- **Proposed conceptually by:** Data Analyst (new report, metric #2 HIGH + viz #2).
- **Effort:** **Medium (~1.5 days).** New `processing/sequences.py` (pure pandas) reusing possession-change logic implicit in `pressure.py`.
- **Expected user impact:** **High.** Adds the missing *team-identity* layer (`play_style.py` today describes player archetypes, not build-up identity) and gives Pre-Match an instant opponent-style read — exactly the "playing style / role" context modern scouting dashboards lead with ([Comparisonator](https://comparisonator.com/blog/top-5-football-data-analytics-tools-for-clubs-agents)).
- **Implementation notes:** Define the sequence-break rules once and reuse; aggregate to per-team season means in `season_tactics.py`.

### 6. Post-Match caching audit + single Parquet conversion of `matches.json` — *SHOULD-HAVE (engineering, keep the demo fast as features land)*
- **What it is:** (a) Audit `pages/3_Post_Match_Analysis.py` so per-match `partidos/*.json` parsing is memoized on `match_id`, not on a parsed object; (b) write-through Parquet cache for the season-wide `jsons/matches.json` (read by Home/Tactics/Scouting), JSON stays source-of-truth + fallback.
- **Proposed conceptually by:** Data Engineer (caching strategy + columnar storage).
- **Effort:** **Medium (~1–1.5 days).** Caching infra (`@st.cache_data(ttl=3600)`) is already pervasive in `data/loader.py`; this is coverage + one new helper, not new plumbing.
- **Expected user impact:** **Medium.** Streamlit re-runs the whole script on every interaction, so uncached per-match parsing is the classic latency trap; caching keeps the defense demo snappy as six new metrics pile on. Manage cache size with `ttl`/`max_entries` to avoid the memory blow-up ([Towards Data Science](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/), [Streamlit caching docs](https://docs.streamlit.io/develop/api-reference/caching-and-state)).
- **Implementation notes:** Key the Parquet cache on source mtime; `.gitignore` the artifact. Capture a before/after cold-load timing — it becomes a measurable performance line in the dissertation.

---

## 📋 BACKLOG (Approved but deferred)

- **Expected Pass Completion (xP) + PAx + xPT** *(Analyst #3, MEDIUM-HIGH)*. Real value (separates passing ambition from execution), but it's a *second* cached model competing for the same model-building hours as xGOT. **Deferred:** build it after xGOT proves the cached-model pattern; it slots in cleanly next to the still-open packing/line-break proxy.
- **Set-Piece xG + attacking corner-threat** *(Analyst #4, MEDIUM)*. High tactical relevance (set pieces ~23% of top-flight goals this season) and the natural complement to the existing `corner_defense.py`. **Deferred:** a third segmented model; sequence the modelling work, don't parallelize it on one developer.
- **Progressive carries from events + packing proxy** *(carried from the 2026-06-17 cycle)*. Completes the on-ball-value triad. **Deferred:** behind wiring xDEF and shipping xGOT; reuses take-on extraction already in `xt.py`.
- **`viz/pizza.py` hardening** (percentiles not raw counts; attack/defence slice grouping; usage+outcome mix). Cheap and academically defensible. **Deferred:** promote the next time Scouting is touched — it showcases the new xGOT/PAx execution metrics best once they exist.
- **Advanced "scenario" filtering on Scouting** (minutes / position / competition / home-away). Strong demo moment. **Deferred:** competes for the same hours as surfacing built analytics.
- **VAEP / unified action-value (`processing/action_value.py`).** The eventual industry standard (OBV/VAEP). **Deferred to a season-end milestone** and gated on the feasibility spike below — xT + the now-surfaced xDEF cover possession value for the thesis at a fraction of the cost.

**One-line rationale:** each is either blocked by data the Opta F24 feed lacks, or it competes for the same single-developer hours as higher-ROI "surface / finish what's already built" work.

---

## ❌ REJECTED / NEEDS MORE RESEARCH

- **Full migration to Parquet/DuckDB as the *primary* store this term.** **REJECTED.** Rewriting `data/loader.py`'s entire I/O layer mid-thesis with no test suite is high-risk; the incremental Parquet cache (item #6) captures most of the win safely.
- **DuckDB query engine.** **REJECTED for now.** Dataset isn't large enough to justify the dependency; Parquet alone captures the benefit.
- **VAEP production model before a timeboxed spike.** **NEEDS MORE RESEARCH.** No evidence yet it beats the shipped xT/xDEF for thesis purposes. Approve only a **2-day hard-capped feasibility spike → 1-page go/no-go memo**, never an unbounded implementation.
- **Off-ball valuation / GNNs / Dynamic xT (DxT) / pitch-control from tracking.** **OUT OF REACH.** Requires positional/tracking data the F24 event feed does not carry. Flag as aspirational in the literature-review chapter, do not build.
- **Bespoke xG model from scratch.** **REJECTED for the sprint.** xG already lives in Opta qualifier 395; re-deriving risks *worse* numbers than the provider. (Note: xGOT in item #4 *extends* xG with placement — it does not re-derive it. Keep the provider's pre-shot xG.)
- **Real-time/live ingestion, migrating off Streamlit, multi-user/auth/deployment hardening.** **REJECTED.** No live feed in scope; large rewrites with zero analytical value for a single-user thesis demo — pure scope creep against the defense clock.

---

## ⚠️ RISK FLAGS

1. **Broken-on-clone (VERIFIED LIVE — top priority).** `app.py` references pages `13`/`14` that are untracked; any commit of `app.py` without them breaks nav on a fresh checkout. *Mitigation: item #1 — commit `app.py` and its page files atomically, first.*
2. **The plan keeps re-flagging the same hygiene (NEW concern).** Wiring xDEF and committing the tree were *last* cycle's must-haves and **still did not ship**. Repeating an unshipped must-have is how technical debt compounds. *Mitigation: this cycle's success metric #1 is binary — the foundation closes or the sprint failed. Do not start item #4 until items #1–#2 are green.*
3. **Uncommitted feature sprawl.** ~7 new `.py` files + ~45 modified files are unversioned — work that isn't committed isn't safe. *Mitigation: staged commits before any new build.*
4. **No test suite, no linter.** Every refactor (caching, Parquet, PAdj) is unguarded. *Mitigation: keep changes small; verify each page renders in the running app before committing; add lightweight smoke assertions on `xdef.py`/`pressure.py` outputs.*
5. **Coordinate / qualifier convention bugs.** Documented history (penalty Q9-vs-Q22, formation Q130-vs-row-count). xDEF's `100 − x` flip and the new goalmouth `Q102/Q103` for xGOT both depend on axis orientation. *Mitigation: verify each against a known event before trusting any metric.*
6. **Model proliferation.** xGOT, then xP, then set-piece xG each add a cached model + a failure surface, on a codebase with no tests. *Mitigation: land **one** model per sprint, validated, before approving the next — enforced by the backlog sequencing above.*
7. **Methodology labelling.** `pressure.py`, `xdef.py`, and PAdj are Opta *approximations* of StatsBomb-native concepts. Surfacing without a caption is examiner-bait. *Mitigation: a one-line methodology caption on every approximated metric.*
8. **Early-season sample noise.** Default season `2025-2026` is thin; new leaderboards (xDEF-p90, PAdj, GK shot-stopping) are volatile. *Mitigation: honor `MIN_*` guards; show "low sample" over a misleading number.*

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

1. **Zero untracked feature files + clean cold start.** `git status` shows no untracked feature code, and a cold `streamlit run app.py` renders **all 14 registered nav pages** without import/runtime error. *Binary — closes Risk #1 and #3.*
2. **xDEF is live, possession-adjusted, and spot-checked.** `grep -rl xdef pages/` returns **≥1**, the `DEF` rating consumes PAdj-adjusted counts, and one hand-checked "threat denied" value (a known deep defensive action) matches the flipped Karun grid within tolerance. *Binary — shipped & validated, or not.*
3. **No regression in demo responsiveness.** With the three immediate items merged, a cold Post-Match load is no slower than baseline (and, once item #6 lands next sprint, ≥30% faster) — captured as a before/after timing in a commit message for the dissertation.

---

*Prioritization is deliberately ruthless. The Data Analyst's xGOT/goalkeeping direction is correct and approved — but it is sequenced **behind** the foundation, because the repo audit shows last cycle's must-haves never shipped and `app.py` is one commit away from a broken demo. This sprint's job is to **commit the in-flight work, wire and possession-adjust the one built-but-orphaned metric (xDEF), and keep the demo fast** — then lead the next sprint with the platform's first goalkeeper metric. Finish before you build.*

### Sources
- [MoSCoW Prioritisation — Agile Business Consortium (DSDM)](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html)
- [MoSCoW method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)
- [Feature prioritization: RICE, MoSCoW, Kano — Plane](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained)
- [How to Prioritize MVP Features — NetSolutions](https://www.netsolutions.com/hub/minimum-viable-product/prioritize-features/)
- [Top 5 Football Data Analytics Tools for Clubs & Agents — Comparisonator](https://comparisonator.com/blog/top-5-football-data-analytics-tools-for-clubs-agents)
- [Top Websites for Football Stats & Player Analytics 2025 — Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/)
- [Best Premier League Goalkeepers 2025-26 (56 keepers tracked) — Football Analytics AI](https://footballanalytics.ai/data/best/premier-league/gk/2025-26)
- [Introducing Expected Goals on Target (xGOT) — Stats Perform](https://www.statsperform.com/insights/introducing-expected-goals-on-target-xgot/)
- [What Are Expected Goals on Target (xGOT)? — Opta Analyst](https://theanalyst.com/articles/what-are-expected-goals-on-target-xgot)
- [Technical Debt vs Feature Development — Logiciel](https://logiciel.io/blog/technical-debt-vs-feature-development-whats-the-tradeoff)
- [Optimize Streamlit Deployment — Towards Data Science](https://towardsdatascience.com/optimize-streamlit-deployment-1b9bb0e415b/)
- [Caching and state — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state)
