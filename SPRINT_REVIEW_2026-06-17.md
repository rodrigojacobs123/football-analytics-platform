# MANAGER SPRINT REVIEW & APPROVALS

**Author:** Analytics Engineering Manager
**Date:** 2026-06-17
**Project:** Club América Analytics Platform (TFM) — Streamlit + Pandas + Opta event data, 77 competitions
**Inputs consolidated:** Data Analyst (metrics & viz), Data Engineer (performance & storage), Data Architect (roadmap & data model)
**Prioritization framework:** MoSCoW, filtered through a single hard constraint — *this is a one-person thesis project with a finite defense deadline.* Effort that does not show up in the thesis writeup or the live demo is deprioritized regardless of technical merit.

---

## Decision context (why these calls)

Three facts from the codebase shaped every decision below:

1. **xT already exists.** `processing/xt.py` implements Karun Singh's 12×8 grid with per-player/per-team aggregation. The Data Analyst's "add xT" proposal is therefore ~70% done — the gap is *surfacing it in the UI*, not building it. This is the single highest-leverage move in the whole backlog: high impact, low remaining effort.
2. **No Parquet/DuckDB yet.** `data/loader.py` reads raw JSON/CSV under `@st.cache_data(ttl=3600)`. Caching is correctly applied, so the app is not pathologically slow — but the season-wide `matches.json` and on-demand `partidos/*.json` are the known hot paths. Storage migration is a *real* win but a *deep* one.
3. **Recent untracked work** (`archetypes.py`, `corner_defense.py`, `tactical_positions.py`, `plotly_pitch.py`) shows the developer is already mid-flight on new analytics. The sprint must *finish and integrate* in-flight work before opening new fronts — half-built features are the dominant risk to a thesis demo.

