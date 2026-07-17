# MANAGER SPRINT REVIEW & APPROVALS

**Platform:** Club América Sports Analytics Platform (TFM)
**Date:** 2026-07-17 (re-run / verification pass, cycle 8)
**Author:** Analytics Engineering Manager — automated 3-day improvement cycle
**Inputs consolidated:**
- Data Analyst — `reports/data_analyst_report_2026-07-17_0643.md` (cycle 8: 5 new metrics, 3 viz upgrades)
- Data Engineer — `reports/data_engineer_brief_2026-06-25.md` (P0–P3 storage / test / mart tasks)
- Data Architect — `reports/data_architect_report_2026-06-25_0715.md` (governance + storage evolution)
- Prior approvals — `reports/manager_sprint_review_2026-07-17.md` (earlier consolidation, same cycle)

> **This is an approval document, not a discussion.** Every item was re-verified against the working tree today before it was ranked. The headline of this pass is a repeat, and that is exactly why it is a problem: **the #1 Must-Have from the previous consolidation — commit the untracked production modules — was not actioned. 31 production files in `processing/`, `viz/`, and `data/` are still `??` untracked, including the already-built `bench_impact.py` feature and the entire silver-storage slice.** The leak did not shrink; it is still one `git clean -fd` away from erasing a third of the platform. It stays at the top, non-negotiable, until `git status` is clean for code.

---

## Verification Ledger (what I confirmed this run)

| Claim under review | Verdict | Evidence (2026-07-17, working tree) |
|---|---|---|
| Prior sprint's Immediate #1 ("commit untracked modules") was done | ❌ **Not done** | `git status --porcelain \| grep '^??'` still lists 31 code files: `data/{build,silver_events,match_index}.py`, `processing/{action_value,aerials,archetypes,attack_play,bench_impact,buildup_play,carries,corner_defense,discipline,expected_pass,game_state,gk_value,match_insights,player_threats,sequences,tactical_positions,team_shape,transitions,wide_play,wyscout_bridge,wyscout_scouting,xdef,xg_chain,xgot}.py`, `viz/{attack_play,buildup,plotly_pitch,sonar}.py`. |
| Analyst #1 "Bench-Impact absent in `processing/`" | ⚠️ **Built but unbanked** | `processing/bench_impact.py` exists on disk, is untracked, and is wired into no page. Compute is ~done; it is uncommitted and unverified. |
| Analyst #2/#4/#5 (Press-Value, Rest-Defense, xShotDanger) | ✅ **Genuinely absent** | `processing/{press_value,rest_defense,shot_danger}.py` → not found. Real new work. |
| Engineer P1 DuckDB / test suite | ✅ **Absent** | no `duckdb` in `requirements.txt`; no `tests/` directory. |
| Silver layer committed on this branch | ❌ **No** | `data/silver_events.py` and `data/build.py` are untracked here; the silver tier exists only as loose files, not protected or wired to hot paths. |

**Prioritization frame:** MoSCoW, with the DSDM handbook's own guardrail — *no more than ~60% of sprint effort on Must-Haves, a ~20% pool of Could-Haves* — so this stays a solo TFM sprint, not a wish-list. "Must-Have" is applied strictly: *the sprint fails without it.* By that test, governance (not a metric) leads. Industry MVP guidance reinforces the discipline: an MVP should carry **3–5 features, not 10+** — so we approve exactly three now and three next, and defer the rest without apology.

---

## ✅ APPROVED FOR IMMEDIATE IMPLEMENTATION (Next 3 days)

> Theme: **stop the leak, bank the storage win, then ship the feature that is already 80% built.** One governance Must-Have, one performance Must-Have, one feature Should-Have. ~3 dev-days, at the 60% cap.

