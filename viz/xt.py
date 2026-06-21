"""Expected-Threat (xT) visualisations — pitch heatmap + top contributors bar."""

import pandas as pd
import plotly.graph_objects as go
from processing.xt import XT_GRID, N_COLS, N_ROWS
from config import AME_DARK_BG, AME_WHITE, AME_YELLOW, AME_BLUE


def xt_grid_heatmap(title: str = "Expected Threat (xT) Grid") -> go.Figure:
    """Show the canonical Karun-Singh xT grid as a pitch heatmap.

    Useful as an explainer on a Data Sources / Methodology page.
    """
    fig = go.Figure(data=go.Heatmap(
        z=XT_GRID,
        x=[f"{int(i / N_COLS * 100)}%" for i in range(N_COLS)],
        y=[f"{int(i / N_ROWS * 100)}%" for i in range(N_ROWS)],
        colorscale="Viridis",
        colorbar=dict(title=dict(text="xT", font=dict(color=AME_WHITE)),
                      tickfont=dict(color=AME_WHITE)),
        hovertemplate="x=%{x} y=%{y}<br>xT=%{z:.4f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color=AME_WHITE)),
        height=320, paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        font=dict(color=AME_WHITE),
        xaxis=dict(title="Attacking direction →"),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=20, r=20, t=40, b=30),
    )
    return fig


def xt_pitch_heatmap(passes_df: pd.DataFrame, title: str = "") -> go.Figure:
    """Heatmap of *xT added by passes* aggregated to the 12x8 grid.

    Shows where on the pitch this team's passes generated threat.
    """
    fig = go.Figure()
    if passes_df.empty or "xt_added" not in passes_df.columns:
        fig.update_layout(paper_bgcolor=AME_DARK_BG)
        return fig

    # Aggregate xt_added by start cell of each pass
    df = passes_df[passes_df["xt_added"] > 0].copy()
    if df.empty:
        fig.update_layout(paper_bgcolor=AME_DARK_BG)
        return fig

    df["col"] = (df["x"] / 100.0 * N_COLS).clip(0, N_COLS - 1).astype(int)
    df["row"] = (df["y"] / 100.0 * N_ROWS).clip(0, N_ROWS - 1).astype(int)
    grid = df.groupby(["row", "col"])["xt_added"].sum().reset_index()

    z = [[0.0] * N_COLS for _ in range(N_ROWS)]
    for _, r in grid.iterrows():
        z[int(r["row"])][int(r["col"])] = float(r["xt_added"])

    fig = go.Figure(data=go.Heatmap(
        z=z,
        colorscale=[[0, "rgba(14,17,23,0.0)"], [0.4, "#3E1B1B"], [0.7, "#C62828"], [1, "#FFB74D"]],
        showscale=True,
        colorbar=dict(title=dict(text="xT added", font=dict(color=AME_WHITE, size=10)),
                      tickfont=dict(color=AME_WHITE, size=9), thickness=10, len=0.7),
        hovertemplate="cell xT %{z:.3f}<extra></extra>",
    ))
    # Pitch outline overlay (simplified — just draw vertical 3rds)
    for x_third in [N_COLS / 3, 2 * N_COLS / 3]:
        fig.add_vline(x=x_third - 0.5, line=dict(color="rgba(255,255,255,0.25)", dash="dot", width=1))
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(color=AME_WHITE, size=13)),
        height=320, paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(visible=False, range=[-0.5, N_COLS - 0.5]),
        yaxis=dict(visible=False, range=[N_ROWS - 0.5, -0.5]),
    )
    fig.add_annotation(x=N_COLS - 0.5, y=N_ROWS / 2, text="→ Attack",
                       showarrow=False, xanchor="right", yanchor="middle",
                       font=dict(color="rgba(255,255,255,0.4)", size=11))
    return fig


def xt_top_contributors_bar(top_df: pd.DataFrame, title: str = "",
                            color: str = AME_YELLOW) -> go.Figure:
    """Horizontal bar chart of top xT contributors."""
    fig = go.Figure()
    if top_df.empty:
        fig.update_layout(paper_bgcolor=AME_DARK_BG)
        return fig

    df = top_df.iloc[::-1]   # so highest sits at the top of the chart
    fig.add_trace(go.Bar(
        x=df["xt_added"], y=df["player_name"],
        orientation="h", marker_color=color,
        text=df.apply(lambda r: f" +{r['xt_added']:.2f}  ({int(r['passes'])})", axis=1),
        textposition="outside", textfont=dict(color=AME_WHITE, size=11),
        hovertemplate="<b>%{y}</b><br>xT added: +%{x:.3f}<br>"
                      "passes: %{customdata}<extra></extra>",
        customdata=df["passes"],
    ))
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(color=AME_WHITE, size=13)),
        height=320, paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        margin=dict(l=10, r=70, t=40, b=20),
        xaxis=dict(title="xT added", gridcolor="#333",
                   tickfont=dict(color=AME_WHITE, size=10)),
        yaxis=dict(tickfont=dict(color=AME_WHITE, size=11)),
        font=dict(color=AME_WHITE),
        showlegend=False,
    )
    return fig


def xdef_top_defenders_bar(top_df: pd.DataFrame, title: str = "",
                           color: str = AME_BLUE) -> go.Figure:
    """Horizontal bar chart of top xDEF (defensive threat denied) defenders.

    Defensive twin of ``xt_top_contributors_bar``. Expects columns
    ``player_name``, ``xdef`` and ``actions`` (as produced by
    ``processing.xdef.compute_season_xdef``'s leaderboard).
    """
    fig = go.Figure()
    if top_df.empty:
        fig.update_layout(paper_bgcolor=AME_DARK_BG)
        return fig

    df = top_df.iloc[::-1]   # highest sits at the top of the chart
    fig.add_trace(go.Bar(
        x=df["xdef"], y=df["player_name"],
        orientation="h", marker_color=color,
        text=df.apply(lambda r: f" {r['xdef']:.2f}  ({int(r['actions'])})", axis=1),
        textposition="outside", textfont=dict(color=AME_WHITE, size=11),
        hovertemplate="<b>%{y}</b><br>xDEF (threat denied): %{x:.3f}<br>"
                      "actions: %{customdata}<extra></extra>",
        customdata=df["actions"],
    ))
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(color=AME_WHITE, size=13)),
        height=320, paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        margin=dict(l=10, r=70, t=40, b=20),
        xaxis=dict(title="xDEF (threat denied)", gridcolor="#333",
                   tickfont=dict(color=AME_WHITE, size=10)),
        yaxis=dict(tickfont=dict(color=AME_WHITE, size=11)),
        font=dict(color=AME_WHITE),
        showlegend=False,
    )
    return fig
