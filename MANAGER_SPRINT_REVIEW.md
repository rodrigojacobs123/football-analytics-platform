# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** CLU AMÉRICA Sports Analytics (TFM) — Streamlit / Pandas / Plotly / mplsoccer
**Prepared by:** Analytics Engineering Manager
**Date:** 2026-06-17
**Inputs:** 3-day review reports from Data Analyst, Data Engineer, Data Architect
**Constraint:** Single developer, thesis timeline. Prioritization is ruthless by necessity.

---

## EXECUTIVE SUMMARY — what the code review changed

Before approving anything, I audited the live codebase against the three reports. This materially changed my decisions:

| Proposed "new" metric | Reality in repo | Verdict |
|---|---|---|
| Expected Threat (xT) | **Already built** — `processing/xt.py` (Karun Singh 12×8 grid), `viz/xt.py`. Surfaced **only** on Post-Match Analysis. | Don't rebuild — **expose** it |
| PPDA | **Already built** — `formations.py:compute_ppda()`, surfaced on Tactics. | Done — leave it |
| Progressive passes | **Already built** — surfaced on Tactics. | Done — leave it |
| Pressing / defensive-line / high-turnover metrics | **Built but ORPHANED** — `processing/pressure.py` is fully written and imported by **no page**. | **Surface it — biggest quick win** |
| VAEP | **Not present** anywhere in the repo. | Genuinely new + high-risk → defer |

**The headline:** the Data Analyst's flagship asks are ~70% already coded. The highest-ROI work this sprint is **surfacing analytics the developer already wrote**, not building new models. This is the cheapest possible path to visible thesis impact. Caching is already pervasive (`@st.cache_data(ttl=3600)` across `data/loader.py`), so the Data Engineer's "add caching" framing is also largely satisfied — the real engineering win is targeted, not foundational.

