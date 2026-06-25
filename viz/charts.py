from __future__ import annotations
"""Plotly chart builders — bar, line, scatter, histogram, heatmap, xG race."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import AME_YELLOW, AME_BLUE, AME_WHITE, AME_DARK_BG, AME_GRID


def line_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
               color: str = AME_YELLOW, y_label: str = "", markers: bool = False) -> go.Figure:
    """Simple line chart with Club América theme."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode="lines+markers" if markers else "lines",
        line=dict(color=color, width=2.5),
        marker=dict(size=6) if markers else None,
        name=y_label or y,
    ))
    fig.update_layout(title=title, xaxis_title=x, yaxis_title=y_label or y,
                      template="ame_dark")
    return fig


def multi_line_chart(df: pd.DataFrame, x: str, y_cols: list[str],
                     colors: list[str] | None = None, title: str = "",
                     y_label: str = "") -> go.Figure:
    """Multiple line series on the same chart."""
    if colors is None:
        colors = [AME_YELLOW, AME_BLUE, AME_WHITE, "#888888", "#4CAF50", "#2196F3"]
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col],
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2.5),
            name=col,
        ))
    fig.update_layout(title=title, yaxis_title=y_label, template="ame_dark")
    return fig


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
              color: str = AME_YELLOW, horizontal: bool = False) -> go.Figure:
    """Single-series bar chart."""
    if horizontal:
        fig = go.Figure(go.Bar(x=df[y], y=df[x], orientation="h",
                               marker_color=color))
        fig.update_layout(title=title, xaxis_title=y, yaxis_title=x,
                          template="ame_dark")
    else:
        fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=color))
        fig.update_layout(title=title, xaxis_title=x, yaxis_title=y,
                          template="ame_dark")
    return fig


def grouped_bar_chart(df: pd.DataFrame, x: str, y_cols: list[str],
                      colors: list[str] | None = None, title: str = "",
                      bar_names: list[str] | None = None) -> go.Figure:
    """Grouped bar chart with multiple series."""
    if colors is None:
        colors = [AME_YELLOW, AME_BLUE, AME_WHITE, "#888"]
    if bar_names is None:
        bar_names = y_cols
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Bar(
            x=df[x], y=df[col],
            name=bar_names[i],
            marker_color=colors[i % len(colors)],
        ))
    fig.update_layout(title=title, barmode="group", template="ame_dark")
    return fig


def scatter_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
                  size: str | None = None, color: str | None = None,
                  text: str | None = None, add_diagonal: bool = False) -> go.Figure:
    """Scatter plot with optional size, color, and text."""
    fig = px.scatter(
        df, x=x, y=y, size=size, color=color, text=text,
        title=title, template="ame_dark",
    )
    if add_diagonal:
        min_val = min(df[x].min(), df[y].min())
        max_val = max(df[x].max(), df[y].max())
        fig.add_trace(go.Scatter(
            x=[min_val, max_val], y=[min_val, max_val],
            mode="lines", line=dict(color="#666", dash="dash", width=1),
            showlegend=False,
        ))
    return fig


def histogram(values: pd.Series | np.ndarray, title: str = "",
              x_label: str = "", color: str = AME_YELLOW, nbins: int = 30) -> go.Figure:
    """Histogram chart."""
    fig = go.Figure(go.Histogram(x=values, nbinsx=nbins, marker_color=color))
    fig.update_layout(title=title, xaxis_title=x_label, yaxis_title="Frequency",
                      template="ame_dark")
    return fig


def donut_chart(labels: list[str], values: list[float], title: str = "",
                colors: list[str] | None = None) -> go.Figure:
    """Donut / pie chart."""
    if colors is None:
        colors = [AME_YELLOW, AME_BLUE, "#888888", "#4CAF50", "#2196F3"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5,
        marker_colors=colors[:len(labels)],
        textinfo="label+percent",
        textfont=dict(size=12),
    ))
    fig.update_layout(title=title, showlegend=True, template="ame_dark")
    return fig


def heatmap_grid(matrix: np.ndarray, x_labels: list[str], y_labels: list[str],
                 title: str = "", x_title: str = "", y_title: str = "",
                 annotate: bool = True, fmt: str = ".1%") -> go.Figure:
    """Heatmap grid (e.g., for Poisson scoreline probabilities)."""
    text_matrix = None
    if annotate:
        text_matrix = [[f"{v:{fmt}}" if v >= 0.005 else "" for v in row] for row in matrix]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=x_labels,
        y=y_labels,
        colorscale=[[0, AME_DARK_BG], [0.3, "#3D0A0A"], [0.6, AME_YELLOW], [1.0, AME_BLUE]],
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11),
        showscale=False,
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        xaxis=dict(dtick=1),
        yaxis=dict(dtick=1, autorange="reversed"),
        template="ame_dark",
    )
    return fig


