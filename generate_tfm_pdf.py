"""Generate Jacobs_Rodrigo_TFM_EntregaFinal.pdf — Master's Thesis presentation."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

OUT = os.path.join(os.path.dirname(__file__), "Jacobs_Rodrigo_TFM_EntregaFinal.pdf")

NAVY = HexColor("#04132E")
GOLD = HexColor("#FFD100")
BLUE = HexColor("#2E6BD6")
SURFACE = HexColor("#0A1F44")
TEXT = HexColor("#222222")
GRAY = HexColor("#555555")
LIGHT_BG = HexColor("#F4F6FA")
ACCENT = HexColor("#1A3A6E")

W, H = A4

styles = {
    "cover_title": ParagraphStyle("cover_title", fontSize=22, leading=28,
        textColor=white, alignment=TA_CENTER, fontName="Helvetica-Bold",
        spaceAfter=8),
    "cover_sub": ParagraphStyle("cover_sub", fontSize=13, leading=18,
        textColor=HexColor("#CCCCCC"), alignment=TA_CENTER, fontName="Helvetica"),
    "cover_author": ParagraphStyle("cover_author", fontSize=14, leading=20,
        textColor=GOLD, alignment=TA_CENTER, fontName="Helvetica-Bold",
        spaceAfter=4),
    "section_num": ParagraphStyle("section_num", fontSize=11, leading=14,
        textColor=BLUE, fontName="Helvetica-Bold", spaceAfter=2),
    "h1": ParagraphStyle("h1", fontSize=18, leading=24, textColor=NAVY,
        fontName="Helvetica-Bold", spaceAfter=10, spaceBefore=6),
    "h2": ParagraphStyle("h2", fontSize=13, leading=17, textColor=ACCENT,
        fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=10),
    "body": ParagraphStyle("body", fontSize=10, leading=15, textColor=TEXT,
        fontName="Helvetica", alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontSize=10, leading=15, textColor=TEXT,
        fontName="Helvetica", alignment=TA_LEFT, spaceAfter=4,
        leftIndent=18, bulletIndent=6),
    "toc": ParagraphStyle("toc", fontSize=11, leading=18, textColor=TEXT,
        fontName="Helvetica", spaceAfter=3, leftIndent=10),
    "caption": ParagraphStyle("caption", fontSize=9, leading=12, textColor=GRAY,
        fontName="Helvetica-Oblique", alignment=TA_CENTER, spaceAfter=8),
    "footer": ParagraphStyle("footer", fontSize=8, leading=10, textColor=GRAY,
        fontName="Helvetica", alignment=TA_CENTER),
    "metric_name": ParagraphStyle("metric_name", fontSize=10, leading=14,
        textColor=ACCENT, fontName="Helvetica-Bold", spaceAfter=2),
    "metric_desc": ParagraphStyle("metric_desc", fontSize=9.5, leading=14,
        textColor=TEXT, fontName="Helvetica", spaceAfter=8, leftIndent=12),
}


def cover_page(story):
    story.append(Spacer(1, 4 * cm))
    # Navy banner via table
    banner_data = [[""]]
    banner = Table(banner_data, colWidths=[16 * cm], rowHeights=[8 * cm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, GOLD),
    ]))

    inner = []
    inner.append(Spacer(1, 1.2 * cm))
    inner.append(Paragraph("TRABAJO FINAL DE MASTER", styles["cover_sub"]))
    inner.append(Spacer(1, 0.5 * cm))
    inner.append(Paragraph(
        "Plataforma de Analisis Deportivo<br/>para Club America", styles["cover_title"]))
    inner.append(Spacer(1, 0.3 * cm))
    inner.append(Paragraph(
        "Herramienta de Inteligencia Futbolistica con Datos Opta", styles["cover_sub"]))
    inner.append(Spacer(1, 0.8 * cm))
    inner.append(Paragraph("Rodrigo Jacobs", styles["cover_author"]))
    inner.append(Spacer(1, 0.2 * cm))
    inner.append(Paragraph("Master en Sports Analytics", styles["cover_sub"]))
    inner.append(Paragraph("Junio 2026", styles["cover_sub"]))

    cell_content = inner
    banner_data2 = [[cell_content]]
    banner2 = Table(banner_data2, colWidths=[16 * cm], rowHeights=[9 * cm])
    banner2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 1.5, GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(banner2)
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "GitHub: https://github.com/rodrigojacobs123/football-analytics-platform",
        ParagraphStyle("link", fontSize=9, textColor=BLUE, alignment=TA_CENTER, fontName="Helvetica")))
    story.append(PageBreak())


def section(story, num, title):
    story.append(Paragraph(f"SECCION {num}", styles["section_num"]))
    story.append(Paragraph(title, styles["h1"]))
    line_data = [[""]]
    line = Table(line_data, colWidths=[16 * cm], rowHeights=[2])
    line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
    story.append(line)
    story.append(Spacer(1, 0.4 * cm))


def bullet(story, text):
    story.append(Paragraph(f"<bullet>&bull;</bullet> {text}", styles["bullet"]))


def sub_heading(story, text):
    story.append(Paragraph(text, styles["h2"]))


def body(story, text):
    story.append(Paragraph(text, styles["body"]))


def metric_block(story, name, desc):
    story.append(Paragraph(name, styles["metric_name"]))
    story.append(Paragraph(desc, styles["metric_desc"]))


def kpi_table(story, data, col_widths=None):
    if col_widths is None:
        col_widths = [4 * cm, 12 * cm]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))


def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,
        title="Jacobs_Rodrigo_TFM_EntregaFinal",
        author="Rodrigo Jacobs",
    )
    story = []

    # ── COVER ──
    cover_page(story)

    # ── TABLE OF CONTENTS ──
    section(story, "0", "Indice")
    toc_items = [
        ("1", "Contexto del Proyecto"),
        ("2", "Objetivos"),
        ("3", "Metodologia"),
        ("4", "Desarrollo de la Herramienta"),
        ("5", "Analisis Realizado — Metricas Avanzadas"),
        ("6", "Resultados"),
        ("7", "Conclusiones"),
        ("8", "Toma de Decisiones"),
        ("9", "Referencias Tecnicas"),
        ("10", "Anexo — Repositorio y Estructura"),
    ]
    for num, title in toc_items:
        story.append(Paragraph(
            f"<b>{num}.</b>&nbsp;&nbsp;{title}", styles["toc"]))
    story.append(PageBreak())

    # ── 1. CONTEXTO ──
    section(story, "1", "Contexto del Proyecto")
    body(story,
        "El presente Trabajo Final de Master desarrolla una plataforma integral de "
        "analisis deportivo para el <b>Club America</b> (Liga MX), disenada para "
        "transformar datos de eventos Opta en inteligencia futbolistica accionable.")
    body(story,
        "La plataforma procesa un dataset masivo de <b>47 GB</b> compuesto por "
        "<b>38,271 archivos</b> JSON de eventos Opta, cubriendo <b>22 competiciones</b> "
        "de Norteamerica y CONCACAF con temporadas desde 2010 hasta 2026.")

    sub_heading(story, "Competiciones cubiertas")
    bullet(story, "<b>Mexico:</b> Liga MX, Copa MX, Supercopa MX")
    bullet(story, "<b>CONCACAF:</b> Champions Cup, Leagues Cup, Gold Cup, Nations League, "
           "Clasificatorios al Mundial, U17, U20, Campeones Cup")
    bullet(story, "<b>Estados Unidos:</b> MLS, USL Championship, USL League One, "
           "MLS Next Pro, US Open Cup")
    bullet(story, "<b>Canada:</b> Canadian Premier League")

    body(story,
        "La herramienta esta orientada al cuerpo tecnico del club (entrenadores, "
        "analistas, direccion deportiva y scouting), proporcionando analisis de "
        "partidos, inteligencia tactica, evaluacion de jugadores y preparacion "
        "de rivales en una interfaz web interactiva.")
    story.append(PageBreak())

    # ── 2. OBJETIVOS ──
    section(story, "2", "Objetivos")
    sub_heading(story, "Objetivo principal")
    body(story,
        "Construir una plataforma end-to-end que transforme datos crudos de eventos "
        "Opta (JSON) en inteligencia futbolistica accionable, cubriendo todo el ciclo "
        "de trabajo analitico: preparacion pre-partido, analisis tactico, revision "
        "post-partido, scouting de jugadores y toma de decisiones estrategicas.")

    sub_heading(story, "Objetivos secundarios")
    bullet(story, "Desarrollar <b>metricas avanzadas</b> mas alla de las estadisticas basicas: "
           "xG, xT, xGOT, xDEF, PPDA, field tilt, action value (VAEP)")
    bullet(story, "Crear <b>visualizaciones profesionales</b>: mapas de tiro, heatmaps, "
           "redes de pases, formaciones, graficos radar, diagramas de pizza")
    bullet(story, "Implementar <b>modelos predictivos</b> para preparacion de partidos: "
           "sistema Elo + Poisson + correccion Dixon-Coles")
    bullet(story, "Soportar <b>scouting</b> con ratings estilo FC (PAC/SHO/PAS/DRI/DEF/PHY) "
           "y deteccion de arquetipos de jugador")
    bullet(story, "Proporcionar <b>inteligencia tactica</b>: formaciones, intensidad de "
           "pressing, transiciones, jugadas a balon parado")
    story.append(PageBreak())

    # ── 3. METODOLOGIA ──
    section(story, "3", "Metodologia")
    sub_heading(story, "Stack tecnologico")
    tech_data = [
        ["Tecnologia", "Uso"],
        ["Python 3.9+", "Lenguaje principal de desarrollo"],
        ["Streamlit", "Framework web para dashboards interactivos"],
        ["Pandas / NumPy", "Procesamiento y analisis de datos tabulares"],
        ["Plotly", "Graficos interactivos (xG race, barras, scatter)"],
        ["mplsoccer", "Visualizaciones sobre cancha (shot maps, heatmaps, formaciones)"],
        ["scikit-learn", "Modelo de xG (regresion logistica)"],
        ["ReportLab", "Generacion de reportes PDF"],
    ]
    kpi_table(story, tech_data, [4 * cm, 12 * cm])

    sub_heading(story, "Arquitectura de 4 capas")
    body(story, "La aplicacion sigue un diseno modular en 4 capas claramente separadas:")
    bullet(story, "<b>Capa de Datos</b> (data/): paths.py, loader.py, event_parser.py — "
           "lectura de JSON/CSV con cache TTL de 1 hora via @st.cache_data")
    bullet(story, "<b>Capa de Procesamiento</b> (processing/): 42 modulos de analitica "
           "pure-pandas — funciones que reciben DataFrames y devuelven DataFrames/dicts, "
           "sin dependencias de Streamlit")
    bullet(story, "<b>Capa de Visualizacion</b> (viz/): 14 modulos — Plotly charts, "
           "mplsoccer pitches, componentes HTML con design tokens CSS")
    bullet(story, "<b>Capa de Paginas</b> (pages/): 11 dashboards interactivos registrados "
           "explicitamente en app.py via st.navigation")

    sub_heading(story, "Proceso ETL")
    body(story,
        "El flujo de datos sigue el patron: <b>JSON Opta crudo</b> &rarr; event_parser.py "
        "extrae DataFrames tipados (shots, passes, tackles, etc.) &rarr; modulos de "
        "processing computan metricas avanzadas &rarr; modulos de viz renderizan "
        "visualizaciones interactivas. El sistema de cache de Streamlit (TTL=3600s) "
        "evita re-parsear los archivos JSON en cada interaccion del usuario.")

    sub_heading(story, "Escala del proyecto")
    scale_data = [
        ["Metrica", "Valor"],
        ["Lineas de codigo", "29,243"],
        ["Modulos de procesamiento", "42"],
        ["Modulos de visualizacion", "14"],
        ["Dashboards interactivos", "11"],
        ["Competiciones cubiertas", "22"],
        ["Temporadas", "12+ (2010-2026)"],
        ["Tamano del dataset", "47 GB / 38,271 archivos"],
    ]
    kpi_table(story, scale_data, [5 * cm, 11 * cm])
    story.append(PageBreak())

    # ── 4. DESARROLLO ──
    section(story, "4", "Desarrollo de la Herramienta")
    body(story,
        "La plataforma cuenta con <b>11 dashboards interactivos</b>, cada uno disenado "
        "para cubrir un aspecto especifico del analisis futbolistico:")

    dashboards = [
        ("Season Dashboard (Home)",
         "KPI cards con posicion en liga, puntos, record W-D-L, diferencia de goles. "
         "Tabla de posiciones, tendencias cross-temporada. Filtro de torneo "
         "Apertura/Clausura especifico para Liga MX."),
        ("Pre-Match Analysis",
         "Ratings Elo dinamicos, historial H2H, comparacion radar, prediccion Poisson "
         "con simulacion Monte Carlo (100,000 iteraciones) y correccion Dixon-Coles "
         "para resultados de marcador bajo."),
        ("Post-Match Analysis",
         "Grafico xG race, mapas de tiro, heatmaps, redes de pases, visualizacion de "
         "formaciones con posiciones canonicas y promedio, ratings de partido, timeline "
         "de eventos clave, analisis de jugadas a balon parado."),
        ("Tactics",
         "Deteccion de formacion via qualifier 130, redes de pases por tiempo, acciones "
         "defensivas, pases progresivos, PPDA, field tilt, intensidad de pressing, "
         "momentum xT."),
        ("Player Scouting",
         "Ratings estilo FC (PAC/SHO/PAS/DRI/DEF/PHY), deteccion de arquetipos de "
         "estilo de juego, leaderboards a nivel liga con filtros por posicion."),
        ("xG Explorer",
         "Explorador interactivo de mapas de tiro con filtros por equipo, jugador, "
         "tipo de disparo y resultado."),
        ("Injury Tracker",
         "Inteligencia sintetica de lesiones con timeline y analisis de patrones."),
        ("Data Sources",
         "Diagnosticos del dataset, conteo de archivos por competicion/temporada, "
         "documentacion del schema Opta."),
        ("Manager Profiles",
         "Comparacion de entrenadores, huellas tacticas, historial de resultados."),
        ("Corner Defense",
         "Inteligencia defensiva en corners, analisis por tipo de entrega (inswing, "
         "outswing, short), zonas de peligro."),
        ("Player Intelligence",
         "Reportes de arquetipos de jugador, evaluacion de amenazas, perfiles "
         "detallados con metricas multi-dimensionales."),
    ]
    for name, desc in dashboards:
        story.append(Paragraph(
            f"<b>{name}</b>", styles["metric_name"]))
        story.append(Paragraph(desc, styles["metric_desc"]))
    story.append(PageBreak())

    # ── 5. ANALISIS ──
    section(story, "5", "Analisis Realizado — Metricas Avanzadas")
    body(story,
        "La plataforma implementa un conjunto extenso de metricas avanzadas que van "
        "mas alla de las estadisticas tradicionales del futbol:")

    metrics = [
        ("xG — Expected Goals (Goles Esperados)",
         "Modelo de regresion logistica entrenado sobre distancia de tiro, angulo, "
         "parte del cuerpo y situacion de juego. Calcula la probabilidad de gol "
         "para cada disparo. Penaltis usan un xG fijo calibrado (xG_penalty)."),
        ("xT — Expected Threat (Amenaza Esperada)",
         "Matriz de transicion 12x8 que mide la ganancia de valor territorial. "
         "Cada accion (pase, conduccion) se evalua por cuanto incrementa la "
         "probabilidad de gol del equipo basandose en la zona de origen y destino."),
        ("xGOT — Expected Goals on Target",
         "Calidad de colocacion del disparo usando coordenadas de la porteria "
         "(qualifier 103). Mide la dificultad del disparo para el portero "
         "independientemente de la posicion del tirador."),
        ("xDEF — Defensive Expected Goals Prevented",
         "Mide la contribucion defensiva de cada jugador calculando los goles "
         "esperados que previene con sus acciones (tackles, intercepciones, "
         "bloqueos, recuperaciones)."),
        ("PPDA — Passes Per Defensive Action",
         "Metrica de intensidad de pressing: numero de pases que el rival "
         "completa por cada accion defensiva (tackle, intercepcion, falta) "
         "en su propio tercio. Menor PPDA = pressing mas intenso."),
        ("Action Value (inspirado en VAEP)",
         "Framework de valoracion de acciones que estima el impacto de cada "
         "evento en la probabilidad de gol, considerando el contexto tactico "
         "y la secuencia de juego."),
        ("Sistema Elo",
         "Rating dinamico de fuerza de equipo con K=20, ventaja local=50 puntos. "
         "Se actualiza partido a partido y permite comparar equipos de diferentes "
         "ligas en una escala comun."),
        ("Prediccion Dixon-Coles",
         "Modelo Poisson mejorado con correccion rho=-0.13 para resultados de "
         "marcador bajo (0-0, 1-0, 0-1, 1-1). Simulacion Monte Carlo con "
         "100,000 iteraciones para obtener probabilidades de victoria, empate y derrota."),
        ("Player Ratings (Ratings de Jugador)",
         "Sistema de ratings especificos por posicion (GK/DEF/MID/FWD) con "
         "umbrales minimos de apariciones (5) y minutos (450). Escala 40-99 "
         "con categorias especificas por demarcacion."),
        ("Motor de Posiciones Tacticas",
         "Sistema de coordenadas canonicas para 25 posiciones con override por "
         "formacion. Modo de posicion promedio calculado desde eventos reales "
         "con filtrado de balones parados y blending configurable."),
    ]
    for name, desc in metrics:
        metric_block(story, name, desc)
    story.append(PageBreak())

    # ── 6. RESULTADOS ──
    section(story, "6", "Resultados")
    body(story,
        "Como ejemplo de aplicacion practica, se presenta el analisis de "
        "<b>Club America en el Clausura 2025-2026</b> de la Liga MX:")

    results_data = [
        ["Indicador", "Valor"],
        ["Posicion en liga", "#7"],
        ["Puntos", "27"],
        ["Record (W-D-L)", "7-6-6"],
        ["Diferencia de goles", "+3"],
        ["Goles a favor", "26"],
        ["Goles en contra", "23"],
        ["Partidos jugados", "19"],
        ["Puntos por partido", "1.42"],
    ]
    kpi_table(story, results_data, [5 * cm, 11 * cm])

    sub_heading(story, "Capacidades demostradas")
    bullet(story, "Procesamiento en tiempo real de la temporada completa de Liga MX "
           "con actualizacion automatica al agregar nuevos archivos de partidos")
    bullet(story, "Preparacion pre-partido con probabilidades de victoria basadas "
           "en Elo + Poisson para cada jornada")
    bullet(story, "Revision tactica post-partido con evaluacion de rendimiento "
           "basada en xG, mapas de tiro y redes de pases")
    bullet(story, "Scouting a nivel liga con leaderboards y comparaciones "
           "multi-dimensionales de jugadores")
    bullet(story, "Analisis de corners y balones parados con zonas de peligro "
           "y tipos de entrega")

    sub_heading(story, "Cobertura de datos")
    body(story,
        "La plataforma procesa exitosamente datos de 22 competiciones diferentes, "
        "12+ temporadas (2010-2026), con un total de 38,271 archivos y 47 GB de "
        "datos de eventos Opta. El sistema de cache garantiza tiempos de respuesta "
        "rapidos incluso con este volumen de datos.")
    story.append(PageBreak())

    # ── 7. CONCLUSIONES ──
    section(story, "7", "Conclusiones")
    body(story,
        "La plataforma transforma exitosamente 47 GB de datos crudos de eventos en "
        "una herramienta analitica interactiva que cubre el flujo completo de "
        "inteligencia futbolistica.")

    sub_heading(story, "Logros principales")
    bullet(story, "<b>42 modulos analiticos</b> cubriendo cada aspecto del analisis "
           "de partidos: desde xG basico hasta valoracion de acciones avanzada")
    bullet(story, "<b>Interfaz profesional</b> con tema oscuro, sistema de design tokens "
           "CSS y tematizacion dinamica por club")
    bullet(story, "<b>Procesamiento en tiempo real</b> con sistema de cache de Streamlit "
           "que minimiza re-calculos innecesarios")
    bullet(story, "<b>Modelos predictivos</b> que combinan Elo + Poisson + metricas "
           "tacticas para prediccion de resultados")
    bullet(story, "<b>Arquitectura escalable</b> que cubre 22 competiciones y 12+ "
           "temporadas sin degradacion de rendimiento")
    bullet(story, "<b>29,243 lineas de codigo</b> Python organizadas en una arquitectura "
           "modular de 4 capas")

    sub_heading(story, "Limitaciones y trabajo futuro")
    bullet(story, "El modelo de xG podria mejorarse con features adicionales como "
           "presion defensiva y posicion del portero")
    bullet(story, "Implementar tracking data (coordenadas de todos los jugadores) "
           "cuando este disponible para metricas off-ball")
    bullet(story, "Agregar exportacion automatica de reportes PDF por partido")
    bullet(story, "Implementar alertas automaticas para cambios significativos "
           "en metricas de rendimiento")
    story.append(PageBreak())

    # ── 8. TOMA DE DECISIONES ──
    section(story, "8", "Toma de Decisiones")
    body(story,
        "La plataforma habilita la toma de decisiones basada en datos en "
        "multiples areas del club:")

    decisions = [
        ("Preparacion de partidos",
         "Evaluacion de fuerza del rival via Elo y probabilidades de victoria "
         "Poisson. Identificacion de fortalezas y debilidades tacticas del "
         "oponente para disenar el plan de partido."),
        ("Ajustes tacticos",
         "Analisis de formaciones con deteccion automatica, triggers de pressing "
         "(PPDA), patrones de transicion, field tilt y momentum xT para "
         "identificar fases del partido donde el equipo pierde control."),
        ("Evaluacion de jugadores",
         "Ratings multi-dimensionales con metricas especificas por posicion "
         "que permiten evaluar el rendimiento individual mas alla de goles "
         "y asistencias: contribucion defensiva, progresion de balon, "
         "amenaza territorial."),
        ("Scouting y fichajes",
         "Leaderboards a nivel liga con clasificacion de arquetipos que "
         "permiten identificar perfiles de jugador compatibles con el "
         "sistema de juego del equipo y comparar candidatos."),
        ("Estrategia de balon parado",
         "Analisis de corners por tipo de entrega (inswing/outswing/short), "
         "zonas de peligro en tiros libres, y evaluacion de la efectividad "
         "defensiva en situaciones de balon parado."),
    ]
    for name, desc in decisions:
        metric_block(story, name, desc)
    story.append(PageBreak())

    # ── 9. REFERENCIAS ──
    section(story, "9", "Referencias Tecnicas")
    refs = [
        "Opta Sports. <i>Opta Event Data Feed — Technical Specification</i>. Stats Perform.",
        "Dixon, M.J. & Coles, S.G. (1997). <i>Modelling Association Football Scores "
        "and Inefficiencies in the Football Betting Market</i>. Applied Statistics, 46(2), 265-280.",
        "Singh, K. (2019). <i>Introducing Expected Threat (xT)</i>. karun.in/blog.",
        "Decroos, T. et al. (2019). <i>Actions Speak Louder than Goals: Valuing Player "
        "Actions in Soccer</i>. KDD 2019. (Framework VAEP)",
        "Streamlit Inc. <i>Streamlit Documentation</i>. streamlit.io/docs.",
        "mplsoccer. <i>mplsoccer Documentation</i>. mplsoccer.readthedocs.io.",
        "Plotly Technologies Inc. <i>Plotly Python Documentation</i>. plotly.com/python.",
        "Pedregosa, F. et al. (2011). <i>Scikit-learn: Machine Learning in Python</i>. "
        "JMLR 12, 2825-2830.",
    ]
    for i, ref in enumerate(refs, 1):
        story.append(Paragraph(f"[{i}] {ref}", styles["body"]))
    story.append(PageBreak())

    # ── 10. ANEXO ──
    section(story, "10", "Anexo — Repositorio y Estructura")
    sub_heading(story, "Repositorio GitHub")
    body(story,
        "<b>URL:</b> https://github.com/rodrigojacobs123/football-analytics-platform")
    body(story,
        "El repositorio contiene todo el codigo fuente, los 42 modulos de procesamiento, "
        "14 modulos de visualizacion, 11 paginas de dashboard, y el dataset completo "
        "de 47 GB de datos Opta.")

    sub_heading(story, "Estructura del proyecto")
    structure = [
        ["Directorio", "Contenido", "Archivos"],
        ["app.py", "Punto de entrada de la aplicacion Streamlit", "1"],
        ["config.py", "Configuracion central (IDs, constantes, colores)", "1"],
        ["nav.py", "Registro de navegacion de paginas", "1"],
        ["data/", "Capa de datos: paths, loader, event_parser, silver_events", "6"],
        ["processing/", "42 modulos analiticos pure-pandas", "42"],
        ["viz/", "14 modulos de visualizacion (Plotly, mplsoccer, HTML)", "14"],
        ["pages/", "11 dashboards interactivos", "11"],
        ["components/", "Componentes reutilizables (sidebar, selectores)", "4"],
        [".streamlit/", "Configuracion de tema oscuro (config.toml)", "1"],
        ["testeo_ligas_norteamerica/", "Dataset Opta: 22 competiciones, 38,271 archivos", "38,271"],
    ]
    kpi_table(story, structure, [4.5 * cm, 8.5 * cm, 3 * cm])

    sub_heading(story, "Instrucciones de ejecucion")
    body(story, "<b>Requisitos:</b> Python 3.9+, pip")
    body(story, "<b>Instalacion:</b>")
    story.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;&nbsp;pip install -r requirements.txt",
        ParagraphStyle("code", fontSize=9, fontName="Courier", textColor=ACCENT,
                      spaceAfter=4, leftIndent=18)))
    body(story, "<b>Ejecucion:</b>")
    story.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;&nbsp;streamlit run app.py",
        ParagraphStyle("code2", fontSize=9, fontName="Courier", textColor=ACCENT,
                      spaceAfter=4, leftIndent=18)))
    body(story,
        "La aplicacion se abre automaticamente en http://localhost:8501")

    doc.build(story)
    print(f"PDF generado: {OUT}")


if __name__ == "__main__":
    build()
