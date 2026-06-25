from __future__ import annotations
"""Phase & transition visualizations — donut, side-by-side bars, KPI cards."""

import pandas as pd
import plotly.graph_objects as go
from processing.game_phases import PHASES, PHASE_LABELS, PHASE_COLORS
from config import AME_DARK_BG, AME_WHITE, AME_YELLOW, AME_BLUE


# Group phases for charts (display grouping ≠ classification)
SETTLED_IN_POSS  = ["BUILD_UP", "PROGRESSION", "FINAL_THIRD"]
SETTLED_OUT_POSS = ["HIGH_PRESS", "MID_BLOCK", "LOW_BLOCK"]
TRANSITIONS_GROUP = ["DEF_TRANSITION_5S", "DEF_TRANSITION_7S", "OFF_TRANSITION_10S"]


def phase_donut(distribution: dict[str, dict], title: str = "") -> go.Figure:
    """Donut chart of phase share for a single team.

    `distribution` is the {phase: {events, share_pct}} dict from
    `phase_distribution()`.

    Each slice is dark enough to carry white text (contrast ≥ 4.5:1).
    Hover shows both the label and the % share for clarity.
    """
    labels, values, colors, events = [], [], [], []
    for p in PHASES:
        share = distribution.get(p, {}).get("share_pct", 0)
        n_ev  = distribution.get(p, {}).get("events", 0)
        if share <= 0:
            continue
        labels.append(PHASE_LABELS[p])
        values.append(share)
        colors.append(PHASE_COLORS[p])
        events.append(n_ev)

    # Total event count for centre annotation
    total_events = sum(events)

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.60,
        marker=dict(
            colors=colors,
            line=dict(color="#0E1117", width=2),   # dark gap between slices
        ),
        textposition="inside",
        textinfo="percent+label",                   # show label AND % inside each slice
        insidetextorientation="horizontal",
        textfont=dict(color="white", size=10, family="Arial Black, sans-serif"),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "%{percent} of match events<br>"
            "<extra></extra>"
        ),
        customdata=events,
        sort=False,
        pull=[0.04 if v == max(values) else 0 for v in values],  # pop the biggest slice
    )])

    # Centre annotation: total events logged
    fig.add_annotation(
        text=f"<b>{total_events}</b><br><span style='font-size:9px'>events</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color=AME_WHITE),
        align="center",
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(size=13, color=AME_WHITE)),
        height=400,
        margin=dict(l=10, r=10, t=44, b=10),
        legend=dict(
            orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01,
            font=dict(color=AME_WHITE, size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor=AME_DARK_BG,
        plot_bgcolor=AME_DARK_BG,
        showlegend=True,
    )
    return fig


# Tactical families: (display label, member phases, accent colour for the band)
PHASE_FAMILIES = [
    ("In possession",     SETTLED_IN_POSS,   "#2E7D32"),   # green band
    ("Out of possession", SETTLED_OUT_POSS,  "#C62828"),   # red band
    ("Transition",        TRANSITIONS_GROUP, "#F57C00"),   # amber band
]


def _family_share(dist: dict, members: list[str]) -> float:
    """Sum the share_pct of every phase in a tactical family."""
    return round(sum(dist.get(p, {}).get("share_pct", 0) for p in members), 1)


def phase_family_bars(home_dist: dict, away_dist: dict,
                      home_name: str, away_name: str) -> go.Figure:
    """Grouped bars rolling the 9 phases into 3 tactical families.

    Answers the headline question a 9-slice donut buries: *what is each
    team's tactical balance* — settled in possession, settled out of
    possession, or in transition?  Both teams sit side-by-side per family
    so the comparison is a single horizontal scan.
    """
    families = [f[0] for f in PHASE_FAMILIES]
    home_vals = [_family_share(home_dist, m) for _, m, _ in PHASE_FAMILIES]
    away_vals = [_family_share(away_dist, m) for _, m, _ in PHASE_FAMILIES]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=families, y=home_vals, name=home_name, marker_color=AME_YELLOW,
        text=[f"{v:.0f}%" for v in home_vals], textposition="outside",
        textfont=dict(color=AME_WHITE, size=12),
        hovertemplate=f"<b>{home_name}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=families, y=away_vals, name=away_name, marker_color=AME_BLUE,
        text=[f"{v:.0f}%" for v in away_vals], textposition="outside",
        textfont=dict(color=AME_WHITE, size=12),
        hovertemplate=f"<b>{away_name}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
    ))

    # Faint coloured band behind each family group to encode the tactical dimension
    for i, (_, _, band) in enumerate(PHASE_FAMILIES):
        fig.add_vrect(x0=i - 0.5, x1=i + 0.5, line_width=0,
                      fillcolor=band, opacity=0.10, layer="below")

    top = max(home_vals + away_vals + [10])
    fig.update_layout(
        barmode="group", bargap=0.35, bargroupgap=0.08,
        height=400, margin=dict(l=10, r=10, t=40, b=30),
        yaxis=dict(title="Share of match events (%)", range=[0, top * 1.18],
                   gridcolor="#333", zeroline=False),
        xaxis=dict(tickfont=dict(size=13, color=AME_WHITE)),
        paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        font=dict(color=AME_WHITE),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="center", x=0.5),
    )
    return fig


