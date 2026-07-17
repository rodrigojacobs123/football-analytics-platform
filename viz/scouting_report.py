from __future__ import annotations
"""PDF scouting report generator for the Scouting Hub.

Produces a committee-ready descriptive report (Spanish) from the uploaded
Wyscout market: universe + data quality, distributions, benchmarks, rankings
per style profile (the ARCHETYPES bundles), young-talent shortlists and
highlighted scatters. Modeled on the club's reference report format
(Reporte_LCB_Scouting): navy tables, matplotlib charts, orange highlights.

Layer note: this is presentation (like the rest of viz/) but renders to PDF
bytes instead of Streamlit — no st.* calls here, the page wires the download.
"""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from processing.wyscout_scouting import (
    ARCHETYPES, GROUP_LABELS, ROLE_METRICS, rank_col,
)

# ── Palette (reference report look: navy headers, matplotlib blues) ─────────
NAVY = colors.HexColor("#16395c")
NAVY_LIGHT = colors.HexColor("#eaf1f8")
GRID = colors.HexColor("#9db4c8")
CHART_BLUE = "#2e7ebc"
CHART_ORANGE = "#f28e2b"

_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=21,
                        leading=25, textColor=NAVY, alignment=1, spaceAfter=8)
_SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11.5,
                           leading=14.5, alignment=1, spaceAfter=5)
_META = ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5,
                       textColor=colors.HexColor("#444444"), alignment=1)
_H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13,
                     textColor=NAVY, spaceBefore=14, spaceAfter=6)
_H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5,
                     textColor=colors.HexColor("#1d5c8f"), spaceBefore=10, spaceAfter=4)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.5,
                       spaceAfter=6)
_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.6, leading=9.5)
_FOOT = ParagraphStyle("foot", fontName="Helvetica", fontSize=7.5,
                       textColor=colors.HexColor("#666666"), alignment=1)

# Spanish display names for the metrics that reach tables/comments.
METRIC_ES = {
    "Successful defensive actions per 90": "Acciones defensivas exitosas/90",
    "Defensive duels won, %": "Duelos defensivos ganados %",
    "Aerial duels won, %": "Duelos aéreos ganados %",
    "Aerial duels per 90": "Duelos aéreos/90",
    "PAdj Interceptions": "Intercepciones ajustadas",
    "Shots blocked per 90": "Tiros bloqueados/90",
    "Accurate passes, %": "Precisión de pase %",
    "Passes per 90": "Pases/90",
    "Progressive passes per 90": "Pases progresivos/90",
    "Accurate progressive passes, %": "Precisión pases progresivos %",
    "Accurate long passes, %": "Precisión pase largo %",
    "Progressive runs per 90": "Conducciones progresivas/90",
    "Fouls per 90": "Faltas/90",
    "Yellow cards per 90": "Amarillas/90",
    "Duels won, %": "Duelos ganados %",
    "Crosses per 90": "Centros/90",
    "Accurate crosses, %": "Precisión de centro %",
    "xA per 90": "xA/90",
    "Key passes per 90": "Pases clave/90",
    "Accelerations per 90": "Aceleraciones/90",
    "Passes to final third per 90": "Pases a último tercio/90",
    "Received passes per 90": "Pases recibidos/90",
    "Smart passes per 90": "Pases filtrados/90",
    "xG per 90": "xG/90",
    "Non-penalty goals per 90": "Goles sin penal/90",
    "Touches in box per 90": "Toques en área/90",
    "Shots per 90": "Tiros/90",
    "Shots on target, %": "Tiros a puerta %",
    "Goal conversion, %": "Conversión %",
    "Dribbles per 90": "Regates/90",
    "Successful dribbles, %": "Regates exitosos %",
    "Offensive duels won, %": "Duelos ofensivos ganados %",
    "Deep completions per 90": "Pases al área rival/90",
    "Shot assists per 90": "Asistencias de tiro/90",
    "Head goals per 90": "Goles de cabeza/90",
    "Prevented goals per 90": "Goles evitados/90",
    "Save rate, %": "% de paradas",
    "Conceded goals per 90": "Goles recibidos/90",
    "Exits per 90": "Salidas/90",
    "Aerial duels per 90.1": "Duelos aéreos/90",
    "Passes to penalty area per 90": "Pases al área/90",
    "Through passes per 90": "Pases al hueco/90",
}

