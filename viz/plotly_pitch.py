from __future__ import annotations
"""Interactive Plotly pitch — draw a football pitch using Plotly shapes.

Unlike mplsoccer (which is static Matplotlib), this produces fully interactive
Plotly figures: hover, click-select, zoom, and animated traces all work.
Coordinate system: Opta 0–100 (x = pitch length, y = pitch width).
"""

import plotly.graph_objects as go
from config import AME_YELLOW, AME_BLUE, AME_DARK_BG

# ── Opta pitch constants (0–100 scale) ───────────────────────────────────────
_PITCH_BG   = "#0D1117"
_LINE_COLOR = "#2A2A38"

# Key zone boundaries in Opta coords (x=0→100 left→right, y=0→100 bottom→top)
ZONES = {
    "six_yard_left":    {"x0": 0,    "x1": 5.8,  "y0": 36.8, "y1": 63.2},
    "penalty_left":     {"x0": 0,    "x1": 17.0, "y0": 21.1, "y1": 78.9},
    "six_yard_right":   {"x0": 94.2, "x1": 100,  "y0": 36.8, "y1": 63.2},
    "penalty_right":    {"x0": 83.0, "x1": 100,  "y0": 21.1, "y1": 78.9},
    "half_space_left":  {"x0": 66.0, "x1": 83.0, "y0": 21.1, "y1": 40.0},
    "half_space_right": {"x0": 66.0, "x1": 83.0, "y0": 60.0, "y1": 78.9},
    "central_attack":   {"x0": 66.0, "x1": 83.0, "y0": 40.0, "y1": 60.0},
}

# ── Side labels ───────────────────────────────────────────────────────────────
def side_of_field(y: float) -> str:
    """Return 'Left', 'Centre', or 'Right' for an Opta y-coordinate."""
    if y < 33.3:
        return "Left"
    if y > 66.6:
        return "Right"
    return "Centre"


# ── Core pitch builder ────────────────────────────────────────────────────────

def make_pitch_figure(
    title: str = "",
    height: int = 520,
    bg_color: str = _PITCH_BG,
    line_color: str = _LINE_COLOR,
    show_zones: bool = False,
    attacking_right: bool = True,
) -> go.Figure:
    """Create a blank Plotly pitch figure in Opta 0–100 coordinates.

    Parameters
    ----------
    attacking_right : if True, team attacks right→left so right goal = attacking end.
    show_zones      : overlay named danger-zone rectangles.
    """
    shapes: list[dict] = [
        # Pitch boundary
        _rect(0, 100, 0, 100, line_color, bg_color, width=2.5),
        # Halfway line
        _line(50, 50, 0, 100, line_color),
        # Left penalty area
        _rect(0, 17, 21.1, 78.9, line_color, bg_color),
        # Right penalty area
        _rect(83, 100, 21.1, 78.9, line_color, bg_color),
        # Left 6-yard box
        _rect(0, 5.8, 36.8, 63.2, line_color, bg_color),
        # Right 6-yard box
        _rect(94.2, 100, 36.8, 63.2, line_color, bg_color),
        # Left goal
        _rect(-2, 0, 45.2, 54.8, line_color, "rgba(0,0,0,0)"),
        # Right goal
        _rect(100, 102, 45.2, 54.8, line_color, "rgba(0,0,0,0)"),
        # Centre circle
        _circle(50, 50, 9.15, line_color, bg_color),
        # Penalty spots
        _dot(11, 50, line_color),
        _dot(89, 50, line_color),
        # Centre spot
        _dot(50, 50, line_color),
        # Left penalty arc (approximate semi-circle)
        _arc(17, 50, 9.15, 270, 90, line_color),
        # Right penalty arc
        _arc(83, 50, 9.15, 90, 270, line_color),
        # Corner arcs
        _corner_arc(0, 0, line_color),
        _corner_arc(0, 100, line_color, flip_y=True),
        _corner_arc(100, 0, line_color, flip_x=True),
        _corner_arc(100, 100, line_color, flip_x=True, flip_y=True),
    ]

    if show_zones:
        zone_colors = {
            "six_yard_left":    "rgba(218,41,28,0.15)",
            "six_yard_right":   "rgba(218,41,28,0.15)",
            "penalty_left":     "rgba(218,41,28,0.08)",
            "penalty_right":    "rgba(218,41,28,0.08)",
            "half_space_left":  "rgba(255,205,0,0.07)",
            "half_space_right": "rgba(255,205,0,0.07)",
            "central_attack":   "rgba(66,165,245,0.07)",
        }
        for zname, z in ZONES.items():
            shapes.append(_rect(
                z["x0"], z["x1"], z["y0"], z["y1"],
                "rgba(0,0,0,0)", zone_colors.get(zname, "rgba(255,255,255,0.04)"),
            ))

    # Register the dark template if available; otherwise use explicit colours.
    import plotly.io as _pio
    _tpl = "ame_dark" if "ame_dark" in _pio.templates else None

    fig = go.Figure()
    layout_kwargs = dict(
        title=dict(text=title, font=dict(size=16, color="#FAFAFA"), x=0),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color="#FAFAFA", family="'JetBrains Mono', monospace"),
        height=height,
        shapes=shapes,
        xaxis=dict(range=[-3, 103], showgrid=False, zeroline=False,
                   visible=False, fixedrange=True),
        yaxis=dict(range=[-3, 103], showgrid=False, zeroline=False,
                   visible=False, fixedrange=True, scaleanchor="x", scaleratio=0.68),
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="closest",
        dragmode=False,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#FAFAFA")),
    )
    if _tpl:
        layout_kwargs["template"] = _tpl
    fig.update_layout(**layout_kwargs)
    return fig


