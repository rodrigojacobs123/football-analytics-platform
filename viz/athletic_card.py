"""Visualization components for The Athletic-style player profile cards.

Components:
  - style_matrix_figure: 5×5 coloured squares showing dimension ratings
  - shot_map_figure:     mplsoccer half-pitch shot map (forwards)
  - passing_rose_figure: Plotly polar bar chart of pass directions (midfielders)
  - chance_creation_figure: mplsoccer arrows for key passes (creators)
  - heatmap_figure:      mplsoccer KDE touch density (all positions)
  - similar_players_figure: Plotly horizontal bar of similarity scores
"""

from __future__ import annotations

import math
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from mplsoccer import Pitch, VerticalPitch

from config import MU_RED, MU_GOLD, MU_DARK_BG, MU_CARD_BG

# Shared dark theme colours
_BG = "#0E1117"
_CARD = "#1A1A2E"
_TEXT_LIGHT = "#CCCCCC"
_TEXT_DIM = "#888888"
_EMPTY_SQUARE = "#2A2A3E"


# ── Style Matrix (5×5 squares) ────────────────────────────────────────────────

def style_matrix_figure(
    dimensions: dict[str, int],
    position_color: str = MU_RED,
) -> go.Figure:
    """Render a 5-row × 5-column coloured-square matrix as a Plotly figure.

    Args:
        dimensions: {dimension_name: rating_1_to_5}
        position_color: Colour for filled squares.

    Returns:
        Plotly Figure.
    """
    dim_names = list(dimensions.keys())
    n_rows = len(dim_names)
    n_cols = 5

    fig = go.Figure()

    for row_idx, dim_name in enumerate(dim_names):
        rating = dimensions[dim_name]  # 1-5
        y = n_rows - row_idx  # top row = highest y

        for col_idx in range(n_cols):
            filled = col_idx < rating
            color = position_color if filled else _EMPTY_SQUARE

            # Rectangle shape
            fig.add_shape(
                type="rect",
                x0=col_idx + 0.05, x1=col_idx + 0.85,
                y0=y - 0.75, y1=y - 0.10,
                fillcolor=color,
                line=dict(color="rgba(0,0,0,0)", width=0),
                layer="below",
            )

        # Dimension label on the left
        fig.add_annotation(
            x=-0.1, y=y - 0.42,
            text=dim_name,
            showarrow=False,
            font=dict(color=_TEXT_LIGHT, size=11),
            xanchor="right",
            xref="x", yref="y",
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=n_rows * 50 + 20,
        margin=dict(l=120, r=20, t=10, b=10),
        xaxis=dict(visible=False, range=[-0.2, n_cols]),
        yaxis=dict(visible=False, range=[0.2, n_rows + 0.5]),
        showlegend=False,
    )
    return fig


# ── Shot Map ─────────────────────────────────────────────────────────────────

