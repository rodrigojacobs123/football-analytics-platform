# Guión para Video Presentación TFM
## Rodrigo Jacobs — Plataforma de Análisis Deportivo para Club América
### Duración máxima: 45 minutos

---

## PARTE 1: Introducción y Contexto (5 min)

### Slide: Portada
- "Buenos días/tardes. Mi nombre es Rodrigo Jacobs y voy a presentar mi Trabajo Final de Máster: una Plataforma de Análisis Deportivo para Club América, construida con datos Opta."

### Slide: Contexto
- "El proyecto nace de la necesidad de transformar datos crudos de eventos en inteligencia futbolística accionable."
- "Trabajamos con un dataset masivo de **47 GB** — 38,271 archivos JSON de Opta cubriendo 22 competiciones de Norteamérica y CONCACAF."
- "La plataforma está orientada al cuerpo técnico: entrenadores, analistas, dirección deportiva y scouting."

### Slide: Objetivos
- "El objetivo principal es construir una herramienta end-to-end que cubra todo el ciclo de trabajo analítico: desde la preparación pre-partido hasta el scouting de jugadores."
- Mencionar los 5 objetivos secundarios brevemente.

---

## PARTE 2: Metodología y Arquitectura (5 min)

### Slide: Stack Tecnológico
- "La plataforma está construida 100% en Python con Streamlit como framework web."
- Mostrar la tabla de tecnologías: Pandas, Plotly, mplsoccer, scikit-learn.

### Slide: Arquitectura
- "Seguimos una arquitectura modular de 4 capas claramente separadas."
- **Explicar cada capa** y por qué es importante la separación (testabilidad, reutilización).
- "En total son 29,243 líneas de código en 42 módulos de procesamiento, 14 de visualización y 11 dashboards."

### Slide: ETL
- "El proceso ETL va desde JSON crudo → DataFrames tipados → métricas → visualizaciones."
- "El sistema de cache evita re-parsear archivos en cada interacción."

---

## PARTE 3: Demo de la Herramienta (20 min)