def phase_compare_bars(home_dist: dict, away_dist: dict,
                       home_name: str, away_name: str) -> go.Figure:
    """Diverging horizontal bars — same-phase share for both teams.

    Each phase row has two bars: home (left, red) and away (right, gold).
    Lets you read both teams' tactical balance at a glance.
    """
    rows = []
    for p in PHASES:
        rows.append({
            "phase": PHASE_LABELS[p],
            "home_pct": home_dist.get(p, {}).get("share_pct", 0),
            "away_pct": away_dist.get(p, {}).get("share_pct", 0),
        })
    df = pd.DataFrame(rows)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["phase"], x=-df["home_pct"], name=home_name,
        orientation="h", marker_color=AME_YELLOW,
        hovertemplate=f"<b>{home_name}</b><br>%{{y}}: %{{customdata:.1f}}%<extra></extra>",
        customdata=df["home_pct"],
        text=df["home_pct"].apply(lambda v: f"{v:.1f}%" if v > 0 else ""),
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=df["phase"], x=df["away_pct"], name=away_name,
        orientation="h", marker_color=AME_BLUE,
        hovertemplate=f"<b>{away_name}</b><br>%{{y}}: %{{x:.1f}}%<extra></extra>",
        text=df["away_pct"].apply(lambda v: f"{v:.1f}%" if v > 0 else ""),
        textposition="inside",
    ))

    max_v = max(df["home_pct"].max(), df["away_pct"].max(), 5)
    fig.update_layout(
        barmode="overlay",
        height=420,
        margin=dict(l=10, r=10, t=30, b=30),
        xaxis=dict(title="Share of events (%)",
                   range=[-max_v * 1.1, max_v * 1.1],
                   tickvals=[-max_v, -max_v / 2, 0, max_v / 2, max_v],
                   ticktext=[f"{max_v:.0f}%", f"{max_v/2:.0f}%", "0%",
                             f"{max_v/2:.0f}%", f"{max_v:.0f}%"],
                   gridcolor="#333"),
        yaxis=dict(autorange="reversed", gridcolor="#333"),
        paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        font=dict(color=AME_WHITE),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    fig.add_vline(x=0, line_color="#666", line_width=1)
    return fig


def transition_matrix(chain_with_phases: pd.DataFrame, team_id: str,
                      title: str = "") -> go.Figure:
    """Phase-to-phase transition matrix heatmap (Hudl/StatsBomb style).

    A 9×9 grid where rows are the *starting* phase and columns are the
    *next* phase the team enters.  Cell values are the % of the row's
    transitions that go to that destination — i.e. each row sums to 100%.
    This is far clearer than a Sankey when there are 9 phases and many
    cross-flows.

    Reading guide:
        Look across one row to see "when in phase X, where do we go next?"
        The diagonal is excluded (same-phase events aren't transitions).
    """
    own = chain_with_phases[chain_with_phases["team_id"] == team_id].copy()
    if own.empty or len(own) < 2:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
            annotations=[dict(text="No data for phase transitions",
                              showarrow=False, font=dict(color=AME_WHITE))]
        )
        return fig

    own = own.sort_values("t").reset_index(drop=True)
    own["next_phase"] = own["phase"].shift(-1)
    flows = own.dropna(subset=["next_phase"])
    flows = flows[flows["phase"] != flows["next_phase"]]

    # Find phases actually present (keep canonical order)
    phases_used = [p for p in PHASES
                   if p in set(flows["phase"]).union(flows["next_phase"])]
    if len(phases_used) < 2:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG)
        return fig

    # Build raw count matrix, then normalise rows to %
    n = len(phases_used)
    idx = {p: i for i, p in enumerate(phases_used)}
    raw = [[0] * n for _ in range(n)]
    for _, r in flows.iterrows():
        raw[idx[r["phase"]]][idx[r["next_phase"]]] += 1

    # Row-normalise (% of transitions OUT of each phase)
    pct = [[0.0] * n for _ in range(n)]
    for i in range(n):
        row_sum = sum(raw[i])
        if row_sum > 0:
            pct[i] = [round(c / row_sum * 100, 1) for c in raw[i]]

    short = {
        "BUILD_UP": "Build", "PROGRESSION": "Prog", "FINAL_THIRD": "Final⅓",
        "HIGH_PRESS": "Hi-Pr", "MID_BLOCK": "Mid-B", "LOW_BLOCK": "Lo-B",
        "DEF_TRANSITION_5S": "CP-5s", "DEF_TRANSITION_7S": "CP-7s",
        "OFF_TRANSITION_10S": "CA-10s",
    }
    x_labels = [short[p] for p in phases_used]
    y_labels = [PHASE_LABELS[p] for p in phases_used]

    # Cell text: show % only where ≥ 5% so the chart is readable
    text = [[f"{v:.0f}%" if v >= 5 else "" for v in row] for row in pct]

    fig = go.Figure(data=go.Heatmap(
        z=pct, x=x_labels, y=y_labels, text=text, texttemplate="%{text}",
        textfont=dict(color="white", size=11),
        colorscale=[[0, "#0E1117"], [0.25, "#3E1B1B"], [0.5, "#7A2A2A"],
                    [0.75, "#C62828"], [1, "#FF5252"]],
        zmin=0, zmax=60,   # cap so a 100% diag-skip cell doesn't wash everything else out
        colorbar=dict(title=dict(text="% of exits", font=dict(color=AME_WHITE, size=10)),
                      tickfont=dict(color=AME_WHITE, size=9), thickness=10, len=0.7),
        hovertemplate="<b>From</b> %{y}<br><b>To</b> %{x}<br>%{z:.1f}% of exits<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(size=13, color=AME_WHITE)),
        height=460,
        margin=dict(l=10, r=10, t=50, b=40),
        paper_bgcolor=AME_DARK_BG, plot_bgcolor=AME_DARK_BG,
        font=dict(color=AME_WHITE, size=11),
        xaxis=dict(title="Next phase", side="bottom", tickfont=dict(size=10)),
        yaxis=dict(title="From phase", autorange="reversed", tickfont=dict(size=10)),
    )
    return fig


# ── Backward compat alias (same name, new chart) ────────────────────────────
transition_flow_sankey = transition_matrix


def transition_kpi_html(metrics: dict, ppda: float | None = None) -> str:
    """Render transition metrics + PPDA as a styled HTML block.

    Used inside `st.markdown(unsafe_allow_html=True)` to keep the layout
    tight on a Streamlit page (st.metric cards force their own grid).
    """
    cp5  = metrics.get("counter_press_5s_pct", 0)
    cp7  = metrics.get("counter_press_7s_pct", 0)
    rec  = metrics.get("avg_recovery_time_s")
    rec_text = f"{rec:.1f} s" if rec is not None else "—"
    ca_sh = metrics.get("counter_attack_shots", 0)
    ca_ft = metrics.get("counter_attack_final_third_pct", 0)
    ppda_text = f"{ppda}" if ppda is not None else "—"

    return f"""
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:6px 0;">
      <div style="background:#1A1A2E;border-left:3px solid {AME_YELLOW};padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">PPDA (Hudl 60%)</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{ppda_text}</div>
        <div style="font-size:10px;color:#aaa;">Lower = more press</div>
      </div>
      <div style="background:#1A1A2E;border-left:3px solid #F57C00;padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">Counter-press (5s)</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{cp5}%</div>
        <div style="font-size:10px;color:#aaa;">Re-won within 5 s</div>
      </div>
      <div style="background:#1A1A2E;border-left:3px solid #FFB74D;padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">Counter-press (7s)</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{cp7}%</div>
        <div style="font-size:10px;color:#aaa;">Hudl standard window</div>
      </div>
      <div style="background:#1A1A2E;border-left:3px solid #66BB6A;padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">Avg Recovery Time</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{rec_text}</div>
        <div style="font-size:10px;color:#aaa;">After losing the ball</div>
      </div>
      <div style="background:#1A1A2E;border-left:3px solid {AME_BLUE};padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">Counter-attack Shots</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{ca_sh}</div>
        <div style="font-size:10px;color:#aaa;">Within 10 s of winning ball</div>
      </div>
      <div style="background:#1A1A2E;border-left:3px solid #FFC107;padding:10px;border-radius:4px;">
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;">Reach Final Third</div>
        <div style="font-size:22px;font-weight:700;color:#FFF;">{ca_ft}%</div>
        <div style="font-size:10px;color:#aaa;">Within 10 s after winning</div>
      </div>
    </div>
    """