Prioritization framework applied: **MoSCoW**, scored on *user/thesis impact ÷ effort*, with a hard bias toward shipping already-written code ([MoSCoW method](https://en.wikipedia.org/wiki/MoSCoW_method), [Userpilot](https://userpilot.com/blog/moscow-prioritization/)).

---

## APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

### 1. Surface the orphaned pressing/turnover metrics (`pressure.py`) — MUST-HAVE
- **What:** `processing/pressure.py` already computes pressure regains, defensive-line height, ball-recovery height, high turnovers, and shot-ending high turnovers — none of it reaches a page. Wire it into the **Tactics** page (new "Pressing & Transitions" section) reusing the existing PPDA layout.
- **Proposed conceptually by:** Data Analyst (advanced pressing metrics / industry trends).
- **Effort:** **Low (~0.5–1 day).** The hard part (event approximation from Opta F24, which lacks native pressure events) is already done. This is plumbing + 2–3 Plotly charts.
- **Expected impact:** **High.** Pressing intensity and high-turnover-to-shot are exactly the metrics modern clubs surface ([Sportmonks key data points](https://www.sportmonks.com/glossary/key-data-points/), [The Football Analyst – PPDA](https://the-footballanalyst.com/ppda-football-statistics-explained/)). Converts dead code into a defensible thesis chapter on pressing identity.
- **Implementation notes:** Go through `data.loader` (cached) — do not re-parse JSON in the page. Respect `MIN_MATCHES_FOR_PREDICTION`-style sample guards; pressing metrics are noisy early-season. Add a one-line methodology caption noting these are Opta-approximated, not StatsBomb native (the module docstring already explains why).

### 2. Promote xT from Post-Match-only to a season-level player/team view — MUST-HAVE
- **What:** xT is computed but visible on a single match page. Add a season-aggregated xT contribution leaderboard (top ball progressors) to **Player Scouting** and a team xT panel to **Home**, reusing `processing/xt.py`'s existing per-player/per-team aggregation.
- **Proposed conceptually by:** Data Analyst.
- **Effort:** **Low–Medium (~1 day).** Aggregation functions exist; work is a new leaderboard table + one pitch-zone viz via `viz/xt.py`.
- **Expected impact:** **High.** xT-as-possession-value is the canonical "who actually creates threat" metric ([Jan Van Haaren – Soccer Analytics 2025](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)). High visibility for low cost.
- **Implementation notes:** Cache the season aggregation (it's heavier than per-match). Enforce `MIN_APPEARANCES_FOR_RATING` on the leaderboard to avoid a sub's one cameo topping the chart. Reference players by `AME_TEAM_ID`/player ID, not name.

### 3. Profile and cache the Post-Match Analysis hot path — MUST-HAVE (engineering)
- **What:** `pages/3_Post_Match_Analysis.py` is the largest page (67 KB) and loads heavy per-match `partidos/*.json`. Time the load, confirm `event_parser` outputs are cached per `match_id`, and memoize the most expensive DataFrame transforms.
- **Proposed conceptually by:** Data Engineer (Streamlit performance / caching strategy).
- **Effort:** **Low (~0.5 day).** Caching infrastructure already exists; this is auditing TTL coverage and adding `@st.cache_data` where parsing currently re-runs on rerun.
- **Expected impact:** **Medium–High.** Streamlit reruns the whole script on every interaction; uncached per-match parsing is the classic latency trap ([CompareePrice – Streamlit large datasets](https://www.comparepriceacross.com/post/master_large_datasets_for_peak_performance_in_streamlit/)). A snappy demo matters for the thesis defense.
- **Implementation notes:** Cache on `match_id`, not on the parsed DataFrame object. Capture a simple before/after timing in the commit message — this becomes a measurable "performance" line in the dissertation.

---

## APPROVED FOR NEXT SPRINT (Days 4-9)

### 4. Single Parquet conversion of the season bundle (`matches.json`) — SHOULD-HAVE
- **What:** Convert the season-wide `jsons/matches.json` (read by Home/Tactics/Scouting) into a Parquet cache on first load; read Parquet thereafter.
- **Proposed conceptually by:** Data Engineer (Parquet/columnar move).
- **Effort:** **Medium (~1.5 days).** New helper in `data/paths.py` + write-through cache in `data/loader.py`.
- **Expected impact:** **Medium.** Parquet gives columnar compression and far faster repeat scans ([DuckDB in Streamlit](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit)). Scoped to one file keeps risk contained.
- **Implementation notes:** **Parquet only — no DuckDB engine yet** (see Rejected). Keep JSON as the source of truth; Parquet is a derived cache that can be deleted/regenerated. Add to `.gitignore`.

### 5. VAEP feasibility spike (timeboxed, no production model) — SHOULD-HAVE
- **What:** A strictly timeboxed investigation: can a credible VAEP/action-value model be built from Opta F24 alone, and is it differentiated from the xT already shipped?
- **Proposed conceptually by:** Data Analyst.
- **Effort:** **Medium (2 days, hard cap).** Spike → written go/no-go, not an implementation.
- **Expected impact:** **Medium (de-risking).** Prevents the developer sinking a week into a model that may not beat existing xT for thesis purposes.
- **Implementation notes:** Output is a 1-page memo + a notebook, not a page. If the spike shows VAEP needs labelled training data or tracking data the dataset lacks, kill it immediately and bank xT as the possession-value story.

### 6. New "Pressing & Transitions" identity page (consolidation) — SHOULD-HAVE
- **What:** Promote the Day-1–3 pressing work into a dedicated page combining PPDA + `pressure.py` metrics + field tilt into a single team-identity dashboard.
- **Proposed conceptually by:** Data Architect (new page opportunities).
- **Effort:** **Medium (~1.5 days).** Mostly composition of items #1 and existing PPDA.
- **Expected impact:** **Medium–High.** A coherent narrative page demos better than scattered metrics.
- **Implementation notes:** Register explicitly in `app.py`'s `st.navigation` list (pages are NOT auto-discovered). Reuse `viz/theme.py` palette; no new theming.

---

## BACKLOG (Approved but deferred)

- **DuckDB query engine over Parquet** — Good long-term direction ([Developers Voice – Streamlit + DuckDB](https://developersvoice.com/blog/data-analytics/streamlit-duckdb-production-dashboards/)), but the dataset is not yet large enough to justify the dependency and rewrite. Revisit only if Parquet (#4) proves insufficient.
- **Dynamic xT (DxT) / off-ball-adjusted threat** — Cutting-edge but requires positional/tracking data the Opta F24 feed doesn't carry. Out of reach with current data.
- **Heatmap/positional upgrades across all pages** — Nice polish, but heatmaps already exist on Post-Match. Cosmetic; defer until core metrics are surfaced.
- **VAEP production model** — Conditional on the #5 spike returning "go". Not pre-approved.
- **Manager/Archetype page expansions** (`tactical_positions.py`, `archetypes.py`) — Promising orphaned modules, but lower thesis-narrative priority than pressing/xT.

**Why deferred:** Each is either blocked by data the dataset lacks, or it competes for the same single-developer hours as higher-ROI "surface what's already built" work.

---

## REJECTED / NEEDS MORE RESEARCH

- **Full migration to Parquet/DuckDB as the primary store (this sprint).** REJECTED for now. Rewriting `data/loader.py`'s entire I/O layer mid-thesis is high-risk for a single dev with no test suite. The incremental Parquet cache (#4) captures most of the benefit at a fraction of the risk.
- **Building VAEP before the feasibility spike.** REJECTED. No evidence yet it beats the xT already in production; risks duplicating possession-value work.
- **Any architecture change that bypasses the `data/ → processing/ → viz/` layering** (e.g. pages reading JSON directly for speed). REJECTED outright — violates `CLAUDE.md` and would erode the clean architecture that is itself a thesis asset.

---

## RISK FLAGS

1. **No test suite + no linter.** Every refactor (caching, Parquet) is unguarded. *Mitigation:* keep changes small, verify each page renders in the running app before committing; add at least smoke assertions for `pressure.py` outputs.
2. **Orphaned/uncommitted code sprawl.** `git status` shows ~45 modified files plus untracked new pages (`13_Corner_Defense`, `14_Player_Intelligence`) and modules (`archetypes`, `tactical_positions`, `gap_analysis`) all uncommitted. *Mitigation:* commit the working tree in logical chunks **before** sprint work begins — a single catastrophic loss right now would be unrecoverable.
3. **Metric methodology must be labelled.** `pressure.py` metrics are Opta *approximations* of StatsBomb pressure events. Surfacing them without a caption inviting that nuance is an examiner-bait risk. *Mitigation:* methodology captions on every approximated metric.
4. **Early-season sample noise.** Default season `2025-2026` is thin. Respect `MIN_APPEARANCES_FOR_RATING` / `MIN_MATCHES_FOR_PREDICTION` on every new leaderboard.
5. **Tech-debt vs. features tension** is real even for a solo dev ([Pete Ratkevich – balancing tech debt](https://medium.com/getting-started-in-product/the-art-of-prioritization-how-to-balance-feature-requests-and-technical-debt-without-losing-your-9810dc34fb2e)). This sprint deliberately front-loads low-effort feature exposure (#1, #2) and only *one* infra item (#3) to keep momentum visible.

---

## SUCCESS METRICS FOR THIS SPRINT

1. **Coverage of already-written analytics:** `processing/pressure.py` goes from **0 → ≥1** referencing page, and xT from **1 → ≥3** referencing pages. (Verifiable by `grep -rl "import pressure\|processing.xt" pages/`.)
2. **Post-Match page load time:** measured end-to-end load of a single match drops by **≥30%** after the caching audit (#3), captured as a before/after timing in the commit.
3. **No regression / clean ship:** all currently-registered pages in `app.py`'s `st.navigation` render without error after changes, and the working tree is committed in coherent chunks (closing Risk #2). Zero pages bypass the `data/→processing/→viz/` layering.

---

### Sources
- [MoSCoW method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)
- [MoSCoW Prioritization — Userpilot](https://userpilot.com/blog/moscow-prioritization/)
- [Balancing feature requests and technical debt — Medium](https://medium.com/getting-started-in-product/the-art-of-prioritization-how-to-balance-feature-requests-and-technical-debt-without-losing-your-9810dc34fb2e)
- [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
- [Key data points — Sportmonks](https://www.sportmonks.com/glossary/key-data-points/)
- [PPDA explained — The Football Analyst](https://the-footballanalyst.com/ppda-football-statistics-explained/)
- [Master Large Datasets in Streamlit — ComparePriceAcross](https://www.comparepriceacross.com/post/master_large_datasets_for_peak_performance_in_streamlit/)
- [Using DuckDB in Streamlit — DuckDB](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit)
- [Streamlit + DuckDB production dashboards — Developers Voice](https://developersvoice.com/blog/data-analytics/streamlit-duckdb-production-dashboards/)