### 3.1 Season Dashboard (3 min)
**[Abrir la app en http://localhost:8501]**
- Mostrar la página Home con KPI cards
- Explicar el filtro Apertura/Clausura y por qué es necesario en Liga MX
- Mostrar la tabla de posiciones
- "Club América está en posición #7 con 27 puntos, record 7-6-6"

### 3.2 Pre-Match Analysis (3 min)
**[Navegar a Pre-Match Analysis]**
- Seleccionar un rival (ej: Cruz Azul o Guadalajara)
- Mostrar ratings Elo de ambos equipos
- Mostrar el radar de comparación
- Mostrar la predicción Poisson: "El modelo combina Elo + Poisson + Dixon-Coles para estimar probabilidades de victoria"
- "Esto es exactamente lo que el cuerpo técnico revisa antes de cada partido"

### 3.3 Post-Match Analysis (4 min)
**[Navegar a Post-Match Analysis]**
- Seleccionar un partido reciente
- Mostrar el hero card con marcador y xG
- "Aquí vemos que el xG nos dice otra historia diferente al marcador"
- Mostrar el xG race chart: "Este gráfico muestra cómo evolucionó la calidad de las oportunidades"
- Mostrar el mapa de tiros
- Mostrar la formación con posiciones canónicas vs promedio de eventos
- Mostrar las estadísticas comparativas

### 3.4 Tactics (3 min)
**[Navegar a Tactics]**
- Mostrar detección automática de formación vía qualifier 130
- Mostrar PPDA: "Esto mide la intensidad de pressing — menor número = pressing más agresivo"
- Mostrar field tilt
- Mostrar el momentum xT

### 3.5 Player Scouting (3 min)
**[Navegar a Player Scouting]**
- Mostrar ratings estilo FC (PAC/SHO/PAS/DRI/DEF/PHY)
- Seleccionar un jugador y mostrar su perfil
- Mostrar el leaderboard filtrado por posición
- "Este sistema permite al scout comparar jugadores de toda la liga en segundos"

### 3.6 Otras páginas (4 min)
**[Mostrar brevemente]**
- xG Explorer: "Explorador interactivo de mapas de tiro"
- Corner Defense: "Análisis de corners por tipo de entrega"
- Manager Profiles: "Comparación de entrenadores"
- Player Intelligence: "Reportes de arquetipos de jugador"

---

## PARTE 4: Códigos y Métricas Avanzadas (7 min)

### Slide: Estructura del código
- "Vamos a ver cómo funcionan los códigos por dentro."
- Abrir `config.py`: "Aquí centralizamos todos los IDs de eventos Opta — esto evita errores de hardcoding"
- Abrir `data/event_parser.py`: "El parser convierte JSON crudo en DataFrames tipados"
- Abrir `processing/xg.py`: "El modelo xG usa regresión logística con distancia, ángulo y parte del cuerpo"

### Slide: Métricas clave
- **xG**: "Probabilidad de gol para cada disparo"
- **xT**: "Ganancia de valor territorial — mide cuánto avanza un equipo hacia el gol con cada acción"
- **PPDA**: "Intensidad de pressing — pases del rival por acción defensiva"
- **Dixon-Coles**: "Mejora el modelo Poisson básico corrigiendo la sobre-predicción de empates a cero"
- **Action Value**: "Inspirado en VAEP — valora cada acción por su impacto en la probabilidad de gol"

### Slide: Motor de posiciones tácticas
- Abrir `processing/tactical_positions.py`
- "Este módulo mapea las 25 posiciones posibles con coordenadas canónicas"
- "Permite comparar la formación teórica vs las posiciones reales durante el partido"

---

## PARTE 5: Análisis desde el rol de Análisis de Juego (5 min)

### Caso práctico: Club América Clausura 2025-2026
- "Desde el rol de analista de juego, voy a mostrar las conclusiones principales"
- **Rendimiento general**: Posición #7, 27 pts, GD +3 — "Rendimiento por debajo de las expectativas para un equipo grande"
- **xG vs realidad**: Comparar xG acumulado vs goles reales
- **Patrón táctico**: Mostrar cómo la formación y el pressing varían por rival
- **Implicaciones**: "El equipo necesita mejorar la conversión de oportunidades — el xG sugiere que crea suficiente peligro"

### Propuestas de mejora
- "Basándome en los datos, las áreas de mejora serían:"
  1. Eficiencia en la finalización (xG vs goles)
  2. Solidez defensiva en transiciones
  3. Efectividad en corners (mostrar datos de Corner Defense)

---

## PARTE 6: Conclusiones y Toma de Decisiones (3 min)

### Slide: Conclusiones
- "La plataforma logra transformar 47 GB de datos en inteligencia accionable"
- "42 módulos analíticos, 11 dashboards, 29,243 líneas de código"
- "Cubre el ciclo completo: pre-partido, partido, post-partido, scouting"

### Slide: Toma de decisiones
- "La herramienta permite tomar decisiones basadas en datos en 5 áreas clave"
- Enumerar: preparación, táctica, evaluación, scouting, balón parado

### Cierre
- "Muchas gracias por su atención. El código está disponible en GitHub."
- Mostrar URL del repositorio

---

## NOTAS PARA LA GRABACIÓN

1. **Antes de grabar**: Asegurarse de que la app está corriendo (`streamlit run app.py`)
2. **Resolución**: Grabar en 1080p mínimo
3. **Software recomendado**: OBS Studio, Loom, o QuickTime (Mac)
4. **Tip**: Tener la presentación PDF abierta en una ventana y la app en otra para alternar
5. **Duración por sección**: No exceder los tiempos sugeridos — total 45 min máximo
6. **Tono**: Profesional pero cercano — estás explicando tu trabajo a un tribunal académico
