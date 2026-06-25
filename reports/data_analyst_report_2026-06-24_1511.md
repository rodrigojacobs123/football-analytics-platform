## DATA ANALYST REPORT — 2026-06-24 (cycle 5, 15:11)

### Executive summary

Cycles 1–4 drained the first- and second-generation event-metric backlog (xT, PPDA, xGOT, xDEF, field tilt, sequences, game phases, archetypes shipped; VAEP/OBV, xGChain/xGBuildup, xP/PAx, packing proxy, set-piece xG, team-shape geometry, game-state segmentation, aerial win-probability, pass risk/reward, line-breaking passes, momentum chart, pass sonars all queued). **Those carry-overs remain valid and are NOT re-counted here.** Since cycle 4, `processing/buildup_play.py` shipped (playing-out-from-the-back: exit-pass channel × style + build-out involvement), so the build-out phase is now covered.

This cycle deliberately changes vein. Rather than mine more on-ball *attacking* event metrics (now saturated), I targeted the three under-served corners of the app verified by grep this run: **the goalkeeper**, **the bench/manager**, and **wide-play & transition value**. The 2025–26 literature has moved hardest in exactly these areas (GVM goalkeeper models, substitution-interval win-probability, causal crossing analysis, Dynamic xT, and the GNN/generative-transformer frontier). Every candidate was checked against the codebase before listing:

| Candidate | grep result | Verdict |
|---|---|---|
| Player similarity / "players like X" | `player_profile.py:360` `find_similar_players` (cosine on per-90) | ❌ skip — already ships |
| GK shot-stopping (xGOT residual) | `xgot.py` ships | ❌ skip the residual itself… |
| GK **composite** value (distribution xT + sweeper + handling) | raw CSV counts only (`player_ratings.py:32`), no model | ✅ new (model/composite layer) |
| Substitution / bench impact (win-prob on↔off) | only positional `classify_sub_position` | ✅ new |
| Crossing / cutback expected-value model | archetype count feature only (`crosses_p90`) | ✅ new |
| Manager over/under-achievement (xPts) | Poisson/xG exist; no xPts-vs-actual layer | ✅ new |
| Counter-attack conversion profile | phase/sequence *detection* ships; no conversion/value layer | ✅ new (value layer on existing detection) |
| Dynamic xT (DxT, off-ball), GNN corner setup (TacticAI) | — | ⚠️ tracking/freeze-frame — flagged honestly below |

---

### Top 5 New Metrics to Implement

#### 1. Goalkeeper Value Model — composite GVM · **Priority: HIGH** (NEW)
**What:** A single goalkeeper rating that, like StatsBomb's GVM, blends four sub-scores into one number — but built from Opta events + the existing `xgot.py`:
- **Shot-stopping** = goals prevented = `Σ xGOT_faced − goals_conceded` (already computable from `xgot.py`; just aggregate per keeper).
- **Distribution value** = `Σ xT(pass_end) − xT(pass_start)` over GK passes, split short vs **launch%** (long >~40m, qualifier-length), with completion by distance bucket — the "ball-playing keeper" signal Ederson/Neuer score on.
- **Sweeper actions** = defensive actions (clearance/interception/tackle, also `typeId` 10 keeper-pickup edge cases) with `x > ~78` *outside the box*, per 90 — proactive line-management.
- **Handling/claims** = cross-claim rate using existing `Catches`/`Punches`/`Crosses not Claimed` fields, expressed as claim% of claimable crosses.

**Why:** The Scouting / Player Intelligence GK block currently leans on **raw counting stats** (`player_ratings.py:32-37`) — it rewards a keeper who faces many easy shots and punishes a sweeper-keeper on a dominant team. GVM is the execution-vs-situation residual pattern (the xG→xGOT idea the whole field has adopted) applied to the most under-modelled position in the app. Highest payoff because GKs are presently the weakest page.
**Compute (`processing/gk_value.py`):**
```python
shot_stop = xgot_faced.sum() - goals_conceded          # from xgot.py, per keeper-match
gk_passes = passes[passes.player_id == gk_id]
dist_value = (xt(gk_passes.end) - xt(gk_passes.start)).sum()   # reuse xt.py grid
launch_pct = (gk_passes.length > LAUNCH_M).mean()
sweeps = def_actions[(def_actions.x > 78)].per90()             # reuse pressure.py filter
gvm = z(shot_stop)*w1 + z(dist_value)*w2 + z(sweeps)*w3 + z(claim_pct)*w4
```
Respect `MIN_APPEARANCES_FOR_RATING`; weights documented in-app. Folds the existing xGOT cleanly rather than duplicating it.

