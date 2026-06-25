## DATA ANALYST REPORT — 2026-06-25 (cycle 7, `_0853`)

**Scope discipline:** Started by re-reading `processing/` (43 modules) and the implemented-metrics memory. Cycles 1–6 have already shipped xT, xGOT/PSxG, xDEF (+league percentile scan), PPDA/pressure/5s-gegenpress-regains, field-tilt, sequences/directness, game-phases, archetypes, xGChain/xGBuildup, game-state-by-scoreline, GVM (goalkeeper value), MOU (manager over/under-achievement), crossing/cutback, throw-in/long-throw, Stretch-Index/convex-hull team shape, xB (expected booking/discipline), set-piece second-phase xG, and the "Insights of the Game" narrative. **None of those are re-proposed below.** Every item here was verified absent from `processing/` this run (`grep` for `extract_carries`/`expected_pass`/`action_value` → 0 hits).

This cycle pushes on the **on-ball action-value frontier** — the cluster of open items that all share one foundation (a learned per-action value surface). I sequence them so the first item unblocks the rest.

---

### Top 5 New Metrics to Implement

#### 1. Expected Pass Completion (xP) + Pass Risk/Reward decomposition — **Priority: HIGH**
**What:** Per-pass completion probability, then decompose every pass into **reward** (xT/OBV gained if completed) vs **risk** (1 − xP, the turnover probability). Opta ships its own xP model; the industry standard pairs it with a value surface so you can separate *ambition* from *execution* — exactly what scouting and tactics need (a 78%-completion midfielder attempting only 0.02-xT passes is not the same player as one completing 74% at 0.06-xT).