# Per-group archetype names in Spanish for section titles.
ARCHETYPE_ES = {
    "Ball-Playing": "Salida de balón", "Stopper": "Stopper",
    "Aerial Dominator": "Juego aéreo", "Mobile Carrier": "Conducción",
    "Attacking": "Ofensivo", "Defensive": "Defensivo",
    "Inverted Playmaker": "Interior/creador", "Destroyer": "Destructor",
    "Deep-Lying Playmaker": "Organizador", "Box-to-Box": "Box-to-box",
    "Playmaker": "Creador", "Ball-Winner": "Recuperador",
    "Creator": "Creador", "Shadow Striker": "Mediapunta llegador",
    "Dribbler": "Regateador", "Direct Dribbler": "Extremo directo",
    "Goal Threat": "Extremo goleador", "Wide Creator": "Extremo centrador",
    "Poacher": "Rematador", "Target Man": "Referencia aérea",
    "Link-Up Forward": "Delantero asociativo",
    "Shot-Stopper": "Atajador", "Sweeper Keeper": "Portero líbero",
    "Distributor": "Portero con pies",
}


def _es(col: str) -> str:
    return METRIC_ES.get(col, col)


def _fig_image(fig, width_cm_: float = 17.0) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    w, h = fig.get_size_inches()
    return Image(buf, width=width_cm_ * cm, height=width_cm_ * cm * h / w)


def _style_axes(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.title.set_fontsize(10.5)


def _table(header: list[str], rows: list[list], col_widths=None) -> Table:
    data = [[Paragraph(f"<b>{h}</b>",
                       ParagraphStyle("th", parent=_CELL, textColor=colors.white))
             for h in header]]
    for r in rows:
        data.append([Paragraph(str(v), _CELL) for v in r])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), NAVY_LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _fmt_value(mv) -> str:
    if pd.isna(mv) or mv == 0:
        return "n.d."
    return f"{mv / 1e6:.1f}".rstrip("0").rstrip(".")


def _fmt_num(v, dec: int = 1) -> str:
    return "n.d." if pd.isna(v) else f"{v:.{dec}f}"


# ── Chart builders (reference-report style) ─────────────────────────────────
def _bar_dist(labels: list[str], counts: list[int], title: str) -> Image:
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    bars = ax.bar(labels, counts, color=CHART_BLUE)
    ax.bar_label(bars, fontsize=8)
    ax.set_ylabel("Jugadores", fontsize=8.5)
    ax.set_title(title)
    _style_axes(ax)
    return _fig_image(fig, 15.5)


def _quality_bar(issues: dict[str, int]) -> Image:
    items = [(k, v) for k, v in issues.items() if v > 0]
    fig, ax = plt.subplots(figsize=(7.2, 0.5 + 0.42 * max(1, len(items))))
    labels = [k for k, _ in items][::-1]
    vals = [v for _, v in items][::-1]
    bars = ax.barh(labels, vals, color=CHART_BLUE)
    ax.bar_label(bars, fontsize=8, padding=2)
    ax.set_xlabel("Jugadores", fontsize=8.5)
    ax.set_title("Principales issues de calidad de datos")
    _style_axes(ax)
    return _fig_image(fig, 15.5)


