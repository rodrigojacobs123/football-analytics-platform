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
    scout_hooks, suggest_thread, publication_plan,
)
from config import AME_YELLOW, AME_BLUE

apply_theme()

page_header("Player Report", subtitle="Wyscout match-by-match — form, filters, PDF ficha")

st.markdown(
    "Upload a Wyscout **Player stats** export (one player, one row per match). "
    "The coach view, charts and the PDF ficha reflect **whatever the filters "
    "select**: last N matches, competitions, dates."
)

_PARSE_VERSION = 2


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

# Set by the vs-Market tab in this same run; the Social tab reads it. A plain
# variable (not session_state) so it can never go stale across reruns.
market_ctx: dict | None = None

tab_coach, tab_tech, tab_comp, tab_market, tab_social, tab_pdf = st.tabs(
    ["🧑‍🏫 Coach view", "📊 Technical analysis", "🏆 By competition",
     "⚖️ vs Market", "📱 Social post", "📄 PDF report"]
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

    # Cumulative finishing: does he convert what he generates?
    cum = view.sort_values("Date")
    cfig = go.Figure()
    cfig.add_scatter(x=cum["Date"], y=cum["xG"].cumsum().round(2),
                     name="xG acumulado", line=dict(color=AME_BLUE, width=2.5))
    cfig.add_scatter(x=cum["Date"], y=cum["Goals"].cumsum(),
                     name="Goles acumulados",
                     line=dict(color=AME_YELLOW, width=2.5))
    cfig.update_layout(
        height=340, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF0FA"),
        title="Finalización: xG acumulado vs goles (líneas separadas = sobre/infra-rendimiento)")
    st.plotly_chart(cfig, width="stretch")

    # Rolling efficiency: the quality complement to the volume chart above.
    w = 5
    eff = view.sort_values("Date").copy()
    for att, ok, dst in (("dribbles", "dribbles_ok", "drib_pct"),
                         ("duels", "duels_ok", "duel_pct")):
        r_ok = eff[ok].rolling(w, min_periods=1).sum()
        r_at = eff[att].rolling(w, min_periods=1).sum()
        eff[dst] = (100.0 * r_ok / r_at.where(r_at > 0)).round(1)
    efig = go.Figure()
    efig.add_scatter(x=_dates, y=eff["drib_pct"], name="% regates exitosos (móvil 5)",
                     line=dict(color=AME_YELLOW, width=2.5))
    efig.add_scatter(x=_dates, y=eff["duel_pct"], name="% duelos ganados (móvil 5)",
                     line=dict(color=AME_BLUE, width=2.5))
    efig.add_hline(y=50, line_dash="dot", line_color="#556677")
    efig.update_layout(
        height=320, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF0FA"), yaxis=dict(range=[0, 100]),
        title="Eficiencia: acierto en regate y duelo (no volumen, calidad)")
    st.plotly_chart(efig, width="stretch")

    # Season-by-season trajectory in four small multiples.
    traj = view.copy()
    traj["season"] = traj["Date"].map(
        lambda d: f"{d.year}-{str(d.year + 1)[2:]}" if d.month >= 7
        else f"{d.year - 1}-{str(d.year)[2:]}")
    seg_rows = []
    for sname, sub in sorted(traj.groupby("season")):
        a = aggregate_per90(sub)
        if a and a["minutes"] >= 360:
            seg_rows.append({"season": sname, **a})
    if len(seg_rows) >= 2:
        st.markdown("**Trayectoria por temporada** (mín. 360′ por temporada):")
        mini = st.columns(4)
        for col, (key, label) in zip(mini, [
                ("ga90", "G+A/90"), ("xg90", "xG/90"),
                ("dribbles90", "Regates/90"), ("duels_pct", "% duelos ganados")]):
            with col:
                mfig2 = go.Figure(go.Bar(
                    x=[r["season"] for r in seg_rows],
                    y=[r[key] for r in seg_rows],
                    marker_color=AME_YELLOW,
                    text=[r[key] for r in seg_rows], textposition="outside"))
                mfig2.update_layout(
                    height=230, margin=dict(l=6, r=6, t=30, b=6), title=label,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#EAF0FA", size=10),
                    yaxis=dict(visible=False))
                st.plotly_chart(mfig2, width="stretch")

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
                    market_ctx = {
                        "group": g,
                        "label": f"{g} — {GROUP_LABELS.get(g, g)}",
                        "score": pseudo_score, "rank": rank, "n": len(gdf),
                        "shared": shared,
                        "similar": mmatches.head(5)[
                            ["Player", "Team", "similarity"]
                        ].to_dict("records"),
                    }
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

                    # FBref-style percentile bars: exact standing per metric.
                    ordered = sorted(pseudo_pct.items(), key=lambda kv: kv[1])
                    pfig2 = go.Figure(go.Bar(
                        x=[v for _, v in ordered],
                        y=[k for k, _ in ordered], orientation="h",
                        marker=dict(color=[v for _, v in ordered],
                                    colorscale=[[0, "#E53935"],
                                                [0.5, "#FFD100"],
                                                [1, "#4CAF50"]],
                                    cmin=0, cmax=100),
                        text=[f"{v:.0f}" for _, v in ordered],
                        textposition="outside"))
                    pfig2.update_layout(
                        height=80 + 40 * len(ordered),
                        margin=dict(l=10, r=40, t=40, b=10),
                        xaxis=dict(range=[0, 108], title="Percentil en el pool"),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#EAF0FA"),
                        title=f"Percentiles de {player} dentro del pool ({g})")
                    st.plotly_chart(pfig2, width="stretch")

                    # Pool scatter: the whole group on two key axes.
                    per90_shared = [c for c in shared if "per 90" in c] or shared
                    xcol = ("Dribbles per 90" if "Dribbles per 90" in shared
                            else per90_shared[0])
                    ycol = ("xG per 90" if "xG per 90" in shared and xcol != "xG per 90"
                            else per90_shared[-1])
                    if xcol != ycol:
                        simnames = mmatches.head(5)["Player"].tolist()
                        rest = gdf[~gdf["Player"].isin(simnames)]
                        simdf = gdf[gdf["Player"].isin(simnames)]
                        sfig = go.Figure()
                        sfig.add_scatter(
                            x=rest[xcol], y=rest[ycol], mode="markers",
                            name="Pool", text=rest["Player"],
                            marker=dict(color="#33507A", size=7, opacity=0.8))
                        sfig.add_scatter(
                            x=simdf[xcol], y=simdf[ycol], mode="markers+text",
                            name="Más parecidos", text=simdf["Player"],
                            textposition="top center",
                            textfont=dict(size=9, color="#9DB4C8"),
                            marker=dict(color=AME_BLUE, size=10))
                        if xcol in profile and ycol in profile:
                            sfig.add_scatter(
                                x=[profile[xcol]], y=[profile[ycol]],
                                mode="markers+text", name=player, text=[player],
                                textposition="top center",
                                textfont=dict(size=11, color=AME_YELLOW),
                                marker=dict(color=AME_YELLOW, size=18,
                                            symbol="star"))
                        sfig.update_layout(
                            height=460, margin=dict(l=10, r=10, t=40, b=10),
                            xaxis=dict(title=xcol), yaxis=dict(title=ycol),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#EAF0FA"),
                            title=f"El pool completo ({len(gdf)} jugadores) — "
                                  "⭐ = " + player)
                        st.plotly_chart(sfig, width="stretch")

# ── Tab 5: social post — X-ready cards + suggested copy ──────────────────────
with tab_social:
    ame_section("DIFUSIÓN", "Post para X — imágenes y texto listos")
    st.caption(
        f"Tarjetas 16:9 (1680×945) con la ventana actual (**{filters_desc}**) "
        "para adjuntar al post. La tarjeta de mercado aparece si cargaste un "
        "pool en **⚖️ vs Market** en esta misma sesión."
    )
    from viz.social_cards import stat_card, form_card, market_card, suggest_posts

    cards: list[tuple[str, bytes]] = [
        ("stats", stat_card(player, team, filters_desc, agg, cons)),
        ("forma", form_card(player, team, ctx)),
    ]
    if market_ctx:
        cards.append(("mercado", market_card(
            player, market_ctx["label"], market_ctx["score"],
            market_ctx["rank"], market_ctx["n"], market_ctx["similar"],
            len(market_ctx["shared"]))))

    cols = st.columns(len(cards))
    for col, (label, png) in zip(cols, cards):
        with col:
            st.image(png, caption=f"Tarjeta: {label}", width="stretch")
            st.download_button(
                f"📥 PNG — {label}", data=png,
                file_name=f"{player.replace(' ', '_')}_{label}.png",
                mime="image/png", key=f"dl_card_{label}",
            )

    # Ganchos: the angles that make a club stop scrolling.
    hooks = scout_hooks(view, ctx, team)
    if hooks:
        ame_section("GANCHOS", "Por qué un club se interesaría")
        hcols = st.columns(min(3, len(hooks)))
        for i, h in enumerate(hooks):
            with hcols[i % len(hcols)]:
                st.markdown(
                    f'<div style="background:#0E1B36;border-radius:10px;'
                    f'padding:0.8rem;margin-bottom:0.6rem;min-height:9rem;">'
                    f'<div style="font-size:1.1rem;">{h["icon"]} '
                    f'<span style="color:#FFD100;font-size:0.72rem;font-weight:700;'
                    f'text-transform:uppercase;">{h["title"]}</span></div>'
                    f'<div style="color:#EAF0FA;font-size:0.78rem;'
                    f'margin-top:0.3rem;">{h["text"]}</div></div>',
                    unsafe_allow_html=True)

    # Publication plan: title options + named, ordered steps with image slots.
    plan = publication_plan(player, team, filters_desc, agg, hooks, market_ctx)
    ame_section("PLAN", "Título y orden de publicación")
    st.markdown("**Opciones de título para el post** (elige una):")
    for t in plan["titles"]:
        st.code(t, language=None)
    st.markdown("**🧵 Hilo, en este orden** — cada paso dice qué imagen adjuntar:")
    for step in plan["steps"]:
        st.markdown(f"**{step['order']}. {step['name']}** · 📎 {step['attach']}")
        st.code(step["text"], language=None)

    with st.expander("Posts sueltos (alternativa al hilo)"):
        for text in suggest_posts(player, team, filters_desc, agg, cons, market_ctx):
            st.code(text, language=None)

# ── Tab 6: PDF ───────────────────────────────────────────────────────────────
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
