## DATA ANALYST REPORT — 2026-07-17

**Cycle 8** of the 3-day continuous-improvement loop. Prior cycles (1–7) shipped a large action-value stack: xT / xGOT / xDEF / PPDA / field-tilt / sequences / game-phases / archetypes, then xGChain-xGBuildup, game-state xG, xT-momentum, GVM (GK value), MOU (manager over/under-achievement), crossing-cutback, attack/build-up connections, set-piece **corner** second-phase xG, throw-in threat, Stretch Index / team-shape hull, Expected Booking (xB) discipline, league-percentile player xDEF, the auto "Insights of the Game" narrative, and the full cycle-7 on-ball cluster — **xP** (expected pass), **carries**, **OBV** (VAEP-lite composite), **opponent-adjusted aerials**, **transition conversion**, plus pass-sonar / risk-reward / carry-map viz.

This report is **additive only** — every candidate below was grep-verified absent in `processing/` on 2026-07-17. Nothing already shipped is re-proposed.

**Method:** searched StatsBomb/Hudl, the Jan Van Haaren *Soccer Analytics Review 2025*, World-Cup-2026 analytics coverage, and current substitution / pressing / set-piece research. The industry's 2025–26 frontier splits cleanly into (a) **tracking-gated** work we cannot honestly fake from Opta events (DeepMind TacticAI GNN corners, DxT off-ball weighting, cover-shadows, pitch-control, space-at-transition) and (b) **event-derivable** gaps we genuinely still have. The five metrics below are all in bucket (b).

---

### Top 5 New Metrics to Implement

#### 1. Substitute Interval / Bench-Impact Model — **Priority: HIGH**
The single longest-standing open item (flagged unbuilt in cycles 5, 6 **and** 7). 2025–26 was the year the industry formalised it: Marc Lamberts' **Substitute Interval Model** (win-probability change when a player is on vs off) and the EURO-2024 substitution-outcome studies both landed this cycle. We have zero on/off impact analytics — `player_ratings.py` uses subs (`typeId` 18 off / 19 on) only for appearance counts, and `tactical_positions.classify_sub_position` is positional only.

- **What it measures:** each player's team xG−xGA (and xT) *swing per minute while on the pitch* vs while off — a poor-man's plus/minus that isolates bench impact and starter dependency.
- **Compute from Opta:** build each player's on-pitch interval from the starting XI (formation/lineup at KO) plus sub events (`typeId` 18 = off, 19 = on; player id on the event, minute from `timeMin`/`timeSec`). Segment the match into intervals bounded by every sub/red-card. For each interval, sum team and opponent xG (qualifier 395) and xT (reuse `xt.py`) **per minute**; attribute the on-pitch delta to every player present. Aggregate per player across the season → `xg_swing_per90_on`, `off` baseline, and `net`.
- **Implementation:** new `processing/bench_impact.py`. Interval construction mirrors the game-state segmentation already proven in `game_state.py:segment_match_by_state` (same "split the timeline, accumulate per segment" shape). Guard with `MIN_MINUTES` (early-season noise). Cache season-wide like `compute_league_gk_value`.
- **Why it matters for América:** answers "which subs actually change games" and "who are we carrying" — directly actionable for squad rotation and in-game decisions.

#### 2. Player-Level Pressing Value (exPress-style) — **Priority: HIGH**
StatsBomb's **exPress** and Joris Bekkers' **Pressing Intensity** were both 2025 headline releases: pressing valued *per player, in context*, not just as a team rate. Our pressing stack is **team-only** — `pressure.py` ships PPDA, pressure/recovery height, PAdj baseline and the 5-second gegenpress regain (`pressure_regains_5s`), but there is no per-player press value. `archetypes.py`'s "press" hit is a raw count only.

- **What it measures:** value each defensive/pressing action by the xT it *denies* plus a share of any regain within 5 s, credited to the individual presser — so we can distinguish a high-volume, low-impact runner from a genuine ball-winner.
- **Compute from Opta:** for each pressure/defensive action (tackles `typeId` 7, interceptions 8, ball recoveries 49, challenges 45, pressures where tagged), credit `xT_prevented` (reuse the `xdef.py` per-action xT-prevented engine — it already exists team-wide) **attributed to the acting player**, plus a fraction of the opponent-possession xT extinguished when a `pressure_regains_5s` event follows. Roll up per player, then **percentile-rank league-wide** — mandatory per [[def-rating-is-league-percentile]]: a team-only slice is meaningless without the cross-team scan.
- **Implementation:** the engine is 80 % built — `xdef.py` already computes per-action xT-prevented and `xdef.py:compute_league_xdef` already does the league percentile scan. The new work is the **presser attribution + 5-s regain credit join** on top of it. New `processing/press_value.py` consuming `xdef` + `pressure` outputs; wire into Player Scouting §2 next to the shipped xDEF percentile bar.
- **Honesty note:** true pressing intensity (closing speed, distance to carrier) is tracking-gated — flag this as the *event proxy* (which defensive actions succeeded and what threat they killed), not velocity-based intensity.