def xg_race_chart(xg_timeline: pd.DataFrame, home_team: str, away_team: str,
                  goals: pd.DataFrame | None = None) -> go.Figure:
    """Stepped xG race chart with goal annotations."""
    fig = go.Figure()

    # Home team xG line
    fig.add_trace(go.Scatter(
        x=xg_timeline["minute"], y=xg_timeline["home_xg"],
        mode="lines", line=dict(color=AME_YELLOW, width=2.5, shape="hv"),
        name=f"{home_team} xG", fill="tozeroy",
        fillcolor="rgba(218,41,28,0.08)",
    ))

    # Away team xG line
    fig.add_trace(go.Scatter(
        x=xg_timeline["minute"], y=xg_timeline["away_xg"],
        mode="lines", line=dict(color="#42A5F5", width=2.5, shape="hv"),
        name=f"{away_team} xG", fill="tozeroy",
        fillcolor="rgba(66,165,245,0.08)",
    ))

    # Half-time marker
    fig.add_vline(x=45, line_dash="dash", line_color="#555555",
                  line_width=1, opacity=0.7)
    fig.add_annotation(
        x=45, y=1.0, yref="paper", yanchor="top",
        text="HT", showarrow=False,
        font=dict(size=10, color="#888"),
    )

    # Goal markers
    if goals is not None and not goals.empty:
        for _, g in goals.iterrows():
            is_home = g.get("team_id") == xg_timeline.attrs.get("home_id", "")
            team_color = AME_YELLOW if is_home else "#42A5F5"
            fig.add_vline(
                x=g["minute"], line_dash="dot",
                line_color=team_color, opacity=0.5,
            )
            y_val = xg_timeline.loc[
                xg_timeline["minute"] <= g["minute"],
                "home_xg" if is_home else "away_xg"
            ].iloc[-1] if len(xg_timeline) > 0 else 0
            fig.add_annotation(
                x=g["minute"], y=y_val,
                text=f"⚽ {g.get('player_name', '')}",
                showarrow=True, arrowhead=2, arrowcolor=team_color,
                font=dict(size=10, color="#FAFAFA"),
                bgcolor="rgba(30,30,30,0.85)", bordercolor=team_color,
            )

    fig.update_layout(
        title="xG Race",
        xaxis_title="Minute",
        yaxis_title="Cumulative xG",
        xaxis=dict(range=[0, 95]),
        hovermode="x unified",
        template="ame_dark",
    )
    return fig


def momentum_chart(momentum: pd.DataFrame, home_team: str, away_team: str,
                   goals: pd.DataFrame | None = None,
                   home_id: str | None = None) -> go.Figure:
    """xT momentum flow: rolling (home − away) threat across the match.

    ``momentum`` is the output of ``processing.xt.compute_xt_momentum``:
    columns ``minute, home_xt, away_xt, net``.  The single ``net`` series is
    drawn as a bi-colour area band — above zero shaded in the home colour
    (América yellow), below zero in the away colour — so a glance reads which
    side was on top and when.  Goal markers reuse the xG-race convention.
    """
    fig = go.Figure()

    if momentum is None or momentum.empty:
        fig.update_layout(template="ame_dark", title="xT Momentum")
        return fig

    minute = momentum["minute"]
    net = momentum["net"]

    # Above-zero band → home; below-zero band → away. Two traces filled to y=0.
    fig.add_trace(go.Scatter(
        x=minute, y=net.clip(lower=0),
        mode="lines", line=dict(color=AME_YELLOW, width=0.5),
        fill="tozeroy", fillcolor="rgba(255,209,0,0.45)",
        name=f"{home_team} ▲", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=minute, y=net.clip(upper=0),
        mode="lines", line=dict(color="#42A5F5", width=0.5),
        fill="tozeroy", fillcolor="rgba(66,165,245,0.45)",
        name=f"{away_team} ▼", hoverinfo="skip",
    ))
    # Invisible hover line carrying the signed momentum value.
    fig.add_trace(go.Scatter(
        x=minute, y=net, mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0),
        name="xT momentum", showlegend=False,
        hovertemplate="Min %{x}<br>net xT %{y:.3f}<extra></extra>",
    ))

    fig.add_hline(y=0, line_color="#555555", line_width=1, opacity=0.7)
    fig.add_vline(x=45, line_dash="dash", line_color="#555555",
                  line_width=1, opacity=0.7)
    fig.add_annotation(x=45, y=1.0, yref="paper", yanchor="top",
                       text="HT", showarrow=False,
                       font=dict(size=10, color="#888"))

    # Goal markers (vertical lines coloured by scoring team).
    if goals is not None and not goals.empty and home_id is not None:
        for _, g in goals.iterrows():
            is_home = g.get("team_id") == home_id
            team_color = AME_YELLOW if is_home else "#42A5F5"
            fig.add_vline(x=g["minute"], line_dash="dot",
                          line_color=team_color, opacity=0.5)

    fig.update_layout(
        title="xT Momentum",
        xaxis_title="Minute",
        yaxis_title="Rolling xT  (home ▲ / away ▼)",
        xaxis=dict(range=[0, 95]),
        hovermode="x unified",
        template="ame_dark",
    )
    return fig