def shot_map_figure(
    shots_df: pd.DataFrame,
    xg_total: float | None = None,
    goals_total: int | None = None,
) -> plt.Figure:
    """Half-pitch shot map: sized by xG, filled = goal, hollow = no goal.

    Args:
        shots_df: DataFrame with columns x, y, xg, outcome (1=goal).
        xg_total: Season xG total (shown in annotation).
        goals_total: Season goals (shown in annotation).
    """
    pitch = VerticalPitch(
        pitch_type="opta",
        half=True,
        pitch_color=_BG,
        line_color="#444",
        linewidth=1.2,
        goal_type="box",
    )
    fig, ax = pitch.draw(figsize=(5, 4))
    fig.patch.set_facecolor(_BG)

    if shots_df.empty:
        ax.text(50, 70, "No shot data", ha="center", va="center",
                color=_TEXT_DIM, fontsize=12)
        return fig

    goals_mask = shots_df["outcome"] == 1
    non_goals = shots_df[~goals_mask]
    goals = shots_df[goals_mask]

    dot_scale = 600

    if not non_goals.empty:
        xg_vals = non_goals.get("xg", pd.Series([0.1] * len(non_goals))).fillna(0.1)
        pitch.scatter(
            non_goals["x"], non_goals["y"],
            s=(xg_vals * dot_scale).clip(20, 400),
            color="#4A90D9",
            edgecolors="#AACCEE",
            linewidth=0.8,
            alpha=0.75,
            ax=ax,
        )

    if not goals.empty:
        xg_vals = goals.get("xg", pd.Series([0.2] * len(goals))).fillna(0.2)
        pitch.scatter(
            goals["x"], goals["y"],
            s=(xg_vals * dot_scale).clip(30, 450),
            color=MU_RED,
            edgecolors="#FF8888",
            linewidth=1.2,
            alpha=0.95,
            ax=ax,
        )

    # Annotations
    if xg_total is not None:
        ax.text(25, 52, f"xG\n{xg_total:.1f}", ha="center", va="center",
                color="#4A90D9", fontsize=14, fontweight="bold")
    if goals_total is not None:
        ax.text(75, 52, f"Goals\n{goals_total}", ha="center", va="center",
                color=MU_RED, fontsize=14, fontweight="bold")

    fig.tight_layout(pad=0.5)
    return fig


# ── Passing Direction Rose ────────────────────────────────────────────────────

def passing_rose_figure(passes_df: pd.DataFrame) -> go.Figure:
    """Plotly polar bar chart showing pass direction frequency, coloured by avg distance.

    Bins passes into 16 compass directions (22.5° each).
    In Opta coords: x goes 0→100 attacking (forward = increasing x),
    y goes 0→100 left-to-right. We map so 'forward' (increasing x) = top of rose.

    Args:
        passes_df: DataFrame with x, y, end_x, end_y columns.
    """
    if passes_df.empty or len(passes_df) < 5:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=220,
            annotations=[dict(text="Insufficient pass data", showarrow=False,
                              font=dict(color=_TEXT_DIM, size=12), x=0.5, y=0.5,
                              xref="paper", yref="paper")],
        )
        return fig

    dx = passes_df["end_x"] - passes_df["x"]
    dy = passes_df["end_y"] - passes_df["y"]

    # Angle in degrees: forward (dx>0) = 0°, rotate so 0° = top of polar chart
    # atan2(dx, dy) gives clockwise bearing from "forward"
    angles_rad = np.arctan2(dy, dx)
    angles_deg = np.degrees(angles_rad)
    # Shift so forward pass (dx>0, dy=0) = 90° in math, but we want 0° in polar
    compass = (90 - angles_deg) % 360

    distances = np.sqrt(dx**2 + dy**2)

    n_bins = 16
    bin_size = 360 / n_bins
    bins = np.floor(compass / bin_size).astype(int) % n_bins

    bin_counts = np.zeros(n_bins)
    bin_avg_dist = np.zeros(n_bins)
    for b in range(n_bins):
        mask = bins == b
        bin_counts[b] = mask.sum()
        bin_avg_dist[b] = distances[mask].mean() if mask.sum() > 0 else 0

    # Scale distances to yards (Opta coords are ~% of pitch, ~105m×68m)
    bin_avg_dist_yards = bin_avg_dist * 1.05  # rough: 100 units ≈ 105 yards

    theta = [i * bin_size for i in range(n_bins)]

    colorscale = [
        [0, "#1A3A5C"],
        [0.33, "#1E5F8C"],
        [0.66, "#1A7FBE"],
        [1.0, "#A0D4F5"],
    ]
    max_d = bin_avg_dist_yards.max() if bin_avg_dist_yards.max() > 0 else 1
    colors = [
        f"rgb({int(30 + 170 * (d/max_d))}, {int(100 + 100 * (d/max_d))}, {int(200 + 55 * (d/max_d))})"
        for d in bin_avg_dist_yards
    ]

    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=bin_counts,
        theta=theta,
        width=[bin_size] * n_bins,
        marker_color=colors,
        marker_line_color="rgba(0,0,0,0.3)",
        marker_line_width=0.5,
        opacity=0.92,
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        polar=dict(
            bgcolor=_BG,
            radialaxis=dict(visible=False),
            angularaxis=dict(
                tickmode="array",
                tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                ticktext=["Forward", "", "Right", "", "Back", "", "Left", ""],
                tickfont=dict(color=_TEXT_DIM, size=9),
                direction="clockwise",
                rotation=90,
                linecolor="#333",
                gridcolor="#222",
            ),
        ),
        margin=dict(l=30, r=30, t=30, b=30),
        height=240,
        showlegend=False,
        title=dict(
            text="Avg dist (yards)",
            font=dict(color=_TEXT_DIM, size=9),
            x=0.85, y=0.05,
        ),
    )
    return fig