#### 3. Free-Kick Routine Phases + Direct-FK Expected Goals — **Priority: MEDIUM**
Cycle 6 shipped **corner** first-vs-second-phase xG (`set_pieces.compute_set_piece_phase_value`), and the shipped memory explicitly lists "*Set-piece FK routines (only corners have phase split so far)*" as open. With ~25 % of non-penalty goals from set pieces in 2025–26 and direct free kicks carrying a knowable ~0.06 xG, FKs are the obvious next extension of an engine that already exists.

- **What it measures:** (a) direct-FK shot xG and conversion vs expectation; (b) indirect-FK **first-phase** (shot ≤6 s from the delivery contact) vs **second-phase** xG, mirroring the corner split.
- **Compute from Opta:** identify free-kick deliveries via the free-kick qualifier on the pass/shot event (verify the exact id against `config.py` — corners are already detected in `set_pieces.py`; add the FK constant the same way, do **not** hardcode). Reuse the **critical cycle-6 fix**: anchor the phase window on the **delivery contact / first real touch**, NOT the award timestamp (Opta stamps set pieces at the award, 15–40 s before the kick — anchoring on the award mis-binned 99.7 % of xG into "second phase"). `FIRST_CONTACT_SECS = 6` is already the tuned constant.
- **Implementation:** extend `set_pieces.py` (`compute_set_piece_phase_value` already parameterised by routine); add a `free_kick` branch. Wire into Tactics §5 alongside the existing corner phase bars.

#### 4. Rest-Defense / Counter-Vulnerability Index — **Priority: MEDIUM**
"Space evaluation at transition starting points" was a named 2025 research theme, and World-Cup-2026 coverage centres transition quality. Cycle 7 shipped *our own* attacking `transitions.py` (value of regains we convert). The **mirror** — how exposed **we** are at the moment we lose the ball — does not exist (grep: no `rest_defen*` / `counter_vuln*`).

- **What it measures:** at each of our possession-losses (turnover, tackled, dispossessed) in the opponent half, how many of our own players are already goal-side vs stranded upfield — an event proxy for "rest defense" balance and counter-attack exposure.
- **Compute from Opta:** at each turnover event, use the last-known event positions of our players in that possession (0–100 coords) to count how many are behind the ball (`x < ball_x`). Cross with whether the opponent generated a shot within a 10-s window (reuse the transition-window logic already in `transitions.py`). Output `rest_defense_balance` and `xG_conceded_per_high_turnover`.
- **Implementation:** new slice in `transitions.py` (it already parses possession chains and the 10-s shot window — this is the defensive-facing companion). **Honesty note:** true positions of all 22 players need tracking; the event approximation uses only players who touched the ball recently — flag as a proxy, as we did for `carries.line_break`.

#### 5. Expected Shot Danger (xShotDanger) — context multiplier over base xG — **Priority: MEDIUM**
Named in the 2025 review as an alternative to raw xG. Our `xg_model.estimate_xg` is location + body-part only (grep: no `fast_break` / `assisted` / `shot_danger`). Shot **context** — was it a fast break, first-time, assisted through-ball — measurably shifts conversion and is fully in the qualifier stream.

- **What it measures:** a context multiplier that enriches base xG with build-up danger: fast-break flag, assisted vs unassisted, through-ball / cut-back assist, first-time strike. Distinguishes an equal-xG tap-in-from-a-cutback from a settled 25-yard effort.
- **Compute from Opta:** read shot qualifiers — fast-break (qualifier 23), assisted / related-pass qualifiers, first-time, and the through-ball/cross flags already added to `extract_passes` in cycle 7 (`QUAL_THROUGH_BALL=4`, `QUAL_CROSS=2`). Fit a small logistic residual (goal ~ base_xG + context flags) on our own corpus — same closed-form-then-calibrate pattern as `expected_pass.estimate_xp` (no external artefact; FBref lost its Opta licence Jan 2026 so we train in-house).
- **Implementation:** additive columns on `xg.py` / a thin `processing/shot_danger.py`; surface on the xG Explorer (page 9) and Post-Match shot maps as a colour/size channel. Keep raw xG untouched for comparability.

---

### Top 3 Visualization Upgrades

1. **Substitution-Impact Ribbon (Post-Match, page 3).** A horizontal timeline: each player's on-pitch bar coloured by their interval xG-swing (green = team outscored xG while on, red = bled). Directly renders metric #1 and makes the sub story legible at a glance. Implementation: Plotly horizontal bars / Gantt keyed to interval boundaries — no new dependency. (Proposed as "substitution-impact ribbon" back in cycle 5, still unbuilt.)

2. **Voronoi / pitch-control approximation overlay (Tactics, page 4).** Memory confirms "NO convex-hull/Voronoi yet" for *control* — the shipped `team_shape.plot_team_shape` draws a hull for *shape/compactness*, not a possession-value tessellation. Add a `scipy.spatial.Voronoi` overlay on average player positions at a chosen possession phase to approximate territorial control. **Must be labelled an event approximation** (true pitch control needs tracking + velocities) — mplsoccer supports the pitch backdrop; `Voronoi` regions clip to the pitch polygon.