# ── Trace helpers ─────────────────────────────────────────────────────────────

def add_scatter(
    fig: go.Figure,
    x, y,
    color: str = AME_YELLOW,
    size: int = 10,
    label: str = "",
    text: list[str] | None = None,
    symbol: str = "circle",
    opacity: float = 0.85,
    row: int | None = None,
    col: int | None = None,
) -> go.Figure:
    """Add a scatter trace (events, player positions, etc.)."""
    kwargs = dict(
        x=x, y=y,
        mode="markers",
        marker=dict(color=color, size=size, symbol=symbol,
                    line=dict(color="#000", width=0.5), opacity=opacity),
        name=label,
        text=text,
        hovertemplate="%{text}<extra></extra>" if text else "%{x:.0f}, %{y:.0f}<extra></extra>",
    )
    if row and col:
        fig.add_trace(go.Scatter(**kwargs), row=row, col=col)
    else:
        fig.add_trace(go.Scatter(**kwargs))
    return fig


def add_arrows(
    fig: go.Figure,
    sequences: list[list[tuple[float, float]]],
    color: str = "#42A5F5",
    opacity: float = 0.6,
) -> go.Figure:
    """Draw event-sequence arrows on the pitch.

    sequences: list of [(x0,y0),(x1,y1),...] point lists — one per event chain.
    """
    for seq in sequences:
        if len(seq) < 2:
            continue
        for i in range(len(seq) - 1):
            x0, y0 = seq[i]
            x1, y1 = seq[i + 1]
            # Thin connecting line
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=1.5),
                opacity=opacity,
                showlegend=False,
                hoverinfo="skip",
            ))
            # Arrow head annotation
            fig.add_annotation(
                x=x1, y=y1, ax=x0, ay=y0,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.2,
                arrowwidth=1.5, arrowcolor=color, opacity=opacity,
            )
    return fig


def add_heatmap_overlay(
    fig: go.Figure,
    x, y,
    colorscale: list | None = None,
    name: str = "Density",
) -> go.Figure:
    """Add a 2-D density heatmap overlay on the pitch."""
    if colorscale is None:
        colorscale = [
            [0.0, "rgba(0,0,0,0)"],
            [0.3, "rgba(218,41,28,0.3)"],
            [0.7, "rgba(218,41,28,0.6)"],
            [1.0, "rgba(255,205,0,0.9)"],
        ]
    fig.add_trace(go.Histogram2dContour(
        x=x, y=y,
        colorscale=colorscale,
        showscale=False,
        ncontours=12,
        contours=dict(coloring="fill"),
        name=name,
        hoverinfo="skip",
        line=dict(width=0),
    ))
    return fig


def add_network_edges(
    fig: go.Figure,
    edges: list[tuple],  # [(x0,y0,x1,y1,weight,label), ...]
    max_weight: float = 1.0,
    color: str = "#42A5F5",
) -> go.Figure:
    """Draw player-interaction network edges on the pitch."""
    for x0, y0, x1, y1, weight, label in edges:
        width = max(1.0, (weight / max(max_weight, 1)) * 5)
        alpha = max(0.2, (weight / max(max_weight, 1)) * 0.8)
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=width),
            opacity=alpha,
            showlegend=False,
            hoverinfo="text",
            hovertext=label,
        ))
    return fig


# ── Shape factory helpers (internal) ─────────────────────────────────────────

def _rect(x0, x1, y0, y1, line_color, fill_color, width=1.5):
    return dict(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                line=dict(color=line_color, width=width),
                fillcolor=fill_color, layer="below")


def _line(x0, x1, y0, y1, color, width=1.5):
    return dict(type="line", x0=x0, x1=x1, y0=y0, y1=y1,
                line=dict(color=color, width=width), layer="below")


def _circle(cx, cy, r, line_color, fill_color):
    # Approximate circle with ellipse (accounting for 0.68 aspect ratio)
    ry = r / 0.68
    return dict(type="circle",
                x0=cx - r, x1=cx + r, y0=cy - ry, y1=cy + ry,
                line=dict(color=line_color, width=1.5),
                fillcolor=fill_color, layer="below")


def _dot(cx, cy, color, r=0.6):
    return dict(type="circle",
                x0=cx - r, x1=cx + r, y0=cy - r / 0.68, y1=cy + r / 0.68,
                fillcolor=color, line=dict(color=color, width=0), layer="below")


def _arc(cx, cy, r, t0_deg, t1_deg, color):
    """Very rough arc via SVG path."""
    import math
    steps = 20
    dt = (t1_deg - t0_deg) % 360
    pts = []
    for i in range(steps + 1):
        t = math.radians(t0_deg + dt * i / steps)
        pts.append((cx + r * math.cos(t), cy + r / 0.68 * math.sin(t)))
    path = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
    return dict(type="path", path=path,
                line=dict(color=color, width=1.5), layer="below")


def _corner_arc(cx, cy, color, r=2.5, flip_x=False, flip_y=False):
    """Quarter-circle at a corner."""
    import math
    steps = 12
    # Determine quadrant
    x_dir = -1 if flip_x else 1
    y_dir = -1 if flip_y else 1
    pts = []
    for i in range(steps + 1):
        t = math.radians(i / steps * 90)
        x = cx + x_dir * r * math.cos(t)
        y = cy + y_dir * r / 0.68 * math.sin(t)
        pts.append((x, y))
    path = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
    return dict(type="path", path=path,
                line=dict(color=color, width=1.5), layer="below")