def probability_bars(home_prob: float, draw_prob: float, away_prob: float,
                     home_team: str, away_team: str) -> go.Figure:
    """Horizontal stacked bar showing win/draw/loss probabilities."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[home_prob * 100], orientation="h",
        marker_color=AME_YELLOW, name=f"{home_team} Win",
        text=f"{home_prob:.0%}", textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[draw_prob * 100], orientation="h",
        marker_color="#888", name="Draw",
        text=f"{draw_prob:.0%}", textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[away_prob * 100], orientation="h",
        marker_color="#42A5F5", name=f"{away_team} Win",
        text=f"{away_prob:.0%}", textposition="inside",
    ))
    fig.update_layout(
        barmode="stack", showlegend=True,
        height=120, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        template="ame_dark",
    )
    return fig


def goals_by_matchday(df: pd.DataFrame, title: str = "Goals by Matchday") -> go.Figure:
    """Bar chart of goals scored vs conceded per matchday."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["matchday"], y=df["club_score"],
        name="Scored", marker_color="#4CAF50",
    ))
    fig.add_trace(go.Bar(
        x=df["matchday"], y=df["opp_score"],
        name="Conceded", marker_color=AME_YELLOW,
    ))
    fig.update_layout(title=title, barmode="group",
                      xaxis_title="Matchday", yaxis_title="Goals",
                      template="ame_dark")
    return fig


def monte_carlo_histogram(simulations: np.ndarray, home_team: str, away_team: str,
                          title: str = "Monte Carlo Simulation (10,000 matches)") -> go.Figure:
    """Histogram of goal difference from Monte Carlo simulations."""
    fig = go.Figure()

    # Split into win/draw/loss
    home_wins = simulations[simulations > 0]
    draws = simulations[simulations == 0]
    away_wins = simulations[simulations < 0]

    bins_range = dict(start=simulations.min() - 0.5, end=simulations.max() + 0.5, size=1)

    fig.add_trace(go.Histogram(
        x=home_wins, name=f"{home_team} Win",
        marker_color=AME_YELLOW, xbins=bins_range,
    ))
    fig.add_trace(go.Histogram(
        x=draws, name="Draw",
        marker_color="#888888", xbins=bins_range,
    ))
    fig.add_trace(go.Histogram(
        x=away_wins, name=f"{away_team} Win",
        marker_color="#42A5F5", xbins=bins_range,
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Goal Difference (Home - Away)",
        yaxis_title="Frequency",
        barmode="stack",
        template="ame_dark",
    )
    return fig


def tactical_progression_chart(
    df: pd.DataFrame,
    metrics: list[str],
    rolling_cols: list[str] | None = None,
    result_col: str = "result",
    matchday_col: str = "match_num",
    title: str = "Tactical Progression",
    colors: list[str] | None = None,
    y_label: str = "",
) -> go.Figure:
    """Multi-metric line chart with rolling averages and W/D/L result markers.

    Parameters
    ----------
    df : DataFrame with matchday data
    metrics : column names to plot (raw per-match values shown as faint dots)
    rolling_cols : column names for rolling averages (shown as bold lines).
                   If None, looks for '{metric}_rolling' columns.
    result_col : column with W/D/L values for marker coloring
    matchday_col : column for x-axis
    """
    if colors is None:
        colors = [AME_YELLOW, AME_BLUE, "#42A5F5", "#4CAF50", "#FF9800"]

    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = go.Figure()

    for i, metric in enumerate(metrics):
        color = colors[i % len(colors)]

        # Faint dots for raw per-match values
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[metric],
            mode="markers",
            marker=dict(size=6, color=color, opacity=0.3),
            name=f"{metric} (per match)",
            showlegend=False,
        ))

        # Bold rolling average line
        r_col = (rolling_cols[i] if rolling_cols else f"{metric}_rolling")
        if r_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[r_col],
                mode="lines",
                line=dict(color=color, width=3),
                name=metric.replace("_", " ").title(),
            ))

    # W/D/L markers along bottom
    if result_col in df.columns:
        for _, row in df.iterrows():
            res = row[result_col]
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[0],
                mode="markers",
                marker=dict(
                    size=10, color=RESULT_COLORS.get(res, "#888"),
                    symbol="square",
                ),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        yaxis_title=y_label,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="ame_dark",
    )
    return fig


