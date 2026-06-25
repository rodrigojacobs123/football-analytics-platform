from __future__ import annotations
"""Attacking-third connection visualization — mirror of ``viz.buildup``.

Renders ``processing.attack_play.attack_report`` on a VerticalPitch: channel
arrows (Left/Central/Right) into the final third sized by connection volume with
the dominant route highlighted, plus the key connectors at their average
attacking position, each labelled with its share (%) of all connections.
``attack_summary_md`` gives the matching text read-out.
"""

import streamlit as st
from mplsoccer import VerticalPitch

from config import AME_YELLOW, AME_DARK_BG

# Opta-y centre of each channel (y=100 is the team's LEFT, y=0 its RIGHT)
_CHANNEL_Y = {"Left": 83.0, "Central": 50.0, "Right": 17.0}
_ARROW_X0, _ARROW_X1 = 56.0, 84.0   # middle-third origin → final-third target


def _surname(name: str) -> str:
    return name.split()[-1] if name else ""


def _spread_positions(items: list[tuple], min_dist: float = 13.0,
                      iterations: int = 60) -> dict:
    """Push apart connector dots that cluster near goal so labels don't collide.

    ``items`` = [(key, x, y), ...]. Returns {key: (x, y)} nudged so no two are
    closer than ``min_dist`` (Opta units). Connectors in the final third bunch
    together, so without this their name/% labels overlap.
    """
    pts = {k: [float(x), float(y)] for k, x, y in items}
    keys = list(pts)
    for _ in range(iterations):
        moved = False
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ax, ay = pts[keys[i]]
                bx, by = pts[keys[j]]
                dx, dy = bx - ax, by - ay
                dist = (dx * dx + dy * dy) ** 0.5 or 0.01
                if dist < min_dist:
                    push = (min_dist - dist) / 2.0
                    nx, ny = dx / dist * push, dy / dist * push
                    pts[keys[i]] = [ax - nx, ay - ny]
                    pts[keys[j]] = [bx + nx, by + ny]
                    moved = True
        if not moved:
            break
    # Keep inside the pitch bounds.
    return {k: (min(max(v[0], 4), 96), min(max(v[1], 4), 96)) for k, v in pts.items()}


def plot_attack(report: dict, title: str = "Attack — Connecting in the Final Third",
                team_color: str = AME_YELLOW) -> None:
    """Vertical pitch: channel connection-arrows + key connectors with %."""
    if not report or report.get("n_connections", 0) == 0:
        st.info("Not enough data to map final-third connections.")
        return

    pitch = VerticalPitch(
        pitch_type="opta", pitch_color="#0D1117", line_color="#2A3A4A",
        linewidth=1.2, goal_type="box", corner_arcs=True,
        pad_top=4, pad_bottom=4, pad_left=2, pad_right=2,
    )
    fig, ax = pitch.draw(figsize=(6, 9))
    fig.set_facecolor(AME_DARK_BG)
    ax.set_facecolor("#0D1117")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=12)

    # Third boundaries (final third = top, where connections land)
    pitch.lines(33.33, 0, 33.33, 100, ax=ax, color="#2A3A4A",
                lw=0.8, ls=":", zorder=1)
    pitch.lines(66.66, 0, 66.66, 100, ax=ax, color="#3A4A5A",
                lw=1, ls="--", zorder=1)
    pitch.annotate("FINAL THIRD", (95, 50), ax=ax, color="#5A6A7A",
                   fontsize=8, fontweight="bold", ha="center", va="center",
                   rotation=90, zorder=1)

    channels = report["channels"]
    dom = report["dominant_route"]
    max_ct = max((c["count"] for c in channels.values()), default=1) or 1

    # ── Channel connection arrows (into the final third) ─────────────────────
    for ch, y in _CHANNEL_Y.items():
        info = channels.get(ch, {"count": 0, "pct": 0})
        if info["count"] == 0:
            continue
        ratio = info["count"] / max_ct
        is_dom = dom and dom["channel"] == ch
        color = team_color if is_dom else "#41607A"
        alpha = 0.95 if is_dom else 0.45
        pitch.arrows(_ARROW_X0, y, _ARROW_X1, y, ax=ax,
                     width=ratio * 5 + 1.2, headwidth=5, headlength=5,
                     color=color, alpha=alpha, zorder=4)
        pitch.annotate(f"{info['pct']:.0f}%", (_ARROW_X1 + 5, y), ax=ax,
                       color="white", fontsize=11, fontweight="bold",
                       ha="center", va="center", zorder=6,
                       bbox=dict(facecolor="#000000CC", edgecolor=color,
                                 lw=1.0, boxstyle="round,pad=0.25"))
        pitch.annotate(ch, (_ARROW_X0 - 3, y), ax=ax, color="#9AAAB8",
                       fontsize=8, ha="center", va="center", zorder=5)

    # ── Key connectors at their average attacking position (with % share) ────
    positions = report.get("player_positions", {})
    top = [p for p in report.get("top_players", [])[:5]
           if positions.get(p["player"])]
    if top:
        max_inv = max(p["connections"] for p in top) or 1
        spread = _spread_positions([
            (p["player"], positions[p["player"]]["x"], positions[p["player"]]["y"])
            for p in top
        ])
        for p in top:
            x, y = spread[p["player"]]
            size = p["connections"] / max_inv * 520 + 160
            pitch.scatter(x, y, s=size, ax=ax,
                          color="#0D1117", edgecolors=team_color,
                          linewidth=2, zorder=7, alpha=0.95)
            pitch.annotate(f"{_surname(p['player'])}  {p['pct']:.0f}%",
                           (x, y - 4.5), ax=ax, color="white",
                           fontsize=8, fontweight="bold",
                           ha="center", va="top", zorder=8)

    _show(fig)


def _show(fig):
    st.pyplot(fig, use_container_width=True)
    import matplotlib.pyplot as plt
    plt.close(fig)


def attack_summary_md(report: dict, team_name: str) -> str:
    """Markdown read-out: dominant route, key link, top connectors with %."""
    if not report or report.get("n_connections", 0) == 0:
        return f"*No final-third connections logged for {team_name}.*"

    dom = report["dominant_route"]
    link = report.get("top_link")
    types = report["types"]
    entry = types.get("Entry", {}).get("pct", 0)
    combo = types.get("Combination", {}).get("pct", 0)

    lines = [
        f"**{team_name} — connecting in the final third** "
        f"({report['n_connections']} connections)",
        "",
        f"- **Most common route:** {dom['channel']} channel, "
        f"{dom['type'].lower()} — {dom['pct']:.0f}% of connections",
        f"- **How they arrive:** {entry:.0f}% entries from outside · "
        f"{combo:.0f}% combinations inside",
    ]
    if link:
        lines.append(
            f"- **Key link:** {_surname(link['passer'])} → "
            f"{_surname(link['receiver'])} ({link['count']}×)")
    if report["top_players"]:
        names = " · ".join(
            f"{_surname(p['player'])} ({p['pct']:.0f}%)"
            for p in report["top_players"][:4])
        lines.append(f"- **Top connectors (share of total):** {names}")
    return "\n".join(lines)
