## DATA ANALYST REPORT — 2026-06-21 (cycle 4, 09:11)

### Executive summary

The three earlier cycles (2026-06-17 and two on 2026-06-21) drained the "first-generation" backlog (xT, PPDA, xGOT, field tilt, sequences — all shipped) and queued the "second-generation integrative" layer (VAEP/OBV, xGChain/xGBuildup, xP/PAx, packing proxy, set-piece xG, xT-momentum/Voronoi viz). **Those carry-overs remain valid and are NOT re-counted here.**

This cycle deliberately sources a *different* vein: 2025–26 industry releases that are (a) genuinely absent from `processing/`, verified by grep this run, and (b) computable from pure Opta event data — no tracking/360 freeze-frames. The throughlines in the literature this quarter are **team-shape geometry**, **game-state context-adjustment**, and **execution-vs-situation residual models** (aerial, pass-risk). I cross-checked every candidate against the codebase before listing it:

| Candidate | grep result | Verdict |
|---|---|---|
| Defensive line height | exists (`pressure.py:80`, `formations.py:232`) | ❌ skip — already ships |
| Block compactness / width / surface | 0 matches | ✅ new |
| Game-state segmentation (xG/xT by scoreline) | 0 matches | ✅ new |
| Aerial win-probability model | `extract_aerials()` exists but raw counts only | ✅ new (model layer) |
| Pass risk/reward decomposition | 0 matches | ✅ new |
| Line-breaking passes (StatsBomb 360 spec) | partial overlap w/ carry-over packing proxy | ✅ new (concrete binary spec) |
| Momentum chart / Pass sonar viz | 0 matches | ✅ new |
| Ball receipts in space, Pressing-Intensity (velocities), true pitch-control/Voronoi | — | ⚠️ tracking-only, flagged honestly below |

---

### Top 5 New Metrics to Implement

#### 1. Team block compactness, width & surface area · **Priority: HIGH** (NEW)
**What:** The shape geometry of the defending team. `line height` already ships, but the *spread* around it does not. Three numbers per team per game-phase:
- **Vertical compactness** = spread of own defensive-action x-coords (e.g. `x.quantile(.9) − x.quantile(.1)`, or stdev) — short = compact block.
- **Width** = same on the y-axis.
- **Surface area** = convex-hull area of the outfield defensive-action cloud (compact aggressive blocks shrink it).

**Why:** It is the single most-cited team-shape family in 2025 tactical writing (high line + tight compactness = aggressive press; deep + compact = low block). It directly answers "is América defending as a unit or stretched?" and pairs with the existing PPDA/line-height to give a full pressing picture. Pure pandas, no model.
**Compute (Opta event data, coords already normalised 0–100):**
```python
# processing/team_shape.py — reuse defensive-action filter already in pressure.py
defs = extract_defensive_actions(events, team_id)   # tackles 7, interceptions 8, etc.
shape = {
    "line_height":   defs.x.mean(),                       # parity with existing
    "vert_compact":  defs.x.quantile(.9) - defs.x.quantile(.1),
    "width":         defs.y.quantile(.9) - defs.y.quantile(.1),
    "block_surface": ConvexHull(defs[["x","y"]].values).volume,  # scipy; 'volume'==area in 2D
}
# Split by game_phases.py phase + by 15-min bucket to show the block stretching under pressure.
```
Trim outliers (a CB stepping into midfield) with the 10–90 quantile band, not min/max.

#### 2. Game-state-adjusted xG / xT (Gamestate score) · **Priority: HIGH** (NEW)
**What:** Every existing attacking metric (xG, xT, shots, field tilt) re-cut by **scoreline state** at the moment of the event: *losing / level / winning*. Reported as separate columns, not one blended number. Leading teams deliberately cede possession; trailing teams inflate xG against tired/open defences — raw season aggregates silently mix these regimes.
**Why:** This is the strongest "predictiveness" win in the 2025 literature (multiple arXiv/Sage papers this year). It makes Pre-Match form and Home-dashboard trends far more honest: "América's xT while level" is a much better signal of true level than blended xT. Low effort, high interpretive payoff.
**Compute:** derive a running scoreline from goal events (`typeId==16`) ordered by `timeMin/timeSec`, tag every event with `state ∈ {-1,0,+1}`, then `groupby(state)` over whatever metric:
```python
# processing/game_state.py
goals = events[events.typeId==16].sort_values(["timeMin","timeSec"])
# build a step function home_lead(t); join onto each event by time; state = sign(team_lead)
xg_by_state = shots.assign(state=tag_state(shots)).groupby("state").xg.sum()
```
Surface as a small 3-column table on `1_Home` and `2_Pre_Match_Analysis`; respect `MIN_MATCHES_FOR_PREDICTION` before trusting per-state splits.