def ppda_trend_chart(
    df: pd.DataFrame,
    matchday_col: str = "match_num",
    result_col: str = "result",
    title: str = "Pressing Intensity (PPDA)",
) -> go.Figure:
    """PPDA trend chart with tactical reference bands.

    Background bands show pressing intensity zones:
      < 9  = High press (green)
      9-13 = Mid-block (amber)
      > 13 = Low block (red)
    """
    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = go.Figure()

    # Reference bands
    fig.add_hrect(y0=0, y1=9, fillcolor="#4CAF50", opacity=0.08,
                  line_width=0, annotation_text="High Press",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#4CAF50"))
    fig.add_hrect(y0=9, y1=13, fillcolor="#FFC107", opacity=0.08,
                  line_width=0, annotation_text="Mid-Block",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#FFC107"))
    fig.add_hrect(y0=13, y1=40, fillcolor="#F44336", opacity=0.06,
                  line_width=0, annotation_text="Low Block",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#F44336"))

    # Per-match dots
    fig.add_trace(go.Scatter(
        x=df[matchday_col], y=df["ppda"],
        mode="markers",
        marker=dict(size=7, color=AME_BLUE, opacity=0.35),
        name="Per Match",
        showlegend=False,
    ))

    # Rolling average
    r_col = "ppda_rolling"
    if r_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[r_col],
            mode="lines",
            line=dict(color=AME_BLUE, width=3),
            name="5-Match Avg",
        ))

    # W/D/L markers
    if result_col in df.columns:
        y_base = max(df["ppda"].max() + 2, 20)
        for _, row in df.iterrows():
            res = row.get(result_col, "")
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[y_base],
                mode="markers",
                marker=dict(size=9, color=RESULT_COLORS.get(res, "#888"),
                            symbol="square"),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        yaxis_title="PPDA (lower = more pressing)",
        yaxis=dict(range=[0, max(df["ppda"].max() + 5, 25)]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="ame_dark",
    )
    return fig


def dual_axis_trend_chart(
    df: pd.DataFrame,
    matchday_col: str = "match_num",
    left_metric: str = "",
    right_metric: str = "",
    left_rolling: str = "",
    right_rolling: str = "",
    left_color: str = AME_BLUE,
    right_color: str = "#42A5F5",
    left_label: str = "",
    right_label: str = "",
    title: str = "",
    result_col: str = "result",
) -> go.Figure:
    """Dual y-axis trend chart — left axis for one metric, right for another."""
    from plotly.subplots import make_subplots

    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Left metric (dots + line)
    if left_metric in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[left_metric],
            mode="markers", marker=dict(size=6, color=left_color, opacity=0.3),
            name=left_label + " (per match)", showlegend=False,
        ), secondary_y=False)
        if left_rolling in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[left_rolling],
                mode="lines", line=dict(color=left_color, width=3),
                name=left_label,
            ), secondary_y=False)

    # Right metric (dots + line)
    if right_metric in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[right_metric],
            mode="markers", marker=dict(size=6, color=right_color, opacity=0.3),
            name=right_label + " (per match)", showlegend=False,
        ), secondary_y=True)
        if right_rolling in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[right_rolling],
                mode="lines", line=dict(color=right_color, width=3),
                name=right_label,
            ), secondary_y=True)

    # W/D/L markers
    if result_col in df.columns:
        for _, row in df.iterrows():
            res = row.get(result_col, "")
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[0],
                mode="markers",
                marker=dict(size=9, color=RESULT_COLORS.get(res, "#888"),
                            symbol="square"),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ), secondary_y=False)

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="ame_dark",
        paper_bgcolor=AME_DARK_BG,
        plot_bgcolor=AME_DARK_BG,
        font=dict(color="#FAFAFA"),
    )
    fig.update_yaxes(title_text=left_label, secondary_y=False,
                     title_font=dict(color=left_color),
                     tickfont=dict(color=left_color),
                     gridcolor="#1F1F2A")
    fig.update_yaxes(title_text=right_label, secondary_y=True,
                     title_font=dict(color=right_color),
                     tickfont=dict(color=right_color),
                     gridcolor="#1F1F2A")
    fig.update_xaxes(gridcolor="#1F1F2A")
    return fig


def formation_donut(formations: list[dict], title: str = "Formation Usage") -> go.Figure:
    """Donut chart of formation frequency from compute_formation_usage() output.

    formations: list of dicts with 'formation', 'count', 'pct' keys.
    """
    if not formations:
        return go.Figure()

    labels = [f["formation"] for f in formations]
    values = [f["count"] for f in formations]

    top_colors = [AME_YELLOW, AME_BLUE, "#42A5F5", "#4CAF50", "#FF9800", "#9C27B0", "#888"]
    chart_colors = top_colors[:len(labels)]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker_colors=chart_colors,
        textinfo="label+percent",
        textfont=dict(size=12),
        hovertemplate="%{label}: %{value} matches (%{percent})<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=True, template="ame_dark")
    return fig


def goalmouth_shot_map(shots: pd.DataFrame, title: str = "Goal-Mouth Placement",
                       color_by: str = "xgot") -> go.Figure:
    """Plot on-target shots on the goal frame, coloured by xGOT (post-shot xG).

    Expects the columns from ``data.event_parser.extract_shots`` plus an
    ``xgot`` column (see ``processing.xgot.add_xgot``).  The x-axis is the
    goal-mouth width (Opta y, posts ≈ 44.6 / 55.4) and the y-axis the height
    (Opta z, crossbar ≈ 38).  Shots whose height was not recorded by the feed
    (placeholder z ≈ 19) are excluded from this view — they have no meaningful
    height to plot — and the count is annotated so nothing is hidden silently.

    Goals are drawn as filled stars, saved shots as circles.
    """
    # Goal-frame display geometry (mirrors constants in processing/xgot.py)
    LEFT_POST, RIGHT_POST, CROSSBAR = 44.62, 55.38, 38.0
    Z_PLACEHOLDER = 19.0

    fig = go.Figure()

    if shots is None or shots.empty or "goalmouth_y" not in shots.columns:
        fig.update_layout(title=title, template="ame_dark")
        return fig

    df = shots[shots.get("on_target", False) & shots["goalmouth_y"].notna()
               & shots["goalmouth_z"].notna()].copy()
    n_total = len(df)
    df = df[(df["goalmouth_z"] - Z_PLACEHOLDER).abs() > 0.2]   # drop placeholder-height
    n_hidden = n_total - len(df)

    # ── Draw the goal frame ────────────────────────────────────────────────
    frame = dict(color=AME_WHITE, width=3)
    fig.add_shape(type="line", x0=LEFT_POST, y0=0, x1=LEFT_POST, y1=CROSSBAR, line=frame)
    fig.add_shape(type="line", x0=RIGHT_POST, y0=0, x1=RIGHT_POST, y1=CROSSBAR, line=frame)
    fig.add_shape(type="line", x0=LEFT_POST, y0=CROSSBAR, x1=RIGHT_POST, y1=CROSSBAR, line=frame)
    fig.add_shape(type="line", x0=LEFT_POST - 2, y0=0, x1=RIGHT_POST + 2, y1=0,
                  line=dict(color=AME_GRID, width=2))

    if not df.empty:
        goals = df[df["outcome"] == "Goal"]
        saves = df[df["outcome"] != "Goal"]
        for sub, symbol, name in [(saves, "circle", "Saved"), (goals, "star", "Goal")]:
            if sub.empty:
                continue
            cval = sub[color_by] if color_by in sub.columns else sub["xg"]
            fig.add_trace(go.Scatter(
                x=sub["goalmouth_y"], y=sub["goalmouth_z"],
                mode="markers", name=name,
                marker=dict(
                    symbol=symbol, size=14 if symbol == "star" else 11,
                    color=cval, colorscale="YlOrRd", cmin=0, cmax=1,
                    line=dict(color=AME_DARK_BG, width=1),
                    colorbar=dict(title="xGOT"),
                    showscale=(name == "Saved" or goals.empty),
                ),
                text=sub.get("player_name", ""),
                customdata=np.c_[cval, sub["xg"]],
                hovertemplate=("%{text}<br>xGOT %{customdata[0]:.2f} · "
                               "xG %{customdata[1]:.2f}<extra>" + name + "</extra>"),
            ))

    note = f"  ·  {n_hidden} shot(s) with unrecorded height omitted" if n_hidden else ""
    fig.update_layout(
        title=title + note, template="ame_dark", showlegend=True,
        xaxis=dict(title="Goal width", range=[LEFT_POST - 4, RIGHT_POST + 4],
                   showgrid=False, zeroline=False),
        yaxis=dict(title="Height", range=[-2, CROSSBAR + 6],
                   showgrid=False, zeroline=False, scaleanchor=None),
    )
    return fig


