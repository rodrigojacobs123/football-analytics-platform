from __future__ import annotations
"""Pizza / percentile-pie charts — scouted.football & FBref scouting standard.

A pizza chart is a polar bar chart where each slice represents one attribute
percentile (0-100) within a peer group, color-coded by category (attacking /
possession / defending). It's the canonical scouting visualization.
"""

import plotly.graph_objects as go
from config import AME_DARK_BG, AME_WHITE, AME_YELLOW, AME_BLUE


CATEGORY_COLORS = {
    "Attack":   "#E15554",   # red
    "Possess":  "#FFB400",   # gold
    "Defend":   "#3BB273",   # green
}


def pizza_chart(
    player_name: str,
    metrics: list[dict],
    title_suffix: str = "",
) -> go.Figure:
    """Render a pizza-percentile chart.

    `metrics` is a list of dicts:
        [{"label": "Goals/90", "value": 0.85, "category": "Attack"}, ...]
    where ``value`` is a 0–1 percentile (or 0–100 — auto-detected).

    Slices are arranged in the order given. Use the same order as a
    grouping over Attack → Possession → Defending for the cleanest read.
    """
    if not metrics:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=AME_DARK_BG)
        return fig

    # Normalise values to 0–100
    raw_vals = [m["value"] for m in metrics]
    vmax = max(raw_vals) if raw_vals else 1
    if vmax <= 1.0:
        values = [v * 100 for v in raw_vals]
    else:
        values = list(raw_vals)

    labels = [m["label"] for m in metrics]
    cats   = [m.get("category", "Possess") for m in metrics]
    colors = [CATEGORY_COLORS.get(c, AME_BLUE) for c in cats]

    n = len(metrics)
    width = 360 / n   # equal-angle slices
    theta = [width * i + width / 2 for i in range(n)]   # slice centers

    fig = go.Figure()

    # Real coloured value slices (drawn FIRST so they sit at the back of the
    # rendering stack beneath the labels)
    fig.add_trace(go.Barpolar(
        r=values, theta=theta, width=[width * 0.95] * n,
        marker=dict(
            color=colors,
            line=dict(color=AME_DARK_BG, width=2),
        ),
        opacity=0.92,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                      "Pctile: %{r:.0f}<extra></extra>",
        customdata=list(zip(labels, cats)),
        showlegend=False,
    ))
    # Faint outer ring (the 100% reference) — drawn as a single-line polar trace
    fig.add_trace(go.Scatterpolar(
        r=[100] * (n + 1),
        theta=theta + [theta[0]],
        mode="lines",
        line=dict(color="rgba(255,255,255,0.25)", width=1),
        hoverinfo="skip", showlegend=False,
    ))
    # Percentile number labels just inside the slice tip
    fig.add_trace(go.Scatterpolar(
        r=[max(v - 12, 8) for v in values],
        theta=theta, mode="text",
        text=[f"{v:.0f}" for v in values],
        textfont=dict(color="white", size=12, family="Arial Black"),
        hoverinfo="skip", showlegend=False,
    ))

    fig.update_layout(
        title=dict(text=f"{player_name}<br><sub style='color:#aaa;font-size:11px;'>"
                        f"{title_suffix}</sub>",
                   x=0.5, xanchor="center", font=dict(color=AME_WHITE, size=15)),
        polar=dict(
            bgcolor=AME_DARK_BG,
            radialaxis=dict(range=[0, 100], showticklabels=False, ticks="",
                            gridcolor="rgba(255,255,255,0.1)"),
            angularaxis=dict(
                tickmode="array", tickvals=theta, ticktext=labels,
                rotation=90, direction="clockwise",
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(color=AME_WHITE, size=10),
            ),
        ),
        paper_bgcolor=AME_DARK_BG,
        height=520,
        margin=dict(l=20, r=20, t=80, b=20),
        showlegend=False,
    )

    # Category color legend at the bottom (so it never collides with axis labels)
    for i, (cat, col) in enumerate(CATEGORY_COLORS.items()):
        fig.add_annotation(
            x=0.18 + i * 0.32, y=-0.05, xref="paper", yref="paper",
            text=f"<span style='color:{col};font-size:14px;'>■</span> "
                 f"<span style='color:white;'>{cat}</span>",
            showarrow=False, font=dict(size=11),
        )
    return fig