#### 3. Aerial duel win-probability model (HOPS-style) · **Priority: MEDIUM** (NEW)
**What:** StatsBomb shipped **HOPS** (`hops_rating`) in 2025 — a per-player aerial-duel win-probability model. `extract_aerials()` already pulls the duels but only as raw win/loss counts. Upgrade to **expected aerials won**: model `P(win | location, attacking/defending, set-piece-or-open)`, then a player's `aerials_won − expected` isolates true aerial ability from "took lots of easy duels."
**Why:** The `PHY`/`Aerial` rating block in `player_ratings.py` currently leans on raw win%, which punishes target men who contest harder duels. This is the execution-residual pattern (mirror of xG→xGOT) applied to the air. Feeds Scouting directly.
**Compute:** logistic model on `extract_aerials()` features (x, y, is set-piece via qualifier, team in/out of possession); persist like `xg_model.py`. `expected_won = P.sum()`, `aerial_pax = won − expected` per 90. Guard with `MIN_APPEARANCES_FOR_RATING`.

#### 4. Pass risk/reward decomposition · **Priority: MEDIUM** (NEW)
**What:** For each attempted pass, two numbers: **reward** = `xT(end) − xT(start)` *if completed*, and **risk** = `P(incomplete) × xT_swing_to_opponent`. Net = `reward − risk`. Surfaces players who add threat *net of giveaways* — the 2025 EPV "reward & risk for passes" framework (arXiv 2502.02565).
**Why:** It reuses `xt.py` plus the carry-over `xP` model (#3 in the prior cycle) — so it's the natural sequel, not a duplicate: xP gives `P(complete)`, this prices the *consequence* of each outcome. Distinguishes a safe sideways-passer from a line-breaker who occasionally loses it but nets positive threat.
**Compute:** `processing/pass_value.py`; needs the carry-over xP model first, then pure arithmetic over `extract_passes()` end-coords (`QUAL_PASS_END_X/Y`). Aggregate net pass value per 90 into the `PAS` block.

#### 5. Line-breaking passes (StatsBomb 360 event-data proxy) · **Priority: MEDIUM** (NEW, refines carry-over packing)
**What:** StatsBomb's 2025 360 release defines a **line-breaking pass** precisely: a *completed* pass that (a) advances the ball **≥10% of pitch length** toward goal **and** (b) passes **behind the opponent defensive line** or between two close defenders. The carry-over "packing proxy" counts bypassed opponents generally; this is the canonical **binary** version with an exact, defensible spec — better for a TFM.
**Why:** "Did this pass break a line?" is more legible to coaches than a packing count, and the spec is reproducible. We can approximate the defensive line from the opponent's `team_shape.py` (#1) line-height at that timestamp — no tracking needed.
**Compute:**
```python
# in processing/progression.py (the carry-over module)
forward_gain = (end_x - start_x) >= 10          # ≥10% goalward
opp_line_x   = opponent_line_height_at(time)    # from #1, sampled per minute
breaks_line  = (start_x < opp_line_x) & (end_x > opp_line_x) & completed
```
Label it an *event-data approximation of the 360 metric* in-app for academic honesty.

---

### Top 3 Visualization Upgrades

#### 1. Match momentum chart → `3_Post_Match_Analysis` · **NEW**
An area chart of **home xT − away xT** in rolling ~3-min windows across the 90 (the AWS/Bundesliga "Match Momentum" pattern, but xT-based since we already have `xt.py`). Above-zero band shaded in `AME_YELLOW`, below-zero in the opponent colour; overlay goal markers. This is the long-promised "xT-momentum" carry-over made concrete — it turns the existing per-event xT into the single most engaging plot on the page.
**Implementation:** Plotly filled area; `viz/charts.py` new `momentum_chart(events)`; bucket xT by minute, rolling-mean window, `fill='tozeroy'` with two traces split on sign.

#### 2. Pass sonars → `4_Tactics` · **NEW**
Per-player polar bars at the player's average position: each wedge = a pass-direction bin, length = volume (or completion%), colour = avg xT gain. One sonar grid per XI gives an instant read of *how* each player distributes — far richer than the current arrow maps.
**Implementation:** `viz/pitch.py` + matplotlib polar insets on the mplsoccer pitch, or Plotly `barpolar` per player; bin `atan2(dy, dx)` of `extract_passes()` into 8–12 sectors.

#### 3. Team-shape / compactness overlay → `4_Tactics` · **NEW** (pairs with metric #1)
Convex-hull polygon of the defensive block + line-height marker + width band, per half or per game-phase. Visualises whether América holds shape or gets stretched.
**Honesty caveat for the TFM:** true **pitch control / Voronoi** needs all-22 tracking and is *not* derivable from event data — render the convex-hull of *event* locations and label it as such; do **not** present it as pitch control. (Same caveat retires the speculative "Voronoi" carry-over: scope it to the event-data hull, not full pitch control.)

---

### Emerging techniques (where the industry is moving)

- **Geometry over counts.** 2025 team analysis is shape-first: line height + compactness + width + surface area, segmented by phase — not aggregate possession %. (#1)
- **Context-adjustment is the new baseline.** Game-state, red-card, and venue adjustment of xG/xT is treated as *required* for predictiveness now, not optional. (#2)
- **Execution-vs-situation residuals everywhere.** The xG→xGOT idea (skill = actual − expected) has spread to passes (PAx), aerials (HOPS), and carries. Every raw rate is getting an "expected" twin. (#3, #4)
- **Unified possession value (OBV/VAEP/EPV) is the convergence point** — already our top carry-over; the field has fully standardised on one threat-currency per action.
- **Tracking-only frontier (flag, don't chase):** ball receipts in space, pressing-intensity via player velocities/reaction-times (arXiv 2501.04712), and genuine pitch control all need positional tracking data we do not have. Worth a one-line "future work with tracking data" note in the TFM rather than a fake event-data version.

---

### Recommended next actions (scoped to this Python/Streamlit codebase)

1. **Ship #2 (game-state segmentation) first** — highest payoff-to-effort: a `processing/game_state.py` tagger (~40 lines, pure pandas) plus a 3-column table on `1_Home` and `2_Pre_Match_Analysis`. No model, no new viz, immediate interpretive lift.
2. **Then #1 (team shape) + Viz #3 together** — one `processing/team_shape.py` (reuse `pressure.py`'s defensive-action filter; `scipy.spatial.ConvexHull` for surface) feeds directly into the Tactics overlay. Cache with `@st.cache_data(ttl=3600)` like the rest of the loaders.
3. **Build Viz #1 (momentum)** off existing per-event xT — closes the long-standing xT-momentum carry-over with one `viz/charts.py` function; cheapest high-visibility win for `3_Post_Match_Analysis`.
4. **Sequence the model work** — do the carry-over **xP** model before #4 (pass risk/reward depends on it) and before #5's break-detection; do #3 (aerial model) independently, persisted via the `xg_model.py` pattern.
5. **Documentation/honesty pass** — add a "Metrics derived from event data vs. requiring tracking" subsection to `11_Data_Sources`, explicitly listing the tracking-only frontier (pitch control, pressing intensity, receipts in space) as future work. Strengthens the TFM's methodological defensibility.
6. **Guardrails** — every per-state / per-90 split must respect `MIN_MATCHES_FOR_PREDICTION` / `MIN_APPEARANCES_FOR_RATING`; early-season Liga MX samples are thin and game-state buckets shrink fast.

**Carry-overs still open (re-validated, not re-counted):** VAEP/OBV unified action value, xGChain/xGBuildup, xP/PAx, packing proxy + `extract_carries()`, attacking set-piece xG.

---
*Sources:* [Hudl StatsBomb — Line-Breaking Passes & Ball Receipts in Space](https://www.hudl.com/blog/hudl-statsbomb-launch-new-360-metrics-line-breaking-passes-and-ball-receipts-in-space) · [StatsBomb Evolve — OBV/360](https://blogarchive.statsbomb.com/news/what-happened-at-statsbomb-evolve-360-data-quality-obv-and-more/) · [Revisiting EPV — reward & risk for passes (arXiv 2502.02565)](https://arxiv.org/html/2502.02565v1) · [Pressing Intensity (arXiv 2501.04712)](https://arxiv.org/pdf/2501.04712) · [Adjusting xG for game context (Sage, 2026)](https://journals.sagepub.com/doi/10.1177/22150218261454824) · [Minute-by-minute game-context adjustment (arXiv 2508.04008)](https://arxiv.org/pdf/2508.04008) · [Gamestate xG Score — Marc Lamberts](https://marclamberts.medium.com/gamestate-xg-score-expected-goals-adjusted-by-game-state-83bc40562d66) · [Bundesliga Match Momentum (AWS)](https://aws.amazon.com/blogs/media/bundesliga-match-fact-match-momentum-revealing-the-games-invisible-pulse/) · [PassSonar — Nightingale](https://medium.com/nightingale/passsonar-visualizing-player-interactions-in-soccer-analytics-7708e1d94afc) · [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html)