def _profile_scatter(gdf: pd.DataFrame, xcol: str, ycol: str,
                     top: pd.DataFrame, title: str) -> Image:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.scatter(gdf[xcol], gdf[ycol], s=14, color=CHART_BLUE, alpha=0.45,
               edgecolors="none")
    ax.scatter(top[xcol], top[ycol], s=42, color=CHART_ORANGE, zorder=3)
    for _, r in top.iterrows():
        if pd.notna(r[xcol]) and pd.notna(r[ycol]):
            ax.annotate(r["Player"], (r[xcol], r[ycol]), fontsize=6.5,
                        xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel(_es(xcol), fontsize=8.5)
    ax.set_ylabel(_es(ycol), fontsize=8.5)
    ax.set_title(title)
    _style_axes(ax)
    return _fig_image(fig, 16.0)


# ── Content helpers ─────────────────────────────────────────────────────────
def _quality_issues(pooled: pd.DataFrame) -> dict[str, int]:
    issues = {
        "Valor de mercado = 0": int((pooled["Market value"].fillna(0) == 0).sum()),
        "Contrato sin fecha": int(pooled["Contract expires"].isna().sum()),
        "Pie desconocido": int(pooled["Foot"].isna().sum()
                               + (pooled["Foot"].astype(str).str.lower() == "unknown").sum()),
        "Altura faltante/cero": int((pooled["Height"].fillna(0) == 0).sum()),
        "Peso faltante/cero": int((pooled["Weight"].fillna(0) == 0).sum()),
    }
    pct_cols = [c for c in pooled.columns if c.endswith("%")]
    if pct_cols:
        bad_pct = int((pooled[pct_cols] > 100).any(axis=1).sum())
        if bad_pct:
            issues["% imposibles (>100)"] = bad_pct
    return issues


def _bin_counts(series: pd.Series, edges: list[float],
                labels: list[str]) -> tuple[list[str], list[int]]:
    binned = pd.cut(series, bins=edges, labels=labels, include_lowest=True)
    counts = binned.value_counts().reindex(labels).fillna(0).astype(int)
    return labels, counts.tolist()


def _player_comment(row: pd.Series, gdf_cols: list[str]) -> str:
    """One-liner from the player's two strongest percentile metrics."""
    pcts = {c.removeprefix("pct: "): row[c] for c in gdf_cols
            if c.startswith("pct: ") and pd.notna(row.get(c))}
    if not pcts:
        return ""
    best = sorted(pcts.items(), key=lambda kv: -kv[1])[:2]
    parts = []
    for col, pct in best:
        raw = row.get(col)
        val = f" ({raw:.2f})" if pd.notna(raw) else ""
        grade = "Élite" if pct >= 90 else ("Fuerte" if pct >= 75 else "Correcto")
        parts.append(f"{grade} en {_es(col).lower()}{val}")
    return "; ".join(parts) + "."


def _scatter_axes(group: str, cols: list[str]) -> tuple[str, str] | None:
    """Two highest-weighted per-90 (non-%) role metrics available."""
    per90 = [(c, w) for c, w, _ in ROLE_METRICS.get(group, [])
             if not c.endswith("%") and c in cols]
    if len(per90) < 2:
        return None
    per90.sort(key=lambda t: -t[1])
    return per90[0][0], per90[1][0]


# ── Main entry point ────────────────────────────────────────────────────────
def build_scouting_report(pooled: pd.DataFrame, scored: pd.DataFrame,
                          group: str, min_minutes: int,
                          starred: set[str] | None = None) -> bytes:
    """Render the full PDF for one position group; returns the file bytes.

    ``pooled`` is the pre-filter universe (for data-quality/universe pages);
    ``scored`` is the exploded, scored frame the Hub displays. ``starred``
    marks shortlisted "Player|Team" keys with ★ in ranking tables.
    """
    starred = starred or set()
    RANK = rank_col(scored)
    universe = pooled[pooled["position_groups"].map(lambda g_: group in g_ if isinstance(g_, list) else False)]
    gdf = scored[scored["position_group"] == group]
    if gdf.empty:
        raise ValueError(f"No scored players for group {group}")
    label_es = GROUP_LABELS.get(group, group)
    today = date.today().strftime("%d/%m/%Y")
    header_txt = f"Reporte de Scouting {group} | Análisis descriptivo | {today}"

    def _star(r) -> str:
        return "★ " if f"{r['Player']}|{r['Team']}" in starred else ""

    story: list = []

    # 1 ── Cover / summary ---------------------------------------------------
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(f"Reporte de Scouting — {label_es} ({group})", _TITLE))
    story.append(Paragraph(
        "Análisis descriptivo de universo, calidad de datos, benchmarks y shortlists",
        _SUBTITLE))
    story.append(Paragraph(
        f"Base analizada: {len(pooled)} registros | Rankings: jugadores con "
        f"≥{min_minutes} minutos | Fecha del reporte: {today}", _META))
    story.append(Spacer(1, 0.8 * cm))

    n_universe = len(universe)
    n_ranked = len(gdf[["Player", "Team"]].drop_duplicates())
    n_1500 = int((universe["Minutes played"] >= 1500).sum())
    n_secondary = int((gdf["group_role"] == "secondary").sum())
    feet = universe["Foot"].astype(str).str.lower()
    mv0 = int((universe["Market value"].fillna(0) == 0).sum())
    story.append(_table(
        ["Indicador", "Dato", "Lectura"],
        [
            ["Jugadores analizados", len(pooled), "Universo completo de los archivos subidos"],
            [f"Jugadores del grupo {group}", n_universe,
             f"Incluyen {group} como posición listada"],
            [f"Jugadores ≥{min_minutes} min", n_ranked, "Muestra recomendada para rankings"],
            ["Jugadores ≥1,500 min", n_1500, "Muestra robusta"],
            ["Rol secundario en el grupo", n_secondary,
             "Cubren la posición como segunda opción"],
            ["Pie izquierdo / derecho",
             f"{int((feet == 'left').sum())} / {int((feet == 'right').sum())}",
             "Perfil de lateralidad del universo"],
            ["Valor de mercado = 0", mv0, "Tratar como dato faltante"],
        ],
        col_widths=[6.2 * cm, 3.2 * cm, 7.6 * cm],
    ))
    story.append(Spacer(1, 0.5 * cm))
    top_row = gdf.sort_values(RANK, ascending=False).iloc[0]
    arch_counts = gdf["Archetype"].value_counts()
    arch_txt = ", ".join(f"{ARCHETYPE_ES.get(a, a)} ({n})" for a, n in arch_counts.items())
    story.append(Paragraph(
        f"<b>Conclusión ejecutiva.</b> El filtro de ≥{min_minutes} minutos deja "
        f"{n_ranked} jugadores comparables mediante percentiles dentro del grupo "
        f"{label_es}. La distribución de perfiles es: {arch_txt}. "
        f"El mejor score compuesto del universo es {top_row['Player']} "
        f"({top_row['Team']}, {_fmt_num(top_row[RANK])}). Los rankings por perfil "
        f"—con validación posterior en video— son la vía recomendada para construir "
        f"la shortlist accionable.", _BODY))
    story.append(PageBreak())

    # 2 ── Methodology & data quality ---------------------------------------
    story.append(Paragraph("1. Metodología y calidad de datos", _H2))
    below = len(universe) - int((universe["Minutes played"] >= min_minutes).sum())
    story.append(Paragraph(
        f"<b>Corte de muestra.</b> Los rankings usan jugadores con al menos "
        f"{min_minutes} minutos. Los {below} jugadores por debajo de ese umbral se "
        f"mantienen como radar, pero no deberían compararse directamente con la "
        f"muestra principal.", _BODY))
    story.append(Paragraph(
        "<b>Método.</b> Cada métrica se convierte a percentil dentro del grupo "
        "posicional y se pondera según el rol; los jugadores polivalentes se "
        "evalúan en cada grupo que cubren contra la muestra correcta. El valor de "
        "mercado igual a cero se trata como dato faltante y no como precio de "
        "adquisición.", _BODY))
    issues = _quality_issues(pooled)
    story.append(_quality_bar(issues))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_table(
        ["Issue", "Registros afectados", "Implicación"],
        [
            ["Valor de mercado = 0", issues.get("Valor de mercado = 0", 0),
             "No interpretar como oportunidad de bajo costo"],
            ["Contrato sin fecha", issues.get("Contrato sin fecha", 0),
             "Limita priorización por vencimiento"],
            ["Pie desconocido", issues.get("Pie desconocido", 0),
             "Revisar manualmente antes de shortlist final"],
            ["Altura/peso faltante o cero",
             f"{issues.get('Altura faltante/cero', 0)} / {issues.get('Peso faltante/cero', 0)}",
             "Afecta lectura física y juego aéreo"],
            ["Header duplicado: Aerial duels per 90", 2,
             "Usar la primera columna para jugadores de campo"],
        ],
        col_widths=[5.6 * cm, 3.6 * cm, 7.8 * cm],
    ))

    # 3 ── Universe ----------------------------------------------------------
    story.append(Paragraph("2. Lectura del universo", _H2))
    age = universe["Age"].dropna()
    labels, counts = _bin_counts(age, [0, 21, 24, 28, 32, 99],
                                 ["≤21", "22-24", "25-28", "29-32", "33+"])
    story.append(_bar_dist(labels, counts, "Distribución por edad"))
    mins = universe["Minutes played"].fillna(0)
    labels, counts = _bin_counts(mins, [-1, 449, 899, 1499, 2499, 99999],
                                 ["<450", "450-899", "900-1499", "1500-2499", "2500+"])
    story.append(_bar_dist(labels, counts, "Distribución por minutos"))
    mv = universe["Market value"].fillna(0)
    labels, counts = _bin_counts(mv, [-1, 0, 1e6 - 1, 5e6, 15e6, 30e6, 9e9],
                                 ["0/missing", "<€1m", "€1-5m", "€5-15m", "€15-30m", "€30m+"])
    story.append(_bar_dist(labels, counts, "Distribución por valor de mercado"))
    story.append(PageBreak())

    # 4 ── Benchmarks --------------------------------------------------------
    story.append(Paragraph(f"3. Benchmarks de la muestra ≥{min_minutes} minutos", _H2))
    story.append(Paragraph(
        "<b>Uso recomendado.</b> Para una criba inicial, el cuartil superior puede "
        "usarse como umbral de alerta positiva. La mediana sirve como línea base "
        "para evaluar si un candidato está por encima, en línea o por debajo de la "
        "muestra comparable.", _BODY))
    bench_rows = []
    for col, _, _ in ROLE_METRICS.get(group, []):
        if col not in gdf.columns:
            continue
        s = gdf[col].dropna()
        if s.empty:
            continue
        bench_rows.append([_es(col), _fmt_num(s.quantile(0.25)),
                           _fmt_num(s.median()), _fmt_num(s.quantile(0.75))])
    story.append(_table(["Métrica", "P25", "Mediana", "P75"], bench_rows,
                        col_widths=[8.0 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm]))

    # 5 ── Rankings per profile ---------------------------------------------
    story.append(Paragraph("4. Rankings por perfil", _H2))
    story.append(Paragraph(
        "<b>Lectura.</b> Los scores son descriptivos y no ajustan por posesión del "
        "equipo, rol táctico ni calidad de rivales (el ajuste por nivel de liga "
        "aplica solo si se etiquetó cada archivo). Sirven como primer filtro para "
        "orientar video scouting y validación contextual.", _BODY))
    header = ["Jugador", "Equipo", "Edad", "Pie", "Min.", "Valor €m", "Score"]
    widths = [4.2 * cm, 3.4 * cm, 1.4 * cm, 1.4 * cm, 1.8 * cm, 2.0 * cm, 1.8 * cm]

    def _rank_rows(sub: pd.DataFrame, score_col: str) -> list[list]:
        return [[_star(r) + str(r["Player"]), r.get("Team", ""),
                 _fmt_num(r.get("Age"), 0), str(r.get("Foot", "?"))[:1].upper(),
                 _fmt_num(r.get("Minutes played"), 0), _fmt_value(r.get("Market value")),
                 _fmt_num(r.get(score_col))]
                for _, r in sub.iterrows()]

    for arch_label, _cols in ARCHETYPES.get(group, []):
        col = f"arch: {arch_label}"
        if col not in gdf.columns:
            continue
        sub = gdf.sort_values(col, ascending=False).head(6)
        story.append(Paragraph(ARCHETYPE_ES.get(arch_label, arch_label), _H3))
        story.append(_table(header, _rank_rows(sub, col), widths))
    story.append(Paragraph("Equilibrado (score compuesto)", _H3))
    story.append(_table(header,
                        _rank_rows(gdf.sort_values(RANK, ascending=False).head(6), RANK),
                        widths))
    story.append(PageBreak())

    # 6 ── Young talent ------------------------------------------------------
    story.append(Paragraph("5. Talento joven y oportunidades de valor", _H2))
    gdf_cols = list(gdf.columns)
    young = gdf[gdf["Age"] <= 23].sort_values(RANK, ascending=False).head(6)
    if not young.empty:
        story.append(Paragraph("<b>Menores de 24.</b> Producción suficiente y "
                               "perfiles diferenciados dentro de la muestra.", _BODY))
        rows = [[_star(r) + str(r["Player"]), r["Team"], _fmt_num(r["Age"], 0),
                 _fmt_num(r["Minutes played"], 0), _fmt_value(r["Market value"]),
                 _fmt_num(r[RANK]), _player_comment(r, gdf_cols)]
                for _, r in young.iterrows()]
        story.append(_table(
            ["Jugador", "Equipo", "Edad", "Min.", "Valor €m", "Score", "Lectura"],
            rows, col_widths=[3.0 * cm, 2.6 * cm, 1.2 * cm, 1.5 * cm,
                              1.8 * cm, 1.5 * cm, 5.4 * cm]))
    value = gdf[(gdf["Age"] <= 25) & (gdf["Market value"].between(1, 10e6))]
    value = value.sort_values(RANK, ascending=False).head(6)
    if not value.empty:
        story.append(Paragraph("U25 con valor positivo hasta €10m", _H3))
        story.append(_table(header, _rank_rows(value, RANK), widths))

    # 7 ── Usage recommendation ---------------------------------------------
    story.append(Paragraph("6. Recomendación de uso", _H2))
    for txt in (
        "<b>Usar percentiles por perfil:</b> evitar un ranking único — cada "
        "arquetipo debe evaluarse con pesos distintos, como hace este reporte.",
        "<b>Validar en video:</b> confirmar orientación corporal, defensa de "
        "espacio, timing de duelos y perfil de pase bajo presión antes de "
        "cualquier decisión.",
        "<b>Agregar contexto de equipo y liga:</b> ajustar por posesión, bloque "
        "defensivo, altura de línea y calidad de rivales antes de recomendar "
        "inversión.",
    ):
        story.append(Paragraph(txt, _BODY))
    story.append(PageBreak())

    # 8 ── Profile scatters --------------------------------------------------
    for arch_label, arch_cols in ARCHETYPES.get(group, []):
        cols_avail = [c for c in arch_cols if c in gdf.columns]
        if len(cols_avail) < 2:
            continue
        xcol, ycol = cols_avail[0], cols_avail[1]
        col = f"arch: {arch_label}"
        if col not in gdf.columns:
            continue
        top = gdf.sort_values(col, ascending=False).head(8)
        es = ARCHETYPE_ES.get(arch_label, arch_label)
        story.append(Paragraph(f"Parte 4 / Perfil {es}", _H3))
        story.append(_profile_scatter(
            gdf, xcol, ycol, top, f"Perfil {es} — jugadores destacados"))
        story.append(Paragraph(
            f"Los nombres destacados corresponden a los líderes del perfil {es.lower()}.",
            _BODY))
        story.append(PageBreak())

    # 9 ── Shortlist scatters ------------------------------------------------
    axes = _scatter_axes(group, list(gdf.columns))
    if axes:
        xcol, ycol = axes
        young_all = gdf[gdf["Age"] <= 23]
        if len(young_all) >= 5:
            top = young_all.sort_values(RANK, ascending=False).head(10)
            story.append(Paragraph("Parte 5 / Shortlist U23", _H3))
            story.append(_profile_scatter(
                gdf, xcol, ycol, top, "Shortlist U23 — jugadores destacados"))
            story.append(Paragraph(
                "La visualización identifica a los jóvenes con mejor combinación "
                "de producción y proyección.", _BODY))
            story.append(PageBreak())
    with_value = gdf[gdf["Market value"] > 0].copy()
    if len(with_value) >= 5:
        with_value["Valor €m"] = with_value["Market value"] / 1e6
        top = with_value[with_value["Age"] <= 25].sort_values(
            "value_index", ascending=False).head(10)
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        ax.scatter(with_value["Valor €m"], with_value[RANK], s=14,
                   color=CHART_BLUE, alpha=0.45, edgecolors="none")
        ax.scatter(top["Market value"] / 1e6, top[RANK], s=42,
                   color=CHART_ORANGE, zorder=3)
        for _, r in top.iterrows():
            ax.annotate(r["Player"], (r["Market value"] / 1e6, r[RANK]),
                        fontsize=6.5, xytext=(4, 3), textcoords="offset points")
        ax.set_xlabel("Valor de mercado (€m)", fontsize=8.5)
        ax.set_ylabel("Score compuesto", fontsize=8.5)
        ax.set_title("Shortlist U25 valor — score vs precio")
        _style_axes(ax)
        story.append(Paragraph("Parte 5 / Shortlist U25 valor", _H3))
        story.append(_fig_image(fig, 16.0))
        story.append(Paragraph(
            "La visualización permite identificar oportunidades de mercado con "
            "buena relación score/valor.", _BODY))

    # ── Build with running header/footer ────────────────────────────────────
    buf = io.BytesIO()

    def _decorate(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(1.6 * cm, letter[1] - 1.0 * cm, header_txt)
        canvas.drawCentredString(letter[0] / 2, 0.9 * cm, header_txt)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.5 * cm,
        title=f"Reporte de Scouting {group}",
    )
    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buf.getvalue()