# ── Chance Creation Map ───────────────────────────────────────────────────────

def chance_creation_figure(keypasses_df: pd.DataFrame) -> plt.Figure:
    """mplsoccer pitch with arrows showing key pass origins → destinations.

    Args:
        keypasses_df: DataFrame with x, y, end_x, end_y columns.
    """
    pitch = Pitch(
        pitch_type="opta",
        pitch_color=_BG,
        line_color="#444",
        linewidth=1.2,
    )
    fig, ax = pitch.draw(figsize=(5, 3.5))
    fig.patch.set_facecolor(_BG)

    if keypasses_df.empty:
        ax.text(50, 50, "No chance creation data", ha="center", va="center",
                color=_TEXT_DIM, fontsize=11)
        return fig

    pitch.lines(
        keypasses_df["x"], keypasses_df["y"],
        keypasses_df["end_x"], keypasses_df["end_y"],
        lw=1.5, comet=True,
        color="#4A90D9", alpha=0.6,
        ax=ax,
    )
    pitch.scatter(
        keypasses_df["end_x"], keypasses_df["end_y"],
        s=30, color="#4A90D9", alpha=0.8, ax=ax,
        edgecolors="#AACCEE", linewidth=0.5,
    )
    pitch.scatter(
        keypasses_df["x"], keypasses_df["y"],
        s=20, color=MU_GOLD, alpha=0.9, ax=ax,
    )

    # Label xA and assists if present
    xa = keypasses_df.get("xg", pd.Series(dtype=float)).sum()
    assists = int(keypasses_df.get("is_assist", pd.Series(0)).sum())
    if xa > 0:
        ax.text(20, 5, f"xA\n{xa:.1f}", ha="center", va="bottom",
                color="#4A90D9", fontsize=13, fontweight="bold")
    if assists > 0:
        ax.text(80, 5, f"Assists\n{assists}", ha="center", va="bottom",
                color=MU_RED, fontsize=13, fontweight="bold")

    fig.tight_layout(pad=0.5)
    return fig


# ── Season Heatmap ────────────────────────────────────────────────────────────

def heatmap_figure(events_df: pd.DataFrame, team_color: str = MU_RED) -> plt.Figure:
    """mplsoccer KDE touch density heatmap (open play only).

    Args:
        events_df: DataFrame with x, y columns (all events for the player, open play).
        team_color: Primary colour for the KDE gradient.
    """
    pitch = Pitch(
        pitch_type="opta",
        pitch_color=_BG,
        line_color="#333",
        linewidth=1.0,
    )
    fig, ax = pitch.draw(figsize=(5, 3.5))
    fig.patch.set_facecolor(_BG)

    if events_df.empty or len(events_df) < 5:
        ax.text(50, 50, "No event data available", ha="center", va="center",
                color=_TEXT_DIM, fontsize=11)
        return fig

    valid = events_df.dropna(subset=["x", "y"])
    if len(valid) < 5:
        ax.text(50, 50, "Insufficient events", ha="center", va="center",
                color=_TEXT_DIM, fontsize=11)
        return fig

    # Build a matplotlib colormap from dark background to team colour
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "player_heat", [_BG, team_color], N=256
    )

    pitch.kdeplot(
        valid["x"], valid["y"],
        ax=ax, cmap=cmap,
        fill=True, alpha=0.75,
        levels=100, bw_adjust=0.7,
    )

    fig.tight_layout(pad=0.5)
    return fig


