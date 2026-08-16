"""Player Report — Wyscout match-by-match exports: coach view, filters, PDF ficha."""

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
    parse_match_context, position_split, venue_split, coach_traffic_lights,
)
from config import AME_YELLOW, AME_BLUE

apply_theme()

page_header("Player Report", subtitle="Wyscout match-by-match — form, filters, PDF ficha")

st.markdown(
    "Upload a Wyscout **Player stats** export (one player, one row per match). "
    "The coach view, charts and the PDF ficha reflect **whatever the filters "
    "select**: last N matches, competitions, dates."
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
ame_section("WINDOW", "Filters — coach view AND PDF follow these")
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
    + (f"{len(sel_comps)}/{len(comps_all)} competiciones · "
       if len(sel_comps) < len(comps_all) else "todas las competiciones · ")
    + f"{view['Date'].min():%b %Y}–{view['Date'].max():%b %Y}"
    + (f" · ≥{int(min_mins)}′/partido" if min_mins else "")
)

agg = aggregate_per90(view)
cons = consistency(view)
ctx = parse_match_context(view, team)

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

tab_coach, tab_tech, tab_comp, tab_market, tab_pdf = st.tabs(
    ["🧑‍🏫 Coach view", "📊 Technical analysis", "🏆 By competition",
     "⚖️ vs Market", "📄 PDF report"]
)

# ── Tab 1: coach view — answers, not axes ────────────────────────────────────
_RESULT_COLOR = {"V": "#4CAF50", "E": "#9E9E9E", "D": "#E53935", "": "#555"}


def _match_card(r) -> str:
    color = _RESULT_COLOR.get(r["result"], "#555")
    goals = "⚽" * int(r["Goals"]) + "🅰️" * int(r["Assists"])
    venue = "🏠" if r["venue"] == "Casa" else ("✈️" if r["venue"] == "Fuera" else "")
    return (f'<div style="flex:0 0 110px;background:#0E1B36;border-radius:8px;'
            f'padding:8px 10px;border-top:3px solid {color};">'
            f'<div style="color:#8899AA;font-size:0.62rem;">{r["Date"]:%d %b %y} {venue}</div>'
            f'<div style="color:#EAF0FA;font-size:0.72rem;font-weight:600;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{r["opponent"]}</div>'
            f'<div style="color:{color};font-weight:700;font-size:0.85rem;">'
            f'{r["result"]} {r["score"]}</div>'
            f'<div style="color:#EAF0FA;font-size:0.7rem;">{int(r["Minutes played"])}′ '
            f'{goals}</div></div>')


