from __future__ import annotations
"""Build-up visualization — how a team plays the ball out of the back.

Renders the report from `processing.buildup_play.build_up_report` on a
VerticalPitch: channel arrows (Left/Central/Right) sized by exit volume with
the dominant route highlighted, plus the key build-up players at their average
position. `build_up_summary_md` gives the matching text read-out.
"""

import streamlit as st
from mplsoccer import VerticalPitch

from config import AME_YELLOW, AME_BLUE, AME_DARK_BG

# Opta-y centre of each channel (y=100 is the team's LEFT, y=0 its RIGHT)
_CHANNEL_Y = {"Left": 83.0, "Central": 50.0, "Right": 17.0}
_ARROW_X0, _ARROW_X1 = 16.0, 44.0   # def-third origin → middle-third target


def _surname(name: str) -> str:
    return name.split()[-1] if name else ""


def plot_build_up(report: dict, title: str = "Build-up — Out of the Back",
                  team_color: str = AME_YELLOW) -> None:
    """Vertical pitch: channel exit-arrows + key build-up players."""
    if not report or report.get("n_exits", 0) == 0:
        st.info("Not enough build-up data to map exits from the defensive third.")
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

    # Third boundaries (defensive third = bottom, where build-up starts)
    pitch.lines(33.33, 0, 33.33, 100, ax=ax, color="#3A4A5A",
                lw=1, ls="--", zorder=1)
    pitch.lines(66.66, 0, 66.66, 100, ax=ax, color="#2A3A4A",
                lw=0.8, ls=":", zorder=1)
    pitch.annotate("DEFENSIVE THIRD", (5, 50), ax=ax, color="#5A6A7A",
                   fontsize=8, fontweight="bold", ha="center", va="center",
                   rotation=90, zorder=1)

    channels = report["channels"]
    dom = report["dominant_route"]
    max_ct = max((c["count"] for c in channels.values()), default=1) or 1

    # ── Channel exit arrows ──────────────────────────────────────────────────
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
        pitch.annotate(f"{info['pct']:.0f}%", (_ARROW_X1 + 4, y), ax=ax,
                       color="white", fontsize=11, fontweight="bold",
                       ha="center", va="center", zorder=6,
                       bbox=dict(facecolor="#000000CC", edgecolor=color,
                                 lw=1.0, boxstyle="round,pad=0.25"))
        pitch.annotate(ch, (_ARROW_X0 - 3, y), ax=ax, color="#9AAAB8",
                       fontsize=8, ha="center", va="center", zorder=5)

    # ── Key build-up players at their average position ───────────────────────
    positions = report.get("player_positions", {})
    top = report.get("top_players", [])
    if top:
        max_inv = max(p["exits"] for p in top) or 1
        for p in top:
            pos = positions.get(p["player"])
            if not pos:
                continue
            size = p["exits"] / max_inv * 520 + 160
            pitch.scatter(pos["x"], pos["y"], s=size, ax=ax,
                          color="#0D1117", edgecolors=team_color,
                          linewidth=2, zorder=7, alpha=0.95)
            pitch.annotate(_surname(p["player"]), (pos["x"], pos["y"] - 4),
                           ax=ax, color="white", fontsize=8, fontweight="bold",
                           ha="center", va="top", zorder=8)

    _show(fig)


def _show(fig):
    st.pyplot(fig, use_container_width=True)
    import matplotlib.pyplot as plt
    plt.close(fig)


def build_up_summary_md(report: dict, team_name: str) -> str:
    """Markdown read-out: dominant route, key link, top build-up players."""
    if not report or report.get("n_exits", 0) == 0:
        return f"*No build-up exits logged for {team_name}.*"

    dom = report["dominant_route"]
    link = report.get("top_link")
    styles = report["styles"]
    short = styles.get("Short", {}).get("pct", 0)
    direct = styles.get("Long / Direct", {}).get("pct", 0)

    lines = [
        f"**{team_name} — playing out of the back** ({report['n_exits']} exits)",
        "",
        f"- **Most common route:** {dom['channel']} channel, "
        f"{dom['style'].lower()} — {dom['pct']:.0f}% of exits",
        f"- **Build style:** {short:.0f}% short · {direct:.0f}% long/direct",
    ]
    if link:
        lines.append(
            f"- **Key link:** {_surname(link['passer'])} → "
            f"{_surname(link['receiver'])} ({link['count']}×)")
    if report["top_players"]:
        names = " · ".join(
            f"{_surname(p['player'])} ({p['exits']})"
            for p in report["top_players"][:4])
        lines.append(f"- **Key players (exits):** {names}")
    return "\n".join(lines)