Industry context confirms the direction: Opta/StatsBomb-class dashboards in 2025–26 lead on **xT, PPDA, progressive actions, percentile radars, and advanced filtering** ([Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/), [The PFSA on xT/VAEP](https://thepfsa.co.uk/beyond-expected-goals-meet-xt-and-vaep-the-metrics-redefining-player-value/)), and the canonical Streamlit performance lever is binary columnar storage (Parquet/Arrow) behind cached loaders ([Streamlit perf guide](https://blog.streamlit.io/six-tips-for-improving-your-streamlit-app-performance/amp/)).

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

### 1. Surface Expected Threat (xT) in the UI — *the flagship metric*
- **What:** Wire the already-built `processing/xt.py` into the live app. Add an xT zone-value heatmap (Plotly, via existing `viz/plotly_pitch.py`), a per-player/per-team xT-added leaderboard, and an xT contribution column on Post-Match and Player Scouting.
- **Proposed by (conceptually):** Data Analyst (advanced metrics / industry parity).
- **Effort:** **Low–Medium (0.5–1 day).** Computation exists; this is a viz + page-wiring task. Reuse `viz/charts.py` and the dark Club América palette.
- **User impact:** **High.** xT is the headline "modern analytics" metric examiners will look for. It differentiates the platform from a basic stats dashboard and gives the thesis a strong narrative ("possession value, not just shots").
- **Implementation notes:** Verify coord mapping — Opta events are normalised 0–100 in `x` and `y`; `xt.py` expects the Karun grid orientation (x toward attacking goal). Confirm the axis convention before trusting the leaderboard. Add a one-line methodology caption citing karun.in for academic defensibility.

### 2. PPDA (pressing intensity) on the Tactics page
- **What:** Passes Per Defensive Action per team per match, plus a season trend. Definition: opponent passes allowed ÷ (your tackles + interceptions + challenges + fouls) in the opponent's defensive ⅔.
- **Proposed by (conceptually):** Data Analyst (pressing metrics).
- **Effort:** **Low (0.5 day).** It's a ratio over event counts the parser already extracts; no new data plumbing. Slots into the existing `4_Tactics` page.
- **User impact:** **High.** Pressing is a core tactical story for a Liga MX side; PPDA is the standard, recognisable measure. Cheap to compute, very legible in the demo.
- **Implementation notes:** Add a context caption — PPDA is noisy when a team is chasing a game ([KU Leuven on context](https://dtai.cs.kuleuven.be/sports/blog/valuing-on-the-ball-actions-in-soccer-a-critical-comparison-of-xt-and-vaep/)). Respect existing minimum-sample guards; show "low sample" rather than a misleading number early-season.

### 3. Finish & integrate the in-flight analytics (Corner Defense + Archetypes)
- **What:** Promote the untracked `corner_defense.py`/`13_Corner_Defense.py` and `archetypes.py`/`14_Player_Intelligence.py` from half-built to demo-ready: confirm they're registered in `app.py`'s `st.navigation` list, run them against real match data, and fix any breakage. Then **commit** them.
- **Proposed by (conceptually):** Data Architect (new page opportunities) — and already started by the developer.
- **Effort:** **Medium (1–1.5 days).** Logic exists; cost is testing, edge-case hardening, and nav wiring.
- **User impact:** **High.** Two distinctive pages that are *almost free* because the hard work is done. Leaving them half-finished is pure risk — uncommitted, unintegrated code that could rot before the defense.
- **Implementation notes:** These currently sit as untracked files (`git status`). Get them committed once verified — an unversioned demo feature is a liability. Do not start any *new* page until these two render cleanly end-to-end.

---

## 🔜 APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. Progressive actions (passes + carries) as a first-class metric
- **What:** Progressive passes/carries leaderboards and per-match counts (e.g. forward movement ≥ a threshold toward goal, ending in the attacking ⅓). Natural companion to xT.
- **Proposed by (conceptually):** Data Analyst.
- **Effort:** **Medium (1–1.5 days).** Reuses xT's pass/carry extraction; mostly thresholding + aggregation + a leaderboard view.
- **User impact:** **High.** Completes the modern on-ball-value triad (xT + PPDA + progression) that defines a 2025-era analytics platform.
- **Implementation notes:** Reuse `extract_passes`/`extract_take_ons` already imported in `xt.py`. Define "progressive" once in `config.py` and cite the convention.

### 2. Parquet conversion of the season-wide hot path (`matches.json`)
- **What:** Add a one-time build step that materialises the parsed season bundle to Parquet, and have `data/loader.py` prefer the Parquet artifact when present (JSON stays the source of truth + fallback).
- **Proposed by (conceptually):** Data Engineer (storage/performance).
- **Effort:** **Medium (1–2 days).** Touches the loader layer; needs careful cache-key and fallback handling.
- **User impact:** **Medium.** Faster cold loads and a smoother demo. Caching already hides most repeat-load latency, so this is an optimisation, not a rescue — hence next sprint, not now.
- **Implementation notes:** Scope to `matches.json` only this sprint; leave `partidos/*.json` on JSON (loaded on-demand, less painful). Keep all reads behind `data.loader` so caching/format choice stays in one place. Measure cold-load before/after to put a number in the thesis.

### 3. Advanced filtering on Player Scouting (the "scenario" filter)
- **What:** Filter leaderboards by minutes played, position group, competition, and home/away — the "find me players in scenario X" pattern that 2025 dashboards lead with ([Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/)).
- **Proposed by (conceptually):** Data Architect (data model / UX) + Data Analyst.
- **Effort:** **Medium (1 day).** Streamlit widgets over existing DataFrames.
- **User impact:** **Medium–High.** Turns static leaderboards into an interactive scouting tool — strong live-demo moment.
- **Implementation notes:** Enforce `MIN_APPEARANCES_FOR_RATING` inside the filter so sample-size noise can't be filtered *into* a misleading ranking.

---

## 📋 BACKLOG (Approved but deferred)

- **VAEP (Valuing Actions by Estimating Probabilities).** Conceptually excellent ([KU Leuven](https://dtai.cs.kuleuven.be/sports/blog/valuing-on-the-ball-actions-in-soccer-a-critical-comparison-of-xt-and-vaep/)), but it's an ML model needing labelled scoring/conceding outcomes and careful validation. xT already captures "possession value" for the thesis at a fraction of the cost. **Deferred:** redundant with xT for now; high build + validation cost against a thesis clock.
- **DuckDB query layer.** Real value at multi-million-row scale, but the app is single-process with effective caching. **Deferred:** Parquet captures most of the win; DuckDB is premature until profiling proves Pandas is the bottleneck.
- **`partidos/*.json` → Parquet.** Per-match files load on-demand and individually aren't the pain point. **Deferred:** revisit only if per-match pages feel slow after the season-bundle migration.
- **xT-based defensive metric (xDEF-style threat reduction).** Elegant extension once xT is live and trusted. **Deferred:** sequencing — ship and validate offensive xT first.
- **Manager/tactical comparison enrichments.** Nice-to-have polish on an existing page. **Deferred:** lower marginal impact than new headline metrics.

---

## ❌ REJECTED / NEEDS MORE RESEARCH

- **Full real-time / live-match ingestion.** No live Opta feed in scope; the dataset is historical JSON. Out of scope for a thesis platform. **Rejected.**
- **Migrating off Streamlit (e.g. to a JS frontend / FastAPI backend).** Massive rewrite, zero analytical value, enormous schedule risk. The architecture note is acknowledged but **rejected** for this project's lifetime.
- **Training a bespoke xG model from scratch.** xG already lives in Opta qualifier 395; re-deriving it is a research project, not a sprint item, and risks *worse* numbers than the provider's. **Needs more research** — only justified if the thesis specifically requires a self-built model section.
- **Multi-user / auth / deployment hardening.** Single-user thesis demo. **Rejected** as scope creep.

---

## ⚠️ RISK FLAGS

1. **Uncommitted in-flight code.** `corner_defense.py`, `archetypes.py`, `tactical_positions.py`, `plotly_pitch.py`, and two pages are untracked (`git status`). This is the top risk — work that isn't committed isn't safe. *Mitigation: Immediate-sprint item #3 forces verify-then-commit.*
2. **Coordinate/qualifier convention bugs.** The codebase has a documented history of exactly this (penalty Q9-vs-Q22, formation Q130-vs-row-counting in `CLAUDE.md`). xT and progressive actions both depend on coordinate orientation — *verify axis direction against a known event before trusting any new metric.*
3. **Early-season small samples.** New metrics (PPDA, xT-added, progression) are volatile with few matches. *Honor `MIN_*` guards and label low-sample cells — a misleading number in the defense is worse than an honest "insufficient data."*
4. **Feature-vs-stability tradeoff.** Every new page is demo surface that can break live. *Freeze the feature list after the Days 4–9 sprint; reserve the run-up to defense for hardening, not new metrics.*
5. **Parquet cache invalidation.** Introducing a derived artifact alongside source JSON creates a staleness risk. *Key the cache on source mtime and always keep JSON as authoritative fallback.*

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT

1. **xT is live and correct.** The xT heatmap + leaderboard render on a real match, and a hand-checked spot value (a known dangerous pass) matches the Karun grid within tolerance. *Binary: shipped & validated, or not.*
2. **Three recognised modern metrics visible in the app.** xT, PPDA, and the integrated corner/archetype pages all render end-to-end without error on live data — measured by a clean click-through of each page in the running app.
3. **Zero untracked feature files at sprint end.** Everything demoed is committed to git, and the app launches clean (`streamlit run app.py`, no import/runtime errors on the navigated pages). *Measured by `git status` clean for feature code + a successful cold start.*

---

*Prioritization is deliberately ruthless: finish what's started, ship the one metric that's 70% built, add the two cheapest high-recognition metrics, and defer everything that costs more than it demonstrates. Storage/ML depth is real but secondary to a complete, working, committed thesis demo.*

### Sources
- [Top Websites for Football Stats & Player Analytics 2025 — Football Toast](https://footballtoast.com/blog/top-websites-to-find-accurate-football-stats-and-player-analytics-in-2025/)
- [Beyond Expected Goals: xT and VAEP — The PFSA](https://thepfsa.co.uk/beyond-expected-goals-meet-xt-and-vaep-the-metrics-redefining-player-value/)
- [Valuing On-the-Ball Actions: xT vs VAEP — KU Leuven DTAI](https://dtai.cs.kuleuven.be/sports/blog/valuing-on-the-ball-actions-in-soccer-a-critical-comparison-of-xt-and-vaep/)
- [Six Tips for Improving Streamlit App Performance — Streamlit Blog](https://blog.streamlit.io/six-tips-for-improving-your-streamlit-app-performance/amp/)
- [FAQ: Improving performance of apps with large data — Streamlit](https://discuss.streamlit.io/t/faq-how-to-improve-performance-of-apps-with-large-data/64007)
- [MoSCoW Prioritization Method — monday.com](https://monday.com/blog/project-management/moscow-prioritization-method/)
- [Feature Prioritization: RICE, MoSCoW, Kano — Plane](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained)
- [MoSCoW Method — Wikipedia](https://en.wikipedia.org/wiki/MoSCoW_method)
