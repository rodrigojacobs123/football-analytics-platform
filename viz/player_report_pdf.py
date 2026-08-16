from __future__ import annotations
"""Individual player PDF (ficha de scouting) from a Wyscout match-by-match export.

Follows the 8-section committee format (profile → performance → strengths →
charts → context → video checklist → recommendation) and REFLECTS THE PAGE
FILTERS: the caller passes the already-filtered match set plus a human
description of the active filters, which is printed under the title so the
committee knows exactly what window they are reading.

Reuses the look of viz/scouting_report.py (navy headers, Helvetica, matplotlib
figures embedded as images).
"""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
)

from viz.scouting_report import (  # shared look & helpers
    NAVY, CHART_BLUE, CHART_ORANGE,
    _TITLE, _SUBTITLE, _META, _H2, _H3, _BODY, _FOOT,
    _fig_image, _style_axes, _table,
)
from processing.wyscout_player import (
    aggregate_per90, competition_split, consistency, form_series,
    strengths_weaknesses, ATTACKER_REFERENCE,
)


def _timeline_fig(fs: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    x = range(len(fs))
    ax.bar(x, fs["ga"], color=CHART_ORANGE, alpha=0.55, label="G+A del partido")
    ax.plot(x, fs["xg90_roll"], color=CHART_BLUE, lw=2, label="xG/90 (móvil 5)")
    ax.plot(x, fs["ga90_roll"], color=NAVY.hexval().replace("0x", "#"), lw=2,
            ls="--", label="G+A/90 (móvil 5)")
    step = max(1, len(fs) // 9)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels(fs["Date"].dt.strftime("%b %y").tolist()[::step], fontsize=7)
    ax.set_title("Forma: producción por partido y tendencia", fontsize=10)
    ax.legend(fontsize=7.5, loc="upper left")
    _style_axes(ax)
    return fig


def _volume_fig(fs: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = range(len(fs))
    ax.plot(x, fs["dribbles90_roll"], color=CHART_BLUE, lw=2, label="Regates/90 (móvil 5)")
    ax.plot(x, fs["duels90_roll"] / 4.0, color=CHART_ORANGE, lw=2,
            label="Duelos/90 ÷4 (móvil 5)")
    step = max(1, len(fs) // 9)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels(fs["Date"].dt.strftime("%b %y").tolist()[::step], fontsize=7)
    ax.set_title("Volumen de conducción y duelo", fontsize=10)
    ax.legend(fontsize=7.5, loc="upper left")
    _style_axes(ax)
    return fig


def _minutes_fig(fs: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    comps = fs["Competition"].astype("category")
    palette = plt.get_cmap("tab10")
    color_by = {c: palette(i % 10) for i, c in enumerate(comps.cat.categories)}
    ax.bar(range(len(fs)), fs["Minutes played"],
           color=[color_by[c] for c in fs["Competition"]])
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_by[c])
               for c in comps.cat.categories]
    ax.legend(handles, list(comps.cat.categories), fontsize=6.5, ncol=2,
              loc="upper left")
    step = max(1, len(fs) // 9)
    ax.set_xticks(list(range(len(fs)))[::step])
    ax.set_xticklabels(fs["Date"].dt.strftime("%b %y").tolist()[::step], fontsize=7)
    ax.set_title("Minutos por partido y competición", fontsize=10)
    _style_axes(ax)
    return fig


def _bench_fig(agg: dict):
    """Player vs approximate top-league starter reference (labelled as such)."""
    rows = [
        ("G+A/90", agg["ga90"], ATTACKER_REFERENCE["ga90"]),
        ("xG/90", agg["xg90"], ATTACKER_REFERENCE["xg90"]),
        ("Tiros/90", agg["shots90"], ATTACKER_REFERENCE["shots90"]),
        ("Regates/90", agg["dribbles90"], ATTACKER_REFERENCE["dribbles90"]),
        ("Regates %", agg["dribbles_pct"] / 10, ATTACKER_REFERENCE["dribbles_pct"] / 10),
        ("Duelos %", agg["duels_pct"] / 10, ATTACKER_REFERENCE["duels_pct"] / 10),
        ("Pase %", agg["passes_pct"] / 10, ATTACKER_REFERENCE["passes_pct"] / 10),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    y = range(len(rows))
    ax.barh([i + 0.18 for i in y], [r[1] for r in rows], height=0.36,
            color=CHART_BLUE, label="Jugador (ventana filtrada)")
    ax.barh([i - 0.18 for i in y], [r[2] for r in rows], height=0.36,
            color="#b7c9d8", label="Referencia titular liga top (aprox.)")
    ax.set_yticks(list(y))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.legend(fontsize=7.5, loc="lower right")
    ax.set_title("Perfil vs referencia (los % van divididos entre 10)", fontsize=10)
    _style_axes(ax)
    return fig


def _verdict(agg: dict, cons: dict) -> tuple[str, str]:
    """Rule-based verdict + rationale paragraph."""
    if agg["ga90"] >= 0.45 and agg["matches"] >= 10:
        v = "FICHAR / AVANZAR"
        why = ("Producción de nivel titular sostenida en la ventana analizada. "
               "Pasar a verificación de video y contexto contractual.")
    elif agg["dribbles90"] >= 3 or agg["duels90"] >= 18:
        v = "SEGUIR DE CERCA"
        why = ("Volumen de intervención (conducción/duelo) por encima de su "
               "producción final: perfil de proyecto cuyo precio subirá en "
               "cuanto los G+A acompañen. La ventana de oportunidad es antes "
               "de esa explosión; el riesgo, que nunca llegue.")
    else:
        v = "MONITORIZAR"
        why = ("Ni la producción ni el volumen destacan en la ventana filtrada. "
               "Reevaluar con más partidos o en otro rol.")
    return v, why


def build_player_report(filtered: pd.DataFrame, full: pd.DataFrame,
                        player_name: str, team: str,
                        filters_desc: str) -> bytes:
    """Render the ficha PDF for the FILTERED window (full sample = context)."""
    agg = aggregate_per90(filtered)
    if not agg:
        raise ValueError("No matches after filters — nothing to report.")
    cons = consistency(filtered)
    fs = form_series(filtered)
    S, W = strengths_weaknesses(agg)
    verdict, why = _verdict(agg, cons)
    split = competition_split(filtered)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        leftMargin=1.7 * cm, rightMargin=1.7 * cm,
        title=f"Ficha de scouting — {player_name}")
    story = []

    # Header
    story.append(Paragraph("FICHA DE SCOUTING", _TITLE))
    story.append(Paragraph(f"<b>{player_name}</b> — {team}", _SUBTITLE))
    story.append(Paragraph(
        f"Ventana analizada: {filters_desc} · Generado {date.today():%d/%m/%Y} · "
        "Fuente: export Wyscout partido a partido", _META))
    story.append(Spacer(1, 10))

    # 1 · Perfil
    story.append(Paragraph("1 · Perfil", _H2))
    d0, d1 = filtered["Date"].min(), filtered["Date"].max()
    full0 = full["Date"].min()
    story.append(_table(
        ["Campo", "Valor"],
        [["Club", team],
         ["Ventana", f"{d0:%d/%m/%Y} → {d1:%d/%m/%Y} "
                     f"({agg['matches']} partidos, {agg['minutes']}′)"],
         ["Posiciones en la ventana",
          ", ".join(filtered["Position"].astype(str).str.split(",")
                    .explode().str.strip().value_counts().head(5).index)],
         ["Historial en archivo", f"desde {full0:%m/%Y} ({len(full)} partidos)"],
         ["Titular (≥60′) / completos", f"{cons['starts']} / {cons['full_matches']}"]],
        col_widths=[5.2 * cm, 11.8 * cm]))
    story.append(Paragraph(
        "Edad, pie, altura, valor de mercado y contrato no vienen en este "
        "export — completar con 'Search results' o Transfermarkt antes de comité.",
        _FOOT))

    # 2 · Rendimiento
    story.append(Paragraph("2 · Resumen de rendimiento (ventana filtrada)", _H2))
    story.append(_table(
        ["Métrica", "Total", "Per 90", "Métrica", "Per 90 / %"],
        [["Goles", agg["goals"], agg["goals90"], "Regates",
          f"{agg['dribbles90']} ({agg['dribbles_pct']:.0f}%)"],
         ["Asistencias", agg["assists"], agg["assists90"], "Duelos",
          f"{agg['duels90']} ({agg['duels_pct']:.0f}%)"],
         ["xG", agg["xg"], agg["xg90"], "Aéreos",
          f"{agg['aerials90']} ({agg['aerials_pct']:.0f}%)"],
         ["G+A", agg["goals"] + agg["assists"], agg["ga90"], "Pases",
          f"{agg['passes90']} ({agg['passes_pct']:.0f}%)"],
         ["Tiros/90", "—", f"{agg['shots90']} ({agg['shots_pct']:.0f}% puerta)",
          "Recuperaciones", agg["recoveries90"]],
         ["Amarillas/Rojas", f"{agg['yellows']}/{agg['reds']}", "—",
          "Pérdidas", agg["losses90"]]],
        col_widths=[3.4 * cm, 2.2 * cm, 3.4 * cm, 3.6 * cm, 4.4 * cm]))
    story.append(Paragraph(
        f"Consistencia: marca o asiste en el {cons['ga_matches_pct']:.0f}% de los "
        f"partidos de la ventana; racha máxima sin G+A: {cons['max_drought']} "
        f"partidos; media {cons['avg_minutes']:.0f}′ por partido.", _BODY))

    # 3 · Fortalezas / mejoras
    story.append(Paragraph("3 · Fortalezas y áreas de mejora", _H2))
    for s in S:
        story.append(Paragraph(f"+  {s}", _BODY))
    if W:
        story.append(Paragraph("Áreas de mejora", _H3))
        for w in W:
            story.append(Paragraph(f"–  {w}", _BODY))

    story.append(PageBreak())

    # 4 · Visual
    story.append(Paragraph("4 · Insights visuales", _H2))
    story.append(_fig_image(_timeline_fig(fs)))
    story.append(_fig_image(_volume_fig(fs)))
    story.append(_fig_image(_minutes_fig(fs)))
    story.append(PageBreak())

    # 5-6 · Contexto + comparación
    story.append(Paragraph("5 · Contexto por competición", _H2))
    story.append(_table(
        list(split.columns),
        split.astype(str).values.tolist(),
        col_widths=[6.4 * cm, 1.4 * cm, 1.6 * cm, 1.6 * cm, 1.6 * cm,
                    1.6 * cm, 1.9 * cm, 1.6 * cm]))
    story.append(Paragraph("6 · Comparación vs referencia", _H2))
    story.append(_fig_image(_bench_fig(agg)))
    story.append(Paragraph(
        "La referencia es un estándar APROXIMADO de titular ofensivo en liga "
        "top-5, no un percentil calculado: este export no incluye grupo de "
        "comparación. Para percentiles exactos, cruzar con un 'Search results' "
        "de su posición en el Scouting Hub.", _FOOT))

    # 7 · Recomendación
    story.append(Paragraph("7 · Recomendación", _H2))
    story.append(Paragraph(f"<b>VEREDICTO: {verdict}</b>", _BODY))
    story.append(Paragraph(why, _BODY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Este informe se generó con los filtros indicados en la cabecera; "
        "otras ventanas (temporada completa, solo liga, últimos 5) pueden "
        "contar historias distintas — compárese antes de decidir.", _FOOT))

    doc.build(story)
    plt.close("all")
    return buf.getvalue()
