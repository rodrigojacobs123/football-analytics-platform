from __future__ import annotations
"""Corner Defense Intelligence — interactive analysis of how opponent corners
are defended across the full season.

Three embedded models:
  1. First Contact Control Index
  2. Delivery Hotspot Suppression
  3. Second Ball Control

Plus:
  • Side-of-field danger breakdown
  • Player touch network after corners (interactive Plotly graph)
  • Per-sequence drill-down explorer
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.sidebar import render_sidebar
from components.team_selector import team_selector
from data.loader import load_standings, list_standings_stages, build_player_name_map
from data.paths import partidos_dir
from processing.team_stats import get_team_folder_map
from processing.corner_defense import (
    load_season_corner_defense, ZONE_DANGER_WEIGHTS, EVENT_TYPE_LABELS,
)
from viz.plotly_pitch import (
    make_pitch_figure, add_scatter, add_arrows,
    add_heatmap_overlay, add_network_edges, side_of_field,
)
from viz.kpi_cards import page_header, section_header, kpi_row
from viz.theme import apply_theme
from config import AME_TEAM_NAME, AME_YELLOW, AME_BLUE, AME_DARK_BG

apply_theme()

league, season = render_sidebar()
page_header("Corner Intelligence", subtitle=f"{season}")

# ── Tournament selector ───────────────────────────────────────────────────────
_stage_names = list_standings_stages(league, season)
_stage_filter = ""
if len(_stage_names) > 1:
    _stage_filter = st.radio(
        "Tournament", options=_stage_names,
        index=len(_stage_names) - 1, horizontal=True, key="corner_stage",
    )

# ── Team selector + mode toggle ───────────────────────────────────────────────
col_team, col_mode = st.columns([3, 1])
with col_team:
    selected = team_selector(league, season, key="corner_team_sel",
                             multi=False, label="Team")
    team_name = selected[0] if selected else AME_TEAM_NAME
with col_mode:
    corner_mode = st.radio(
        "Corner mode",
        options=["🛡️ Defending", "⚔️ Attacking"],
        index=0, key="corner_mode",
    )
is_attack = corner_mode.startswith("⚔️")
mode_str  = "attack" if is_attack else "defend"

standings = load_standings(league, season, stage_name=_stage_filter)
team_row = standings[standings["team_name"] == team_name]
team_id = team_row.iloc[0]["team_id"] if not team_row.empty else ""

if not team_id:
    st.warning(f"Could not resolve team ID for {team_name}.")
    st.stop()

pdir = partidos_dir(league, season)
if not pdir.exists():
    st.error("No match files found for this competition/season.")
    st.stop()

# ── Load corner data ──────────────────────────────────────────────────────────
spinner_msg = ("Scanning attacking corners…" if is_attack
               else "Scanning all corners across the season…")
with st.spinner(spinner_msg):
    data = load_season_corner_defense(
        league, season, team_id,
        stage_filter=_stage_filter, mode=mode_str,
    )

if not data.get("all_sequences"):
    label = "attacking" if is_attack else "opponent"
    st.info(f"No {label} corner sequences found. Ensure partidos/ match files exist.")
    st.stop()

fc       = data["first_contact"]
dlv      = data["delivery"]
sb       = data["second_ball"]
side     = data["side_danger"]
net      = data["touch_network"]
seqs     = data["all_sequences"]
name_map = data["name_map"]
n_goals  = data.get("goals", 0)
n_shots  = data.get("shots", 0)

# ── Top-level KPIs ────────────────────────────────────────────────────────────
st.markdown("---")
total_c = fc.get("total_corners", 0)

if is_attack:
    # Attacking context: "won" = attacker made first contact = good
    kpi_row([
        {"label": "Attacking Corners",    "value": total_c},
        {"label": "First Contact Won",    "value": f"{fc.get('win_rate', 0)*100:.0f}%",
         "subtitle": "Attacker got first touch"},
        {"label": "Corners → Shot",       "value": n_shots,
         "subtitle": f"{n_shots/total_c*100:.0f}% conversion" if total_c else ""},
        {"label": "Corners → Goal ⚽",    "value": n_goals,
         "subtitle": f"{n_goals/total_c*100:.1f}% rate" if total_c else ""},
    ])
    kpi_row([
        {"label": "Delivery Danger Score", "value": f"{dlv.get('danger_score', 0)}/100",
         "subtitle": "Higher = landed in box"},
        {"label": "2nd Ball Won",          "value": f"{sb.get('second_ball_rate', 0)*100:.0f}%",
         "subtitle": "Attacker won loose ball"},
        {"label": "Dangerous Deliveries",  "value": f"{fc.get('dangerous_rate', 0)*100:.0f}%",
         "subtitle": "Led to shot or goal"},
        {"label": "Avg Delivery Depth",
         "value": f"{sb.get('avg_recovery_dist', 0):.0f} u",
         "subtitle": "From target goal"},
    ])
else:
    # Defending context
    kpi_row([
        {"label": "Corners Faced",         "value": total_c},
        {"label": "First Contact Won",     "value": f"{fc.get('win_rate', 0)*100:.0f}%",
         "subtitle": "Defender got first touch"},
        {"label": "Conceded → Shot",       "value": n_shots,
         "subtitle": f"{n_shots/total_c*100:.0f}% of corners" if total_c else ""},
        {"label": "Goals Conceded ⚽",     "value": n_goals,
         "subtitle": f"{n_goals/total_c*100:.1f}% of corners" if total_c else ""},
    ])
    kpi_row([
        {"label": "Delivery Danger Score", "value": f"{dlv.get('danger_score', 0)}/100",
         "subtitle": "Higher = more dangerous"},
        {"label": "2nd Ball Won",          "value": f"{sb.get('second_ball_rate', 0)*100:.0f}%",
         "subtitle": "Defender won loose ball"},
        {"label": "Dangerous Deliveries",  "value": f"{fc.get('dangerous_rate', 0)*100:.0f}%",
         "subtitle": "Led to shot or goal"},
        {"label": "Clearances Tracked",    "value": sb.get("clearances_tracked", 0)},
    ])

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📍 Sequence Explorer",
    "🎯 First Contact",
    "🗺️ Delivery Zones",
    "🔁 Second Ball",
    "🕸️ Touch Network",
])


# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — Interactive sequence explorer
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    mode_label = "Attacking" if is_attack else "Defending"
    section_header(f"Corner Sequence Explorer — {mode_label}")
    st.caption(
        "Select any corner from the season. The pitch shows every event in "
        "the 20-second window that follows — coloured by which team touched "
        "the ball and what happened. ⚽ = sequence ended in a goal."
    )

    # ── Match + corner selector ───────────────────────────────────────────
    match_labels = [m[1] for m in data["match_index"] if m[2] > 0]
    if not match_labels:
        st.info(f"No matches with {mode_label.lower()} corners found.")
    else:
        col_match, col_corner = st.columns([2, 1])
        with col_match:
            selected_match = st.selectbox("Select Match", match_labels,
                                          key="seq_match_sel")
        match_seqs = [s for s in seqs if s.get("match_label") == selected_match]
        with col_corner:
            corner_labels = [
                f"{'⚽ ' if s.get('led_to_goal') else ''}"
                f"Corner {i+1} — MD {s['minute']}' "
                f"({'L' if s['corner_y'] < 50 else 'R'} side)"
                for i, s in enumerate(match_seqs)
            ]
            if corner_labels:
                sel_corner_idx = st.selectbox("Corner", range(len(corner_labels)),
                                              format_func=lambda i: corner_labels[i],
                                              key="seq_corner_sel")
                seq = match_seqs[sel_corner_idx]
            else:
                st.info("No corners in this match.")
                seq = None

    if seq:
        role_label = "attacking" if is_attack else "defending"
        goal_badge = " ⚽ GOAL" if seq.get("led_to_goal") else ""
        fig = make_pitch_figure(
            title=f"Corner at MD {seq['minute']}′ — {team_name} {role_label}{goal_badge}",
            height=560,
        )

        # Corner kick origin
        fig.add_trace(go.Scatter(
            x=[seq["corner_x"]], y=[seq["corner_y"]],
            mode="markers+text",
            marker=dict(color=AME_BLUE, size=16, symbol="star",
                        line=dict(color="#000", width=1)),
            text=["⚑ Corner"], textposition="top center",
            textfont=dict(color=AME_BLUE, size=11),
            name="Corner kick",
            showlegend=True,
        ))

        # Event dots + arrows
        ev_x, ev_y, ev_text, ev_color = [], [], [], []
        arrow_seqs = []
        prev_xy = (seq["corner_x"], seq["corner_y"])

        type_colors = {
            12: "#42A5F5",   # clearance = blue (defending)
            44: "#FFC107",   # aerial = amber
            49: "#4CAF50",   # ball recovery = green
             1: "#9C27B0",   # pass = purple
            16: "#DA291C",   # goal = red
        }
        for tid in [13, 14, 15, 16]:          # shots
            type_colors[tid] = "#DA291C"

        for e in seq["events"]:
            ex = float(e.get("x", 50))
            ey = float(e.get("y", 50))
            tid = e.get("typeId", 0)
            team = e.get("contestantId", "")
            pname = name_map.get(e.get("playerId", ""), e.get("playerName", ""))

            is_defending = team == seq["defending_team_id"]
            base_color = type_colors.get(tid, "#888")
            if not is_defending:
                base_color = "#FF5252"   # attacking events = bright red

            TYPE_LABELS = {
                12: "Clearance", 44: "Aerial", 49: "Recovery",
                1: "Pass", 16: "Goal ⚽", 15: "Attempt Saved",
                13: "Shot Missed", 10: "Save", 7: "Tackle", 8: "Interception",
            }
            tlabel = TYPE_LABELS.get(tid, f"Event {tid}")
            ev_x.append(ex); ev_y.append(ey)
            ev_text.append(f"{tlabel}<br>{pname}<br>{'Defending' if is_defending else 'Attacking'}")
            ev_color.append(base_color)
            arrow_seqs.append(prev_xy)
            prev_xy = (ex, ey)

        if len(arrow_seqs) >= 2:
            chains = [
                [arrow_seqs[i], (ev_x[i], ev_y[i])]
                for i in range(len(arrow_seqs))
            ]
            add_arrows(fig, chains, color="#AAAAAA", opacity=0.45)

        fig.add_trace(go.Scatter(
            x=ev_x, y=ev_y,
            mode="markers",
            marker=dict(color=ev_color, size=13,
                        line=dict(color="#000", width=0.8)),
            text=ev_text,
            hovertemplate="%{text}<extra></extra>",
            name="Events",
        ))

        # Legend patches
        for lbl, col in [("Defending event", "#42A5F5"),
                          ("Attacking event", "#FF5252"),
                          ("Goal / Shot", "#DA291C"),
                          ("Corner origin", AME_BLUE)]:
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(color=col, size=10),
                name=lbl, showlegend=True,
            ))

        st.plotly_chart(fig, use_container_width=True)

        # Event list table
        if seq["events"]:
            rows = []
            for e in seq["events"]:
                team = e.get("contestantId", "")
                pname = name_map.get(e.get("playerId", ""), e.get("playerName", ""))
                tid = e.get("typeId", 0)
                is_def = team == seq["defending_team_id"]

                # Special label for corner events — outcome depends on team
                if tid == 6:  # EVENT_CORNER
                    evt_label = "✅ Corner Won (Defending)" if is_def else "⚠️ Corner Retained (Attacking)"
                else:
                    evt_label = EVENT_TYPE_LABELS.get(tid, f"TypeId {tid}")

                rows.append({
                    "Min′Sec":  f"{e.get('timeMin',0)}′{e.get('timeSec',0):02d}″",
                    "Event":    evt_label,
                    "Player":   pname or "–",
                    "Side":     "✅ Defending" if is_def else "🔴 Attacking",
                    "x": round(float(e.get("x", 0)), 1),
                    "y": round(float(e.get("y", 0)), 1),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No events recorded in this corner's 20-second window.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — First Contact Control Index
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    section_header("First Contact Index")
    if is_attack:
        st.caption(
            "After each **attacking** corner, what was the **first meaningful action**? "
            "🟡 = team made first contact (good). 🔵 = opponent cleared it first."
        )
    else:
        st.caption(
            "After each **opponent** corner, what was the **first meaningful action**? "
            "🔵 = defending team controlled it. 🟡 = attacker had first contact (danger)."
        )

    by_type = fc.get("by_type", {})
    if by_type:
        types = list(by_type.keys())
        counts = [by_type[t] for t in types]

        # Colour depends on mode:
        # defend mode: yellow = danger (attacker got it), blue = we won it
        # attack mode: yellow = success (we got it), blue = they cleared it
        if is_attack:
            GOOD_TYPES   = {"Clearance", "Aerial Duel", "Tackle", "Interception",
                            "Save", "Keeper Claim", "Recovery", "Ball Out",
                            "Corner Won (Def)"}   # ← these mean OPPONENT cleared = bad for attacker
            SUCCESS_TYPES = {"Corner Retained (Att)", "Recycled / Flick-on",
                             "Shot Conceded", "Goal Conceded"}
            bar_colors = [
                AME_YELLOW if t in SUCCESS_TYPES
                else ("#42A5F5" if t in GOOD_TYPES else "#888")
                for t in types
            ]
        else:
            DANGER_TYPES = {"Shot Conceded", "Goal Conceded",
                            "Corner Retained (Att)", "Recycled / Flick-on"}
            WON_TYPES    = {"Clearance", "Aerial Duel", "Tackle", "Interception",
                            "Save", "Keeper Claim", "Recovery", "Ball Out",
                            "Corner Won (Def)"}
            bar_colors = [
                AME_YELLOW if t in DANGER_TYPES
                else ("#42A5F5" if t in WON_TYPES else "#888")
                for t in types
            ]

        fig_fc = go.Figure(go.Bar(
            y=types, x=counts,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color="#000", width=0.5)),
            text=[f"{c}  ({c/total_c*100:.0f}%)" for c in counts],
            textposition="outside",
            textfont=dict(color="#FAFAFA"),
        ))
        fig_fc.update_layout(
            template="ame_dark",
            title="First Contact Type Distribution",
            xaxis_title="Count",
            height=380,
            margin=dict(l=10, r=60, t=40, b=20),
        )
        st.plotly_chart(fig_fc, use_container_width=True)

    # Corner-side breakdown
    records_df = pd.DataFrame(fc.get("records", []))
    if not records_df.empty:
        st.markdown("#### By Corner Side (Left vs Right)")
        side_fc = records_df.groupby(["corner_side", "defended"]).size().unstack(fill_value=0)
        if not side_fc.empty:
            fig_side_fc = go.Figure()
            for defended, color, label in [
                (True,  "#42A5F5", "Defended (1st contact won)"),
                (False, AME_YELLOW,   "Not defended"),
            ]:
                col = defended
                vals = side_fc.get(col, pd.Series(dtype=int))
                fig_side_fc.add_trace(go.Bar(
                    x=side_fc.index, y=vals,
                    name=label, marker_color=color,
                ))
            fig_side_fc.update_layout(
                barmode="stack", template="ame_dark",
                title="First Contact by Corner Side",
                yaxis_title="Corners", height=320,
            )
            st.plotly_chart(fig_side_fc, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — Delivery Zones
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    section_header("Corner Delivery Hotspots")
    st.caption(
        "All corners normalised so the **defended goal is on the right**. "
        "Each dot = one corner delivery; colour shows the danger zone. "
        "🔴 six-yard box (highest danger) → 🟡 edge of box → ⚫ outside."
    )

    zone_colors = {
        "six_yard":     "#DA291C",
        "penalty_spot": "#FF6B35",
        "penalty_area": "#FFC107",
        "edge_box":     "#42A5F5",
        "outside":      "#666",
    }
    zone_order = ["six_yard", "penalty_spot", "penalty_area", "edge_box", "outside"]
    zone_labels = {
        "six_yard": "Six-yard box",
        "penalty_spot": "Penalty spot area",
        "penalty_area": "Penalty area",
        "edge_box": "Edge of box",
        "outside": "Outside box",
    }

    pts = dlv.get("landing_points", [])
    if pts:
        # landing_points tuples: (x, y, zone, weight, led_to_goal, led_to_shot)
        goal_label  = "⚽ Goal" if is_attack else "⚽ Goal Conceded"
        zone_title  = (f"Corner Landing Zones — {team_name} (⚽ target goal →)"
                       if is_attack
                       else f"Corner Landing Zones — {team_name} (🛡️ defended goal →)")

        # ── Half-pitch figure (only right half, x = 50–103) ──────────────
        fig_dlv = make_pitch_figure(title=zone_title, height=520, show_zones=True)
        fig_dlv.update_layout(
            xaxis=dict(range=[47, 103], showgrid=False, zeroline=False,
                       visible=False, fixedrange=True),
        )

        from collections import defaultdict
        by_zone: dict[str, list] = defaultdict(list)
        goal_pts, shot_pts, normal_pts = [], [], []
        for tup in pts:
            lx_v, ly_v, lz_v, lw_v = tup[0], tup[1], tup[2], tup[3]
            led_goal = tup[4] if len(tup) > 4 else False
            led_shot = tup[5] if len(tup) > 5 else False
            by_zone[lz_v].append((lx_v, ly_v, lw_v, led_goal, led_shot))
            if led_goal:
                goal_pts.append((lx_v, ly_v))
            elif led_shot:
                shot_pts.append((lx_v, ly_v))
            else:
                normal_pts.append((lx_v, ly_v, lz_v))

        # Regular zone dots
        for zone in zone_order:
            items = [i for i in by_zone.get(zone, []) if not i[3] and not i[4]]
            if not items:
                continue
            xs = [i[0] for i in items]
            ys = [i[1] for i in items]
            texts = [f"{zone_labels[zone]}<br>x={i[0]:.0f}, y={i[1]:.0f}"
                     for i in items]
            fig_dlv.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers",
                marker=dict(color=zone_colors[zone], size=10, opacity=0.75,
                            line=dict(color="#000", width=0.8)),
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                name=f"{zone_labels[zone]} ({len(by_zone.get(zone,[]))})",
            ))

        # Shot corners (larger dot, ring)
        if shot_pts:
            fig_dlv.add_trace(go.Scatter(
                x=[p[0] for p in shot_pts], y=[p[1] for p in shot_pts],
                mode="markers",
                marker=dict(color="#FF6B35", size=16, opacity=0.90,
                            symbol="circle-open",
                            line=dict(color="#FF6B35", width=3)),
                hovertemplate="Shot corner<br>x=%{x:.0f}, y=%{y:.0f}<extra></extra>",
                name=f"→ Shot ({len(shot_pts)})",
            ))

        # Goal corners (star marker, gold)
        if goal_pts:
            fig_dlv.add_trace(go.Scatter(
                x=[p[0] for p in goal_pts], y=[p[1] for p in goal_pts],
                mode="markers+text",
                marker=dict(color=AME_YELLOW, size=22, symbol="star",
                            line=dict(color="#000", width=1.5)),
                text=["⚽"] * len(goal_pts),
                textposition="top center",
                textfont=dict(size=14),
                hovertemplate="GOAL corner<br>x=%{x:.0f}, y=%{y:.0f}<extra></extra>",
                name=f"{goal_label} ({len(goal_pts)})",
            ))

        # KDE density (right half only)
        danger_x = [tup[0] for tup in pts if tup[0] >= 50]
        danger_y = [tup[1] for tup in pts if tup[0] >= 50]
        if danger_x:
            fig_dlv.add_trace(go.Histogram2dContour(
                x=danger_x, y=danger_y,
                colorscale=[
                    [0.0, "rgba(0,0,0,0)"],
                    [0.25, "rgba(218,41,28,0.12)"],
                    [0.6,  "rgba(218,41,28,0.35)"],
                    [1.0,  "rgba(255,205,0,0.55)"],
                ],
                showscale=False,
                ncontours=10,
                contours=dict(coloring="fill"),
                hoverinfo="skip",
                line=dict(width=0),
                name="Density",
                showlegend=False,
            ))

        st.plotly_chart(fig_dlv, use_container_width=True)

        # ── Zone count bar ────────────────────────────────────────────────
        zone_counts = dlv.get("zone_counts", {})
        if zone_counts:
            ordered_zones = [z for z in zone_order if z in zone_counts]
            fig_zc = go.Figure(go.Bar(
                x=[zone_labels.get(z, z) for z in ordered_zones],
                y=[zone_counts[z] for z in ordered_zones],
                marker=dict(color=[zone_colors[z] for z in ordered_zones],
                            line=dict(color="#000", width=0.5)),
                text=[f"{zone_counts[z]} ({zone_counts[z]/dlv['total_corners']*100:.0f}%)"
                      for z in ordered_zones],
                textposition="auto",
                textfont=dict(color="#fff"),
            ))
            fig_zc.update_layout(
                template="ame_dark",
                title="Deliveries per Zone (season total)",
                yaxis_title="Count",
                height=280,
            )
            st.plotly_chart(fig_zc, use_container_width=True)

    # ── By-side breakdown ─────────────────────────────────────────────────
    by_side = dlv.get("by_side", {})
    if any(v for v in by_side.values()):
        st.markdown("#### Danger by Corner Origin Side")
        st.caption("Left / Right = which side of the defended goal the corner comes from.")
        side_data = []
        for s, zones in by_side.items():
            total_s = sum(zones.values())
            if not total_s:
                continue
            danger = sum(
                cnt * ZONE_DANGER_WEIGHTS.get(z, 0)
                for z, cnt in zones.items()
            )
            side_data.append({
                "Side": s,
                "Corners": total_s,
                "Danger Score": round(danger / total_s * 100, 1),
            })
        if side_data:
            side_df = pd.DataFrame(side_data).sort_values("Danger Score", ascending=False)
            fig_sds = go.Figure(go.Bar(
                x=side_df["Side"],
                y=side_df["Danger Score"],
                marker=dict(color=[AME_YELLOW, "#42A5F5", AME_BLUE][:len(side_df)],
                            line=dict(color="#000", width=0.5)),
                text=[f"{row['Corners']} corners<br>{row['Danger Score']}/100"
                      for _, row in side_df.iterrows()],
                textposition="auto",
                textfont=dict(color="#fff"),
            ))
            fig_sds.update_layout(
                template="ame_dark",
                title="Weighted Danger Score by Corner Side (0 = safe, 100 = all in 6-yard box)",
                yaxis_title="Danger Score",
                height=280,
            )
            st.plotly_chart(fig_sds, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — Second Ball
# ═══════════════════════════════════════════════════════════════════════════
with tab4:
    section_header("Second Ball Control")
    st.caption(
        "After a defensive clearance from a corner, who wins the **loose ball**? "
        "A 'danger reset' occurs when the opponent recovers it near the box (< 30u from goal)."
    )

    records_sb = sb.get("records", [])
    if records_sb:
        sb_df = pd.DataFrame(records_sb)

        # Scatter: clearance location coloured by who won second ball
        fig_sb = make_pitch_figure(
            title="Clearance Locations & Second Ball Outcome",
            height=520,
        )
        won_df  = sb_df[sb_df["won_second_ball"] == True]
        lost_df = sb_df[sb_df["won_second_ball"] == False]
        danger_df = sb_df[sb_df["danger_reset"] == True]

        fig_sb.add_trace(go.Scatter(
            x=won_df["clearance_x"], y=won_df["clearance_y"],
            mode="markers",
            marker=dict(color="#4CAF50", size=10, symbol="circle",
                        line=dict(color="#000", width=0.5)),
            name="2nd ball won ✔",
            text=[f"MD {r['minute']}′ — Won 2nd ball, dist {r['recovery_dist_from_goal']}u"
                  for _, r in won_df.iterrows()],
            hovertemplate="%{text}<extra></extra>",
        ))
        fig_sb.add_trace(go.Scatter(
            x=lost_df["clearance_x"], y=lost_df["clearance_y"],
            mode="markers",
            marker=dict(color="#FF9800", size=10, symbol="x",
                        line=dict(color="#000", width=0.5)),
            name="2nd ball lost ✗",
            text=[f"MD {r['minute']}′ — Lost 2nd ball"
                  for _, r in lost_df.iterrows()],
            hovertemplate="%{text}<extra></extra>",
        ))
        if not danger_df.empty:
            fig_sb.add_trace(go.Scatter(
                x=danger_df["clearance_x"], y=danger_df["clearance_y"],
                mode="markers",
                marker=dict(color=AME_YELLOW, size=14, symbol="star",
                            line=dict(color="#000", width=1)),
                name="⚠️ Danger reset",
                text=["Danger reset — opponent near box" for _ in range(len(danger_df))],
                hovertemplate="%{text}<extra></extra>",
            ))
        st.plotly_chart(fig_sb, use_container_width=True)

        # Recovery distance histogram
        fig_dist = go.Figure(go.Histogram(
            x=sb_df["recovery_dist_from_goal"],
            nbinsx=15,
            marker_color=AME_YELLOW,
            opacity=0.75,
        ))
        fig_dist.add_vline(x=30, line_dash="dash", line_color=AME_BLUE,
                           annotation_text="Danger zone threshold (30u)",
                           annotation_font=dict(color=AME_BLUE, size=11))
        fig_dist.update_layout(
            template="ame_dark",
            title="Second Ball Recovery Distance from Goal",
            xaxis_title="Distance from Goal (Opta units, lower = more dangerous)",
            yaxis_title="Count",
            height=300,
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    else:
        st.info(
            "No clearance sequences found. This typically means the Opta feed "
            "for this competition doesn't record intermediate clearance events "
            "within corner sequences, or all corners ended with the ball going "
            "directly out of play without a tracked clearance event (TypeId 12)."
        )
        st.caption(
            "**Tip:** Check the Sequence Explorer tab — if corners end with "
            "'✅ Corner Won (Defending)', the clearance happened but was bundled "
            "into the corner event rather than tracked separately."
        )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — Touch Network
# ═══════════════════════════════════════════════════════════════════════════
with tab5:
    section_header("Post-Corner Touch Network")
    st.caption(
        "Who touches the ball after each opponent corner? Node size = total touches. "
        "Edge thickness = how often two players interact consecutively. "
        "🔵 = Defending team  🔴 = Attacking team"
    )

    nodes = net.get("nodes", {})
    edges = net.get("edges", [])

    if nodes and edges:
        max_weight = max((e[2] for e in edges), default=1)
        max_touches = max((n["touches"] for n in nodes.values()), default=1)

        fig_net = make_pitch_figure(
            title=f"Corner Touch Network — {team_name}",
            height=580,
        )

        # Draw edges
        for from_id, to_id, weight in edges:
            if from_id not in nodes or to_id not in nodes:
                continue
            fn = nodes[from_id]
            tn = nodes[to_id]
            alpha = max(0.15, weight / max_weight * 0.7)
            w = max(1.0, weight / max_weight * 4)
            is_defending = fn["team_id"] == team_id
            edge_color = "#42A5F5" if is_defending else "#FF5252"
            fig_net.add_trace(go.Scatter(
                x=[fn["x"], tn["x"], None],
                y=[fn["y"], tn["y"], None],
                mode="lines",
                line=dict(color=edge_color, width=w),
                opacity=alpha,
                showlegend=False,
                hoverinfo="text",
                hovertext=f"{fn['name']} → {tn['name']} ({weight}×)",
            ))

        # Draw nodes
        for pid, node in nodes.items():
            is_def = node["team_id"] == team_id
            ncolor = "#42A5F5" if is_def else "#FF5252"
            nsize = 8 + (node["touches"] / max_touches) * 24
            fig_net.add_trace(go.Scatter(
                x=[node["x"]], y=[node["y"]],
                mode="markers+text",
                marker=dict(color=ncolor, size=nsize,
                            line=dict(color="#fff", width=1.5)),
                text=[node["name"].split()[-1]],   # last name only
                textposition="top center",
                textfont=dict(color="#FAFAFA", size=9),
                name=f"{node['name']} ({node['touches']})",
                hovertext=f"{node['name']}<br>Touches: {node['touches']}<br>"
                          f"Pos: ({node['x']:.0f}, {node['y']:.0f})",
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            ))

        fig_net.update_layout(
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                font=dict(size=10),
            )
        )
        st.plotly_chart(fig_net, use_container_width=True)

        # Top interaction pairs
        st.markdown("#### Most frequent consecutive touches")
        edge_rows = []
        for from_id, to_id, weight in sorted(edges, key=lambda e: -e[2])[:15]:
            fn = nodes.get(from_id, {})
            tn = nodes.get(to_id, {})
            edge_rows.append({
                "From": fn.get("name", from_id),
                "To":   tn.get("name", to_id),
                "Count": weight,
                "Both Defending": (
                    fn.get("team_id") == team_id and tn.get("team_id") == team_id
                ),
            })
        edge_df = pd.DataFrame(edge_rows)
        st.dataframe(edge_df, use_container_width=True, hide_index=True)

        # Most-touched players
        st.markdown("#### Players with most touches in corner sequences")
        touch_rows = sorted(
            [{"Player": n["name"], "Touches": n["touches"],
              "Team": "Defending" if n["team_id"] == team_id else "Attacking",
              "Avg X": n["x"], "Avg Y": n["y"]}
             for n in nodes.values()],
            key=lambda r: -r["Touches"]
        )[:20]
        st.dataframe(pd.DataFrame(touch_rows), use_container_width=True, hide_index=True)

    else:
        st.info("Not enough event data to build a touch network.")