with tab_coach:
    # 1 · Semáforos: the one-glance row.
    ame_section("EN UNA MIRADA", "Semáforos del jugador")
    lights = coach_traffic_lights(view)
    lcols = st.columns(len(lights) or 1)
    for col, light in zip(lcols, lights):
        with col:
            html = (f'<div style="background:#0E1B36;border-radius:10px;padding:0.8rem;'
                    f'min-height:7.2rem;">'
                    f'<div style="font-size:1.3rem;">{light["icon"]} '
                    f'<span style="color:#FFD100;font-size:0.7rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.5px;">{light["label"]}'
                    f'</span></div>'
                    f'<div style="color:#EAF0FA;font-size:0.78rem;margin-top:0.3rem;">'
                    f'{light["text"]}</div></div>')
            st.markdown(html, unsafe_allow_html=True)

    # 2 · Racha: last matches as cards, newest first.
    ame_section("RACHA", "Últimos partidos")
    recent = ctx.sort_values("Date", ascending=False).head(10)
    strip = ('<div style="display:flex;gap:8px;overflow-x:auto;padding-bottom:6px;">'
             + "".join(_match_card(r) for _, r in recent.iterrows()) + "</div>")
    st.markdown(strip, unsafe_allow_html=True)

    # 3 · ¿Dónde lo pongo? — production by position, with the takeaway spelled out.
    ame_section("ROL", "¿Dónde rinde mejor?")
    pos = position_split(view)
    if not pos.empty:
        c_tbl, c_bar = st.columns([1.2, 1])
        with c_tbl:
            styled_dataframe(pos, height=40 + 36 * len(pos))
        with c_bar:
            reliable = pos[pos["Min"] >= 270]
            if not reliable.empty:
                pfig = go.Figure(go.Bar(
                    x=reliable["G+A/90"], y=reliable["Posición"], orientation="h",
                    marker_color=AME_YELLOW, text=reliable["G+A/90"],
                    textposition="outside"))
                pfig.update_layout(
                    height=60 + 44 * len(reliable),
                    margin=dict(l=10, r=40, t=24, b=10),
                    title="G+A/90 por posición (≥270′)",
                    xaxis=dict(range=[0, max(0.9, reliable["G+A/90"].max() * 1.3)]),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#EAF0FA"))
                st.plotly_chart(pfig, width="stretch")
        reliable = pos[pos["Min"] >= 270]
        if len(reliable) >= 2:
            best = reliable.sort_values("G+A/90", ascending=False).iloc[0]
            used = reliable.sort_values("Min", ascending=False).iloc[0]
            if best["Posición"] != used["Posición"] and best["G+A/90"] >= used["G+A/90"] * 1.5:
                st.markdown(
                    f"💡 **Dato para el cuerpo técnico:** juega sobre todo de "
                    f"**{used['Posición']}** ({used['G+A/90']} G+A/90), pero sus números "
                    f"como **{best['Posición']}** son claramente mejores "
                    f"({best['G+A/90']} G+A/90 en {best['Min']}′)."
                )

    # 4 · Casa / fuera.
    ven = venue_split(ctx)
    if len(ven) == 2:
        ame_section("CONTEXTO", "Casa vs fuera")
        styled_dataframe(ven, height=130)
        casa = ven[ven["Dónde"] == "Casa"]["G+A/90"].iloc[0]
        fuera = ven[ven["Dónde"] == "Fuera"]["G+A/90"].iloc[0]
        hi, lo, where = (casa, fuera, "en casa") if casa > fuera else (fuera, casa, "fuera")
        if lo > 0 and hi / lo >= 1.7:
            st.caption(f"💡 Produce claramente más {where} ({hi} vs {lo} G+A/90).")

# ── Tab 2: technical analysis (the analyst's curves live here now) ───────────
with tab_tech:
    fs = form_series(view)
    _dates = fs["Date"].dt.strftime("%d %b %y")
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

    vfig = go.Figure()
    vfig.add_scatter(x=_dates, y=fs["dribbles90_roll"], name="Dribbles/90 (rolling 5)",
                     line=dict(color=AME_YELLOW, width=2.5))
    vfig.add_scatter(x=_dates, y=fs["duels90_roll"], name="Duels/90 (rolling 5)",
                     line=dict(color=AME_BLUE, width=2.5), yaxis="y2")
    vfig.update_layout(
        height=340, margin=dict(l=10, r=10, t=30, b=10),
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

# ── Tab 3: by competition ────────────────────────────────────────────────────
with tab_comp:
    styled_dataframe(competition_split(view), height=320)
    styled_dataframe(
        ctx.sort_values("Date", ascending=False)[
            ["Date", "opponent", "venue", "score", "result", "Competition",
             "Position", "Minutes played", "Goals", "Assists", "xG"]],
        height=420,
    )

# ── Tab 4: vs Market — percentile the player against a Search results pool ───
with tab_market:
    ame_section("MARKET", "Compare vs a Search results pool")
    st.caption(
        f"Upload a Wyscout **Search results** export and **{player}**'s filtered "
        f"window ({filters_desc}) is percentiled against that pool — real "
        "percentiles instead of approximate references. Only metrics both "
        "formats share are compared; the caption below the results lists them."
    )
    mkt_files = st.file_uploader(
        "Search results exports", type=["xlsx"], accept_multiple_files=True,
        key="market_pool_uploader",
    )
    if not mkt_files:
        st.info("⬆️ Drop a 'Search results' file (e.g. a search of attacking "
                "midfielders) to benchmark the player against it.")
    else:
        from processing.wyscout_scouting import (
            normalize_wyscout, combine_sources, score_players,
            assign_archetypes, GROUP_LABELS, display_columns,
        )
        from processing.wyscout_bridge import (
            player_stats_profile, market_comparison, bridge_radar,
        )
        from viz.radar import radar_chart

        @st.cache_data(ttl=3600, show_spinner=False)
        def _parse_market(file_bytes: bytes, name: str) -> pd.DataFrame:
            return normalize_wyscout(pd.read_excel(io.BytesIO(file_bytes)), name)

        mframes = []
        for up in mkt_files:
            try:
                mframes.append(_parse_market(up.getvalue(), up.name))
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Skipped **{up.name}**: {exc}")
        if mframes:
            mpooled = combine_sources(mframes)
            c1, c2 = st.columns([1.4, 1.6])
            pool_min = c1.slider(
                "Min. minutes in pool", 0, int(mpooled["Minutes played"].max()),
                min(900, int(mpooled["Minutes played"].max())), step=90,
                key="market_pool_min",
            )
            mscored = assign_archetypes(score_players(mpooled, min_minutes=pool_min))
            groups = sorted(mscored["position_group"].dropna().unique())
            if not groups:
                st.warning("Pool is empty after the minutes filter.")
            else:
                default_g = "AM" if "AM" in groups else groups[0]
                g = c2.selectbox(
                    "Compare as", groups, index=groups.index(default_g),
                    format_func=lambda x: f"{x} — {GROUP_LABELS.get(x, x)}",
                    key="market_group",
                )
                profile = player_stats_profile(agg)
                mmatches, pseudo_pct, pseudo_score, shared = market_comparison(
                    mscored, profile, g, k=10)
                gdf = mscored[mscored["position_group"] == g]
                if pseudo_score is None or gdf.empty:
                    st.info("No comparable metrics between this window and the "
                            "pool for that position group.")
                else:
                    rank = int((gdf["Score"] > pseudo_score).sum()) + 1
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        kpi_card("Score in this market", pseudo_score)
                    with b2:
                        kpi_card("Would rank", f"#{rank} of {len(gdf)}")
                    with b3:
                        kpi_card("Metrics compared", len(shared))
                    st.caption(
                        "Compared on: " + ", ".join(shared) + ". Non-penalty "
                        "goals are proxied by total goals (the match-by-match "
                        "export has no penalty split)."
                    )
                    show = mmatches[["similarity"]
                                    + [c for c in display_columns(mmatches)
                                       if c not in ("found_in", "group_role")]]
                    styled_dataframe(show, height=40 + 36 * len(show))

                    rivals = mmatches.head(2)["Player"].tolist()
                    categories, values = bridge_radar(
                        mscored, g, f"{player} (ventana)", pseudo_pct, rivals)
                    if len(categories) >= 3:
                        st.plotly_chart(
                            radar_chart(categories, values,
                                        title=f"{player} vs pool ({len(shared)} "
                                              "shared metrics)"),
                            width="stretch",
                        )

# ── Tab 5: PDF ───────────────────────────────────────────────────────────────
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
