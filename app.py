"""CF América Sports Analytics Platform — Streamlit Entry Point."""

import streamlit as st

st.set_page_config(
    page_title="AME Sports Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import and apply theme
from viz.theme import apply_theme
apply_theme()

# Register all pages — the page set is defined once in nav.PAGE_SPECS, so the
# Data Sources diagnostics page reports exactly what ships here (no drift).
from nav import build_pages
pages = build_pages()

pg = st.navigation(pages)
pg.run()
