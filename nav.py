from __future__ import annotations
"""Single source of truth for the page registry.

Both ``app.py`` (which builds the ``st.navigation`` list) and
``pages/11_Data_Sources.py`` (which renders the live registry for diagnostics)
import from here. Registering a page in exactly one place means the documented
page set can never drift from what actually ships — the failure mode flagged in
the 2026-06-24 architecture review (the task brief said 8 pages, CLAUDE.md said
11, app.py shipped 11). The moment pages are gated by competition or role, a
drifting registry becomes an access-control bug, not just stale docs.

The numeric prefixes in the file names (note the 5/7/8 gaps from deleted pages)
are sort hints only — order in :data:`PAGE_SPECS` is what controls the sidebar.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    """One navigable page. ``path`` is relative to the project root."""
    path: str
    title: str
    icon: str


# ── THE registry. Add/remove/reorder pages here and nowhere else. ────────────
PAGE_SPECS: list[PageSpec] = [
    PageSpec("pages/1_Home.py",                "Home",                "🏠"),
    PageSpec("pages/2_Pre_Match_Analysis.py",  "Pre-Match Analysis",  "🎯"),
    PageSpec("pages/3_Post_Match_Analysis.py", "Post-Match Analysis", "📊"),
    PageSpec("pages/4_Tactics.py",             "Tactics",             "♟️"),
    PageSpec("pages/9_xG_Explorer.py",         "xG Explorer",         "🎯"),
    PageSpec("pages/6_Player_Scouting.py",     "Player Scouting",     "🔍"),
    PageSpec("pages/10_Injury_Tracker.py",     "Injury Tracker",      "🏥"),
    PageSpec("pages/11_Data_Sources.py",       "Data Sources",        "💾"),
    PageSpec("pages/12_Manager_Profiles.py",   "Manager Profiles",    "👔"),
    PageSpec("pages/13_Corner_Defense.py",     "Corner Defense Intel","🔵"),
    PageSpec("pages/14_Player_Intelligence.py","Player Intelligence", "🧬"),
    PageSpec("pages/15_Scouting_Hub.py",       "Scouting Hub",        "📂"),
]


def build_pages():
    """Construct the ``st.Page`` objects for ``st.navigation`` from PAGE_SPECS.

    ``streamlit`` is imported lazily so this module stays importable in
    non-Streamlit contexts (diagnostics, tests, a future headless build CLI).
    """
    import streamlit as st
    return [st.Page(s.path, title=s.title, icon=s.icon) for s in PAGE_SPECS]
