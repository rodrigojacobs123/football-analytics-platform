## DATA ANALYST REPORT — 2026-06-21 (cycle 3, 08:56)

### Executive summary

The continuous-improvement loop is working: items recommended in the **2026-06-17** and earlier **2026-06-21** cycles have shipped. Confirmed in-tree this run:

| Recommended (prior cycle) | Status | Module |
|---|---|---|
| xDEF — defensive threat reduction | ✅ Shipped | `processing/xdef.py` |
| xGOT / PSxG + GK shot-stopping +/− | ✅ Shipped | `processing/xgot.py` (already carries GK value) |
| Sequence framework (directness, direct speed) | ✅ Shipped | `processing/sequences.py` |
| Possession-adjusted defending (baseline) | 🟡 Partial | `PADJ_BASELINE` in `processing/pressure.py` |
| Field tilt, xT, game phases, archetypes, pizza/radar | ✅ Already existed | `formations.py`, `xt.py`, `game_phases.py`, `viz/pizza.py` |

**Consequence for this report:** the "intro" metric backlog (xT, PPDA, xGOT, field tilt, sequences) is essentially exhausted. The remaining value is in **second-generation, integrative metrics** that *reuse the modules we just built* — chiefly a unified action-value layer and possession-xG credit. I deliberately avoid re-recommending anything above.

Still-open carry-overs (re-validated, not re-counted below): VAEP/OBV action value, xP/PAx expected passing, packing/line-break proxy, event-derived progressive carries, attacking set-piece xG, and the xT-momentum / Voronoi visualizations.

---

### Top 5 New Metrics to Implement