#### 2. Substitution / bench-impact model · **Priority: HIGH** (NEW)
**What:** Quantify each player's effect *as a substitution event* — the "super-sub" question. Two outputs:
- **On↔off swing**: team xG-rate (or xT-rate) per minute while the player is on the pitch vs while off, per match and aggregated — the Substitute-Interval-Model idea (Lamberts 2025).
- **Bench-impact**: for players who came on, team's xG-difference rate in the post-sub window vs the pre-sub baseline, **conditioned on game-state** (a sub when chasing ≠ a sub when leading).

**Why:** Nothing in `processing/` treats a substitution as a valued event (`classify_sub_position` is purely positional). This directly serves **Manager Profiles** ("does this coach's subs move the needle?") and **Player Intelligence** ("impact-sub" badge) — two existing pages with no bench analytics. It also pairs naturally with cycle-4's game-state tagger.
**Compute:** substitutions are `typeId == 18` (player off) / `19` (player on). Build per-player on-pitch intervals from line-ups + sub events, attribute team xG/xT accumulated in each interval, normalise per 90, and difference on↔off. Guard with `MIN_MATCHES_FOR_PREDICTION` — bench minutes are thin, so aggregate across the season and report confidence.
```python
on, off = pitch_intervals(lineups, subs)          # subs: typeId 18/19
swing = team_xg_rate(events, on) - team_xg_rate(events, off)
```

#### 3. Crossing & cutback expected-value model · **Priority: MEDIUM** (NEW)
**What:** Treat wide deliveries as their own valued event. Per cross/cutback: **xG generated** = xG of the first shot within ~5s/3 actions of the delivery, attributed to the delivery; plus a **cutback flag** (low, pulled-back pass from byline zone `x>83 & |Δy|` toward the penalty spot). Aggregate to **xG-per-cross by origin zone** and a player **expected-assist-from-wide** number.
**Why:** Crossing is one of 2025's live causal-inference topics, and the app only has a raw `crosses_p90` archetype feature — no notion of whether a cross *was any good*. It upgrades the Winger/Full-Back archetypes and gives Tactics a real wide-play efficiency read (cutbacks convert far better than floated crosses — the metric should expose that gap).
**Compute (`processing/wide_play.py`):** crosses via qualifier 2 (`Cross`); cutback via byline-origin + backward-y geometry; link to the next shot by `possessionId`/time window and pull `QUAL_XG`. `xg_per_cross = linked_shot_xg.sum() / n_crosses`, bucketed by origin zone.

#### 4. Manager Over/Under-achievement (MOU) Index · **Priority: MEDIUM** (NEW)
**What:** Expected points (**xPts**) vs actual points, per manager. For each match, turn team & opponent xG into win/draw/loss probabilities (the Poisson machinery already in `poisson.py`), giving `xPts = 3·P(win) + 1·P(draw)`. A manager's `actual_pts − xPts` per season = over-/under-performance — the MOU index named in the 2025 review.
**Why:** **Manager Profiles** exists but has no outcome-quality metric; this is the canonical one and reuses two things already built (xG + Poisson). It separates "results-merchant / clinical or lucky" managers from those generating sustainable underlying numbers — exactly the comparison that page is for.
**Compute:** per match `xg_for, xg_against → poisson.match_outcome_probs() → xpts`; `groupby(manager).agg(actual=sum(points), expected=sum(xpts))`; MOU = actual − expected, per 38-game season for comparability. Guard with a minimum-matches threshold.

