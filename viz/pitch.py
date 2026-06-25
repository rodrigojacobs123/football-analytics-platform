from __future__ import annotations
"""mplsoccer pitch visualizations — shot maps, pass networks, heatmaps, lineups."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from collections import defaultdict
from mplsoccer import Pitch, VerticalPitch
import streamlit as st

from config import AME_YELLOW, AME_BLUE, AME_DARK_BG, EVENT_PASS, EVENT_GOAL
from viz.theme import PITCH_KWARGS, HALF_PITCH_KWARGS, AME_CMAP

# ── mplsoccer formation string aliases (Opta "4-3-3" → mplsoccer "433") ──────
_FORMATION_ALIASES = {
    "4-4-2": "442", "4-4-1-1": "4411", "4-3-3": "433", "4-5-1": "451",
    "4-1-4-1": "4141", "4-2-3-1": "4231", "4-3-2-1": "4321", "5-3-2": "532",
    "5-4-1": "541", "3-5-2": "352", "3-4-3": "343", "3-4-2-1": "3421",
    "4-1-2-1-2": "41212", "3-5-1-1": "3511", "3-1-4-2": "3142",
    "3-4-1-2": "3412", "4-2-2-2": "4222", "4-2-4-0": "424",
    "4-1-3-2": "4132", "3-2-4-1": "3241",
    # already-clean forms
    "442": "442", "433": "433", "4231": "4231", "451": "451",
    "4411": "4411", "4141": "4141", "532": "532", "541": "541",
    "352": "352", "343": "343",
}

_MPLSOCCER_FORMATIONS = {
    "442", "41212", "433", "451", "4411", "4141", "4231", "4321",
    "532", "541", "352", "343", "3421", "3511", "3412", "3142", "4222",
    "4132", "424", "4312", "3241", "3331", "432", "441", "4311", "4221",
    "4131", "4212", "342", "3411", "351", "531", "431",
}


def _draw_pitch(pitch, figsize=(12, 8)):
    """Draw pitch and set dark background on the figure."""
    fig, ax = pitch.draw(figsize=figsize)
    fig.set_facecolor(AME_DARK_BG)
    return fig, ax


def _show_fig(fig):
    """Display a matplotlib figure in Streamlit and close it."""
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def plot_shot_map(shots: pd.DataFrame, title: str = "Shot Map",
                  half: bool = True) -> None:
    """Plot shots on a pitch. Color by outcome, size by xG."""
    if shots.empty:
        st.info("No shots to display.")
        return

    if half:
        pitch = VerticalPitch(**HALF_PITCH_KWARGS)
    else:
        pitch = Pitch(**PITCH_KWARGS)

    fig, ax = _draw_pitch(pitch, figsize=(10, 7))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    outcome_colors = {
        "Goal": "#4CAF50",
        "Saved": AME_BLUE,
        "Missed": "#888888",
        "Post": "#FF9800",
        "Unknown": "#555555",
    }

    for outcome, group in shots.groupby("outcome"):
        color = outcome_colors.get(outcome, "#555555")
        sizes = group["xg"].clip(0.01, 1.0) * 400 + 30

        if half:
            pitch.scatter(group["x"], group["y"], s=sizes, c=color,
                          edgecolors="white", linewidth=0.5, alpha=0.8,
                          label=outcome, ax=ax, zorder=5)
        else:
            pitch.scatter(group["x"], group["y"], s=sizes, c=color,
                          edgecolors="white", linewidth=0.5, alpha=0.8,
                          label=outcome, ax=ax, zorder=5)

    ax.legend(loc="lower left", fontsize=9, facecolor=AME_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_pass_network(nodes: pd.DataFrame, edges: pd.DataFrame,
                      title: str = "Pass Network",
                      node_color: str = AME_YELLOW) -> None:
    """Pass network on a proper mplsoccer VerticalPitch.

    Players are placed at their average touch position on a real pitch outline.
    Edge thickness = pass volume; only top-25% connections are labelled.

    Coordinate convention (Opta):
        avg_x: 0 = own goal-line → 100 = opponent goal-line  (→ vertical axis)
        avg_y: 0 = right touchline → 100 = left touchline     (→ horizontal, flipped)
    """
    if nodes.empty:
        st.info("No pass network data.")
        return

    nodes = nodes.copy()
    edges = edges.copy()
    nodes["player_id"] = nodes["player_id"].astype(str)
    if not edges.empty:
        edges["from_id"] = edges["from_id"].astype(str)
        edges["to_id"] = edges["to_id"].astype(str)

    # ── Pitch ───────────────────────────────────────────────────────────────
    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color="#0D1117",
        line_color="#2A3A4A",
        linewidth=1.2,
        goal_type="box",
        corner_arcs=True,
        pad_top=4, pad_bottom=4, pad_left=2, pad_right=2,
    )
    fig, ax = pitch.draw(figsize=(6, 9))
    fig.set_facecolor(AME_DARK_BG)
    ax.set_facecolor("#0D1117")

    # Title
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=12)

    # ── Coordinate mapping ──────────────────────────────────────────────────
    # For VerticalPitch with opta: scatter(x, y) → x=width coord, y=length coord
    # Opta avg_y → pitch width (x):  flip because Opta y=0 = right touchline
    # Opta avg_x → pitch length (y): 0=own goal at bottom, 100=opp goal at top
    px = (100 - nodes["avg_y"].values).clip(0, 100)   # horizontal position on pitch
    py = nodes["avg_x"].values.clip(0, 100)            # vertical  position on pitch
    pos = dict(zip(nodes["player_id"], zip(px, py)))   # {pid: (px, py)}

    # ── Edges — pass connections ────────────────────────────────────────────
    if not edges.empty:
        max_passes = max(edges["pass_count"].max(), 1)
        top_threshold = edges["pass_count"].quantile(0.75) if len(edges) > 3 else 0

        for _, edge in edges.iterrows():
            fid, tid = str(edge["from_id"]), str(edge["to_id"])
            if fid not in pos or tid not in pos:
                continue
            fx, fy = pos[fid]
            tx, ty = pos[tid]
            ratio = edge["pass_count"] / max_passes
            lw    = ratio * 7 + 0.8
            alpha = float(np.clip(ratio * 0.65 + 0.15, 0.12, 0.90))

            ax.plot([fx, tx], [fy, ty],
                    color=AME_BLUE, linewidth=lw,
                    alpha=alpha, solid_capstyle="round",
                    transform=ax.transData, zorder=2)

            # Badge on strongest connections only
            if edge["pass_count"] >= top_threshold and edge["pass_count"] > 2:
                mx, my = (fx + tx) / 2, (fy + ty) / 2
                ax.text(mx, my, str(int(edge["pass_count"])),
                        ha="center", va="center", fontsize=7,
                        fontweight="bold", color="white",
                        bbox=dict(facecolor="#000000CC", edgecolor=AME_BLUE,
                                  linewidth=0.8, boxstyle="round,pad=0.25"),
                        zorder=6)

    # ── Nodes — players ────────────────────────────────────────────────────
    has_shirt = "shirt_number" in nodes.columns
    node_sizes = []
    if "pass_count" in nodes.columns:
        pcounts = nodes["pass_count"].fillna(0).values
        pmax = max(pcounts.max(), 1)
        node_sizes = (pcounts / pmax * 900 + 200).tolist()
    else:
        node_sizes = [400] * len(nodes)

    for i, (_, node) in enumerate(nodes.iterrows()):
        pid = node["player_id"]
        if pid not in pos:
            continue
        x, y = pos[pid]
        shirt = str(int(node["shirt_number"])) if (has_shirt and node.get("shirt_number") and
                                                    str(node["shirt_number"]) not in ("", "nan")) else ""
        name = node.get("player_name", "")
        last = name.split()[-1] if name and " " in name else (name or shirt)

        sz = node_sizes[i] if i < len(node_sizes) else 400

        # Glow halo
        ax.scatter(x, y, s=sz + 180, c="none",
                   edgecolors=node_color, linewidths=2.5,
                   alpha=0.35, zorder=3)
        # Main circle
        ax.scatter(x, y, s=sz, c=node_color,
                   edgecolors="white", linewidths=1.5,
                   alpha=0.95, zorder=4)
        # Shirt number inside circle
        ax.text(x, y, shirt,
                ha="center", va="center",
                fontsize=8, fontweight="bold", color="white", zorder=5)
        # Name label just below the circle
        ax.text(x, y - np.sqrt(sz) / 2 / 12 - 1.8, last,
                ha="center", va="top",
                fontsize=6.5, fontweight="bold", color="white",
                zorder=5,
                bbox=dict(facecolor="#00000088", edgecolor="none",
                          boxstyle="round,pad=0.15"))

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def plot_lineup(
    starters: list[dict],
    formation_str: str,
    name_map: dict[str, str],
    title: str = "",
    primary_color: str = "#003366",
    sub_players: list[dict] | None = None,
    events_list: list[dict] | None = None,
) -> None:
    """Draw a match lineup on a proper mplsoccer VerticalPitch.

    Uses mplsoccer's built-in ``get_formation()`` to place all 11 players at
    canonical formation positions — GK at the bottom, forwards at the top.

    Parameters
    ----------
    starters      : list of {player_id, shirt, position_row, order_in_row}
    formation_str : Opta formation string, e.g. "4-3-3" or "4-2-3-1"
    name_map      : {player_id → display_name}
    title         : chart title
    primary_color : fill color for player circles
    sub_players   : list of {player_id, shirt, came_on_for} — shown with a
                    different outline to mark substitutes
    events_list   : raw event list used to sort players laterally by avg touch y
    """
    if not starters:
        st.info("No lineup data available.")
        return

    # ── Resolve mplsoccer formation string ──────────────────────────────────
    fmt_clean = _FORMATION_ALIASES.get(formation_str, formation_str.replace("-", ""))
    if fmt_clean not in _MPLSOCCER_FORMATIONS:
        fmt_clean = "433"   # safe fallback

    # ── Draw the pitch ───────────────────────────────────────────────────────
    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color="#0D1117",
        line_color="#2C3E50",
        linewidth=1.3,
        goal_type="box",
        corner_arcs=True,
        pad_top=6, pad_bottom=6, pad_left=4, pad_right=4,
    )
    fig, ax = pitch.draw(figsize=(5, 8))
    fig.set_facecolor(AME_DARK_BG)
    ax.set_facecolor("#0D1117")
    if title:
        ax.set_title(title, color="white", fontsize=12, fontweight="bold", pad=10,
                     fontfamily="sans-serif")

    # ── Get mplsoccer canonical positions for this formation ─────────────────
    try:
        positions = pitch.get_formation(fmt_clean)
    except Exception:
        st.info(f"Formation {formation_str} not supported for pitch display.")
        plt.close(fig)
        return

    # positions[i] has .x (length, 0=own goal→100) and .y (width, 0=right→100)
    # For VerticalPitch scatter: first arg = y (width), second = x (length)

    # ── Build avg-y map from events for lateral ordering ────────────────────
    avg_y_map: dict[str, float] = {}
    if events_list:
        bucket: dict[str, list[float]] = defaultdict(list)
        for ev in events_list:
            pid = ev.get("playerId", "")
            yv  = ev.get("y")
            if pid and yv is not None:
                bucket[pid].append(float(yv))
        avg_y_map = {pid: sum(ys) / len(ys) for pid, ys in bucket.items() if ys}

    # ── Sort starters to match formation order ───────────────────────────────
    # Group starters by position_row, sort within each row by avg_y (left→right)
    from itertools import chain
    rows: dict[int, list] = defaultdict(list)
    for p in starters:
        rows[p["position_row"]].append(p)

    sub_ids = {p["player_id"] for p in (sub_players or [])}

    ordered: list[dict] = []
    for row_key in sorted(rows):
        row_players = rows[row_key]
        # Sort by avg touch y (low y = right touchline → left touchline)
        row_players.sort(key=lambda p: avg_y_map.get(p["player_id"], p.get("order_in_row", 0) * 25))
        ordered.extend(row_players)

    # Trim / pad to exactly 11
    ordered = ordered[:11]
    while len(ordered) < len(positions):
        ordered.append({"player_id": "", "shirt": "?", "position_row": 3, "order_in_row": 0})

    # ── Draw each player ─────────────────────────────────────────────────────
    for player, pos in zip(ordered, positions):
        px  = pos.y    # width coordinate → horizontal on VerticalPitch
        py  = pos.x    # length coordinate → vertical on VerticalPitch

        pid   = player.get("player_id", "")
        shirt = str(player.get("shirt", "")).strip()
        name  = name_map.get(pid, player.get("player_name", ""))
        last  = name.split()[-1] if name and " " in name else (name or shirt)
        is_sub = pid in sub_ids

        circle_color = primary_color
        edge_color   = AME_BLUE if is_sub else "white"
        edge_width   = 2.5 if is_sub else 1.8

        # Shadow / glow
        ax.scatter(px, py, s=820, c="none",
                   edgecolors=circle_color, linewidths=3.5,
                   alpha=0.20, zorder=3)
        # Main circle
        ax.scatter(px, py, s=620, c=circle_color,
                   edgecolors=edge_color, linewidths=edge_width,
                   alpha=0.95, zorder=4)
        # Shirt number
        ax.text(px, py, shirt,
                ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=5)
        # Name label below circle
        ax.text(px, py - 4.8, last,
                ha="center", va="top",
                fontsize=6.2, fontweight="bold", color="white",
                zorder=5,
                bbox=dict(facecolor="#000000AA", edgecolor="none",
                          boxstyle="round,pad=0.2"))

    # ── Legend for substitutes ───────────────────────────────────────────────
    if sub_players:
        legend_patches = [
            mpatches.Patch(facecolor=primary_color, edgecolor="white",
                           linewidth=1.5, label="Starter"),
            mpatches.Patch(facecolor=primary_color, edgecolor=AME_BLUE,
                           linewidth=2.5, label="Came on (sub)"),
        ]
        ax.legend(handles=legend_patches, loc="upper center",
                  bbox_to_anchor=(0.5, -0.01), ncol=2,
                  fontsize=7, facecolor="#1A1A2E", edgecolor="#333",
                  labelcolor="white", framealpha=0.8)

    # Formation string annotation
    ax.text(50, 3, formation_str,
            ha="center", va="center", fontsize=11, fontweight="bold",
            color=AME_BLUE, alpha=0.8, zorder=6)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def plot_heatmap(touches: pd.DataFrame, title: str = "Touch Heatmap") -> None:
    """Plot a KDE heatmap of all touch events."""
    if touches.empty:
        st.info("No touch data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    pitch.kdeplot(touches["x"], touches["y"], ax=ax,
                  cmap=AME_CMAP, fill=True, levels=50, thresh=0.05,
                  alpha=0.7, zorder=2)

    _show_fig(fig)


def plot_formation(formation: dict, player_names: dict[str, str],
                   title: str = "Formation",
                   primary_color: str = AME_YELLOW,
                   ratings: dict[str, float] | None = None,
                   events_list: list[dict] | None = None,
                   use_avg_positions: bool = False,
                   snap_to_template: bool = False,
                   team_id: str = "") -> None:
    """Plot starting XI on a horizontal Plotly pitch (GK left → FWD right).

    Uses the tactical_positions engine for accurate per-role placement.
    When ``use_avg_positions=True`` and events_list is provided, overlays median
    event positions for maximum fidelity (a real, if cloud-like, position map).
    When ``snap_to_template=True`` instead, players are re-assigned to the clean
    formation template slots by their real average position — a tidy formation
    diagram with the correct player in each slot (fixes Opta's left-right
    identity scramble). ``snap_to_template`` takes precedence if both are set.
    """
    import plotly.graph_objects as go
    from processing.tactical_positions import (
        get_formation_positions, average_player_positions,
        merge_canonical_with_averages, snap_players_to_template,
    )

    if not formation:
        st.info("No formation data available.")
        return

    starters = formation.get("starters", [])
    if not starters:
        st.info("No formation data available.")
        return

    form_str = formation.get("formation_str", "")

    # ── Resolve player positions via tactical engine ────────────────────
    positioned = get_formation_positions(formation, player_names)

    if (snap_to_template or use_avg_positions) and events_list and team_id:
        avg_pos = average_player_positions(events_list, team_id)
        if avg_pos:
            positioned = (snap_players_to_template(positioned, avg_pos)
                          if snap_to_template
                          else merge_canonical_with_averages(positioned, avg_pos))

    # ── Pitch geometry (standard 105 × 68 m) ────────────────────────────
    PW, PH = 105.0, 68.0
    BG           = "#0D1117"
    STRIPE_DARK  = "#0D1117"
    STRIPE_LIGHT = "#111119"
    LINE_CLR     = "#30363D"

    shapes: list[dict] = []

    for i in range(10):
        shapes.append(dict(
            type="rect",
            x0=i * PW / 10, y0=0,
            x1=(i + 1) * PW / 10, y1=PH,
            fillcolor=STRIPE_DARK if i % 2 == 0 else STRIPE_LIGHT,
            line_width=0, layer="below",
        ))

    shapes.append(dict(type="rect", x0=0, y0=0, x1=PW, y1=PH,
                       line=dict(color=LINE_CLR, width=2),
                       fillcolor="rgba(0,0,0,0)"))
    shapes.append(dict(type="line", x0=PW / 2, y0=0, x1=PW / 2, y1=PH,
                       line=dict(color=LINE_CLR, width=1.5)))
    shapes.append(dict(type="circle",
                       x0=PW / 2 - 9.15, y0=PH / 2 - 9.15,
                       x1=PW / 2 + 9.15, y1=PH / 2 + 9.15,
                       line=dict(color=LINE_CLR, width=1.5),
                       fillcolor="rgba(0,0,0,0)"))

    pa_y0, pa_y1 = 13.84, 54.16
    shapes += [
        dict(type="rect", x0=0,         y0=pa_y0, x1=16.5,      y1=pa_y1,
             line=dict(color=LINE_CLR, width=1.5), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=PW - 16.5, y0=pa_y0, x1=PW,        y1=pa_y1,
             line=dict(color=LINE_CLR, width=1.5), fillcolor="rgba(0,0,0,0)"),
    ]

    sb_y0, sb_y1 = 24.84, 43.16
    shapes += [
        dict(type="rect", x0=0,        y0=sb_y0, x1=5.5,  y1=sb_y1,
             line=dict(color=LINE_CLR, width=1), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=PW - 5.5, y0=sb_y0, x1=PW,   y1=sb_y1,
             line=dict(color=LINE_CLR, width=1), fillcolor="rgba(0,0,0,0)"),
    ]

    g_y0, g_y1 = 30.34, 37.66
    shapes += [
        dict(type="rect", x0=-2,   y0=g_y0, x1=0,      y1=g_y1,
             line=dict(color=LINE_CLR, width=1.5),
             fillcolor="rgba(255,255,255,0.04)"),
        dict(type="rect", x0=PW,   y0=g_y0, x1=PW + 2, y1=g_y1,
             line=dict(color=LINE_CLR, width=1.5),
             fillcolor="rgba(255,255,255,0.04)"),
    ]

    # ── Convert normalised 0-100 coords → pitch metres ──────────────────
    # x_norm (0=own goal, 100=opp goal) → pitch x (0 to 105)
    # y_norm (0=right, 100=left) → pitch y (0 to 68)
    pxs: list[float] = []
    pys: list[float] = []
    shirts: list[str] = []
    lastnames: list[str] = []
    pids: list[str] = []
    pratings: list[float | None] = []

    for p in positioned:
        px = p["x"] / 100.0 * PW
        py = p["y"] / 100.0 * PH
        pid = p["player_id"]
        shirt = p["jersey_number"]
        full_name = p["player_name"] or player_names.get(pid, "")
        last = full_name.split()[-1] if " " in full_name else (full_name or shirt)
        rating = ratings.get(pid) if ratings else None
        pxs.append(px)
        pys.append(py)
        shirts.append(shirt)
        lastnames.append(last)
        pids.append(pid)
        pratings.append(rating)

    # ── Build figure ─────────────────────────────────────────────────────
    fig = go.Figure()

    # Player discs — large markers with jersey numbers centred
    fig.add_trace(go.Scatter(
        x=pxs, y=pys,
        mode="markers+text",
        marker=dict(
            size=28,
            color=primary_color,
            line=dict(color="white", width=2),
            symbol="circle",
        ),
        text=shirts,
        textfont=dict(color="white", size=11,
                      family="'JetBrains Mono', 'Courier New', monospace"),
        textposition="middle center",
        hoverinfo="skip",
        showlegend=False,
    ))

    # Annotations: player surnames + rating badges
    annotations: list[dict] = []
    for x, y, name, rating in zip(pxs, pys, lastnames, pratings):
        annotations.append(dict(
            x=x, y=y - 3.8,
            text=name,
            showarrow=False,
            font=dict(color="#BBBBBB", size=8,
                      family="'JetBrains Mono', 'Courier New', monospace"),
            xanchor="center", yanchor="top",
        ))
        if rating is not None:
            badge_bg = "#3DD68C" if rating >= 8.0 else ("#FBE122" if rating >= 7.0 else "#FF9F1C")
            annotations.append(dict(
                x=x + 2.8, y=y + 2.8,
                text=f"<b>{rating:.1f}</b>",
                showarrow=False,
                font=dict(color="#0E0E14", size=7,
                          family="'JetBrains Mono', 'Courier New', monospace"),
                bgcolor=badge_bg,
                bordercolor=badge_bg,
                borderwidth=1,
                borderpad=2,
                xanchor="center", yanchor="middle",
            ))

    title_html = (
        f"<b>{title}</b>"
        + (f"  <span style='font-size:11px;color:#555;'>{form_str}</span>"
           if form_str else "")
    )
    fig.update_layout(
        title=dict(
            text=title_html,
            font=dict(color="white", size=13,
                      family="'JetBrains Mono', 'Courier New', monospace"),
            x=0.5, xanchor="center", pad=dict(t=4, b=0),
        ),
        shapes=shapes,
        annotations=annotations,
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        xaxis=dict(
            range=[-3, PW + 3],
            showgrid=False, zeroline=False, showticklabels=False,
            fixedrange=True,
        ),
        yaxis=dict(
            range=[-5, PH + 3],
            showgrid=False, zeroline=False, showticklabels=False,
            fixedrange=True,
        ),
        margin=dict(l=4, r=4, t=36, b=4),
        height=380,
        dragmode=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def plot_formation_shape(formation_str: str, title: str = "",
                         primary_color: str = AME_YELLOW,
                         pct: float | None = None) -> None:
    """Draw the tactical shape of a formation on a half-pitch.

    Takes a formation string like '3-4-2-1' and places abstract position
    dots in the correct rows.  No player names needed — this is a
    season-level overview.
    """
    if not formation_str or formation_str == "?":
        st.info("No formation data.")
        return

    # Parse "3-4-2-1" → [3, 4, 2, 1]
    try:
        rows = [int(x) for x in formation_str.split("-")]
    except ValueError:
        st.info(f"Cannot parse formation: {formation_str}")
        return

    full_pitch_kwargs = dict(PITCH_KWARGS)
    pitch = VerticalPitch(**full_pitch_kwargs)
    fig, ax = _draw_pitch(pitch, figsize=(5, 8))

    label = formation_str
    if pct is not None:
        label += f"  ({pct:.0f}%)"
    ax.set_title(label if not title else title,
                 color="white", fontsize=14, fontweight="bold", pad=10)

    # Y positions for each row (GK at bottom → FWD at top)
    # GK is always 1 player at y=8
    n_field_rows = len(rows)
    y_positions = np.linspace(25, 82, n_field_rows)

    # Draw GK first
    pitch.scatter(8, 50, s=500, c=primary_color, edgecolors="white",
                  linewidth=2, ax=ax, zorder=5)
    pitch.scatter(8, 50, s=800, c="none", edgecolors=primary_color,
                  linewidth=2, alpha=0.5, ax=ax, zorder=4)
    ax.annotate("GK", xy=(8, 50), ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=6)

    # Draw field rows
    row_labels = _get_row_labels(rows)
    for i, (n_players, y) in enumerate(zip(rows, y_positions)):
        x_positions = np.linspace(15, 85, n_players + 2)[1:-1] if n_players > 1 else [50]
        for x in x_positions:
            # Outer ring
            pitch.scatter(y, x, s=500, c=primary_color, edgecolors="white",
                          linewidth=2, ax=ax, zorder=5)
            pitch.scatter(y, x, s=800, c="none", edgecolors=primary_color,
                          linewidth=2, alpha=0.5, ax=ax, zorder=4)

        # Row label on the right side
        lbl = row_labels[i] if i < len(row_labels) else ""
        ax.annotate(lbl, xy=(y, 96), ha="center", va="bottom",
                    fontsize=8, color="#888", fontstyle="italic", zorder=2)

    # Connection lines between rows (subtle structure lines)
    all_y = [8] + list(y_positions)
    for j in range(len(all_y) - 1):
        ax.plot([all_y[j], all_y[j + 1]], [50, 50],
                color="#444", linewidth=0.8, alpha=0.4, zorder=1,
                linestyle="--")

    _show_fig(fig)


def _get_row_labels(rows: list[int]) -> list[str]:
    """Assign tactical labels to formation rows."""
    n = len(rows)
    if n == 3:
        return ["DEF", "MID", "FWD"]
    elif n == 4:
        return ["DEF", "DM", "AM", "FWD"]
    elif n == 5:
        return ["DEF", "DM", "MID", "AM", "FWD"]
    else:
        return ["DEF"] + ["MID"] * max(0, n - 2) + ["FWD"]


def plot_defensive_actions(tackles: pd.DataFrame, interceptions: pd.DataFrame,
                           title: str = "Defensive Actions") -> None:
    """Plot tackles and interceptions on the pitch."""
    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    if not tackles.empty:
        pitch.scatter(tackles["x"], tackles["y"], s=80,
                      c="#42A5F5", edgecolors="white", linewidth=0.5,
                      alpha=0.7, label="Tackles", ax=ax, zorder=4)

    if not interceptions.empty:
        pitch.scatter(interceptions["x"], interceptions["y"], s=80,
                      c=AME_BLUE, edgecolors="white", linewidth=0.5,
                      alpha=0.7, label="Interceptions", ax=ax, zorder=4)

    ax.legend(loc="lower left", fontsize=9, facecolor=AME_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def _draw_prog_arrows(ax, pitch, df: "pd.DataFrame", label_suffix: str = "") -> None:
    """Draw completed/incomplete pass arrows on ax."""
    completed = df[df["outcome"] == 1]
    incomplete = df[df["outcome"] == 0]
    if not completed.empty:
        pitch.arrows(completed["x"], completed["y"],
                     completed["end_x"], completed["end_y"],
                     color="#4CAF50", alpha=0.65, width=1.5,
                     headwidth=5, headlength=3, ax=ax, zorder=3,
                     label=f"Complete{label_suffix}")
    if not incomplete.empty:
        pitch.arrows(incomplete["x"], incomplete["y"],
                     incomplete["end_x"], incomplete["end_y"],
                     color=AME_YELLOW, alpha=0.45, width=1, headwidth=4,
                     headlength=3, ax=ax, zorder=3,
                     label=f"Incomplete{label_suffix}")
    ax.legend(loc="lower left", fontsize=9, facecolor=AME_DARK_BG,
              edgecolor="#444", labelcolor="white")


def plot_progressive_passes(passes: pd.DataFrame,
                            title: str = "Progressive Passes") -> None:
    """Two-tab progressive pass map.

    Tab 1 — Long progressive carries: >20m total distance AND >10m forward.
    Tab 2 — Final-third entries: pass lands in the attacking third (end_x ≥ 66.7).
    Opta pitch is 0–100; 100 units ≈ 105 m → 20 m ≈ 19.05 units, 10 m ≈ 9.52 units.
    """
    if passes.empty or "end_x" not in passes.columns:
        st.info("No progressive pass data.")
        return

    clean = passes.dropna(subset=["end_x", "end_y"]).copy()
    dx = clean["end_x"] - clean["x"]
    dy = clean["end_y"] - clean["y"]
    dist = (dx**2 + dy**2) ** 0.5

    long_prog = clean[(dist > 19.05) & (dx > 9.52)]
    final_third = clean[(clean["end_x"] >= 66.7) & (dx > 0)]

    tab_long, tab_final = st.tabs([
        f"🔵 Long Progressive ({len(long_prog)})",
        f"🔴 Final-Third Entries ({len(final_third)})",
    ])

    pitch = Pitch(**PITCH_KWARGS)

    with tab_long:
        if long_prog.empty:
            st.info("No long progressive passes (>20m & >10m forward).")
        else:
            fig, ax = _draw_pitch(pitch, figsize=(12, 8))
            ax.set_title(f"{title} — Long Progressive (>20 m, >10 m forward)",
                         color="white", fontsize=13, pad=10)
            _draw_prog_arrows(ax, pitch, long_prog)
            _show_fig(fig)
            st.caption(f"{len(long_prog[long_prog['outcome']==1])} completed · "
                       f"{len(long_prog[long_prog['outcome']==0])} incomplete")

    with tab_final:
        if final_third.empty:
            st.info("No passes into the final third found.")
        else:
            fig, ax = _draw_pitch(pitch, figsize=(12, 8))
            ax.set_title(f"{title} — Final-Third Entries",
                         color="white", fontsize=13, pad=10)
            # Shade the final third
            import matplotlib.patches as mpatches
            ax.axvline(x=66.7, color="#FBE122", lw=1, ls="--", alpha=0.5)
            ax.add_patch(mpatches.Rectangle(
                (66.7, 0), 33.3, 100,
                facecolor="#FBE12215", edgecolor="none", zorder=1,
            ))
            _draw_prog_arrows(ax, pitch, final_third, " (final ⅓)")
            _show_fig(fig)
            st.caption(f"{len(final_third[final_third['outcome']==1])} completed · "
                       f"{len(final_third[final_third['outcome']==0])} incomplete")


def plot_pass_map(passes: pd.DataFrame,
                  title: str = "Pass Map") -> None:
    """Plot all passes on a full pitch — completed (green) and incomplete (red)."""
    if passes.empty or "end_x" not in passes.columns:
        st.info("No pass data to display.")
        return

    clean = passes.dropna(subset=["end_x", "end_y"]).copy()
    if clean.empty:
        st.info("No pass data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    completed = clean[clean["outcome"] == 1]
    incomplete = clean[clean["outcome"] == 0]

    if not completed.empty:
        pitch.arrows(completed["x"], completed["y"],
                     completed["end_x"], completed["end_y"],
                     color="#4CAF50", alpha=0.5, width=1.5,
                     headwidth=5, headlength=3, ax=ax, zorder=3,
                     label="Complete")

    if not incomplete.empty:
        pitch.arrows(incomplete["x"], incomplete["y"],
                     incomplete["end_x"], incomplete["end_y"],
                     color=AME_YELLOW, alpha=0.35, width=1, headwidth=4,
                     headlength=3, ax=ax, zorder=3, label="Incomplete")

    ax.legend(loc="lower left", fontsize=9, facecolor=AME_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_set_piece_map(
    df: pd.DataFrame,
    title: str = "Set Pieces",
    color: str = AME_YELLOW,
    highlight_col: str | None = None,
    highlight_color: str = AME_BLUE,
    highlight_label: str = "Dangerous",
    default_label: str = "Normal",
    color_by: str | None = None,
    color_map: dict[str, str] | None = None,
    goal_col: str | None = None,
) -> None:
    """Plot set-piece locations on a full pitch.

    Parameters
    ----------
    df : DataFrame with x, y columns (Opta 0-100 coordinate system).
    highlight_col : optional bool column to split markers into two groups
                    (e.g. ``had_shot`` for corners, ``dangerous`` for FK zones).
    color_by : optional categorical column to color-code points (e.g.
               ``delivery_label`` for corner delivery type).
    color_map : dict mapping category values to hex colours.
    goal_col : optional bool column; True rows get a star marker (★).
    """
    if df.empty:
        st.info("No set-piece data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # ── Mode 1: color by categorical column (delivery type) ──────────
    if color_by and color_by in df.columns:
        cmap = color_map or {}
        categories = sorted(df[color_by].unique())
        for cat in categories:
            cat_df = df[df[color_by] == cat]
            c = cmap.get(cat, "#999")

            if goal_col and goal_col in cat_df.columns:
                no_goal = cat_df[cat_df[goal_col] != True]   # noqa: E712
                goals = cat_df[cat_df[goal_col] == True]     # noqa: E712
            else:
                no_goal = cat_df
                goals = pd.DataFrame()

            if not no_goal.empty:
                pitch.scatter(no_goal["x"], no_goal["y"], s=100, c=c,
                              edgecolors="white", linewidth=0.6, alpha=0.8,
                              label=cat, ax=ax, zorder=4)
            if not goals.empty:
                pitch.scatter(goals["x"], goals["y"], s=260, c=c,
                              edgecolors="white", linewidth=0.8, alpha=0.95,
                              marker="*", ax=ax, zorder=6)

        # Add a single "Goal" legend entry with a star marker
        if goal_col and goal_col in df.columns and df[goal_col].any():
            ax.scatter([], [], s=180, c="white", marker="*",
                       edgecolors="white", label="Goal ★")

    # ── Mode 2: binary highlight (original behaviour) ────────────────
    elif highlight_col and highlight_col in df.columns:
        hi = df[df[highlight_col] == True]   # noqa: E712
        lo = df[df[highlight_col] != True]   # noqa: E712

        if not lo.empty:
            pitch.scatter(lo["x"], lo["y"], s=80, c="#666",
                          edgecolors="white", linewidth=0.5, alpha=0.6,
                          label=default_label, ax=ax, zorder=4)
        if not hi.empty:
            pitch.scatter(hi["x"], hi["y"], s=140, c=highlight_color,
                          edgecolors="white", linewidth=0.8, alpha=0.9,
                          label=highlight_label, ax=ax, zorder=5)

    # ── Mode 3: plain single colour ──────────────────────────────────
    else:
        pitch.scatter(df["x"], df["y"], s=100, c=color,
                      edgecolors="white", linewidth=0.5, alpha=0.7,
                      ax=ax, zorder=4)

    ax.legend(loc="lower left", fontsize=9, facecolor=AME_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_corner_shot_panels(
    corners_df: pd.DataFrame,
    shots_df: pd.DataFrame,
    team_name: str,
    team_color: str = AME_YELLOW,
    n_matches: int | None = None,
) -> None:
    """Two-panel half-pitch showing shot locations after corners by side.

    Left panel = shots from Left Corners, Right panel = shots from Right Corners.
    Goals rendered as green stars, non-goals as circles sized by xG.
    """
    if corners_df.empty:
        st.info("No corner data to display.")
        return

    sides = ["Left Corner", "Right Corner"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    fig.set_facecolor(AME_DARK_BG)
    fig.suptitle(f"{team_name} — Corner Analysis", color="white",
                 fontsize=14, fontweight="bold", y=0.97)

    for idx, side in enumerate(sides):
        ax = axes[idx]
        pitch = VerticalPitch(**HALF_PITCH_KWARGS)
        pitch.draw(ax=ax)
        ax.set_facecolor(AME_DARK_BG)

        side_corners = corners_df[corners_df["corner_side"] == side]
        n_corners = len(side_corners)

        side_shots = shots_df[shots_df["corner_side"] == side] if not shots_df.empty else pd.DataFrame()
        n_shots = len(side_shots)

        goals = side_shots[side_shots["outcome"] == "Goal"] if not side_shots.empty else pd.DataFrame()
        non_goals = side_shots[side_shots["outcome"] != "Goal"] if not side_shots.empty else pd.DataFrame()
        n_goals = len(goals)
        total_xg = float(side_shots["xg"].sum()) if not side_shots.empty else 0.0

        # Delivery destinations (first touch after each corner)
        if "delivery_x" in side_corners.columns:
            deliveries = side_corners.dropna(subset=["delivery_x", "delivery_y"])
        else:
            deliveries = pd.DataFrame()
        n_deliveries = len(deliveries)

        # Panel title
        ax.set_title(f"{side} ({n_corners})", color="white", fontsize=12, pad=6)

        if n_corners == 0:
            ax.text(50, 82, "No corners\nfrom this side",
                    ha="center", va="center", color="#666", fontsize=11,
                    transform=ax.transData)
        else:
            # KDE heatmap on delivery destinations (more data points)
            if n_deliveries >= 5:
                pitch.kdeplot(deliveries["delivery_x"],
                              deliveries["delivery_y"], ax=ax,
                              cmap=AME_CMAP, fill=True, levels=40,
                              thresh=0.05, alpha=0.3, zorder=2)

            # Delivery destination markers — small circles, low alpha
            if n_deliveries > 0:
                pitch.scatter(deliveries["delivery_x"],
                              deliveries["delivery_y"],
                              s=40, c=team_color, edgecolors="white",
                              linewidth=0.4, alpha=0.45, ax=ax, zorder=3)

            # Non-goal shots — bigger circles sized by xG
            if not non_goals.empty:
                sizes = non_goals["xg"].fillna(0).clip(0) * 300 + 50
                pitch.scatter(non_goals["x"], non_goals["y"],
                              s=sizes, c=team_color, edgecolors="white",
                              linewidth=0.6, alpha=0.75, ax=ax, zorder=4)

            # Goal shots — green stars
            if not goals.empty:
                pitch.scatter(goals["x"], goals["y"],
                              s=350, c="#4CAF50", edgecolors="white",
                              linewidth=0.8, alpha=0.95, marker="*",
                              ax=ax, zorder=6)

            # Fallback text only if NO deliveries AND no shots
            if n_deliveries == 0 and n_shots == 0:
                ax.text(50, 82, f"{n_corners} corners\nno delivery data",
                        ha="center", va="center", color="#888", fontsize=10,
                        transform=ax.transData)

        # Stats annotation at bottom of panel
        stats_lines = [f"{n_corners} corners · {n_shots} shots · {n_goals} goals"]
        stats_lines.append(f"xG: {total_xg:.2f}")
        if n_matches and n_matches > 0 and n_corners > 0:
            rate = round(n_shots / n_matches, 1)
            stats_lines[0] += f" · {rate} shots/G"

        ax.annotate(
            "\n".join(stats_lines),
            xy=(0.5, -0.02), xycoords="axes fraction",
            ha="center", va="top", fontsize=9, color="#ccc",
            bbox=dict(facecolor="#1A1A2E", alpha=0.9, edgecolor="#444",
                      pad=4, boxstyle="round,pad=0.4"),
        )

    # Shared legend
    legend_elements = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=team_color,
                   markersize=5, alpha=0.5, linestyle="None", label="Delivery"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=team_color,
                   markersize=8, linestyle="None", label="Shot"),
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#4CAF50",
                   markersize=12, linestyle="None", label="Goal"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=3,
               fontsize=9, facecolor=AME_DARK_BG, edgecolor="#444",
               labelcolor="white", framealpha=0.9)

    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    _show_fig(fig)


def plot_ball_win_height(tackles: pd.DataFrame, interceptions: pd.DataFrame,
                         recoveries: pd.DataFrame,
                         title: str = "Ball Win Height",
                         color: str = AME_YELLOW) -> None:
    """Plot KDE heatmap of ball wins with average height line.

    Ball wins = tackles + interceptions + ball recoveries.
    The cyan dashed line shows the average x-position (ball win height).
    """
    frames = [df[["x", "y"]] for df in [tackles, interceptions, recoveries]
              if not df.empty]
    if not frames:
        st.info("No ball win data to display.")
        return

    ball_wins = pd.concat(frames, ignore_index=True)
    if ball_wins.empty:
        st.info("No ball win data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # KDE heatmap
    pitch.kdeplot(ball_wins["x"], ball_wins["y"], ax=ax,
                  cmap=AME_CMAP, fill=True, levels=50, thresh=0.05,
                  alpha=0.7, zorder=2)

    # Average ball win height — vertical line at mean x position
    avg_x = ball_wins["x"].mean()
    ax.plot([avg_x, avg_x], [0, 100], color="#00E5FF", linestyle="--",
            linewidth=2, alpha=0.8, zorder=6)
    ax.annotate(
        f"Avg: {avg_x:.1f}",
        xy=(avg_x, 2), ha="center", va="bottom",
        fontsize=10, fontweight="bold", color="#00E5FF",
        bbox=dict(facecolor="#222", alpha=0.8, edgecolor="#00E5FF",
                  pad=2, boxstyle="round,pad=0.3"),
        zorder=7,
    )

    # Ball win count
    ax.annotate(
        f"n = {len(ball_wins)}",
        xy=(96, 97), ha="right", va="top",
        fontsize=9, color="#999", zorder=7,
    )

    _show_fig(fig)


CORNER_SIDE_COLORS = {
    "Left Corner":  "#2196F3",   # blue
    "Right Corner": "#FF9800",   # orange
}


ZONE_ACTION_COLORS = {
    "Shot":         AME_BLUE,
    "Tackle":       "#009688",   # teal
    "Interception": "#9C27B0",   # purple
    "Recovery":     "#2196F3",   # blue
    "Take-on":      "#FF9800",   # orange
    "Aerial":       "#00BCD4",   # cyan
    "Clearance":    "#E91E63",   # pink
    "Cross":        "#CDDC39",   # lime
    "Foul":         "#F44336",   # red
    "Prog. Pass":   "#4CAF50",   # green
}


def plot_dominant_actions_by_zone(actions: pd.DataFrame,
                                  title: str = "Dominant Actions by Zone",
                                  action_colors: dict | None = None) -> None:
    """Plot a 5×3 pitch grid colored by the dominant action type per zone.

    ``actions`` must have columns: x, y, action.
    Optionally accepts a custom ``action_colors`` dict (action → hex).
    """
    from matplotlib.patches import Rectangle, Patch

    if actions.empty or "action" not in actions.columns:
        st.info("No action data for zone analysis.")
        return

    colors = action_colors or ZONE_ACTION_COLORS

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # Zone grid: 5 columns (x) × 3 rows (y)
    x_edges = [0, 20, 40, 60, 80, 100]
    y_edges = [0, 33.33, 66.66, 100]

    for xi in range(len(x_edges) - 1):
        for yi in range(len(y_edges) - 1):
            x_min, x_max = x_edges[xi], x_edges[xi + 1]
            y_min, y_max = y_edges[yi], y_edges[yi + 1]

            zone = actions[
                (actions["x"] >= x_min) & (actions["x"] < x_max)
                & (actions["y"] >= y_min) & (actions["y"] < y_max)
            ]

            if zone.empty:
                continue

            counts = zone["action"].value_counts()
            dominant = counts.idxmax()
            dom_count = int(counts.iloc[0])
            total = int(counts.sum())
            zone_color = colors.get(dominant, "#444444")

            rect = Rectangle(
                (x_min, y_min), x_max - x_min, y_max - y_min,
                facecolor=zone_color, alpha=0.40, edgecolor="white",
                linewidth=1, zorder=2,
            )
            ax.add_patch(rect)

            cx = (x_min + x_max) / 2
            cy = (y_min + y_max) / 2
            ax.annotate(
                f"{dominant}\n({dom_count}/{total})",
                xy=(cx, cy), ha="center", va="center",
                fontsize=7, fontweight="bold", color="white",
                zorder=3,
            )

    # Build legend only for actions that actually appear
    present = set(actions["action"].unique())
    legend_elements = [
        Patch(facecolor=c, alpha=0.55, edgecolor="white", label=lbl)
        for lbl, c in colors.items() if lbl in present
    ]
    if legend_elements:
        ax.legend(handles=legend_elements, loc="lower left", fontsize=8,
                  facecolor=AME_DARK_BG, edgecolor="#444", labelcolor="white")

    _show_fig(fig)


# ── Origin badge colors ─────────────────────────────────────────────────
_ORIGIN_COLORS = {
    "OPEN_PLAY":  "#4CAF50",
    "CORNER":     "#FF9800",
    "FREE_KICK":  "#9C27B0",
    "THROW_IN":   "#00BCD4",
    "PENALTY":    "#F44336",
    "OWN_GOAL":   "#888888",
}
_ORIGIN_LABELS = {
    "OPEN_PLAY":  "Open Play",
    "CORNER":     "Corner",
    "FREE_KICK":  "Free Kick",
    "THROW_IN":   "Throw-In",
    "PENALTY":    "Penalty",
    "OWN_GOAL":   "Own Goal",
}


def plot_goal_buildup(buildup: dict, team_color: str = AME_YELLOW) -> None:
    """Plot a single goal build-up sequence on a full pitch.

    ``buildup`` is one dict from ``extract_goal_buildups()`` containing
    scorer, origin, sequence (list of event rows with x/y/end_x/end_y).
    """
    seq = buildup.get("sequence", [])
    if not seq:
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))

    origin = buildup["origin"]
    scorer = buildup["scorer"]
    minute = buildup["goal_minute"]
    n_passes = buildup["n_passes"]

    # Title
    ax.set_title(
        f"{scorer}  {minute}'",
        color="white", fontsize=13, fontweight="bold", pad=12,
    )

    # Draw pass arrows in sequence
    for i, ev in enumerate(seq):
        ex, ey = ev["x"], ev["y"]
        is_goal = ev["typeId"] == EVENT_GOAL
        is_pass = ev["typeId"] == EVENT_PASS

        if is_pass and ev.get("end_x") is not None:
            alpha = 0.5 + 0.4 * (i / max(len(seq) - 1, 1))
            pitch.arrows(
                ex, ey, ev["end_x"], ev["end_y"],
                color=team_color, alpha=alpha, width=2,
                headwidth=6, headlength=4, ax=ax, zorder=3,
            )
            # Player name at pass origin
            name = ev.get("player_name", "")
            short = name.split()[-1] if " " in name else name
            ax.annotate(
                short, xy=(ex, ey), fontsize=7, color="white",
                ha="center", va="bottom",
                xytext=(0, 6), textcoords="offset points",
                zorder=5,
            )

        # Goal marker — large star
        if is_goal:
            pitch.scatter(
                ex, ey, s=600, marker="*",
                c=AME_BLUE, edgecolors="white", linewidth=1,
                ax=ax, zorder=6,
            )
            ax.annotate(
                "GOAL", xy=(ex, ey), fontsize=8, fontweight="bold",
                color=AME_BLUE, ha="center", va="bottom",
                xytext=(0, 12), textcoords="offset points",
                zorder=7,
            )

    # Non-pass, non-goal events — small dots showing touch positions
    for ev in seq:
        if ev["typeId"] not in (EVENT_PASS, EVENT_GOAL):
            pitch.scatter(
                ev["x"], ev["y"], s=40, c="white", alpha=0.5,
                edgecolors="none", ax=ax, zorder=2,
            )

    # Origin badge (top-right of pitch)
    badge_color = _ORIGIN_COLORS.get(origin, "#666")
    badge_label = _ORIGIN_LABELS.get(origin, origin)
    ax.annotate(
        f"  {badge_label}  ",
        xy=(98, 2), ha="right", va="top",
        fontsize=9, fontweight="bold", color="white",
        bbox=dict(facecolor=badge_color, alpha=0.85, edgecolor="white",
                  linewidth=1, pad=3, boxstyle="round,pad=0.3"),
        zorder=8,
    )

    # Pass count + duration info (bottom-left)
    dur = buildup.get("duration_secs", 0)
    info = f"{n_passes} passes"
    if dur > 0:
        info += f"  ·  {dur}s"
    ax.annotate(
        info, xy=(2, 98), ha="left", va="bottom",
        fontsize=8, color="#aaa", zorder=8,
    )

    _show_fig(fig)


# ── Role → marker colour for the team-shape overlay ──────────────────────────
_SHAPE_ROLE_COLORS = {
    "GK":  "#888888",
    "DEF": AME_YELLOW,
    "MID": AME_BLUE,
    "ATT": "#4CAF50",
}


def plot_team_shape(shape: dict, title: str = "Team Shape & Stretch Index",
                    team_color: str = AME_YELLOW) -> None:
    """Average-position map with the back-four convex hull (Stretch Index).

    ``shape`` is the dict from ``processing.team_shape`` (keys: players with
    role GK/DEF/MID/ATT, stretch_index, exposure, line_height, block_width).
    The four deepest outfielders' hull is shaded — its area IS the Stretch Index.
    """
    players = (shape or {}).get("players", [])
    if not players:
        st.info("No team-shape data to display.")
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

    # Opta normalised → VerticalPitch coords (matches plot_pass_network):
    #   horizontal = 100 - y_norm  ;  vertical = x_norm
    def _xy(p):
        return (100 - p["y"], p["x"])

    # Back-four convex hull = the Stretch Index area.
    back4 = [p for p in players if p["role"] == "DEF"]
    if len(back4) >= 3:
        pts = np.array([_xy(p) for p in back4])
        try:
            from scipy.spatial import ConvexHull
            hull = ConvexHull(pts)
            poly = pts[hull.vertices]
        except Exception:
            poly = pts
        ax.add_patch(mpatches.Polygon(
            poly, closed=True, facecolor=team_color, alpha=0.18,
            edgecolor=team_color, linewidth=1.6, zorder=2))

    # Players.
    for p in players:
        hx, vy = _xy(p)
        c = _SHAPE_ROLE_COLORS.get(p["role"], AME_BLUE)
        ax.scatter(hx, vy, s=240, c=c, edgecolors="white", linewidths=1.2,
                   alpha=0.95, zorder=4)
        ax.text(hx, vy, p["role"][0], ha="center", va="center",
                fontsize=7, fontweight="bold", color="#0E0E14", zorder=5)

    # Defensive-line height marker.
    lh = shape.get("line_height")
    if lh is not None:
        ax.axhline(y=lh, color="#00E5FF", linestyle="--", linewidth=1.2,
                   alpha=0.7, zorder=3)

    # Metric annotation.
    txt = (f"Stretch Index: {shape.get('stretch_index', 0):.0f}   ·   "
           f"Exposure: {shape.get('exposure', 0):.1f}\n"
           f"Line height: {shape.get('line_height', 0):.0f}   ·   "
           f"Block width: {shape.get('block_width', 0):.0f}")
    ax.annotate(txt, xy=(0.5, -0.02), xycoords="axes fraction",
                ha="center", va="top", fontsize=9, color="#ccc",
                bbox=dict(facecolor="#1A1A2E", alpha=0.9, edgecolor="#444",
                          pad=4, boxstyle="round,pad=0.4"))

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def plot_carry_map(carries: pd.DataFrame, title: str = "Ball Carries") -> None:
    """Carry map — arrows from carry start to end, coloured by xT added.

    Brighter / yellower arrows drove the ball into more dangerous space; faint
    arrows are low-value carries. Progressive carries (forward drives) are drawn
    thicker. Consumes the ``processing.carries.carries_value`` frame (needs x, y,
    end_x, end_y, carry_xt, progressive). Renders into Streamlit.
    """
    if carries is None or carries.empty or "end_x" not in carries.columns:
        st.info("No carry data to display.")
        return

    clean = carries.dropna(subset=["end_x", "end_y"]).copy()
    if clean.empty:
        st.info("No carry data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # Colour by carry_xt (yellow = high value), normalised on the match max.
    xt = clean["carry_xt"].to_numpy()
    vmax = xt.max() if xt.size and xt.max() > 0 else 1.0
    import matplotlib.colors as _mcolors
    norm = _mcolors.Normalize(vmin=0.0, vmax=vmax)
    cmap = plt.get_cmap("YlOrRd")
    arrow_colors = cmap(norm(xt))

    prog = clean["progressive"].to_numpy() if "progressive" in clean.columns \
        else np.zeros(len(clean), dtype=bool)
    widths = np.where(prog, 2.4, 1.1)

    pitch.arrows(clean["x"], clean["y"], clean["end_x"], clean["end_y"],
                 color=arrow_colors, width=widths, headwidth=4, headlength=3,
                 ax=ax, zorder=3, alpha=0.8)

    n_prog = int(prog.sum())
    _show_fig(fig)
    st.caption(f"{len(clean)} carries · {n_prog} progressive (thicker) · "
               f"colour = xT added (brighter = drove into more danger)")