# ── Similar Players Bar ───────────────────────────────────────────────────────

def similar_players_figure(
    similar_df: pd.DataFrame,
    position_color: str = MU_RED,
) -> go.Figure:
    """Horizontal bar chart of top-N similar players with similarity %.

    Args:
        similar_df: DataFrame with columns: nombre, equipo, liga, similarity_pct.
        position_color: Bar colour.
    """
    if similar_df.empty:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            height=200,
            annotations=[dict(text="No comparison data", showarrow=False,
                              font=dict(color=_TEXT_DIM, size=12), x=0.5, y=0.5,
                              xref="paper", yref="paper")],
        )
        return fig

    df = similar_df.head(10).copy()
    df = df.sort_values("similarity_pct", ascending=True)

    labels = df["nombre"].tolist()
    values = df["similarity_pct"].tolist()

    # Use lighter shade for lower similarity
    bar_colors = [
        f"rgba({int(218 * (v/100))}, {int(41 * (v/100))}, {int(28 * (v/100))}, 0.85)"
        for v in values
    ]
    # Top match gets full red
    bar_colors[-1] = position_color

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color="white", size=11),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(df) * 30 + 60),
        margin=dict(l=130, r=20, t=10, b=30),
        xaxis=dict(
            range=[90, 100.5],
            tickfont=dict(color=_TEXT_DIM, size=10),
            gridcolor="#1E1E2E",
            showline=False,
        ),
        yaxis=dict(
            tickfont=dict(color=_TEXT_LIGHT, size=11),
            showgrid=False,
        ),
        showlegend=False,
    )
    return fig


# ── Positions Played Bubble ───────────────────────────────────────────────────

_POSITION_COORDS: dict[str, tuple[float, float]] = {
    # (x, y) in a 0-100 pitch coordinate system (attack = top)
    "GK":  (50, 8),
    "CB":  (50, 22), "LCB": (35, 22), "RCB": (65, 22),
    "LB":  (18, 28), "RB":  (82, 28),
    "LWB": (15, 38), "RWB": (85, 38),
    "DM":  (50, 38), "CDM": (50, 38),
    "LM":  (15, 52), "CM":  (50, 52), "RM":  (85, 52),
    "CAM": (50, 62), "AM":  (50, 62),
    "SS":  (38, 68), "RAM": (62, 68),
    "LW":  (18, 72), "RW":  (82, 72),
    "CF":  (50, 80), "ST":  (50, 80),
}


def positions_played_figure(position_pcts: dict[str, float]) -> plt.Figure:
    """Pitch diagram with position bubbles sized by % of minutes.

    Args:
        position_pcts: {position_code: percentage_0_to_100}
    """
    pitch = Pitch(
        pitch_type="opta",
        pitch_color=_BG,
        line_color="#333",
        linewidth=1.0,
        goal_type="box",
    )
    fig, ax = pitch.draw(figsize=(4, 3))
    fig.patch.set_facecolor(_BG)

    for pos_code, pct in position_pcts.items():
        if pct < 2 or pos_code not in _POSITION_COORDS:
            continue
        x, y = _POSITION_COORDS[pos_code]
        size = max(pct * 12, 120)
        alpha = 0.5 + pct / 200

        ax.scatter(x, y, s=size, c=MU_RED, alpha=alpha,
                   zorder=5, edgecolors="white", linewidths=0.6)
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                color="white", fontsize=7, fontweight="bold", zorder=6)
        ax.text(x, y - 5.5, pos_code, ha="center", va="center",
                color=_TEXT_DIM, fontsize=6.5, zorder=6)

    fig.tight_layout(pad=0.3)
    return fig