def cross_channel_chart(by_channel: pd.DataFrame,
                        title: str = "Crossing Value by Channel") -> go.Figure:
    """xG-per-cross by origin channel (Left / Central / Right).

    Bars are coloured by threat (yellow→ higher xG/cross); each bar is annotated
    with the cross volume and completion% so low-volume noise is visible.  Takes
    the ``by_channel`` frame from ``processing.wide_play.compute_cross_value`` /
    ``compute_season_cross_value``.  Empty input → empty ``ame_dark`` figure.
    """
    fig = go.Figure()
    if by_channel is None or by_channel.empty:
        fig.update_layout(title=title, template="ame_dark")
        return fig

    order = ["Left", "Central", "Right"]
    d = by_channel.set_index("channel").reindex(order).dropna(how="all").reset_index()
    fig.add_trace(go.Bar(
        x=d["channel"], y=d["xg_per_cross"], marker_color=AME_YELLOW,
        text=[f"{int(c)} crosses · {p:.0f}% cmp" for c, p in zip(d["crosses"], d["completion_pct"])],
        textposition="outside", textfont=dict(size=11, color=AME_WHITE),
        hovertemplate="%{x}<br>xG/cross %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=title, template="ame_dark", showlegend=False,
        xaxis_title="Origin channel (team attacking)",
        yaxis_title="xG generated per cross",
    )
    return fig


def gvm_bar_chart(df: pd.DataFrame, highlight_id: str | None = None,
                  top_n: int = 12, title: str = "Goalkeeper Value Model (GVM)") -> go.Figure:
    """Horizontal GVM leaderboard — top ``top_n`` teams' keepers by composite.

    The team matching ``highlight_id`` is drawn in América yellow, others in
    blue.  Takes the frame from ``processing.gk_value.compute_league_gk_value``
    (needs ``team_name`` + ``gvm``).  The rating is a **squad-relative composite**
    z-scored across this competition's keepers, not an absolute scale — noted on
    the figure.  Empty input → empty ``ame_dark`` figure.
    """
    fig = go.Figure()
    if df is None or df.empty or "gvm" not in df.columns:
        fig.update_layout(title=title, template="ame_dark")
        return fig

    ranked = df.sort_values("gvm", ascending=False).reset_index(drop=True)
    d = ranked.head(top_n)
    # Always surface the highlighted team (e.g. América), even if below the cut.
    if highlight_id is not None and highlight_id in set(ranked["team_id"]) \
            and highlight_id not in set(d["team_id"]):
        d = pd.concat([d, ranked[ranked["team_id"] == highlight_id]], ignore_index=True)
    d = d.sort_values("gvm", ascending=False).iloc[::-1]
    colors = [AME_YELLOW if t == highlight_id else AME_BLUE for t in d["team_id"]]
    fig.add_trace(go.Bar(
        x=d["gvm"], y=d["team_name"], orientation="h",
        marker_color=colors, text=d["gvm"], textposition="outside",
        textfont=dict(size=11, color=AME_WHITE),
        customdata=np.c_[d["shot_stopping"], d["distribution"], d["sweeper"], d["claims"]],
        hovertemplate=("%{y}<br>GVM %{x}<br>stop %{customdata[0]:.2f} · "
                       "dist-xT %{customdata[1]:.3f} · sweep %{customdata[2]:.2f} · "
                       "claims %{customdata[3]:.2f}<extra></extra>"),
    ))
    fig.update_layout(
        title=f"{title}<br><sup>Composite z-scored across this competition's keepers — relative, not absolute</sup>",
        template="ame_dark", showlegend=False,
        xaxis_title="GVM (shot-stopping · distribution · sweeping · claims)",
        yaxis_title="",
    )
    return fig


def mou_scatter_chart(df: pd.DataFrame, highlight_id: str | None = None,
                      title: str = "Manager Over/Under-achievement") -> go.Figure:
    """xPts-vs-actual scatter — every team a point, break-even diagonal at y=x.

    Plots expected points-per-game (x, from xG) against actual PPG (y).  Points
    *above* the y=x line over-achieved their underlying chances (clinical or
    lucky); points *below* under-achieved (created more than the table shows).
    The team matching ``highlight_id`` is drawn in América yellow.

    Expects the columns from ``processing.manager_stats.compute_league_mou``
    (``team_id, team_name, ppg, xppg, mou, matches``).  No Streamlit, no parsing.

    CAVEAT (on the figure): xPts is derived from xG via an independent-Poisson
    model — it measures chance quality, not finishing/keeping skill, which is
    exactly what the over/under-achievement gap captures.  Empty input → an
    empty ``ame_dark`` figure with the title.
    """
    fig = go.Figure()
    if df is None or df.empty or "xppg" not in df.columns or "ppg" not in df.columns:
        fig.update_layout(title=title, template="ame_dark")
        return fig

    lo = float(min(df["xppg"].min(), df["ppg"].min())) - 0.15
    hi = float(max(df["xppg"].max(), df["ppg"].max())) + 0.15
    lo = max(lo, 0.0)

    # Break-even diagonal (deserved == taken).
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines",
        line=dict(color="#666", dash="dash", width=1),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_annotation(x=lo, y=hi, text="Over-achieving ▲", showarrow=False,
                       xanchor="left", yanchor="top",
                       font=dict(size=10, color="#5F7299"))
    fig.add_annotation(x=hi, y=lo, text="Under-achieving ▼", showarrow=False,
                       xanchor="right", yanchor="bottom",
                       font=dict(size=10, color="#5F7299"))

    others = df[df["team_id"] != highlight_id] if highlight_id else df
    home = df[df["team_id"] == highlight_id] if highlight_id else df.iloc[0:0]

    def _hover(d):
        return [f"<b>{r.team_name}</b><br>Actual {r.ppg:.2f} PPG · "
                f"xPts {r.xppg:.2f} PPG<br>MOU {r.mou:+.1f} over {int(r.matches)} matches"
                for r in d.itertuples()]

    fig.add_trace(go.Scatter(
        x=others["xppg"], y=others["ppg"], mode="markers+text",
        text=others.get("team_name", ""), textposition="top center",
        textfont=dict(size=8, color="#8FA3C8"),
        marker=dict(size=11, color=AME_BLUE, opacity=0.75,
                    line=dict(color=AME_DARK_BG, width=1)),
        name="Teams", hovertext=_hover(others), hoverinfo="text",
    ))
    if not home.empty:
        fig.add_trace(go.Scatter(
            x=home["xppg"], y=home["ppg"], mode="markers+text",
            text=home.get("team_name", ""), textposition="top center",
            textfont=dict(size=11, color=AME_YELLOW),
            marker=dict(size=17, color=AME_YELLOW, symbol="star",
                        line=dict(color=AME_DARK_BG, width=1)),
            name="Selected", hovertext=_hover(home), hoverinfo="text",
        ))

    fig.update_layout(
        title=f"{title}<br><sup>xPts from xG (chance quality) vs points actually taken</sup>",
        template="ame_dark", showlegend=False,
        xaxis=dict(title="Expected points per game (xPts)", range=[lo, hi]),
        yaxis=dict(title="Actual points per game", range=[lo, hi]),
    )
    return fig


def discipline_scatter_chart(df: pd.DataFrame, highlight_id: str | None = None,
                             title: str = "Fouling Efficiency") -> go.Figure:
    """Expected vs actual cards per match — the xB break-even diagonal at y=x.

    Each team is a point: x = **expected** cards/match (Σ xB ÷ matches), y =
    **actual** cards/match.  Points *above* the diagonal are booked more than
    their fouls' locations warrant ("over-booked" — reckless / referee-prone);
    *below* the diagonal are "smart foulers" drawing fewer cards than expected.
    Expects ``processing.discipline.compute_league_discipline``'s ``per_team``
    frame (``team_id, team_name, exp_cards_per_match, cards_per_match``).
    """
    fig = go.Figure()
    if (df is None or df.empty or "exp_cards_per_match" not in df.columns
            or "cards_per_match" not in df.columns):
        fig.update_layout(title=title, template="ame_dark")
        return fig

    lo = 0.0
    hi = float(max(df["exp_cards_per_match"].max(), df["cards_per_match"].max())) + 0.3

    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines",
        line=dict(color="#666", dash="dash", width=1),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_annotation(x=lo, y=hi, text="Over-booked ▲", showarrow=False,
                       xanchor="left", yanchor="top",
                       font=dict(size=10, color="#5F7299"))
    fig.add_annotation(x=hi, y=lo, text="Smart foulers ▼", showarrow=False,
                       xanchor="right", yanchor="bottom",
                       font=dict(size=10, color="#5F7299"))

    others = df[df["team_id"] != highlight_id] if highlight_id else df
    home = df[df["team_id"] == highlight_id] if highlight_id else df.iloc[0:0]

    def _hover(d):
        return [f"<b>{r.team_name}</b><br>Actual {r.cards_per_match:.2f} cards/match · "
                f"xB {r.exp_cards_per_match:.2f}<br>{r.fouls_per_card:.1f} fouls/card · "
                f"{int(r.reds)} reds" for r in d.itertuples()]

    fig.add_trace(go.Scatter(
        x=others["exp_cards_per_match"], y=others["cards_per_match"],
        mode="markers", marker=dict(size=11, color=AME_BLUE, opacity=0.75,
                                    line=dict(color=AME_DARK_BG, width=1)),
        name="Teams", hovertext=_hover(others), hoverinfo="text",
    ))
    if not home.empty:
        fig.add_trace(go.Scatter(
            x=home["exp_cards_per_match"], y=home["cards_per_match"],
            mode="markers+text", text=home.get("team_name", ""),
            textposition="top center", textfont=dict(size=11, color=AME_YELLOW),
            marker=dict(size=17, color=AME_YELLOW, symbol="star",
                        line=dict(color=AME_DARK_BG, width=1)),
            name="Selected", hovertext=_hover(home), hoverinfo="text",
        ))

    fig.update_layout(
        title=f"{title}<br><sup>Expected cards (xB from foul locations) vs cards actually shown</sup>",
        template="ame_dark", showlegend=False,
        xaxis=dict(title="Expected cards per match (xB)", range=[lo, hi]),
        yaxis=dict(title="Actual cards per match", range=[lo, hi]),
    )
    return fig


def _merge_team_threats(threats: dict) -> pd.DataFrame:
    """Join one team's offensive + defensive threat frames into per-player rows.

    Shapes the *already-computed* ``compute_player_threats`` output (no parsing):
    outer-merges the ``offensive`` and ``defensive`` DataFrames on ``player`` so
    every player carries both indices.  A player who only registers on one side
    gets 0 on the other (they did nothing threatening there).  Returns columns
    ``player, off, def, off_why, def_why`` (empty frame if the team has none).
    """
    off = threats.get("offensive")
    deff = threats.get("defensive")
    off = off if isinstance(off, pd.DataFrame) else pd.DataFrame()
    deff = deff if isinstance(deff, pd.DataFrame) else pd.DataFrame()

    o = (off[["player", "threat", "_why"]].rename(columns={"threat": "off", "_why": "off_why"})
         if not off.empty else pd.DataFrame(columns=["player", "off", "off_why"]))
    d = (deff[["player", "threat", "_why"]].rename(columns={"threat": "def", "_why": "def_why"})
         if not deff.empty else pd.DataFrame(columns=["player", "def", "def_why"]))
    if o.empty and d.empty:
        return pd.DataFrame(columns=["player", "off", "def", "off_why", "def_why"])

    m = pd.merge(o, d, on="player", how="outer")
    m["off"] = m["off"].fillna(0.0)
    m["def"] = m["def"].fillna(0.0)
    m["off_why"] = m["off_why"].fillna("")
    m["def_why"] = m["def_why"].fillna("")
    return m


def threat_quadrant_chart(home_threats: dict, away_threats: dict,
                          home_team: str, away_team: str,
                          home_n: int = 5, away_n: int = 5,
                          label_top: int = 3) -> go.Figure:
    """Two-way threat quadrant: offensive (x) vs defensive (y) threat per player.

    Each marker is one player; both squads are overlaid (home in América yellow
    circles, away in blue diamonds).  Marker size grows with the player's
    stronger dimension so the dangerous names pop.  Median guide-lines split the
    plane into the read the cards/table can't give at a glance:
      • top-right   → two-way threats (dangerous attacking *and* ball-winning)
      • bottom-right→ pure attackers · top-left → pure ball-winners/destroyers.
    The squad's standout attacker and ball-winner (plus the top ``label_top`` by
    combined threat) are labelled; everyone else is hover-only.

    Inputs are the dicts returned by ``processing.player_threats.compute_player_threats``
    — one per team (``offensive``/``defensive`` DataFrames with a 0–100 ``threat``
    column).  No Streamlit, no event parsing; only the supplied frames are reshaped.

    CAVEAT (rendered on the figure): the index is **squad-relative** — 0–100 vs.
    *teammates* over the last N matches, NOT an absolute league rating — so a
    home '90' and an away '90' are each "top of their own squad", not equals.
    Empty/insufficient input → an empty ``ame_dark`` figure with the title.
    """
    fig = go.Figure()
    title = "Two-Way Threat Quadrant"
    caveat = ("Squad-relative index (0–100 vs. teammates over last 5), "
              "not an absolute league rating")

    teams = [
        (home_threats, home_team, home_n, AME_YELLOW, "circle"),
        (away_threats, away_team, away_n, "#42A5F5", "diamond"),
    ]
    merged = [(_merge_team_threats(t or {}), name, n, color, sym)
              for t, name, n, color, sym in teams]

    if all(m.empty for m, *_ in merged):
        fig.update_layout(template="ame_dark",
                          title=f"{title}<br><sup>No qualifying players in the selected window</sup>")
        return fig

    # Median guide-lines from the combined plotted population — only meaningful
    # with enough points; with a tiny sample we skip them rather than draw noise.
    allpts = pd.concat([m for m, *_ in merged if not m.empty], ignore_index=True)
    if len(allpts) >= 4:
        xmed, ymed = float(allpts["off"].median()), float(allpts["def"].median())
        fig.add_vline(x=xmed, line=dict(color=AME_GRID, width=1, dash="dash"))
        fig.add_hline(y=ymed, line=dict(color=AME_GRID, width=1, dash="dash"))
        for x, y, txt, xa, ya in [
            (100, 100, "Two-way threat", "right", "top"),
            (100, 0, "Pure attacker", "right", "bottom"),
            (0, 100, "Ball-winner", "left", "top"),
        ]:
            fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                               xanchor=xa, yanchor=ya,
                               font=dict(size=10, color="#5F7299"))

    for m, name, n, color, sym in merged:
        if m.empty:
            continue
        m = m.copy()
        m["_peak"] = m[["off", "def"]].max(axis=1)
        # Danger-men to label: top-N by combined threat + the off & def leaders.
        labelled = set(m.sort_values("_peak", ascending=False).head(label_top)["player"])
        labelled.add(m.loc[m["off"].idxmax(), "player"])
        labelled.add(m.loc[m["def"].idxmax(), "player"])

        m["_label"] = [p if p in labelled else "" for p in m["player"]]
        m["_size"] = 9 + (m["_peak"] / 100.0) * 13          # 9 → 22 px
        # Build hover per row by zipping columns — 'def' is a Python keyword and
        # can't be reached via itertuples attribute/index access.
        m["_hover"] = [
            f"<b>{pl}</b> · {name}<br>"
            f"Offensive {o:g}  ({ow or '—'})<br>"
            f"Defensive {d:g}  ({dw or '—'})"
            for pl, o, ow, d, dw in zip(
                m["player"], m["off"], m["off_why"], m["def"], m["def_why"])
        ]
        few = f"  ·  only {len(m)} qualifying" if len(m) < 3 else ""
        fig.add_trace(go.Scatter(
            x=m["off"], y=m["def"], mode="markers+text",
            text=m["_label"], textposition="top center",
            textfont=dict(size=10, color=color),
            marker=dict(size=m["_size"], color=color, symbol=sym, opacity=0.82,
                        line=dict(color=AME_DARK_BG, width=1)),
            name=f"{name} (last {n}){few}",
            hovertext=m["_hover"], hoverinfo="text",
        ))

    fig.update_layout(
        title=f"{title}<br><sup>{caveat}</sup>",
        template="ame_dark",
        xaxis=dict(title="Offensive threat  →  more dangerous to goal",
                   range=[-5, 108], zeroline=False),
        yaxis=dict(title="Defensive threat  →  more ball-winning",
                   range=[-5, 108], zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def style_quadrant_chart(df: pd.DataFrame, highlight_id: str | None = None,
                         x_col: str = "avg_direct_speed",
                         y_col: str = "avg_passes_per_seq",
                         title: str = "Playing-Style Quadrant") -> go.Figure:
    """Team playing-style quadrant: direct speed (x) vs passes per sequence (y).

    Each team is a point; the team whose id matches ``highlight_id`` is drawn in
    América yellow.  Quadrant guide-lines at the league medians split the plane
    into patient-possession / controlled-build-up / direct / long-ball styles.
    Built on ``processing.sequences.compute_season_sequences``.
    """
    fig = go.Figure()
    if df is None or df.empty or x_col not in df.columns or y_col not in df.columns:
        fig.update_layout(title=title, template="ame_dark")
        return fig

    xmed, ymed = df[x_col].median(), df[y_col].median()
    others = df[df["team_id"] != highlight_id] if highlight_id else df
    home = df[df["team_id"] == highlight_id] if highlight_id else df.iloc[0:0]

    fig.add_vline(x=xmed, line=dict(color=AME_GRID, width=1, dash="dash"))
    fig.add_hline(y=ymed, line=dict(color=AME_GRID, width=1, dash="dash"))

    fig.add_trace(go.Scatter(
        x=others[x_col], y=others[y_col], mode="markers+text",
        text=others.get("team_name", ""), textposition="top center",
        textfont=dict(size=9, color="#8FA3C8"),
        marker=dict(size=10, color=AME_BLUE, opacity=0.75,
                    line=dict(color=AME_DARK_BG, width=1)),
        name="Teams",
        hovertemplate="%{text}<br>direct speed %{x:.2f} m/s · %{y:.1f} passes/seq<extra></extra>",
    ))
    if not home.empty:
        fig.add_trace(go.Scatter(
            x=home[x_col], y=home[y_col], mode="markers+text",
            text=home.get("team_name", ""), textposition="top center",
            textfont=dict(size=11, color=AME_YELLOW),
            marker=dict(size=16, color=AME_YELLOW, symbol="star",
                        line=dict(color=AME_DARK_BG, width=1)),
            name="Selected",
            hovertemplate="%{text}<br>direct speed %{x:.2f} m/s · %{y:.1f} passes/seq<extra></extra>",
        ))

    fig.update_layout(
        title=title, template="ame_dark", showlegend=False,
        xaxis_title="Direct speed (m/s toward goal)  →  more direct",
        yaxis_title="Passes per sequence  →  more patient",
    )
    return fig