#### 1. VAEP / OBV — unified action value · **Priority: HIGH** (carry-over, now *much* cheaper)
**What:** One threat-currency value per on-ball action = `ΔP(score in next k actions) − ΔP(concede in next k actions)`. Replaces a wall of single-purpose metrics with one number that also prices defensive and progressive actions. This is the single clearest 2025–26 industry throughline (StatsBomb OBV is now on 140+ comps; VAEP/`socceraction` is the open standard).
**Why now:** We already have every ingredient — `xt.py` (positional value), `xgot.py` (shot execution), `xdef.py` (defensive denial), `sequences.py` (possession segmentation). A *lightweight, home-grown* VAEP no longer needs `socceraction` or model training: use xT-delta as the offensive label and xDEF as the defensive label, netted per action.
**Compute (Opta event-data, no tracking):**
```python
# processing/action_value.py
# Reuse XT_GRID + _cell() from xt.py and the sequence segmentation from sequences.py.
# Offensive value of a successful move A->B:  xT[B] - xT[A]   (pass/carry)
# Shot value:                                 xGOT - xT[start]   (execution over situation)
# Defensive value of a regain/tackle/intercep: xDEF_denied at that location (already computed)
# Failed action (turnover): negative = -xT[A]  (you handed the opponent the ball at A)
obv = off_value.fillna(0) - def_value_conceded.fillna(0)
# Aggregate per player per 90; feed net OBV into player_ratings.py as an overall "impact" column.
```
**Note:** start with the xT/xDEF-label fallback (ships in days); a trained logistic `P(score|state)` model (mirroring `xg_model.py`'s persisted-model pattern) is the season-end upgrade.

#### 2. xGChain & xGBuildup — possession-xG credit per player · **Priority: HIGH** (NEW)
**What:** Credit the xG of *every shot-ending possession* to **all** players who touched the ball in that possession. `xGChain` = sum of possession-xG of every sequence a player was involved in; `xGBuildup` = same but **excluding** the shot and the assist, isolating deep build-up contributors (the deep-lying playmaker / ball-progressing CB who never shows up in goals/assists).
**Why:** `goal_buildup.py` only traces *goals* backwards — it ignores the ~90% of chances that don't score, and credits no one systematically. xGChain is the canonical fix and is the metric that surfaces América's unsung build-up players in Scouting. Ingredients are all present.
**Compute:**
```python
# processing/xg_chain.py
seqs = compute_sequences(events, team_id)          # sequences.py
shots = extract_shots(events)                      # event_parser; xG from QUAL_XG=395
# Attach each shot's xG to its sequence; for each sequence with a shot:
#   every distinct player_id in the sequence  += possession_xg   -> xGChain
#   exclude shooter + assister                                   -> xGBuildup
```
**Priority HIGH** because effort is low (pure pandas over two existing functions) and it directly enriches `6_Player_Scouting`.

#### 3. Expected Pass (xP) + Passes Above Expected (PAx) · **Priority: MEDIUM-HIGH** (carry-over)
**What:** `P(pass completed)` from start/end coords, distance, angle, direction; `PAx = completed − xP` isolates passing *skill* from passing *safety*. Mirrors the xG→xGOT, xT→OBV "execution residual" pattern.
**Compute:** `processing/expected_pass.py`, cached logistic model on `extract_passes()` features (start x/y, end x/y via `QUAL_PASS_END_X/Y`, length, forward-ness). Feed PAx into the `PAS` rating block of `player_ratings.py`. Respect `MIN_APPEARANCES_FOR_RATING`.
**Why MEDIUM-HIGH:** needs a (small) trained model, but it's the most-requested missing passing metric and pairs naturally with #4.

#### 4. Packing / line-breaking proxy (bypassed opponents) · **Priority: MEDIUM** (carry-over, now feasible)
**What:** Count of opponents a pass/carry plays *past* — true packing needs tracking, but `processing/tactical_positions.py` already produces canonical role coordinates per formation. Approximate "defenders bypassed" by counting opponent roles whose x lies between the pass start-x and end-x.
**Compute:** new `extract_carries()` in `event_parser.py` (consecutive same-player touches without an intervening event), then `processing/progression.py` for progressive carries + the packing proxy. Label clearly as an *event-data approximation* in-app for TFM defensibility.

#### 5. Attacking set-piece xG + corner-routine threat · **Priority: MEDIUM** (carry-over)
**What:** Set-piece-specific xG and per-routine threat (in-swing/out-swing/short). The defensive mirror already exists in `corner_defense.py`; this completes the dead-ball picture. Industry signal is strong — Hudl StatsBomb shipped a new set-piece + HOPS aerial model on **11 Mar 2026**, and clubs treat dead balls as an optimisable system.
**Compute:** `processing/set_piece_xg.py` reusing corner/free-kick detection already in `set_pieces.py` + `corner_defense.py`; flag shots with `QUAL` set-piece context and sum xG by routine.

---

### Top 3 Visualization Upgrades

#### 1. Possession-value (xT/OBV) momentum-flow chart — **Post-Match Analysis** (carry-over, now trivial)
A time-on-x, cumulative-team-xT-on-y area chart (red América vs grey opponent) — the "who was on top, when" view that complements the existing xG race. Pure `viz/charts.py` assembly over per-event xT we already compute in `xt.py`. Highest value-per-hour; was recommended twice and still not built.

#### 2. Convex-hull team compactness + Voronoi space-control snapshot — **Tactics** (NEW + carry-over)
mplsoccer 1.6 ships `Pitch.convexhull()` and `Pitch.voronoi()` natively. Plot the convex hull of each team's average action positions (compactness/defensive block size) and a Voronoi tessellation of average positions as an honest event-data *space-control proxy*. We have the average-position machinery in `tactical_positions.py`; this is mostly `viz/pitch.py` plumbing. **Caveat label required** ("static — ignores player velocity") to stay academically defensible.

#### 3. xGChain credit network / bar — **Player Scouting** (NEW, pairs with metric #2)
Once #2 ships, a horizontal bar of squad xGChain vs xGBuildup-per-90 instantly shows who creates value vs who only finishes it — the most "selling" visual for a recruitment-oriented page. Reuses `viz/charts.py`.

---

### Emerging Techniques (where the industry is moving)

- **Action-value as the universal currency.** OBV / VAEP / EPV have collapsed the metric zoo into one netted score per action (offense minus defense). Our `xt.py` + `xdef.py` already split this; metric #1 just nets them.
- **"Above-expected" residuals everywhere.** xG→xGOT, xP→PAx, xT→OBV — every expectation metric now has a skill-isolating residual. We've shipped the xG side (xGOT); xP/PAx is the open gap.
- **Set pieces as a modelled, coached edge.** Hudl StatsBomb set-piece + HOPS aerial model (Mar 2026) and DeepMind/Liverpool TacticAI (corner GNNs) — dead balls are now an optimisation target, not a footnote.
- **Off-ball & receiver valuation.** Opta Vision (2025) and off-ball-role frameworks (arXiv, Jan 2026) value players *without* the ball via tracking — **out of reach on event data alone**; flag as aspirational, not actionable for us.
- **Dynamic xT / U-Net EPV** keep maturing but need positional/tracking inputs; our static Karun-Singh grid remains the honest event-data choice — keep the caveat.

---

### Recommended Next Actions (scoped to this Python/Streamlit codebase)

1. **Ship xGChain/xGBuildup first (≈1 day, highest ROI this cycle).** New `processing/xg_chain.py` over the *already-built* `sequences.py` + `extract_shots()`; surface xGChain/xGBuildup-per-90 in `6_Player_Scouting` with the new credit-bar viz. No model, no new deps.
2. **Build the xT momentum-flow chart** in `viz/charts.py` for `3_Post_Match_Analysis` — recommended in two prior cycles, still unbuilt, now a pure assembly job over `xt.py`. ~half a day.
3. **Stand up `processing/action_value.py` (VAEP/OBV, fallback mode).** Net `xt.py` deltas against `xdef.py` denials per action; aggregate to a per-90 "impact" column in `player_ratings.py`. Defer the trained `P(score|state)` model to season-end (follow `xg_model.py`'s persist pattern).
4. **Finish the possession-adjustment pass.** `pressure.py` has `PADJ_BASELINE` but the `DEF` rating in `player_ratings.py` still uses raw counts — apply PAdj there (~30 lines) to strip América's possession bias. Cheap, was flagged last cycle.
5. **Add `extract_carries()` to `event_parser.py`** → `processing/progression.py` for progressive carries + the packing/line-break proxy (reusing `tactical_positions.py` role coords). Unblocks consistent progression numbers across Tactics/Post-Match.
6. **Add `processing/expected_pass.py`** (xP/PAx, cached model) and feed PAx into the `PAS` rating — the main outstanding "above-expected" residual.
7. **Add the convex-hull + Voronoi snapshot** to `4_Tactics` via mplsoccer 1.6 natives, with the mandatory "static/event-data approximation" caveat.

**Carried into next cycle if not done:** attacking set-piece xG (`set_piece_xg.py`), trained VAEP model, build-up disruption rate in `pressure.py`.

---

### Sources
- StatsBomb / Hudl — [On-Ball Value (OBV)](https://www.hudl.com/blog/statsbomb-on-ball-value) · [OBV intro (archive)](https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/) · [new HOPS + set-piece model, Mar 2026](https://www.hudl.com/products/statsbomb)
- ML-KULeuven — [socceraction / VAEP & Atomic-VAEP](https://github.com/ML-KULeuven/socceraction) · [Atomic-VAEP docs](https://socceraction.readthedocs.io/en/latest/documentation/valuing_actions/atomic_vaep.html) · [SPADL/VAEP paper](https://arxiv.org/pdf/1802.07127)
- Opta Analyst / Stats Perform — [Opta stat definitions](https://theanalyst.com/articles/opta-football-stats-definitions) · [Opta Vision tracking insights](https://theanalyst.com/articles/opta-vision-stats-tracking-data-premier-league) · [How we measure pressure](https://www.statsperform.com/insights/how-we-measure-pressure/)
- Field tilt — [The Football Analyst](https://the-footballanalyst.com/field-tilt-football-statistics-explained/) · [Driblab](https://www.driblab.com/blog/field-tilt-percentage-of-passes-and-touches-in-the-final-third)
- Visualization — [mplsoccer pitch module (convexhull / voronoi)](https://mplsoccer.readthedocs.io/en/latest/mplsoccer.soccer.pitch.html) · [mplsoccer CHANGELOG](https://github.com/andrewRowlinson/mplsoccer/blob/main/CHANGELOG.md) · [computational geometry in football](https://realsoccerexpand.netlify.app/post/computational-geometry/)