#### 5. Counter-attack / transition conversion profile · **Priority: MEDIUM** (NEW — value layer on existing detection)
**What:** A *conversion/value* layer on top of the phase/sequence detection that already ships (`game_phases.py`, `sequences.py`). Per team, per 90: **counters initiated** (fast, direct, forward sequences started by a regain in own/middle third), their **shot & xG conversion**, and the defensive mirror — **transitions conceded** and xG conceded from them (transition vulnerability). The 2025 counter-attack literature finds ~10 counters/match, ~2 producing shots, and transitions yielding markedly more xG than settled possession — so settled-vs-transition xG should be reported side by side.
**Why:** Detection exists but the *outcome* of transitions is not surfaced anywhere. This is the natural value layer and answers a concrete coaching question for América: "how dangerous are we on the break, and how exposed are we to it?" Builds on shipped modules — not a duplicate.
**Compute:** flag a sequence as a counter when `sequences.directness`/`direct_speed` exceed thresholds **and** it began with a defensive regain (`game_phases` transition tag) in own half; then `groupby(team)` over linked shot xG. Report `xg_per_counter`, `counters_p90`, and the conceded mirror.
**Honesty note:** the full **Dynamic xT (DxT)** version — re-weighting threat by off-ball positions — needs tracking/freeze-frame data we do not have; ship the event-data sequence version and flag DxT as tracking-only future work.

---

### Top 3 Visualization Upgrades

#### 1. Goalkeeper dashboard → `14_Player_Intelligence` / `6_Player_Scouting` · **NEW** (pairs with #1)
A two-panel GK view: (a) a **shot-stopping map** — shots faced plotted at on-target location, marker size = xGOT, colour = saved/conceded, with the running goals-prevented total; (b) a **distribution radial** — pass volume and completion% by direction/distance bucket, colour = xT added. Turns the current bare GK stat block into the app's first real keeper page.
**Implementation:** `viz/pitch.py` shot scatter + a Plotly `barpolar` for distribution; feed from `gk_value.py`.

#### 2. Substitution impact ribbon → `12_Manager_Profiles` · **NEW** (pairs with #2)
A match timeline with team xT-rate (rolling) as the line, vertical markers at each substitution, and the post-sub window shaded green/red by whether the rate improved — instantly shows which of a manager's subs changed the game. Aggregated view: a "super-sub" bar leaderboard of on↔off swing.
**Implementation:** Plotly line + `add_vline` per sub event (`typeId` 18/19); shaded `vrect` for post-sub windows.

#### 3. xPts vs actual scatter → `12_Manager_Profiles` · **NEW** (pairs with #4)
Managers plotted as `xPts` (x) vs `actual points` (y) with the y=x break-even diagonal; above the line = over-achieving, below = under-achieving. One glance separates sustainable from lucky/clinical managers and makes MOU legible without a table.
**Implementation:** Plotly scatter, diagonal reference line, point labels = manager names, marker size = matches managed.

---

### Emerging techniques (where the industry is moving)

