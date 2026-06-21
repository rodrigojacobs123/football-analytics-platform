## DATA ANALYST REPORT — 2026-06-17

**Platform:** CLUB AMÉRICA Sports Analytics Platform (TFM)
**Cycle:** Continuous-improvement run (every 3 days)
**Scope:** Opta F24 event data — North American + CONCACAF competitions, season 2025-2026
**Analyst:** Automated senior-analyst agent (autonomous run, no user present)

---

### Executive summary

The platform already implements a strong core of modern metrics. A codebase audit confirms we **already ship**: Expected Threat (`processing/xt.py`, Karun-Singh 12×8 grid), PPDA and Field Tilt (`processing/formations.py`), progressive-pass counts, defensive-line height / ball-recovery height / high-turnover detection (`processing/pressure.py`), FC-style player ratings and play-style/archetype detection (`processing/player_ratings.py`, `archetypes.py`, `play_style.py`).

So the recommendations below are deliberately **incremental — they fill the gaps the industry has moved into in 2024-2025**, not re-builds. The single biggest theme across StatsBomb/Hudl, Opta (Stats Perform) and the 2025 academic literature is **on-ball value / action-value models that also value defensive and off-ball actions** (OBV, VAEP, xDEF, DxT) — we currently value *attacking* ball-progression (xT) but not the defensive side of the same coin. That is our highest-leverage gap.

---

### Top 5 New Metrics to Implement

#### 1. xDEF — Expected Defensive Threat Reduction · **Priority: HIGH**
**What:** Values each *defensive* action (tackle, interception, clearance, block, ball recovery) by the attacking xT it cancelled. This is the defensive mirror of our existing xT and is the cheapest high-impact win because the grid and event extractors already exist.
**Why it matters:** Our Player Scouting `DEF` rating is currently count-based (tackles, interceptions). xDEF turns "made a tackle" into "denied 0.018 of threat in a dangerous zone," which is exactly the OBV/VAEP-defensive direction StatsBomb and the 2025 *Journal of Big Data* valuation paper are pushing.
**How to compute from Opta event data:**
- For each defensive event by the defending team (`typeId` 7 tackle, 8 interception, 12 clearance, 74 blocked pass, 49 ball recovery), find the **immediately preceding opponent on-ball event** (the pass/carry being stopped) within ~3 s.
- Look up `XT_GRID` value at the opponent's ball location (reuse the `_cell()` helper already in `processing/xt.py`).
- `xDEF = xT[location_of_stopped_action]` — credit the defender with the threat extinguished. Weight clearances under pressure higher.
- Aggregate per-player per-90 with the existing `MIN_MINUTES_FOR_RATING` guard.
**Implementation hint:** New `processing/xdef.py` importing `XT_GRID` and the `_cell()`/coordinate mapper from `xt.py`; extractors already exist in `data/event_parser.py` (`extract_tackles`, `extract_interceptions`, `extract_clearances`, `extract_ball_recoveries`). ~80 lines, no new dependencies.

#### 2. Possession-Value Added (VAEP/OBV-style action value) · **Priority: HIGH**
**What:** A single per-action value covering *all* on-ball actions — passes, carries, dribbles, shots, fouls won, defensive actions — expressed as Δ(P_score) − Δ(P_concede) for the next N actions. The industry standard (StatsBomb OBV across 140+ comps; VAEP in academia).
**Why it matters:** xT only values *successful ball moves into more dangerous space*. It ignores shot quality, turnovers, fouls won, and defensive recoveries. A unified action-value column lets every page rank players/teams on one honest currency and feeds a far better Player Scouting overall.
**How to compute from Opta event data (event-data tractable variant):**
- Frame as two gradient-boosted classifiers (`xgboost`, already common in the stack) predicting `P(goal scored in next 10 actions)` and `P(goal conceded in next 10 actions)` from features: start/end x,y, action type, distance/angle to goal, time, body part (`QUAL_BODY_PART=72`), under-pressure proxy.
- `VAEP(action) = [Pscore_after − Pscore_before] − [Pconcede_after − Pconcede_before]`.
- Train once on the season-wide `jsons/matches.json` bundle, cache the model, score per-match on demand.
**Implementation hint:** New `processing/action_value.py`; persist the fitted model under a cached artefact so it isn't retrained every rerun (mirror the pattern in `xg_model.py`). Start with xT as the label-free fallback if labelled training proves noisy early-season.

