from __future__ import annotations
"""Auto-generated 'Insights of the Game' — a plain-language match narrative.

Synthesises the per-match aggregates the Post-Match page already computes (xG,
shots, possession, goals, xT momentum) into a handful of readable takeaways: the
result-vs-xG verdict, chance quality, finishing over/under-performance, who
controlled the ball, how the goals were sourced, and who finished the stronger.

Pure Python — takes already-computed values in, returns a list of insight dicts
``{icon, text, tone}`` out (no Streamlit, no parsing).  ``tone`` is one of
``good`` / ``bad`` / ``neutral`` / ``info`` and only drives the accent colour;
when an ``ame_team_id`` is supplied the good/bad tone is oriented to Club
América, otherwise everything stays neutral.
"""

import pandas as pd


def _stat(match_stats: list[dict], label: str) -> dict | None:
    return next((s for s in (match_stats or []) if s.get("label") == label), None)


def _ame_tone(good_for_team: str | None, home_id: str, away_id: str,
              ame_team_id: str | None) -> str:
    """Map 'which team this is good for' → a tone, oriented to América if present."""
    if not ame_team_id or ame_team_id not in (home_id, away_id) or good_for_team is None:
        return "neutral"
    return "good" if good_for_team == ame_team_id else "bad"


def generate_match_insights(
    info: dict,
    home_xg: float,
    away_xg: float,
    match_stats: list[dict],
    goals: pd.DataFrame,
    home_shots: pd.DataFrame,
    away_shots: pd.DataFrame,
    momentum: pd.DataFrame,
    home_id: str,
    away_id: str,
    ame_team_id: str | None = None,
) -> list[dict]:
    """Return an ordered list of ``{icon, text, tone}`` match insights."""
    ht, at = info.get("home_team", "Home"), info.get("away_team", "Away")
    hs, as_ = int(info.get("home_score", 0)), int(info.get("away_score", 0))
    hxg, axg = round(float(home_xg), 2), round(float(away_xg), 2)
    out: list[dict] = []

    # ── 1. Result vs xG verdict ───────────────────────────────────────────
    if hs != as_:
        if hs > as_:
            w_team, w_id, w_sc, w_xg, l_xg = ht, home_id, hs, hxg, axg
            l_sc = as_
        else:
            w_team, w_id, w_sc, w_xg, l_xg = at, away_id, as_, axg, hxg
            l_sc = hs
        if w_xg + 0.4 < l_xg:
            txt = (f"{w_team} won {w_sc}–{l_sc} against the run of play — out-created "
                   f"on xG ({w_xg:.2f} vs {l_xg:.2f}) but clinical when it mattered.")
            icon = "🎯"
        elif w_xg > l_xg + 0.4:
            txt = (f"A deserved {w_sc}–{l_sc} for {w_team}, who also won the xG battle "
                   f"{w_xg:.2f}–{l_xg:.2f}.")
            icon = "✅"
        else:
            txt = (f"{w_team} edged it {w_sc}–{l_sc} with the xG almost level "
                   f"({w_xg:.2f}–{l_xg:.2f}) — fine margins.")
            icon = "⚖️"
        out.append({"icon": icon, "text": txt,
                    "tone": _ame_tone(w_id, home_id, away_id, ame_team_id)})
    else:
        if abs(hxg - axg) < 0.3:
            txt = (f"A balanced {hs}–{as_} draw — xG was almost dead level "
                   f"({hxg:.2f}–{axg:.2f}).")
            tone = "neutral"
        else:
            better, b_id = (ht, home_id) if hxg > axg else (at, away_id)
            txt = (f"{hs}–{as_} draw, but {better} created the better chances on xG "
                   f"({max(hxg, axg):.2f}–{min(hxg, axg):.2f}) and will feel they "
                   f"should have won.")
            tone = _ame_tone(b_id, home_id, away_id, ame_team_id)
        out.append({"icon": "🤝", "text": txt, "tone": tone})

    # ── 2. Chance volume — shots & shots on target ────────────────────────
    shots = _stat(match_stats, "Total Shots")
    sot = _stat(match_stats, "Shots on Target")
    if shots:
        sh, sa = int(shots["home_value"]), int(shots["away_value"])
        txt = f"Shots {ht} {sh}–{sa} {at}"
        if sot:
            txt += f" (on target {int(sot['home_value'])}–{int(sot['away_value'])})"
        # who got more, and was it efficient relative to xG
        more_id = home_id if sh > sa else (away_id if sa > sh else None)
        if more_id and abs(sh - sa) >= 4:
            more_team = ht if more_id == home_id else at
            txt += f" — {more_team} dominated the shot count."
        else:
            txt += "."
        out.append({"icon": "📊", "text": txt,
                    "tone": _ame_tone(more_id if abs(sh - sa) >= 4 else None,
                                      home_id, away_id, ame_team_id)})

    # ── 3. Finishing over/under-performance vs xG ─────────────────────────
    fin = []
    for team, t_id, score, xg in ((ht, home_id, hs, hxg), (at, away_id, as_, axg)):
        fin.append((abs(score - xg), team, t_id, score, xg, score - xg))
    fin.sort(reverse=True)
    gap, f_team, f_id, f_sc, f_xg, signed = fin[0]
    if gap >= 0.9:
        if signed > 0:
            txt = (f"{f_team} were clinical — {f_sc} goal(s) from just {f_xg:.2f} xG, "
                   f"well above expectation.")
            tone = _ame_tone(f_id, home_id, away_id, ame_team_id)
        else:
            txt = (f"{f_team} were wasteful in front of goal — {f_xg:.2f} xG but only "
                   f"{f_sc} goal(s) to show for it.")
            tone = _ame_tone(None, home_id, away_id, ame_team_id)
            if ame_team_id and f_id == ame_team_id:
                tone = "bad"
        out.append({"icon": "🥅", "text": txt, "tone": tone})

    # ── 4. Control — possession ───────────────────────────────────────────
    poss = _stat(match_stats, "Possession")
    if poss:
        ph, pa = round(float(poss["home_value"])), round(float(poss["away_value"]))
        dom_id = home_id if ph >= 56 else (away_id if pa >= 56 else None)
        if dom_id:
            dom_team = ht if dom_id == home_id else at
            txt = (f"{dom_team} controlled the ball ({max(ph, pa)}% possession), "
                   f"dictating the tempo.")
            tone = _ame_tone(None, home_id, away_id, ame_team_id)  # control ≠ outcome
        else:
            txt = f"An even contest for the ball ({ph}%–{pa}% possession)."
            tone = "neutral"
        out.append({"icon": "🔄", "text": txt, "tone": tone})

    # ── 5. How the goals were sourced (penalties) ─────────────────────────
    if goals is not None and not goals.empty and "is_penalty" in goals.columns:
        pens = int(goals["is_penalty"].sum())
        if pens >= 1:
            out.append({
                "icon": "⚽",
                "text": (f"{pens} of the {hs + as_} goal(s) came from the penalty "
                         f"spot — dead-ball moments swung this one."),
                "tone": "info",
            })

    # ── 6. Who finished stronger (late xT momentum) ───────────────────────
    if momentum is not None and not momentum.empty and "net" in momentum.columns \
            and len(momentum) >= 15:
        late = float(momentum.tail(15)["net"].mean())
        if abs(late) > 0.03:
            strong_id = home_id if late > 0 else away_id
            strong_team = ht if late > 0 else at
            out.append({
                "icon": "📈",
                "text": (f"{strong_team} finished the stronger side — the closing "
                         f"15 minutes swung their way on xT momentum."),
                "tone": _ame_tone(strong_id, home_id, away_id, ame_team_id),
            })

    return out
