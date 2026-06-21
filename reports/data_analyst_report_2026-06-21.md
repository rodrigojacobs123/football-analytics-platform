## DATA ANALYST REPORT — 2026-06-21

**Platform:** CLUB AMÉRICA Sports Analytics Platform (TFM)
**Cycle:** Continuous-improvement run (every 3 days)
**Scope:** Opta F24 event data — North American + CONCACAF competitions, season 2025-2026
**Analyst:** Automated senior-analyst agent (autonomous run, no user present)

---

### Executive summary

**Last cycle's #1 recommendation shipped.** A codebase audit confirms `processing/xdef.py` (Expected Defensive Threat Reduction) now exists — the defensive mirror of xT we flagged on 2026-06-17 as the highest-leverage gap. Good. The other four items from that cycle (VAEP/OBV action-value, packing proxy, event-derived progressive carries, build-up disruption) are **still outstanding** and remain valid; they are restated briefly under *Next Actions* rather than re-argued here.

This cycle deliberately moves into a **different gap**: we value the *attacking* (xT) and *defensive* (xDEF) sides of ball **progression**, but we have nothing on **shot execution and finishing quality**, nothing on **pass-difficulty / risk**, and no **sequence-based playing-style** layer. The single most concrete, highest-value, event-data-tractable win available to us right now is **xGOT / Post-Shot xG** — it requires no tracking data, plugs straight into our existing shot extractor, and unlocks a goalkeeper-evaluation dimension the platform currently lacks entirely.

The industry context confirms the timing: Hudl StatsBomb launched **new aerial (HOPS) and set-piece models on 11 March 2026**; Stats Perform's **xGOT** now ships men's/women's variants with goalkeeper-position features; and set pieces account for **~23% of Premier League goals this season** (vs a ~15% historical average) — finishing, set-piece threat and goalkeeping are exactly where the 2025-2026 frontier sits.

---

### Top 5 New Metrics to Implement

#### 1. xGOT / Post-Shot xG (PSxG) + Goalkeeper Shot-Stopping +/− · **Priority: HIGH**
**What:** xGOT extends xG by also crediting *where in the goal* an on-target shot was placed. xG = pre-shot chance quality; xGOT = post-shot, adding execution. For a keeper, `PSxG_faced − goals_conceded` = shot-stopping value added. This is the single biggest gap: we have xG everywhere but **no finishing-quality and no goalkeeper metric at all**.
**Why it matters:** Separates a striker's *chance creation* from their *finishing* (`xGOT − xG` per shot = execution over/under-performance), and finally lets us rate goalkeepers fairly — judged on the quality of shots faced, not raw goals conceded. Directly upgrades Player Scouting (`SHO` block + a new GK profile) and Post-Match Analysis.
**How to compute from Opta event data:**
- Restrict to **on-target** shots only: `typeId ∈ {15 (attempt saved), 16 (goal)}` (off-target/blocked have no goalmouth landing point).
- Read the **goalmouth landing coordinates** from the shot qualifiers — Opta F24 carries `qualifier 102` (goal-mouth y, along the goal-line) and `qualifier 103` (goal-mouth z, height). **These are not yet in `config.py`** (confirmed — add `QUAL_GOALMOUTH_Y = 102`, `QUAL_GOALMOUTH_Z = 103`).
- Train a model `P(goal | xG, goalmouth_y, goalmouth_z)` — top corners ≫ central, low-and-wide ≫ straight-at-keeper. A gradient-boosted classifier (`xgboost`, already in the stack via `xg_model.py`) or even a 2D kernel over the goal frame on `jsons/matches.json`.
- `xGOT(shot) = model output`. Player finishing = `Σ(xGOT) − Σ(xG)`. **GK shot-stopping = Σ(xGOT_faced) − goals_conceded**, per-90 with the `MIN_*` guards.
**Implementation hint:** New `processing/xgot.py` reusing `extract_shots()` (extend it to also surface `goalmouth_y/z`); persist the fitted model with the cached-artefact pattern from `xg_model.py`. Fallback if early-season placement data is thin: a static "shot-placement zone" lookup table over the goal frame.