#### 3. Packing / Bypassed-Opponents proxy (line-breaking passes) · **Priority: MEDIUM**
**What:** Per pass/carry, how many opponents were taken out of the game (ball moved goal-side of them). True packing needs tracking data we don't have, so implement the **event-data proxy**: line-breaking passes that cross from one third/zone band into the next toward goal, plus through-balls (`QUAL` through-ball) and passes received between the lines.
**Why it matters:** Distinguishes a 5-yard sideways pass from a vertical pass that eliminates a midfield line — central to "build-up disruption / progression quality," a 2025 focus area. Strengthens the Tactics page beyond raw progressive-pass *counts* we already show.
**How to compute:**
- Reuse `extract_passes()`. Classify each completed pass by zone-band crossing using start/end x (`QUAL_PASS_END_X=140`, `QUAL_PASS_END_Y=141`): forward Δx ≥ 15 normalized units AND crossing a defensive→middle or middle→attacking band = "line-break."
- Flag through-balls and passes received in the 66–100 x band ("between the lines / final third reception").
- `packing_proxy_p90` per player; team line-breaks per match for Tactics.
**Implementation hint:** Extend `processing/formations.py` (already houses progressive-pass logic) or a small `processing/progression.py`. Pure pandas.

#### 4. Progressive Carries from events (not CSV) · **Priority: MEDIUM**
**What:** We currently read "Progressive Carries" from per-team CSV stat columns (`player_ratings.py`, `archetypes.py`). Derive them directly from events for consistency, per-match granularity, and so they appear on Post-Match/Tactics, not just season scouting.
**Why it matters:** Single source of truth; enables carry maps and per-match carry leaders. Opta/StatsBomb threshold = a carry advancing ≥ ~5 m (≈5 normalized units) toward goal, or any carry into the box.
**How to compute:** We already extract take-ons/touches (`extract_take_ons`, `extract_all_touches` are imported in `xt.py`). A carry = ball-retaining movement between two same-player on-ball events with no intervening opponent event; progressive if Δx toward goal exceeds threshold or it ends in the final third/box.
**Implementation hint:** Add `extract_carries()` to `data/event_parser.py`, consume in a `processing/progression.py`. Feeds metric #3 and the xT carry component too.

#### 5. Build-up Disruption Rate (defensive, opposition-phase) · **Priority: MEDIUM**
**What:** How often a team forces the opponent's build-up phase into failure — hurried long balls, turnovers, or clearances in the opponent's own defensive third. The defensive complement to Field Tilt.
**Why it matters:** PPDA tells you *intensity* of pressing; disruption rate tells you *effectiveness*. The 2025 EPL defensive-profile pieces pair PPDA with line height and interceptions exactly this way. We already compute the inputs in `pressure.py`.
**How to compute:**
- Disruption event = opponent loses possession (turnover, errant long pass, forced clearance) within x < 50 within ~6 s of an opponent build-up touch in their own half.
- `disruption_rate = forced_losses / opponent_buildup_sequences`. Pair with existing `high_turnovers` and `shot-ending HTOs` from `pressure.py`.
**Implementation hint:** Extend `processing/pressure.py` (`compute_pressure_metrics` already returns a dict bundle — add two keys). Surface in Tactics next to PPDA/Field Tilt.

---

### Top 3 Visualization Upgrades

