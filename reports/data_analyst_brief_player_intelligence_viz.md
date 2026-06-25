# DATA ANALYST BRIEF — Player Intelligence visualization upgrades

**From:** Analytics Engineering Manager
**To:** Data Analyst
**Date:** 2026-06-25
**Page:** `pages/14_Player_Intelligence.py` (🧬 Player Intelligence)
**Status of the page:** Just hardened — it was landing "broken" (defaulting to an unclassified sub, leaking raw HTML in the Signal Breakdown, a dead Tournament selector). Those are now fixed. **Your job is the next layer: make it genuinely insightful, not just functional.** This brief is self-contained — assume no prior context.

---

## 1. What the page does today (so you don't rebuild it)

Three tabs, all driven by `processing/archetypes.py` over season-aggregate player stats:

- **Tab 1 — League Archetype Map:** an archetype-frequency horizontal bar, a single 2-metric scatter (Recoveries/90 vs Key Passes/90), and a filterable player table.
- **Tab 2 — Player Profile:** a header card, a **percentile radar** (player vs position, 50th-pct league-avg reference ring), a **Signal Breakdown** (per-archetype threshold chips), and a raw per-90 expander.
- **Tab 3 — Archetype Compatibility:** *the weakest tab.* Currently just a teammate-archetype bar + one metric-vs-league number + a static archetype catalogue. Its own caption admits it's a placeholder.

## 2. Data & conventions you must reuse (do not reinvent)

- **Archetype frame:** `assign_archetypes(compute_per90(load_all_player_season_stats(league, season)))` returns one row per player with: `nombre, posicion ('Forward'/'Midfielder'/'Defender'/'Goalkeeper'), equipo, id, archetype, arch_icon, arch_color, arch_desc`, every signal as `*_p90`, **and its within-position percentile as `*_p90_pct`** (0–100). Use the precomputed `_pct` columns — do not recompute percentiles ad hoc (the radar fix just aligned them).
- **Threshold:** `MIN_MINUTES = 450` (column `Time Played`). Players below it are `archetype == "Undefined"`. **Every new view must respect this** — grey out / exclude sub-threshold players, never present them as confident signal. (See memory [[def-rating-is-league-percentile]] and the minimum-sample guards in `CLAUDE.md`.)
- **Archetype catalogue:** `ARCHETYPES`, `archetypes_for_position(pos)`, `archetype_by_name(name)` in `processing/archetypes.py`. Each archetype dict has `name, icon, color, description, signals {sig: (lo_pct, hi_pct)}, priority`.
- **Similarity already exists:** `find_similar_players` at `processing/player_profile.py:360` (cosine on per-90). Reuse it — don't write a new similarity metric.
- **Theme:** Plotly `template="ame_dark"`; palette from `config.py` (`AME_YELLOW`, `AME_BLUE`, `AME_DARK_BG`). Club América is referenced by `AME_TEAM_ID`, never by name.
- **Caching rule (engineering constraint):** any new heavy aggregation must sit behind a `@st.cache_data(ttl=3600)` loader in `data/loader.py` or a cached wrapper — pages must not call raw `processing.*` on the rerun hot path. Pure-Plotly assembly over an already-computed frame can stay in the page.
- **HTML gotcha (just learned):** if you emit multi-line HTML via `st.markdown(..., unsafe_allow_html=True)`, flatten leading indentation (a `_html()` helper now exists in the page) or Markdown renders it as a code block.

## 3. Visualization tasks — prioritized (deliver as `viz/` functions + wire into the page)

Build these as functions in a new `viz/player_intel.py` (Plotly, return `go.Figure`), called from `pages/14_Player_Intelligence.py`. Each takes a DataFrame/Series in, returns a figure — no Streamlit calls inside `viz/`.

### P1 — Two-player comparison radar (Tab 2) · **highest value**
Overlay **two** players' percentile profiles on one radar (e.g. the selected player vs a chosen comparison player, same position). Today the radar is single-player; scouting is inherently comparative. Add a second player picker (default = next-highest-minutes same-position teammate). Distinct fill colors, shared 0–100 axis, keep the 50th-pct reference ring. Acceptance: selecting two CBs shows both polygons; axes are the union of their position's signals.

### P2 — Percentile "pizza" / fingerprint chart (Tab 2, alongside the radar)
The 2025 industry-standard player viz: a circular bar (`go.Barpolar`) where each wedge is a signal, wedge length = percentile, wedge color = attack/defend/possession group. More legible than the radar for ≥6 axes and directly comparable to StatsBomb/The Athletic player cards. Group signals by phase (finishing / creation / progression / defending) and color each group. Acceptance: a Deep Playmaker's creation/progression wedges visibly dominate; sub-threshold players are not rendered.

### P3 — Rebuild Tab 3 as a **Squad Archetype Balance** diagnostic
Replace the placeholder "compatibility" content with a real squad-construction view for the selected player's team:
- A **treemap or stacked bar** of the squad's archetype composition by position (how many Ball-Playing CBs, Deep Playmakers, etc.).
- A **gap callout**: which position-archetypes the squad is missing or thin on (e.g. "no Press Trigger, only 1 Wide Dribbler") — this is the genuinely useful recruitment signal.
Acceptance: for CF América it shows the real mix (e.g. 5 Ball-Playing CBs) and flags absent archetypes. Drop the misleading "compatibility" framing.

### P4 — "Players like X" similar-player panel (Tab 2)
Call `find_similar_players` for the selected player; render the top 5 as small cards (name, team, archetype icon, similarity score) with a mini percentile sparkline. Cross-league scope is fine. Acceptance: for a Deep Playmaker, the list returns other progressive midfielders, not random positions.

### P5 — Upgrade the Tab 1 scatter to a **style-space map**
The current 2-metric scatter (Recoveries vs Key Passes) is arbitrary. Replace with a 2-D embedding (PCA on the `_pct` signal matrix is enough — no UMAP dependency needed) colored by archetype, so clusters = play-styles. Keep hover = name/team/archetype. Acceptance: same-archetype players visibly cluster; the axes are labeled as principal components, not a single stat.

## 4. Scope guardrails (read before you start)

- **Event/tracking honesty:** this page is built on *season-aggregate counting stats*, not event or tracking data. Do **not** propose pitch-control, off-ball, or freeze-frame visuals here — out of scope and we don't license tracking. (Consistent with the standing "future work with tracking data" note.)
- **Effort budget:** this is a single-developer thesis. Deliver P1–P3 first (the high-value trio); P4–P5 are stretch. Each viz function should be ≲ a few hours.
- **No new heavy dependencies:** Plotly + numpy/pandas/scikit-learn (already in `requirements.txt`) only. PCA via `sklearn.decomposition.PCA` is fine.
- **Deliverable format:** a short report (your usual cycle format) listing each viz, the `viz/player_intel.py` function signature, the exact columns it consumes, and a 1-line acceptance check — plus the wiring change in `pages/14_Player_Intelligence.py`. Manual 1-player spot-check per viz is part of the deliverable.

## 5. Why this matters (the decision context)

The metric backlog is largely drained (xT, GVM, xGChain, MOU, momentum all shipped). The remaining lift on this page is **interpretive, not computational** — the 2025 dashboard standard rewards comparative, context-adjusted player narratives (radar overlays, pizza fingerprints, similarity, squad-balance), not more raw numbers. P1–P3 convert Player Intelligence from "a classifier with a table" into the recruitment/scouting surface a club analyst would actually use.