#### 2. Sequence & Possession framework → Directness + Direct Speed · **Priority: HIGH**
**What:** Group consecutive events into **sequences** (one team's passage of play, ended by a defensive action, stoppage or shot) and **possessions** (≥1 sequence by the same team). From these derive **Directness** = upfield (x) progress ÷ total pass distance, and **Direct Speed** = upfield progress ÷ sequence time (m/s toward goal). This is Stats Perform's canonical playing-style backbone.
**Why it matters:** Our `play_style.py` is **rule-based on FC-style PAC/SHO/PAS ratings** — it describes player *quality archetypes*, not *team build-up identity*. Sequences give us the missing team-level "how do we play" layer: patient possession vs vertical/direct, build-up speed, sequences-per-shot. This is the foundation StatsBomb/Opta build most team profiling on, and it feeds Tactics, Pre-Match (opponent style scouting) and Home.
**How to compute from Opta event data:**
- Sort each match's events by `timeMin/timeSec/eventId`; start a new sequence on possession change (recovery, tackle won, throw-in/restart, or shot/stoppage). Reuse the possession-change logic already implicit in `pressure.py`.
- Per sequence: `progress = max_x_reached − start_x`; `length = Σ pass distances`; `time = last_ts − first_ts`.
- `Directness = Σ progress / Σ pass_length`; `Direct Speed = progress / time`. Aggregate to season per-team means.
**Implementation hint:** New `processing/sequences.py` (pure pandas) producing a tidy sequences DataFrame other modules can consume; surface `direct_speed`, `sequences_per_shot`, `build_up_directness` in `season_tactics.py`.

#### 3. Expected Pass Completion (xP) + Passes Above Expected (PAx) + Expected Pass Turnovers (xPT) · **Priority: MEDIUM-HIGH**
**What:** Model the probability a pass is completed given its difficulty (length, angle, start/end zone, direction). `PAx = completed − Σ xP` measures passing *skill* (completing hard passes); `xPT` measures *turnover risk* taken. Caps the risk/reward picture xT can't see.
**Why it matters:** xT only rewards *successful* forward moves and is blind to difficulty — a risky 40-yard line-breaker and a safe square ball both score on their xT delta alone. xP/PAx separate **ambition** from **execution** and identify safe-but-sterile vs progressive-but-loose passers. Strengthens the `PAS` rating in Player Scouting and progression analysis in Tactics.
**How to compute from Opta event data:**
- Feature each pass from `extract_passes()`: start (x,y), end (`QUAL_PASS_END_X=140`, `QUAL_PASS_END_Y=141`), length, forward angle, into-final-third flag, header flag (`QUAL_HEAD=15`). Label = completed (outcome 1) vs not.
- Fit a logistic/GBM `P(complete | features)` on `jsons/matches.json` → `xP` per pass.
- `PAx_p90 = (completed − Σxp)/90`; `xPT = Σ(1 − xP)` over attempted passes (expected losses). Respect `MIN_MINUTES_FOR_RATING`.
**Implementation hint:** New `processing/expected_pass.py`, cache the fitted model like `xg_model.py`. Pairs naturally with the packing/line-break proxy still outstanding from last cycle.

#### 4. Set-Piece Expected Goals (set-piece xG) + corner routine threat · **Priority: MEDIUM**
**What:** A dedicated xG layer for shots originating from set pieces (corners, indirect free kicks), plus an attacking corner-threat score per delivery (zone targeted, first-contact won, shot generated). The attacking complement to our existing `corner_defense.py`.
**Why it matters:** Set pieces are ~23% of top-flight goals this season and a coached, repeatable edge — Hudl StatsBomb shipped a new set-piece + aerial (HOPS) model on 11 Mar 2026, and DeepMind/Liverpool's TacticAI is corner-focused. We already analyse corner *defense*; we have no attacking set-piece valuation. High tactical relevance for América.
**How to compute from Opta event data:**
- Flag set-piece-origin shots: shot within ~N seconds / few events of a corner (`QUAL_CORNER_TYPE=56`) or free kick in the attacking half. Fit/segment xG separately for these (their geometry differs from open play — headers, congestion).
- Per corner: delivery zone (near/far/central from end coords), first-contact recovery, shot/goal generated → a routine-level threat score.
**Implementation hint:** New `processing/set_piece_xg.py` or extend `processing/set_pieces.py`; reuse `extract_shots()` + the corner-event detection already in `corner_defense.py`. Surface an attacking-corner panel on Tactics next to the existing corner-defense view.

#### 5. Possession-Adjusted (PAdj) defensive volume metrics · **Priority: MEDIUM (cheap, high value-per-effort)**
**What:** Normalise raw defensive counts (tackles, interceptions, clearances, recoveries) by the team's *time/volume out of possession*, so a low-possession team's defenders aren't flattered by sheer opportunity. The 2025-2026 public standard (PAdj tackles/interceptions).
**Why it matters:** Our Player Scouting `DEF` rating and `pressure.py` are still partly **raw counts**, which carry a heavy possession bias — América (typically high-possession in Liga MX) systematically *under-counts* its defenders' per-opportunity activity vs low-block opponents. PAdj removes that bias in ~30 lines and makes cross-team scouting honest. Complements the new xDEF nicely (xDEF = value denied; PAdj = volume per opportunity).
**How to compute from Opta event data:**
- Compute each team's share of total passes/possession (opponent passes faced). `PAdj_action = raw_action × (league_avg_opp_possession / team_opp_possession)`, the standard StatsBomb-style possession adjustment.
- Apply to the count inputs already produced in `pressure.py` / `player_ratings.py`.
**Implementation hint:** Small helper in `processing/pressure.py` (or a `processing/possession_adjust.py`); feed the adjusted counts into the `DEF` rating block. No new dependencies, no model.

---

### Top 3 Visualization Upgrades

#### 1. Goalmouth shot-placement map — **Post-Match Analysis + new Goalkeeper view**
A view of the **goal frame** (not the pitch) plotting where on-target shots landed, sized/coloured by xGOT, América attacking and opponent/keeper defending. The natural companion to metric #1.
**Approach:** Draw a simple goal-frame rectangle in Plotly/matplotlib from the `goalmouth_y` (0–100 across the goal) and `goalmouth_z` (height) qualifiers added for xGOT; colour by `xGOT − xG` (finishing over-performance). Reuse the dark América palette in `viz/charts.py`. ~40 lines, no new deps. Doubles as the keeper's "shots faced / saves above expected" panel.

#### 2. Playing-style sequence scatter — **Tactics / Home / Pre-Match**
The signature team-identity chart: **Direct Speed (x) vs sequence length / passes-per-sequence (y)**, each team a point, América highlighted, quadrants labelled (patient-possession, vertical-direct, long-ball, controlled-build-up). Built directly on metric #2.
**Approach:** Aggregate the sequences DataFrame to per-team means in `season_tactics.py`, render a Plotly quadrant scatter (same construction as the PPDA × line-height quadrant recommended last cycle). Pure assembly once #2 exists; also gives Pre-Match an instant opponent-style read.

#### 3. Pizza-chart hardening — **Player Scouting**
Not a new chart — a correctness/readability upgrade to the existing `viz/pizza.py`, following 2025 best-practice guidance: (a) plot **percentiles, not raw counts**; (b) **group attacking metrics on one side, defensive on the other** for visual balance; (c) **mix usage + outcome metrics** (e.g. progressive passes *and* completion %) so volume isn't mistaken for quality.
**Approach:** Audit `viz/pizza.py` slice ordering and inputs; reorder slices into attacking/possession/defensive arcs and confirm every slice is a league percentile. Low effort, immediately more defensible for the TFM. With xGOT and PAx added, the SHO/PAS arcs gain genuine execution metrics, not just volume.

---

### Emerging Techniques (where the industry is moving)

- **Execution layered on top of expectation.** xG → xGOT/PSxG, xP → PAx, xT → VAEP/OBV: every "expected" metric is now paired with an "above-expected" execution residual that isolates *skill* from *situation*. This is the clearest 2025-2026 throughline.
- **Goalkeeping is finally first-class.** xGOT with goalkeeper-position features (Stats Perform, 2025), plus dedicated men's/women's models — keeper evaluation has moved from save% to shot-stopping value-added. We currently have **zero** GK metrics; this is a visible hole for a club platform.
- **Set pieces as a coached, modelled edge.** Hudl StatsBomb's new set-piece + HOPS aerial models (Mar 2026) and TacticAI (DeepMind/Liverpool, corner-focused, D2-equivariant GNNs) — clubs treat dead balls as an optimisable system, not a footnote.
- **Off-ball valuation via GNNs / tracking.** Off-ball defensive role & performance frameworks (arXiv 2601.00748, Jan 2026) and expected-reception models — the frontier values players when they *don't* have the ball. **Tracking-data-dependent**; out of reach for us on event data alone, flag as aspirational.
- **Possession adjustment as default hygiene.** PAdj defensive metrics and possession/out-of-possession normalisation are now standard to strip volume bias — cheap for us and directly relevant given América's possession profile.
- **Dynamic xT (DxT) and U-Net EPV** continue to mature (MDPI 2025; arXiv 2502.02565) but need positional/tracking inputs; our static Karun-Singh grid remains the honest event-data choice.

---

### Recommended Next Actions (scoped to this Python/Streamlit codebase)

1. **Ship xGOT/PSxG first (HIGH ROI, ~2 days).** Add `QUAL_GOALMOUTH_Y=102` / `QUAL_GOALMOUTH_Z=103` to `config.py`; extend `extract_shots()` to surface them; build `processing/xgot.py` with a cached model (mirror `xg_model.py`). Wire `xGOT − xG` into the `SHO` finishing block and stand up a **first-ever goalkeeper profile** (shot-stopping +/−) in Player Scouting. Add the goalmouth placement viz.
2. **Build the sequence layer (`processing/sequences.py`).** Directness + Direct Speed + sequences-per-shot → the playing-style quadrant scatter. Unblocks team-identity profiling across Tactics/Home/Pre-Match and is reused by several future metrics.
3. **Add `processing/expected_pass.py`** for xP / PAx / xPT behind a cached model; feed PAx into the `PAS` rating. Pairs with the still-outstanding packing/line-break proxy.
4. **Do the cheap possession-adjustment pass** in `pressure.py` / `player_ratings.py` (PAdj defensive counts) — ~30 lines, removes América's possession bias from the `DEF` rating immediately; complements the now-shipped xDEF.
5. **Extend set-piece analysis to the attacking side** (`set_piece_xg.py`), reusing corner detection from `corner_defense.py` — high tactical value given the league-wide set-piece goal surge.
6. **Carry over the still-open items from the 2026-06-17 cycle:** VAEP/OBV unified action-value (`processing/action_value.py`, season-end milestone), event-derived progressive carries (`extract_carries()`), packing/line-break proxy, and build-up disruption rate in `pressure.py`. None were implemented this cycle; all remain valid.
7. **Harden `viz/pizza.py`** (percentiles, attack/defence grouping, usage+outcome mix) — low effort, more academically defensible, and it showcases the new xGOT/PAx execution metrics.

**Notes / assumptions made (autonomous run):** Confirmed via code audit that `xdef.py` shipped since the last cycle (last report's #1) and that the platform has **no** xGOT/PSxG, no goalkeeper metric, no goalmouth qualifiers in `config.py`, no sequence/directness layer, and no xP/pass-difficulty model — so all five Top metrics are genuine gaps, not duplicates. Off-ball/GNN and dynamic-xT approaches are flagged as tracking-data-dependent and therefore aspirational, not recommended for build. No code was changed in this reporting run.

---

### Sources

- [Stats Perform — Introducing Expected Goals on Target (xGOT)](https://www.statsperform.com/insights/introducing-expected-goals-on-target-xgot/)
- [Stats Perform — Enhancing Expected Goals on Target (men's/women's models, GK position, 2025)](https://www.statsperform.com/resource/enhancing-expected-goals-on-target/)
- [Opta Analyst — What Are Expected Goals on Target (xGOT)?](https://theanalyst.com/articles/what-are-expected-goals-on-target-xgot)
- [MDPI — An Expected Goals On Target (xGOT) Model: Accounting for Goalkeeper Performance (2025)](https://www.mdpi.com/2504-2289/9/3/64)
- [Opta Analyst — Sequences and Possessions in Football](https://theanalyst.com/articles/possessions-and-sequences-in-football)
- [Stats Perform — Introducing a Possessions Framework](https://www.statsperform.com/resource/introducing-a-possessions-framework/)
- [Opta Analyst — Introducing Expected Pass Completion (xP)](https://theanalyst.com/articles/expected-pass-completion-explained)
- [Taylor & Francis — Expected Pass Turnovers (xPT) (2024)](https://www.tandfonline.com/doi/full/10.1080/02640414.2024.2379697)
- [Driblab — Expected Passing %: between accuracy and difficulty](https://www.driblab.com/blog/expected-passes-between-accuracy-and-difficulty)
- [Hudl StatsBomb — On-Ball Value (OBV) Model Explained (140+ comps; new HOPS + set-piece models, Mar 2026)](https://x.com/Statsbomb/status/1884545777722102016)
- [Michael Caley — The Origins of the Set Piece Revolution](https://www.expectinggoals.com/p/the-origins-of-the-set-piece-revolution)
- [GiveMeSport — Premier League Set-Piece Goals (2025/2026)](https://www.givemesport.com/premier-league-set-piece-goals/)
- [Google DeepMind — TacticAI: an AI assistant for football tactics](https://deepmind.google/blog/tacticai-ai-assistant-for-football-tactics/)
- [arXiv — A Machine Learning Framework for Off-Ball Defensive Role and Performance Evaluation (Jan 2026)](https://arxiv.org/pdf/2601.00748)
- [The Football Analyst — Using Radars, Pizza Charts, and Scatter Plots Correctly](https://the-footballanalyst.com/using-radars-pizza-charts-and-scatter-plots-correctly/)
- [Tactiq — Field Tilt Explained: How Territorial Dominance Is Measured](https://www.tactiq.club/en/blog/field-tilt-territorial-dominance-football/)
- [MDPI — Dynamic Expected Threat (DxT) Model (2025)](https://www.mdpi.com/2076-3417/15/8/4151)
- [arXiv — Revisiting Expected Possession Value: U-Net, Reward & Risk for Passes (2025)](https://arxiv.org/pdf/2502.02565)