#### 1. xT / Momentum Flow chart — **Post-Match Analysis page**
A time-series "momentum" area chart showing cumulative team xT (or VAEP) swing across the 90 minutes, like the xG-race we already have but for territory/threat rather than just shots. Industry-standard match-momentum viz (Kapich/medium pattern).
**Approach:** Compute rolling per-minute net xT per team from the per-event xT we already produce in `xt.py`; plot a diverging filled area (América above zero, opponent below) in Plotly using the dark América palette already wired into `viz/charts.py`. Reuse the `ppda_trend_chart` styling conventions. No new deps.

#### 2. Pitch-control / Voronoi snapshot — **Tactics page**
Static Voronoi tessellation of space ownership at key moments (e.g. the freeze-frame of a goal build-up, or average positions at a formation phase). Voronoi is the accessible event-data approximation of full pitch control (no tracking data needed).
**Approach:** Use `scipy.spatial.Voronoi` over average player positions already computed in `processing/tactical_positions.py`/`pass_network.py`, render onto the mplsoccer pitch in `viz/pitch.py` (coords already normalized 0–100, matching the pitch config). Caveat to log in-app: Voronoi ignores player speed — label it "static space control," per the 2025 literature's own caveat.

#### 3. PPDA × Defensive-Line-Height quadrant scatter — **Tactics / Home**
The signature 2025 pressing-profile chart: each team plotted on PPDA (x) vs defensive-line height (y), América highlighted in yellow, quadrant labels (high press/high line, low block, etc.).
**Approach:** Both axes already exist — `compute_ppda` (`formations.py`) and defensive-line height (`pressure.py`). Aggregate to season means per team via `season_tactics.py`, render a Plotly scatter with quadrant guide-lines. Pure assembly of metrics we already compute; highest-value-per-effort viz.

---

### Emerging Techniques (where the industry is moving)

- **Unified action-value models everywhere.** OBV (StatsBomb/Hudl, now 140+ comps with video sync), VAEP, and EPV have effectively replaced single-purpose metrics — every action gets one threat-currency value, including defensive and off-ball actions.
- **Dynamic / context-aware xT (DxT, 2025).** Static grids (ours) are being upgraded with off-ball positioning and possession state. Worth tracking but only feasible for us at the event-snapshot level without tracking data.
- **Defensive valuation as a first-class citizen.** xDEF, defensive OBV, and ML-based defensive-action valuation (2025 *Journal of Big Data*; "What Happened Next?" deep-learning paper) — the field is finally pricing defending, not just attacking.
- **Pressure & counter-press as collected/derived events.** StatsBomb collects true pressure events; Opta users (us) approximate via recovery timing — we already do this, and counter-press windows (regain within 5 s of loss) are the current frontier.
- **Pitch ownership beyond Voronoi.** Neighbour-based and motion-model pitch-control (2025 arXiv) supersede plain Voronoi — but they need tracking data; Voronoi remains the honest event-data approximation.
- **Standardised data formats (CDF, 2025 arXiv)** are emerging to make event+tracking pipelines portable — relevant if the platform ever ingests a second provider.

---

### Recommended Next Actions (scoped to this Python/Streamlit codebase)