**How to compute from Opta events:**
- Filter `typeId == 1` (passes). Outcome from event `outcome` field (1 = complete).
- Features per pass (all already derivable from the flat pass frame in `event_parser.py`): start `(x,y)`, end `(x,y)` from qualifiers 140/141 (`PASS_END_X`/`PASS_END_Y`), `pass_length`/`pass_angle` (q212/q213 or computed), `dist_to_goal_before`/`after`, `is_forward`, header flag (q15), through-ball (q4), cross (q2), free-kick/throw context. Add `progressive` flag (Δdist-to-goal ≥ ~25% in opp half / central).
- Model: `sklearn` gradient-boosted classifier or logistic on those features → `xp`. Train league-wide once, cache like `compute_league_gk_value`/`compute_league_xdef`. (Memory note: FBref lost the Opta license Jan 2026 — train **on our own event corpus**, not an external feed.)
- **Risk/Reward:** `reward = xt_delta_if_completed` (reuse `xt.py` grid), `risk = 1 − xp`, `pass_value = xp * reward − (1 − xp) * xt_conceded_on_turnover`. This is the natural bridge to OBV (#3).

**Why now:** This is the single highest-leverage open item — it unblocks pass risk/reward, feeds OBV, and powers the pass-sonar and risk-reward-scatter viz upgrades below. New file `processing/expected_pass.py`.

#### 2. Carry valuation — `extract_carries()` + per-carry xT-delta (packing / line-break proxy) — **Priority: HIGH**
**What:** Carries (a player moving with the ball between two of their own on-ball events) are currently **invisible** in the platform — we value passes and shots but not ball-progression by dribble/drive, which is ~25–30% of all open-play progression and the heart of OBV's "ball drive" component. Add a carry extractor and value each carry by xT/OBV gained.

**How to compute:**
- `extract_carries()` in `event_parser.py`: for each team possession chain, a carry exists between consecutive same-player on-ball events where the player received the ball at A and performed their next action at B with no intervening event — distance `A→B` above a threshold (~3–5 normalized units) and not a set-piece. End coords of event *n* → start coords of event *n+1*.
- Value: `carry_xt = xt(end_cell) − xt(start_cell)` using the existing `xt.py` grid; flag **progressive carries** (Δdist-to-goal ≥ 25% or into final third) and **line-breaks** (carry crosses an opposition positional line — event-data proxy: carry origin behind and terminus ahead of the opponent's mean defensive-line x from `formations.py`/`pressure.py`).
- Per-90 leaderboards by player; respect `MIN_APPEARANCES_FOR_RATING`.

**Note on honesty:** True "packing" (Impect) needs tracking data to count defenders bypassed. Our event proxy counts *line* crossings, not *players* bypassed — label it "progressive carries / line-break carries (event proxy)", never "packing", per the platform's tracking-vs-event honesty rule.

#### 3. On-Ball Value (OBV) / VAEP — unified per-action value layer — **Priority: MEDIUM**
**What:** The long-standing open item: one model that assigns every action (pass, carry, shot, dribble, tackle, interception) a single +/− value = Δ(P(score next) − P(concede next)). StatsBomb's OBV is the commercial reference; VAEP (Decroos 2019) is the open methodology. Once xP (#1) and carries (#2) exist, OBV is mostly an *aggregation + state model* on top, not a from-scratch build.

**How to compute (VAEP-lite on Opta events):**
- Build possession-state features per action (location, action type, time, score-state — reuse `game_state.py`). Two gradient-boosted models: `P_score_next_10s` and `P_concede_next_10s` over the next k actions/seconds.
- `action_value = ΔP_score − ΔP_concede`. Sum per player/per-90 → offensive + defensive value added.
- New file `processing/action_value.py` (already the reserved name in memory). Defensive slice = per defensive action value, which **complements** the shipped team-only `xdef.py` and the `compute_league_xdef` percentile scan.

**Why MEDIUM not HIGH:** Heavier to validate and easy to get subtly wrong (label leakage on the "next goal" window — same class of bug as the eventId-not-unique and corner-award-timestamp gotchas). Ship #1 and #2 first; they de-risk it.

#### 4. Aerial HOPS — opponent-adjusted aerial win probability — **Priority: MEDIUM**
**What:** StatsBomb shipped a refreshed **HOPS (Header-Oriented Performance System)** model on 2026-03-11 — it measures *who you win headers against*, not just how many, surfacing true aerial specialists. We currently have `extract_aerials()` returning **raw counts only**. Upgrade to an expected-aerial-win model adjusted for opponent strength.

**How to compute:**
- Aerial duels are paired `typeId == 44` (Aerial) events, one per team at the same x,y/timestamp. Outcome field gives winner.
- Fit `P(win aerial)` per contest from location + a player aerial-rating prior (iterative, like an Elo for aerials, or a simple ridge on opponent mean win-rate). `aerials_won − Σ expected` = aerials won **above expectation**; weight by opponent quality.
- Feeds Player Scouting PHY/DEF sub-scores and set-piece personnel reads.

**Priority MEDIUM:** clean, self-contained, but smaller surface than the action-value cluster.

#### 5. Transition / counter-attack conversion profile — **Priority: MEDIUM**
**What:** A *value* layer on the already-shipped detection in `game_phases.py` + `sequences.py`. We detect transitions; we don't yet profile **how lethal** each team is in them. Counter-attacking identity is a core Liga MX scouting question (América's transition game vs deep-block opponents).

**How to compute:** For each possession tagged "transition/counter" by `game_phases.py`, attach: regain-to-shot time, xT accrued, shot/goal conversion, direct-speed (already in `sequences.py`). Aggregate → per-team transition xG-per-regain, % of attacks that are direct, time-to-shot distribution. Split by game-state (reuse `game_state.py`). No new event parsing — pure aggregation over shipped layers, so it's cheap.

---

### Top 3 Visualization Upgrades

1. **Pass Sonar** (Player Scouting + Tactics) — the canonical per-player pass-direction rose: bar **orientation** = avg pass direction (binned, e.g. 16 sectors), bar **length** = avg distance, bar **color** = volume *or* (better, once #1 lands) mean **xP/reward** of passes in that direction. Implementation: `matplotlib` polar bars per player on a small-multiple grid, or `mplsoccer`'s pitch-anchored sonars at each player's average position (`tactical_positions.average_player_positions`). New `viz/sonar.py`. This is the highest-ROI viz — instantly legible to coaches and it visually *is* the xP risk/reward story.

2. **Pass Risk/Reward scatter** (Tactics + Scouting) — x = avg pass difficulty (1 − xP), y = avg reward (xT/OBV gained), bubble = volume, América players highlighted (reuse the `gvm_bar_chart`/`xdef_percentile_bar` highlight pattern). Quadrants: "safe & low-value", "ambitious & rewarded", etc. Directly visualizes metric #1; `charts.py` Plotly scatter.

3. **Progressive-carry map** (Tactics, Post-Match) — `mplsoccer` arrow overlay of each player's value-adding carries (#2), arrow color = `carry_xt`, on the existing pitch infrastructure in `viz/pitch.py`. Pairs naturally beside the shipped pass-network and attack-connection plots.

---

### Emerging Techniques (industry direction, mostly tracking-gated — flag as future, don't fake from events)

- **U-Net / CNN EPV surfaces** (OJN-Pass-EPV benchmark, arXiv 2502.02565, 2025): full-pitch convolutional value surfaces with **ball-height** as a feature and explicit reward/risk pass decomposition. Our xP+xT pairing (#1) is the event-data approximation of the same idea — the CNN surface itself is a research-only frontier for us.
- **Opponent-skill-adjusted skill models** (StatsBomb HOPS, Mar 2026): the shift from "count actions" to "who did you do it against" — generalizes beyond aerials to duels/pressures. Our aerial-HOPS (#4) adopts this pattern.
- **Possession-state value as the unifying layer** (OBV/VAEP/EPV all converging): the industry has settled on "value every action by Δ score−concede probability" as the substrate that pass/carry/defensive metrics all derive from. Metric #3 is us joining that consensus.
- **Tracking-only frontier (reiterate — never synthesize from events):** true pitch-control/Voronoi, packing (defenders bypassed), pressing intensity via velocities, off-ball run valuation, ball-receipt-in-space. Honest labeling rule stands.

---

### Recommended Next Actions (scoped to the Python/Streamlit codebase)

1. **Build `processing/expected_pass.py`** (#1) — gradient-boosted xP on the existing pass frame; cache a league-wide model like `compute_league_xdef`. Add `pass_value`/`reward`/`risk` columns. *This is the keystone — do it first.*
2. **Add `extract_carries()` to `event_parser.py`** (#2) + `processing/carries.py` valuing each carry via the `xt.py` grid; wire a progressive-carry KPI + the carry-map viz into Tactics §3.
3. **Ship `viz/sonar.py`** (Viz #1) — works standalone on raw pass directions today, upgrades to xP-colored once #1 lands. Wire into Player Scouting.
4. **Then `processing/action_value.py`** (#3, VAEP-lite) on top of #1/#2 — guard the next-goal label window carefully (label-leakage is this build's analog of the corner-award-timestamp bug).
5. **Upgrade `extract_aerials()` → expected aerial wins** (#4) and add the **transition-conversion aggregation** (#5) over shipped `game_phases.py` — both small, independent, parallelizable with the above.

**Sequencing rationale:** #1 → (#2, Viz#1) → #3 is a dependency chain; #4 and #5 are independent and can land any time. After this cycle, the remaining open frontier is mostly tracking-gated (pitch control, true packing, off-ball runs) plus FK set-piece routines (only corners have phase-splits today).

---
**Sources:** [StatsBomb On-Ball Value (OBV)](https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/) · [Hudl/StatsBomb OBV explainer](https://www.hudl.com/blog/statsbomb-on-ball-value) · [Opta Analyst — Expected Pass Completion (xP)](https://theanalyst.com/articles/expected-pass-completion-explained) · [Building an xP model in Python (Medium, Jan 2026)](https://medium.com/@vickyfrissdekereki/building-an-expected-passes-xp-model-for-womens-football-in-python-5068a4be6f0d) · [Revisiting EPV: U-Net, reward & risk for passes (arXiv 2502.02565, 2025)](https://arxiv.org/abs/2502.02565) · [VAEP — Valuing Actions by Estimating Probabilities](https://the-footballanalyst.com/vaep-valuing-actions-by-estimating-probabilities-in-football/) · [Analytics FC — risk/reward of progressive passes](https://analyticsfc.co.uk/blog/2022/02/28/breaking-the-first-line-quantifying-the-risk-reward-of-progressive-passes-in-build-up/) · [PassSonar visualization (Nightingale)](https://medium.com/nightingale/passsonar-visualizing-player-interactions-in-soccer-analytics-7708e1d94afc) · [EPV vs xG for match prediction (NCBI PMC12640942)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12640942/)
