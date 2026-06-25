from __future__ import annotations
"""Pass sonars — the canonical per-player passing rose.

A sonar bins a player's passes by direction and draws one wedge per sector:

    • wedge ORIENTATION  → the direction the passes went (forward = right, matching
      the left→right attacking pitch);
    • wedge LENGTH       → mean pass distance in that direction;
    • wedge COLOUR       → mean xP (completion difficulty) / reward / or volume.

It reads instantly to a coach ("he only ever plays it square-right") and, coloured
by xP, it literally *is* the risk/reward story made visual — long red wedges are
ambitious low-percentage balls; short green wedges are safe recycling.

Consumes the ``processing.expected_pass.passes_xp`` frame (needs x, y, end_x,
end_y, and optionally xp / reward).  Renders straight into Streamlit.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors
import pandas as pd
import streamlit as st

from config import AME_DARK_BG, AME_YELLOW, AME_WHITE, AME_GRID

_N_SECTORS = 16


def _sonar_axes(ax, sub: pd.DataFrame, color_by: str) -> None:
    """Draw one player's sonar onto a polar Axes ``ax``."""
    clean = sub.dropna(subset=["end_x", "end_y"])
    if clean.empty:
        ax.set_xticks([]); ax.set_yticks([])
        return

    dx = (clean["end_x"] - clean["x"]).to_numpy()
    dy = (clean["end_y"] - clean["y"]).to_numpy()
    ang = np.arctan2(dy, dx)                       # 0 = straight forward (+x)
    dist = np.sqrt(dx ** 2 + dy ** 2)

    edges = np.linspace(-np.pi, np.pi, _N_SECTORS + 1)
    idx = np.clip(np.digitize(ang, edges) - 1, 0, _N_SECTORS - 1)

    width = 2 * np.pi / _N_SECTORS
    centers = edges[:-1] + width / 2

    lengths = np.zeros(_N_SECTORS)
    metric = np.full(_N_SECTORS, np.nan)
    counts = np.zeros(_N_SECTORS)
    for s in range(_N_SECTORS):
        m = idx == s
        if not m.any():
            continue
        lengths[s] = dist[m].mean()
        counts[s] = m.sum()
        if color_by == "xp" and "xp" in clean.columns:
            metric[s] = clean["xp"].to_numpy()[m].mean()
        elif color_by == "reward" and "reward" in clean.columns:
            metric[s] = clean["reward"].to_numpy()[m].mean()
        else:
            metric[s] = counts[s]

    # Colour map: xP uses RdYlGn (green = easy/high completion); others Viridis.
    if color_by == "xp":
        norm = colors.Normalize(vmin=0.3, vmax=1.0)
        cmap = plt.get_cmap("RdYlGn")
    else:
        finite = metric[np.isfinite(metric)]
        vmax = finite.max() if finite.size else 1.0
        norm = colors.Normalize(vmin=0.0, vmax=vmax or 1.0)
        cmap = plt.get_cmap("viridis")
    bar_colors = [cmap(norm(v)) if np.isfinite(v) else (0, 0, 0, 0) for v in metric]

    ax.bar(centers, lengths, width=width * 0.92, bottom=0.0,
           color=bar_colors, edgecolor=AME_DARK_BG, linewidth=0.6, alpha=0.95)
    ax.set_theta_zero_location("E")     # forward (+x) points right
    ax.set_theta_direction(1)
    ax.set_xticks([]); ax.set_yticks([])
    ax.spines["polar"].set_color(AME_GRID)
    ax.set_facecolor(AME_DARK_BG)


def plot_pass_sonars(passes: pd.DataFrame, title: str = "Pass Sonars",
                     n_players: int = 6, color_by: str = "xp",
                     min_passes: int = 12) -> None:
    """Small-multiple grid of pass sonars for a team's busiest passers.

    ``passes`` is the ``passes_xp`` frame; ``color_by`` ∈ {"xp", "reward",
    "volume"}.  Forward = right; wedge length = mean distance; colour = the
    chosen metric.  Renders into Streamlit (no return value).
    """
    if passes is None or passes.empty or "player_name" not in passes.columns:
        st.info("No pass data for sonars.")
        return

    counts = passes.groupby("player_name").size().sort_values(ascending=False)
    counts = counts[counts >= min_passes]
    if counts.empty:
        st.info("Not enough passes per player for sonars.")
        return
    players = counts.head(n_players).index.tolist()

    ncols = 3
    nrows = int(np.ceil(len(players) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 3.4 * nrows),
                             subplot_kw={"projection": "polar"})
    fig.set_facecolor(AME_DARK_BG)
    axes = np.atleast_1d(axes).ravel()

    for ax, name in zip(axes, players):
        _sonar_axes(ax, passes[passes["player_name"] == name], color_by)
        n = int(counts[name])
        ax.set_title(f"{name}\n{n} passes", color=AME_WHITE, fontsize=10, pad=8)
    for ax in axes[len(players):]:
        ax.set_visible(False)

    legend = {"xp": "colour = completion likelihood (green easy → red hard)",
              "reward": "colour = xT reward of the pass",
              "volume": "colour = pass volume in that direction"}.get(color_by, "")
    fig.suptitle(f"{title}\n{legend}  ·  forward = right, length = mean distance",
                 color=AME_YELLOW, fontsize=13, y=1.0)
    fig.tight_layout()
    st.pyplot(fig, width="stretch")
    plt.close(fig)