1. **Ship xDEF first (1–2 days, HIGH ROI).** New `processing/xdef.py` reusing `XT_GRID` + `_cell()` from `xt.py` and the existing defensive extractors in `event_parser.py`. Wire a new "Defensive Threat Denied" attribute into the `DEF` rating block of `processing/player_ratings.py`. No new dependencies, no model training, respects `MIN_MINUTES_FOR_RATING`.
2. **Add `extract_carries()` to `data/event_parser.py`** then `processing/progression.py` for progressive carries + packing proxy (metrics #3, #4). This unblocks per-match carry maps and consistent progression numbers across Tactics/Post-Match.
3. **Add the two cheap visualizations that reuse existing metrics:** the PPDA × line-height quadrant scatter and the xT momentum-flow chart — both are pure `viz/charts.py` assembly over metrics we already compute. Highest value-per-hour.
4. **Prototype the VAEP/OBV action-value model (`processing/action_value.py`) behind a cache,** following the persisted-model pattern in `xg_model.py`. Treat it as a season-end milestone, not a quick win — it needs labelled training and validation against the existing xG/xT outputs. Start with xT-as-label fallback.
5. **Extend `compute_pressure_metrics` in `pressure.py`** with `buildup_disruption_rate` and a counter-press-regain (regain ≤5 s after loss) key; surface alongside PPDA/Field Tilt on Tactics.
6. **Add a one-line in-app caveat wherever Voronoi/static metrics appear** ("static — ignores player velocity"), matching how the literature qualifies these models, to keep the TFM academically defensible.

**Notes / assumptions made (autonomous run):** Confirmed via code audit that xT, PPDA, Field Tilt, progressive-pass counts, defensive-line height and high-turnover detection already exist — recommendations were re-scoped to avoid duplication. True packing and full pitch-control are flagged as tracking-data-dependent; only their event-data proxies are recommended. No code was changed in this reporting run.

---

### Sources

- [StatsBomb — Defensive Metrics: Measuring the Intensity of a High Press](https://statsbomb.com/articles/soccer/defensive-metrics-measuring-the-intensity-of-a-high-press/)
- [Hudl/StatsBomb — Introducing On-Ball Value (OBV)](https://www.hudl.com/blog/statsbomb-on-ball-value)
- [Hudl — Pressure Data in Football: Recruitment & Opposition Analysis](https://www.hudl.com/blog/pressure-data-football-statsbomb)
- [The PFSA — Beyond Expected Goals: xT and VAEP](https://thepfsa.co.uk/beyond-expected-goals-meet-xt-and-vaep-the-metrics-redefining-player-value/)
- [Marc Lamberts — Expected Defensive Threat Reduction (xDEF)](https://marclamberts.medium.com/expected-defensive-threat-reduction-xdef-measuring-how-defensive-players-reduce-attacking-879566056310)
- [MDPI Applied Sciences — Dynamic Expected Threat (DxT) Model (2025)](https://www.mdpi.com/2076-3417/15/8/4151)
- [Journal of Big Data — ML approach to football player valuation (2025)](https://link.springer.com/article/10.1186/s40537-025-01302-7)
- [arXiv — Revisiting Expected Possession Value: U-Net, Reward & Risk for Passes (2025)](https://arxiv.org/pdf/2502.02565)
- [arXiv — What Happened Next? Deep Learning to Value Defensive Actions](https://arxiv.org/pdf/2106.01786)
- [Stats Perform — How we measure pressure](https://www.statsperform.com/insights/how-we-measure-pressure/)
- [Total Football Analysis — Premier League 2025/26 Defensive Profiles](https://totalfootballanalysis.com/data-analysis/premier-league-2025-2026-defensive-profiles-data-analysis)
- [Keep Righton — Progressive Passes and Carries: How To Measure](https://keeprighton.co.uk/progressive-passes-and-carries-how-to-measure)
- [Opta Analyst — Opta Football Stats Definitions](https://theanalyst.com/articles/opta-football-stats-definitions)
- [Aleks Kapich — Calculating & Plotting Match Momentum from Event Data](https://medium.com/@aleks-kapich/how-to-calculate-and-plot-football-match-momentum-using-event-data-1ca3a9ac4a39)
- [LRH Analytics — Voronoi Diagrams: Analysing Tactics with Graphics](https://lrhanalytics.co.uk/articles/voronoi-diagrams)
- [arXiv — A Neighbor-based Approach to Pitch Ownership Models (2025)](https://arxiv.org/pdf/2501.05870)
- [arXiv — Common Data Format (CDF) for Match Data (2025)](https://arxiv.org/pdf/2505.15820)