### 1. Commit the 31 untracked modules + add a load-time schema assertion — *(Governance / MUST-HAVE)*
- **What it is:** `git add` the untracked `processing/`, `viz/`, and `data/` modules and commit them in reviewable, domain-grouped commits (analytics engine / silver storage / wyscout / viz). Then add the architect's cheap insurance: a load-time assertion in `data/event_parser.py` that the hot `config.py` qualifier IDs (395 xG, 130 formation, 9 penalty) actually appear in a sampled event per season, logging a warning on absence.
- **Proposed by (conceptually):** Data Architect (Risk #1 — "the single highest-exposure, lowest-effort fix").
- **Effort:** ~0.5 day (mostly review discipline; the assertion is ~20 lines).
- **User/owner impact:** Retires the only true **data-loss** exposure in the entire report. A `git clean -fd`, a discarded worktree, or a fresh clone currently loses a third of the platform — *including the already-built `bench_impact.py`* — silently and unrecoverably. It also unblocks everything else: you cannot test, CI-gate, or diff untracked files.
- **Implementation notes:** Do this **first, before writing any new code**, so nothing else grows the untracked surface. Do **not** squash into one opaque commit — group by domain so provenance is bisectable. Bronze JSON under `testeo_ligas_norteamerica/` stays out of git (data, not code). This is a repeat of the prior sprint's #1 that slipped; treat non-completion this cycle as a sprint failure, per the success metrics below.

### 2. Silver hot-path migration for the 5 heaviest modules — *(Performance / MUST-HAVE)*
- **What it is:** Once item 1 commits `data/silver_events.py`, add a cached `load_events_for_match(...)` / season-level silver reader to `data/loader.py` and migrate the 5 heaviest JSON-parsing consumers (`xt.py`, `pressure.py`, `xdef.py`, `game_state.py`, `sequences.py` — all do `raw.get("liveData",{}).get("event",[])` per match) to read silver instead.
- **Proposed by (conceptually):** Data Engineer P0 / Data Architect Phase 1 (the standing multi-cycle recommendation).
- **Effort:** ~1.5 days.
- **User/owner impact:** Retires the standing **High-severity** storage risks on the match-analysis path. The engineer measured cold read **6.2s → 0.10s, 698 MB → 5.9 MB** on the player-events path; the match path should see the same order-of-magnitude win. This is the difference between a demoable thesis app and one that stalls in front of the panel.
- **Implementation notes:** Ship behind a hard acceptance test — a warm-cache Post-Match render does **zero** raw `json.loads` of `partidos/*` (instrument and log to prove it), and outputs are **byte-identical** before/after (diff one match's Post-Match page). DuckDB is **not** in scope here — plain columnar `pyarrow` reads only. `processing/` keeps receiving DataFrames.

### 3. Ship & verify the Bench-Impact ribbon on Post-Match — *(Feature / SHOULD-HAVE, nearly free)*
- **What it is:** Commit the existing `processing/bench_impact.py` (per-player on/off xG±xT swing per 90), wire it into Post-Match (page 3), and render the **Substitution-Impact Ribbon** — horizontal per-player on-pitch bars coloured by interval xG-swing (green = team outscored xG while on, red = bled).
- **Proposed by (conceptually):** Data Analyst (metric #1 + viz upgrade #1 — the longest-open item, flagged unbuilt in cycles 5, 6, and 7).
- **Effort:** ~1 day — the compute module **already exists** (item 1 rescues it from `??`); remaining work is wiring, the Plotly ribbon, a `MIN_MINUTES` guard, and render verification.
- **User/owner impact:** Delivers the single most-requested-and-most-deferred metric — "which subs actually change games / who are we carrying." High demo value for a Club América rotation story, and it maps directly onto the industry-standard "player comparison + automated report" dashboard expectation.
- **Implementation notes:** Reuse the proven `game_state.segment_match_by_state` interval pattern for on-pitch intervals (subs `typeId` 18 off / 19 on). Verify the ribbon **in the actual app render**, not a headless AppTest — cycle 7 proved `mplsoccer.arrows()` passes stubbed `st.pyplot` but ValueErrors in-app. Plotly horizontal bars need no new dependency.

---

## ✅ APPROVED FOR NEXT SPRINT (Days 4–9)

### 1. Player-Level Pressing Value (exPress-style) — *(Feature)*
- **What it is:** Per-player press value = the xT an individual defensive action denies + a share of any 5-second regain, league-percentile-ranked.
- **Proposed by:** Data Analyst (metric #2).
- **Effort:** ~1.5 days. The engine is ~80% built — `xdef.py` already computes per-action xT-prevented and `xdef.compute_league_xdef` already does the league scan; new work is the presser-attribution + regain-credit join in a new `processing/press_value.py`, plus the press-value heat map (viz upgrade #3).
- **Impact:** First per-player defensive metric on Player Scouting §2; distinguishes a high-volume runner from a real ball-winner. Pressing valued *per player, in context* is a named 2025–26 club-standard (StatsBomb exPress, Pressing Intensity).
- **Notes:** League-percentile is **mandatory**, not optional — a team-only slice is meaningless (standing `def-rating-is-league-percentile` finding). Label it the *event proxy*; true pressing intensity (closing speed) is tracking-gated and out of scope.

### 2. DuckDB in-process query layer over the silver Parquet — *(Architecture)*
- **What it is:** `data/query.py` with a thin `con()`/`sql()` helper reading silver via DuckDB with Hive `league/season` partition pruning + predicate pushdown; re-implement one cross-competition aggregate through it to prove the path.
- **Proposed by:** Data Engineer P1 / Data Architect Phase 2.
- **Effort:** ~1.5 days.
- **Impact:** Unlocks the cross-competition slices JSON makes un-serveable ("all shots for player X across 21 competitions") — the prerequisite for the recruitment / shortlist pages in the backlog. DuckDB + Streamlit + Parquet is a documented sub-second pattern.
- **Notes:** Add `duckdb>=1.0` to `requirements.txt`. DuckDB connections aren't hashable — cache with the `_`-prefix resource pattern. DuckDB stays **inside `data/`**; `processing/` still receives DataFrames. Depends on Immediate #2 landing silver first.

### 3. First test suite + CI on the build pipeline — *(Quality)*
- **What it is:** `tests/` (pytest) covering silver row derivations (xg, `is_penalty` q9-not-q22, goalmouth `z=19` NULL guard, action mapping), staleness logic, and a golden-file check that silver output equals the legacy JSON scan for one fixture match. Wire `python -m data.build --max-files 3` + `pytest` into GitHub Actions.
- **Proposed by:** Data Engineer P1 / Data Architect Phase 2.
- **Effort:** ~1.5 days.
- **Impact:** The ~40-module analytics engine has **zero** tests today; this is its first regression net and the only way to gate silver drift. Only possible *after* Immediate #1 (you cannot CI-gate untracked files).
- **Notes:** The build CLI is the natural harness. Golden-fixture the two documented gotchas (`z=19`, penalty q9) so no future module can re-introduce them.

---

## 📋 BACKLOG (Approved in principle, deliberately deferred)

| Item | Source | Why deferred (not rejected) |
|---|---|---|
| **Free-Kick routine phases + direct-FK xG** | Analyst #3 | Small lift (`set_pieces.py` already parameterised), lower marginal value than bench/press; ships once the corner engine is idle. Reuse the delivery-contact anchor fix; add the FK qualifier to `config.py` (don't hardcode). |
| **Rest-Defense / Counter-Vulnerability index** | Analyst #4 | Proxy-flagged event approximation; sits naturally on `transitions.py` but is a could-have refinement, not a headline metric. |
| **Expected Shot Danger (xShotDanger) multiplier** | Analyst #5 | Needs an in-house logistic fit; valuable but additive polish on an already-good xG model. Keep raw xG untouched for comparability. |
| **Voronoi / pitch-control approximation overlay** | Analyst viz #2 | Must be labelled an event *approximation* (true control needs tracking). Nice-to-have on Tactics; not load-bearing. |
| **Gold medallion marts** (season ratings, xG tables, Elo, GK/team-shape marts) | Engineer P2 / Architect Phase 2 | High value for first-paint latency, but correctly sequenced *after* silver + DuckDB exist to build on. |
| **Versioned schema module (`schema/opta_v1.py`)** | Engineer P2 / Architect Phase 2 | The Immediate #1 load-time assertion buys most of the safety cheaply; full versioning waits until a second feed actually arrives. |
| **New pages: Player Similarity & Shortlist; one-click Opposition Dossier PDF** | Architect §4 | The analytics already exist; the blocker is cross-competition serving, which DuckDB (next sprint) unblocks. Build once storage is ready — not before. |
| **Player-Intelligence `st.stop()`-in-tab refactor; single-option Club selector cleanup** | Engineer P3 | Real code-health, low urgency; fold into whichever sprint touches those files. |

---

## ❌ REJECTED / NEEDS MORE RESEARCH

| Item | Source | Ruling |
|---|---|---|
| **GNN / TacticAI-style set-piece models, DxT, true pitch-control, cover-shadows** | Analyst "emerging techniques" | **Rejected for this platform.** Tracking-gated (need player velocity/positions Opta events don't carry). The analyst is right to flag these as horizon-only — an event fake of them would be dishonest analytics. Track as future-work; do not schedule. |
| **FastAPI serving layer + provider-neutral UIED contract + React UI** | Architect Phase 3 | **Deferred indefinitely / needs a second consumer.** Premature for a single-process solo TFM app. Model the silver `action` column provider-neutrally *now* (free), but build no API until a real second consumer materialises. |
| **Streaming ingestion (Kafka/MSK + Flink, Hawk-Eye pattern)** | Architect Phase 3 | **Rejected for TFM scope.** Explicitly the "if a PL club adopted this" north star; incremental-batch is the realistic ceiling. Do not build streaming infra for a thesis. |
| **Generative / LLM scouting (ScoutGPT, EventGPT)** | Analyst emerging | **Needs more research; not a metric.** Interesting NL layer atop the shipped vectors, but no clear TFM deliverable yet. Park it. |

---

## 🚩 RISK FLAGS (monitor every cycle until cleared)

1. **Data-loss cliff — ACTIVE, HIGHEST, and NOW REPEATED.** 31 code modules untracked *right now*, unchanged since the last consolidation — including an already-built feature (`bench_impact.py`) and the whole silver slice. That the prior sprint's #1 slipped is itself the risk signal: this item must be gated as *done or the sprint fails.* Re-check `git status --porcelain | grep -E '^\?\? (processing|viz|data)/'` at the top of every cycle until it returns empty.
2. **"Byte-stable" claims must be proven, not asserted.** Immediate #2 migrates hot paths — the AC is a before/after diff showing identical output *and* an instrumented log proving zero `json.loads` of `partidos/*` on warm cache. If either isn't demonstrated, the task is not done.
3. **Headless-vs-app render gap.** Cycle 7's `mplsoccer.arrows()` bug passed stubbed `st.pyplot` but ValueError'd in-app. Every viz (Bench ribbon, press heat map) must be verified in the **actual Streamlit render**, screenshot as proof — not via AppTest.
4. **Proxy honesty.** Bench-Impact, Press-Value, Rest-Defense are all *event approximations* of tracking-native concepts. Each must carry explicit UI copy stating the event-vs-tracking limitation — same discipline as `carries.line_break`. Silent proxying misrepresents the analytics in a thesis defence.
5. **Schema drift across 2015–2026 × ~40 consumers.** No load-time validation today; a renamed qualifier surfaces as a wrong number deep in a page. Immediate #1's assertion is the first guard — do not let it slip a second time.

---

## 🎯 SUCCESS METRICS FOR THIS SPRINT (measurable pass/fail)

1. **Governance clean:** `git status --porcelain | grep -E '^\?\? (processing|viz|data)/'` returns **zero lines**, and the load-time schema assertion logs a warning on a deliberately corrupted sample season. *(Immediate #1 — binary pass/fail.)*
2. **Storage win, proven:** an instrumented warm-cache Post-Match render for one real match performs **0** raw `json.loads` of `partidos/*`, and a before/after output diff of that page is **empty** (byte-identical). Bonus target: match-path cold read latency drops ≥ 5× toward the player-path's measured 6.2s → 0.10s. *(Immediate #2.)*
3. **Feature shipped & seen:** the Substitution-Impact Ribbon renders in the live app on Post-Match for a real Club América match (screenshot captured from the running server, not a headless test), with the `MIN_MINUTES` guard suppressing sub-threshold players. *(Immediate #3.)*

**Gate:** If all three are green at day 3, the sprint succeeded. **If Immediate #1 is not green, the sprint failed regardless of the other two** — the leak is the priority, and it has now been allowed to survive one full cycle already.

---

## Sources (industry context consulted for prioritization)

- [Soccer Analytics Review 2025 — Jan Van Haaren](https://janvanhaaren.be/posts/soccer-analytics-review-2025/index.html) — exPress, Pressing Intensity, DxT, Expected Shot Danger, CDF
- [Substitute Interval Model — Marc Lamberts](https://marclamberts.medium.com/substitute-interval-model-quantifying-the-change-in-win-probability-when-a-player-is-on-or-off-the-031d671f07d5)
- [How Data Analytics Is Revolutionizing Player Recruitment in the Premier League — PremierLeagueNow](https://premierleaguenow.co.uk/2025/10/30/how-data-analytics-is-revolutionizing-player-recruitment-in-the-premier-league/)
- [The tools every football analyst should know in 2026 — Liam Henshaw](https://www.liamhenshaw.com/writing/the-tools-every-football-analyst-should-know) (Sportscode + Wyscout + StatsBomb as the 2026 club-standard stack)
- [Football Data Trends 2026: AI, Player Tracking & What's Next — Sportmonks](https://www.sportmonks.com/blogs/football-data-trends-2026-ai-player-tracking-whats-next/)
- [MoSCoW Prioritisation — DSDM Project Framework Handbook, Agile Business Consortium](https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html) (≤60% Must, ~20% Could)
- [Feature prioritization frameworks: RICE, MoSCoW, Kano — Plane](https://plane.so/blog/feature-prioritization-frameworks-rice-moscow-and-kano-explained)
- [How to Prioritize MVP Features — Net Solutions](https://www.netsolutions.com/hub/minimum-viable-product/prioritize-features/) (3–5 feature MVP discipline)
- [Technical Debt vs. Feature Development: What to Prioritize — Metamindz](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize) ("Fix Now / Schedule / Defer" categorization)
- [Balancing Technical Debt Prioritization With New Feature Development — Beyond the Backlog](https://beyondthebacklog.com/2024/01/15/balancing-technical-debt/) (70/30 feature-to-debt split)
- [Using DuckDB in Streamlit — DuckDB](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit)
- [Caching overview — Streamlit Docs](https://docs.streamlit.io/develop/concepts/architecture/caching)
