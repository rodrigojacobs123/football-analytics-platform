"""Player Report — Wyscout match-by-match exports: dashboard, filters, PDF ficha."""

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from viz.theme import apply_theme
from viz.kpi_cards import page_header, kpi_card, ame_section
from viz.tables import styled_dataframe
from processing.wyscout_player import (
    parse_player_stats, player_name_from_filename, infer_team, filter_matches,
    aggregate_per90, form_series, consistency, competition_split,
    strengths_weaknesses, video_checklist,
)
from config import AME_YELLOW, AME_BLUE

apply_theme()

page_header("Player Report", subtitle="Wyscout match-by-match — form, filters, PDF ficha")

st.markdown(
    "Upload a Wyscout **Player stats** export (one player, one row per match — "
    "the file you get from a player's page, not from Search). The dashboard and "
    "the PDF ficha reflect **whatever the filters select**: last N matches, "
    "competitions, dates."
)

_PARSE_VERSION = 1


@st.cache_data(ttl=3600, show_spinner=False)
def _parse(file_bytes: bytes, name: str, version: int) -> pd.DataFrame:
    return parse_player_stats(pd.read_excel(io.BytesIO(file_bytes)), name)


uploads = st.file_uploader(
    "Player stats exports", type=["xlsx"], accept_multiple_files=True,
    help="One file per player ('Player stats <name>.xlsx').",
)
if not uploads:
    st.info("⬆️ Drop one or more 'Player stats' files here — e.g. "
            "`Player stats M. Dami Mane.xlsx`.")
    st.stop()

parsed: dict[str, pd.DataFrame] = {}
for up in uploads:
    try:
        parsed[player_name_from_filename(up.name)] = _parse(
            up.getvalue(), up.name, _PARSE_VERSION)
    except Exception as exc:  # noqa: BLE001 — surface bad files, keep the rest
        st.warning(f"Skipped **{up.name}**: {exc}")
if not parsed:
    st.stop()

player = st.selectbox("Player", list(parsed.keys())) if len(parsed) > 1 \
    else list(parsed.keys())[0]
matches = parsed[player]
team = infer_team(matches)

# ── Filters ──────────────────────────────────────────────────────────────────
ame_section("WINDOW", "Filters — dashboard AND PDF follow these")
f1, f2, f3 = st.columns([1.3, 2, 1])
n_total = len(matches)
last_n = f1.slider(
    "Last N matches", 1, n_total, n_total,
    help="Counts backwards from the most recent match AFTER the other filters "
         "— set competitions to league only and N=10 for 'last 10 league games'.",
)
comps_all = matches["Competition"].value_counts().index.tolist()
sel_comps = f2.multiselect("Competitions", comps_all, default=comps_all)
min_mins = f3.number_input("Min. minutes / match", 0, 90, 0, step=15)

d_lo, d_hi = matches["Date"].min().date(), matches["Date"].max().date()
date_range = st.slider("Date range", d_lo, d_hi, (d_lo, d_hi), format="MMM YYYY")

view = filter_matches(matches, last_n=last_n, competitions=sel_comps,
                      date_range=date_range, min_minutes=int(min_mins))
if view.empty:
    st.warning("No matches left after filters — widen the window.")
    st.stop()

filters_desc = (
    f"últimos {len(view)} partidos · "
    + (f"{len(sel_comps)}/{len(comps_all)} competiciones · " if len(sel_comps) < len(comps_all) else "todas las competiciones · ")
    + f"{view['Date'].min():%b %Y}–{view['Date'].max():%b %Y}"
    + (f" · ≥{int(min_mins)}′/partido" if min_mins else "")
)

agg = aggregate_per90(view)
cons = consistency(view)
fs = form_series(view)

# ── KPIs ─────────────────────────────────────────────────────────────────────
k = st.columns(6)
with k[0]:
    kpi_card("Matches", agg["matches"])
with k[1]:
    kpi_card("Minutes", agg["minutes"])
with k[2]:
    kpi_card("Goals", agg["goals"])
with k[3]:
    kpi_card("Assists", agg["assists"])
with k[4]:
    kpi_card("G+A / 90", agg["ga90"])
with k[5]:
    kpi_card("xG / 90", agg["xg90"])