- **Geometric deep learning / GNNs on set-pieces and now open play.** DeepMind's **TacticAI** (graph-represented corner kicks; suggestions preferred 90% of the time, ~71% shot-from-corner prediction) expanded to **open-play dynamics with Palmeiras (June 2026)**. Frontier for our `13_Corner_Defense` page — but it needs freeze-frame/tracking positions; flag as future work, don't fake from events.
- **Generative transformers — "matches as language."** ScoutGPT and counterfactual player-valuation transformers (arXiv 2603.15212) model event sequences like tokens to value players and ask "what if." Conceptually adjacent to our carry-over OBV/VAEP; note as direction, not near-term build.
- **Context-adjustment is now baseline** (game-state — already queued cycle 4; **Dynamic xT** adds off-ball context but is tracking-bound).
- **Causal inference** entering mainstream analysis (crossing effectiveness, substitution effects) — our #3 and #2 are the event-data-tractable shadows of this.
- **Execution-vs-situation residuals everywhere** — GVM (#1) extends the xG→xGOT residual idea to goalkeeping; every raw count keeps getting an "expected" twin.
- **Data-access watch (operational, not a metric):** **FBref lost its Opta license in January 2026.** Our app reads a *local* Opta dataset, so we're insulated — but the pan-European similarity loader (`player_profile.py`) should not assume it can ever refresh from FBref; note this in `11_Data_Sources`.
- **Tracking-only frontier (flag, don't chase):** DxT off-ball weighting, TacticAI-style GNN corner setups, pitch control/Voronoi, pressing intensity via velocities, receipts-in-space — all need positional data we lack. One honest "future work with tracking data" note in the TFM beats a fake event-data version.

---

### Recommended next actions (scoped to this Python/Streamlit codebase)

1. **Ship #4 (MOU index) first** — highest payoff-to-effort: it reuses `xg` + `poisson.match_outcome_probs` with ~30 lines of aggregation plus the Viz #3 scatter on the already-existing `12_Manager_Profiles`. No new model, immediate lift.
2. **Then #1 (GVM)** — the biggest *gap-fill*: `processing/gk_value.py` folds the shipped `xgot.py` shot-stopping with new distribution-xT (reuse `xt.py`) and sweeper filters (reuse `pressure.py`), surfaced via the Viz #1 GK dashboard. Replaces the raw-count GK block on Scouting/Player Intelligence.
3. **Then #2 (substitution impact)** — `typeId` 18/19 interval builder + xT attribution; pairs with cycle-4's game-state tagger, so sequence game-state first if not yet built. Drives Viz #2 on Manager Profiles.
4. **#3 (crossing/cutback) and #5 (transition conversion)** are the lower-priority Tactics/Pre-Match adds — both are arithmetic over existing extractors (`extract_passes`, `sequences.py`, `game_phases.py`), no new model.
5. **Honesty / methodology pass on `11_Data_Sources`** — extend the cycle-4 "event-data vs tracking" subsection with the new tracking-only frontier (DxT off-ball, TacticAI GNN corner setups) and a one-line note that the pan-European similarity loader cannot refresh from FBref post-Jan-2026.
6. **Guardrails** — every per-90 / per-keeper / per-manager / bench split must respect `MIN_APPEARANCES_FOR_RATING` / `MIN_MATCHES_FOR_PREDICTION`; GK and bench samples are the thinnest in the app and game-state buckets shrink fast — aggregate across the season and show confidence, don't trust single-match splits.

**Carry-overs still open (re-validated, not re-counted):** VAEP/OBV unified action value, xGChain/xGBuildup, xP/PAx, packing proxy + `extract_carries()`, attacking set-piece xG, team-shape geometry, game-state segmentation, aerial win-probability, pass risk/reward, line-breaking passes, momentum chart, pass sonars.

---
*Sources:* [Opta Vision — new 2025/26 metrics (Stats Perform)](https://www.statsperform.com/resource/opta-vision-redefining-football-analysis-2025-26/) · [Soccer Analytics 2025 Review — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html) · [Introducing the Goalkeeper Value Model (GVM) — Marc Lamberts](https://marclamberts.medium.com/introducing-the-goalkeeper-value-model-gvm-726b4c8fe987) · [The Evolution of Goalkeeper Analytics — Breaking The Lines](https://breakingthelines.com/premier-league-analysis/the-evolution-of-goalkeeper-analytics-measuring-the-last-line-of-defense/) · [Substitute Interval Model — Marc Lamberts](https://marclamberts.medium.com/substitute-interval-model-quantifying-the-change-in-win-probability-when-a-player-is-on-or-off-the-031d671f07d5) · [Assessing substitution rule changes (Sage, 2025)](https://journals.sagepub.com/doi/10.1177/17479541251316162) · [AI framework for counterattack detection (J. Big Data, 2025)](https://journalofbigdata.springeropen.com/articles/10.1186/s40537-025-01128-3) · [Dynamic Expected Threat (DxT) — MDPI](https://www.mdpi.com/2076-3417/15/8/4151) · [Counterfactual player valuation — matches as language (arXiv 2603.15212)](https://arxiv.org/pdf/2603.15212) · [TacticAI — Google DeepMind](https://deepmind.google/blog/tacticai-ai-assistant-for-football-tactics/) · [TacticAI to open play with Palmeiras — TNW](https://thenextweb.com/news/google-deepmind-tacticai-football-palmeiras-predict-plays) · [Optimal transport playing-style embedding (arXiv 2501.10299)](https://arxiv.org/pdf/2501.10299)
