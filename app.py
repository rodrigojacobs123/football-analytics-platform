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

# Register all pages
pages = [
    st.Page("pages/1_Home.py", title="Home", icon="🏠"),
    st.Page("pages/2_Pre_Match_Analysis.py", title="Pre-Match Analysis", icon="🎯"),
    st.Page("pages/3_Post_Match_Analysis.py", title="Post-Match Analysis", icon="📊"),
    st.Page("pages/4_Tactics.py", title="Tactics", icon="♟️"),
    st.Page("pages/9_xG_Explorer.py", title="xG Explorer", icon="🎯"),
    st.Page("pages/6_Player_Scouting.py", title="Player Scouting", icon="🔍"),
    st.Page("pages/10_Injury_Tracker.py", title="Injury Tracker", icon="🏥"),
    st.Page("pages/11_Data_Sources.py", title="Data Sources", icon="💾"),
    st.Page("pages/12_Manager_Profiles.py", title="Manager Profiles", icon="👔"),
    st.Page("pages/13_Corner_Defense.py", title="Corner Defense Intel", icon="🔵"),
    st.Page("pages/14_Player_Intelligence.py", title="Player Intelligence", icon="🧬"),
]

pg = st.navigation(pages)
pg.run()