st.caption(
    f"⭐ {team} — G+A in {cons['ga_matches_pct']:.0f}% of matches · longest "
    f"drought {cons['max_drought']} · {cons['starts']} starts (≥60′) in window"
)

tab_form, tab_volume, tab_comp, tab_pdf = st.tabs(
    ["📈 Form", "⚔️ Volume & duels", "🏆 By competition", "📄 PDF report"]
)

_dates = fs["Date"].dt.strftime("%d %b %y")

with tab_form:
    fig = go.Figure()
    fig.add_bar(x=_dates, y=fs["ga"], name="G+A (match)",
                marker_color=AME_YELLOW, opacity=0.55,
                customdata=fs["opponent"],
                hovertemplate="%{customdata}<br>G+A: %{y}<extra></extra>")
    fig.add_scatter(x=_dates, y=fs["xg90_roll"], name="xG/90 (rolling 5)",
                    line=dict(color=AME_BLUE, width=2.5))
    fig.add_scatter(x=_dates, y=fs["ga90_roll"], name="G+A/90 (rolling 5)",
                    line=dict(color="#EAF0FA", width=2, dash="dash"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#EAF0FA"), title="Production & form trend")
    st.plotly_chart(fig, width="stretch")

    mfig = go.Figure(go.Bar(
        x=_dates, y=fs["Minutes played"], marker_color=AME_BLUE,
        customdata=fs["Competition"],
        hovertemplate="%{customdata}<br>%{y}′<extra></extra>"))
    mfig.update_layout(height=240, margin=dict(l=10, r=10, t=30, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color="#EAF0FA"), title="Minutes per match")
    st.plotly_chart(mfig, width="stretch")

with tab_volume:
    vfig = go.Figure()
    vfig.add_scatter(x=_dates, y=fs["dribbles90_roll"], name="Dribbles/90 (rolling 5)",
                     line=dict(color=AME_YELLOW, width=2.5))
    vfig.add_scatter(x=_dates, y=fs["duels90_roll"], name="Duels/90 (rolling 5)",
                     line=dict(color=AME_BLUE, width=2.5), yaxis="y2")
    vfig.update_layout(
        height=380, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF0FA"), title="Carrying & duel volume",
        yaxis=dict(title="Dribbles/90"),
        yaxis2=dict(title="Duels/90", overlaying="y", side="right"))
    st.plotly_chart(vfig, width="stretch")

    s_col, w_col = st.columns(2)
    S, W = strengths_weaknesses(agg)
    with s_col:
        st.markdown("**✅ Strengths (window)**")
        for s in S or ["—"]:
            st.markdown(f"- {s}")
    with w_col:
        st.markdown("**🔴 Areas to improve**")
        for w in W or ["—"]:
            st.markdown(f"- {w}")
    st.markdown("**🎬 Video checklist**")
    for i, item in enumerate(video_checklist(agg, cons), 1):
        st.markdown(f"{i}. {item}")

with tab_comp:
    styled_dataframe(competition_split(view), height=320)
    styled_dataframe(
        view.sort_values("Date", ascending=False)[
            ["Date", "Match", "Competition", "Position", "Minutes played",
             "Goals", "Assists", "xG", "dribbles", "duels"]],
        height=420,
    )

with tab_pdf:
    ame_section("DELIVERABLE", "Ficha de scouting (PDF)")
    st.caption(f"The PDF is built from the current window: **{filters_desc}**. "
               "Change the filters above and regenerate to get a different cut.")
    if st.button("📄 Generate PDF ficha"):
        from viz.player_report_pdf import build_player_report
        with st.spinner("Building report…"):
            pdf = build_player_report(view, matches, player, team, filters_desc)
        st.session_state["player_pdf"] = pdf
        st.session_state["player_pdf_name"] = (
            f"Ficha_{player.replace(' ', '_')}_{len(view)}p.pdf")
    if st.session_state.get("player_pdf"):
        st.download_button(
            f"📥 Download — {st.session_state['player_pdf_name']} "
            f"({len(st.session_state['player_pdf']) / 1e6:.1f} MB)",
            data=st.session_state["player_pdf"],
            file_name=st.session_state["player_pdf_name"],
            mime="application/pdf",
        )