3. **Press-Value heat / regain map (Tactics, page 4).** Renders metric #2: hexbin of where the team wins the ball, coloured by the xT-value denied per regain (not raw count). Complements the shipped PPDA/field-tilt numbers with a spatial "where does our press actually hurt them" view. Reuse `viz/pitch.py` hexbin infra already used for defensive-action maps.

---

### Emerging Techniques (industry direction — mostly tracking-gated, tracked as future-work only)

- **Contextual pressing valuation** (exPress, Pressing Intensity) — the event-proxy slice is metric #2; the full velocity/closing-speed version is tracking-gated.
- **Dynamic Expected Threat (DxT)** — off-ball-weighted xT "addressing the deficit of realism." Needs tracking; do **not** fake from events.
- **GNN / geometric-deep-learning set pieces** (DeepMind TacticAI, now multi-year with Liverpool; new 2026 GNN off-ball defensive-role framework, arXiv 2601.00748) — models corners as player graphs with position/velocity/height. Tracking + heavy ML; out of scope for an event+Streamlit stack, note as horizon.
- **Generative / LLM scouting** — ScoutGPT (sequence-based transfer-fit), FIFA "AI Pro" 3D moment-rebuild, EventGPT. Interesting for a future natural-language scouting layer on top of our shipped vectors, but not a metric.
- **Common Data Format (CDF)** — a 2025 multi-author standard for match data (Bekkers, Brefeld, Davis, Van Haaren et al.). Worth watching for the silver/Parquet event tier (see [[silver-event-layer-built]]) as an interchange target.
- **FIFA public World-Cup-2026 data + Power Rankings (0–10 EFI player ratings)** — a public benchmark to sanity-check our FC-style ratings against once released.

### Recommended Next Actions (scoped to the existing Python/Streamlit codebase)

1. **Build metric #1 (Bench-Impact)** — highest value, longest-open, and structurally low-risk: it reuses the `game_state.segment_match_by_state` interval pattern and the `compute_league_gk_value` caching pattern. New `processing/bench_impact.py` + ribbon viz (upgrade #1) on Post-Match. Respect a `MIN_MINUTES` guard.
2. **Build metric #2 (Press-Value)** as a thin attribution layer over the already-shipped `xdef.py` engine + `pressure.pressure_regains_5s`; new `processing/press_value.py`, league-percentile scan (mandatory per [[def-rating-is-league-percentile]]), wired into Player Scouting §2 next to the xDEF bar, plus the press heat map (upgrade #3).
3. **Extend `set_pieces.py` to free kicks (metric #3)** — smallest lift, engine already exists; **reuse the delivery-contact anchor fix**, add the FK qualifier constant to `config.py` (don't hardcode).
4. **Prototype metrics #4–#5** as additive columns on `transitions.py` and `xg.py` respectively — both are proxy-flagged event approximations; be explicit in the UI copy about the event-vs-tracking limitation (same discipline as `carries.line_break`).
5. **Standing hygiene:** keep [[implemented-analytics-metrics]] updated after each ship, and verify every mplsoccer viz in the **actual app render**, not headless tests — cycle 7 proved `mplsoccer.arrows()` passes stubbed `st.pyplot` but ValueErrors in-app on per-arrow width arrays.

---

**Sources:**
- [Introducing On-Ball Value (OBV) — StatsBomb](https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/) · [OBV explainer — Hudl](https://www.hudl.com/blog/statsbomb-on-ball-value)
- [Soccer Analytics Review 2025 — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html) (exPress, Pressing Intensity, DxT, xPass 360, Expected Shot Danger, CDF)
- [Substitute Interval Model — Marc Lamberts](https://marclamberts.medium.com/substitute-interval-model-quantifying-the-change-in-win-probability-when-a-player-is-on-or-off-the-031d671f07d5) · [UEFA EURO 2024 substitution study — NCBI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12287015/)
- [TacticAI — Google DeepMind](https://deepmind.google/blog/tacticai-ai-assistant-for-football-tactics/) · [A Machine Learning Framework for Off-Ball Defensive Role Evaluation — arXiv 2601.00748](https://arxiv.org/pdf/2601.00748)
- [From xG to Pressing Efficiency: Analytics Spotlight on the 2026 World Cup — Total Football Analysis](https://totalfootballanalysis.com/thought-analysis/from-xg-to-pressing-efficiency-analytics-spotlight-on-the-2026-world-cup) · [When FIFA Opened the Data](https://marcocardinale.com/2026/06/26/when-fifa-opened-the-data-how-the-world-cup-is-changing-the-way-we-understand-the-game/)
- [A Statistical Analysis of Corners and Free Kicks — Sofascore](https://www.sofascore.com/news/a-statistical-analysis-of-corners-and-free-kicks)
