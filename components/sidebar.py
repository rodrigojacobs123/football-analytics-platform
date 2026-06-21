from __future__ import annotations
"""Global sidebar: club selector, crest, season/competition pickers."""

import streamlit as st
from config import (
    AME_CREST_URL, DEFAULT_LEAGUE, DEFAULT_SEASON, COMPETITIONS,
)
from data.paths import list_seasons
from viz.theme import THEMES, DEFAULT_CLUB


def render_sidebar() -> tuple[str, str]:
    """Render the global sidebar with club theme toggle and selectors.

    Returns (league, season) tuple.
    """
    with st.sidebar:
        # ── Club theme selector ──────────────────────────────────────
        club_options = list(THEMES.keys())
        club_labels = [THEMES[k]["label"] for k in club_options]

        current = st.session_state.get("club_theme", DEFAULT_CLUB)
        current_idx = club_options.index(current) if current in club_options else 0

        selected_label = st.selectbox(
            "Club",
            options=club_labels,
            index=current_idx,
            key="_club_selector_raw",
        )
        selected_key = club_options[club_labels.index(selected_label)]
        if st.session_state.get("club_theme") != selected_key:
            st.session_state["club_theme"] = selected_key
            st.rerun()

        t = THEMES[selected_key]
        primary = t["colors"]["primary"]

        # ── Crest + title ────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="text-align:center;padding:.6rem 0 1rem;">
                <img src="{AME_CREST_URL}" width="68"
                     style="margin-bottom:.5rem;filter:drop-shadow(0 4px 12px rgba(0,0,0,.5));"/>
                <h2 style="color:{primary};margin:0;font-size:1.1rem;font-weight:800;
                           font-family:var(--display);letter-spacing:-.01em;">
                    {t["label"]}</h2>
                <p style="color:var(--text-dim);font-size:.68rem;margin:4px 0 0;font-weight:500;
                          letter-spacing:.06em;text-transform:uppercase;">
                    Sports Analytics Platform</p>
            </div>
            <hr style="border-color:var(--border);margin:.5rem 0;opacity:.5;">
            """,
            unsafe_allow_html=True,
        )

        # ── Competition selector ─────────────────────────────────────
        comp_names = list(COMPETITIONS.values())
        comp_keys = list(COMPETITIONS.keys())
        comp_idx = comp_keys.index(DEFAULT_LEAGUE) if DEFAULT_LEAGUE in comp_keys else 0
        comp_label = st.selectbox(
            "Competition",
            options=comp_names,
            index=comp_idx,
            key="global_competition",
        )
        league = comp_keys[comp_names.index(comp_label)]

        # ── Season selector ──────────────────────────────────────────
        available_seasons = list_seasons(league)
        if not available_seasons:
            available_seasons = [DEFAULT_SEASON]

        default_idx = (
            available_seasons.index(DEFAULT_SEASON)
            if DEFAULT_SEASON in available_seasons
            else 0
        )
        season = st.selectbox(
            "Season",
            options=available_seasons,
            index=default_idx,
            key="global_season",
        )

        st.markdown(
            '<hr style="border-color:var(--border);margin:.5rem 0;opacity:.5;">',
            unsafe_allow_html=True,
        )

    return league, season
