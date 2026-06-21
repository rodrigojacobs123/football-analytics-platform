from __future__ import annotations
"""Dashboard KPI card components rendered as HTML."""

import streamlit as st
import pandas as pd
from config import AME_YELLOW, AME_BLUE
from processing.match_stats import crest_url


# ── Page-level branding ──────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", badge: str = "") -> None:
    """Render a branded Club Analytics page header bar."""
    badge_html = (
        f'<span style="font-family:var(--body);font-size:0.6rem;font-weight:700;letter-spacing:0.12em;'
        f'color:#0D1117;background:var(--ame-primary);padding:3px 10px;border-radius:12px;'
        f'text-transform:uppercase;margin-left:10px;">{badge}</span>'
        if badge else ""
    )
    sub_html = (
        f'<div class="ame-page-sub">{subtitle}</div>'
        if subtitle else ""
    )
    html = (
        f'<div class="ame-page-bar">'
        f'<div class="ame-page-bar-accent"></div>'
        f'<div>'
        f'<div style="display:flex;align-items:baseline;gap:8px;">'
        f'<div class="ame-page-title">{title}</div>{badge_html}'
        f'</div>'
        f'{sub_html}'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def ame_section(label: str, title: str) -> None:
    """Render a section header with label + display title."""
    html = (
        f'<div class="ame-section">'
        f'<div class="ame-section-label">━━ {label} ━━</div>'
        f'<div class="ame-section-title">{title}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def ame_tile_row(metrics: list[dict]) -> None:
    """Render compact KPI tiles in the V2 stat-strip style.

    Each dict: {label, value, sub (optional)}
    """
    tiles = []
    for m in metrics:
        sub_html = f'<div class="ame-tile-sub">{m["sub"]}</div>' if m.get("sub") else ""
        tiles.append(
            f'<div class="ame-tile">'
            f'<div class="ame-tile-label">{m["label"]}</div>'
            f'<div class="ame-tile-value">{m["value"]}</div>'
            f'{sub_html}'
            f'</div>'
        )
    html = '<div class="ame-tile-grid">' + "".join(tiles) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def mu_card_header(label: str) -> None:
    """Render a card container header label."""
    st.markdown(
        f'<div class="ame-card-title">{label}</div>',
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value, delta=None, delta_suffix: str = "",
             positive_is_good: bool = True):
    """Render a styled KPI card using custom HTML."""
    delta_html = ""
    if delta is not None:
        is_positive = delta > 0 if isinstance(delta, (int, float)) else False
        delta_class = "positive" if (is_positive == positive_is_good) else "negative"
        sign = "+" if isinstance(delta, (int, float)) and delta > 0 else ""
        delta_html = f'<p class="kpi-delta {delta_class}">{sign}{delta}{delta_suffix}</p>'

    html = f"""
    <div class="kpi-card">
        <p class="kpi-label">{label}</p>
        <p class="kpi-value">{value}</p>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def kpi_row(metrics: list[dict], cols: int = 4):
    """Render a row of KPI cards.

    Each metric dict should have: label, value, and optionally delta, delta_suffix.
    """
    columns = st.columns(cols)
    for i, m in enumerate(metrics):
        with columns[i % cols]:
            kpi_card(
                label=m["label"],
                value=m["value"],
                delta=m.get("delta"),
                delta_suffix=m.get("delta_suffix", ""),
                positive_is_good=m.get("positive_is_good", True),
            )


def form_badges(results: list[str]) -> str:
    """Generate HTML for W/D/L form badges.

    Args:
        results: list of "W", "D", or "L" strings (most recent first)
    """
    badges = ""
    for r in results:
        badges += f'<span class="form-badge {r}">{r}</span>'
    return f'<div style="display:flex;gap:4px;align-items:center;">{badges}</div>'


def section_header(text: str):
    """Render a styled section header."""
    st.markdown(
        f'<div class="ame-section">'
        f'<div class="ame-section-title">{text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def metric_highlight(label: str, value, color: str = AME_YELLOW):
    """Render a single large highlighted metric."""
    html = f"""
    <div style="text-align:center;padding:1rem;">
        <p style="color:var(--text-dim);font-size:0.85rem;text-transform:uppercase;margin:0;">{label}</p>
        <p style="color:{color};font-size:3rem;font-weight:700;margin:0;font-family:var(--mono);">{value}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── Professional Match Dashboard Components ──────────────────────────────────

def match_header_card(
    home_team: str, away_team: str,
    home_score: int, away_score: int,
    home_id: str, away_id: str,
    matchday: int, date: str, venue: str,
    ht_home: int = 0, ht_away: int = 0,
    competition: str = "Premier League",
) -> None:
    """Render professional match header with team crests flanking the score."""
    home_crest = crest_url(home_id)
    away_crest = crest_url(away_id)
    date_str = str(date)[:10]
    html = (
        f'<div class="match-header">'
        f'<div class="match-meta">{competition} &middot; Matchday {matchday} &middot; {date_str} &middot; {venue}</div>'
        f'<div class="score-row">'
        f'<div class="team-block"><img src="{home_crest}" alt="{home_team}"><span class="team-name">{home_team}</span></div>'
        f'<div class="score-display"><span class="home-score">{home_score}</span><span class="score-sep">-</span><span class="away-score">{away_score}</span></div>'
        f'<div class="team-block"><img src="{away_crest}" alt="{away_team}"><span class="team-name">{away_team}</span></div>'
        f'</div>'
        f'<div class="ht-score">HT: {ht_home} - {ht_away}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def stats_comparison_table(stats: list[dict]) -> None:
    """Render side-by-side stat comparison bars.

    Args:
        stats: list from compute_match_stats(), each dict has
               label, home_value, away_value, home_pct, away_pct, format
    """
    rows = []
    for s in stats:
        fmt = s.get("format", "int")
        hv = s["home_value"]
        av = s["away_value"]
        if fmt == "pct":
            h_display = f"{hv:.0f}%"
            a_display = f"{av:.0f}%"
        elif fmt == "float1":
            h_display = f"{hv:.1f}"
            a_display = f"{av:.1f}"
        else:
            h_display = str(int(hv))
            a_display = str(int(av))
        hp = s["home_pct"]
        ap = s["away_pct"]
        label = s["label"]
        # Compact single-line HTML to avoid Streamlit markdown parser issues
        row = (
            f'<div class="stat-row">'
            f'<span class="stat-val home">{h_display}</span>'
            f'<div class="bar-container"><div class="bar-fill-home" style="width:{hp}%"></div></div>'
            f'<span class="stat-label">{label}</span>'
            f'<div class="bar-container"><div class="bar-fill-away" style="width:{ap}%"></div></div>'
            f'<span class="stat-val away">{a_display}</span>'
            f'</div>'
        )
        rows.append(row)

    html = '<div class="stat-comparison">' + "".join(rows) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def content_card(title: str) -> None:
    """Render a content card section title."""
    html = f'<div class="content-card" style="padding:0.8rem 1.2rem;"><div class="card-title">{title}</div></div>'
    st.markdown(html, unsafe_allow_html=True)


def v3_section_header(rule_text: str, title: str) -> None:
    """Render a V3 Stadium Energy editorial section header."""
    html = (
        f'<div class="v3-section">'
        f'<div class="v3-section-rule">━━ {rule_text} ━━</div>'
        f'<div class="v3-section-title">{title}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def match_hero_v3(
    home_team: str, away_team: str,
    home_score: int, away_score: int,
    home_id: str, away_id: str,
    matchday: int, date: str, venue: str,
    ht_home: int = 0, ht_away: int = 0,
    home_xg: float = 0.0, away_xg: float = 0.0,
    competition: str = "Premier League",
) -> None:
    """V3 Stadium Energy cinematic match hero card."""
    home_crest = crest_url(home_id)
    away_crest = crest_url(away_id)
    date_str = str(date)[:10]

    xg_delta = abs(home_xg - away_xg)
    if home_xg > away_xg:
        xg_story = f"{home_team} dominated the xG battle by +{xg_delta:.2f}"
    elif away_xg > home_xg:
        xg_story = f"{away_team} dominated the xG battle by +{xg_delta:.2f}"
    else:
        xg_story = "Both sides created equal quality chances"

    html = f"""
<div class="v3-hero">
  <div class="v3-competition">{competition} &nbsp;·&nbsp; Matchday {matchday} &nbsp;·&nbsp; {date_str}</div>

  <div class="v3-score-row">
    <div class="v3-team-block">
      <img src="{home_crest}" alt="{home_team}">
      <div class="v3-team-name">{home_team}</div>
    </div>
    <div class="v3-score-center">
      <div class="v3-score-digits">
        <span class="v3-score-home">{home_score}</span>
        <span class="v3-score-sep">-</span>
        <span class="v3-score-away">{away_score}</span>
      </div>
      <div class="v3-ht">HT {ht_home} – {ht_away}</div>
    </div>
    <div class="v3-team-block">
      <img src="{away_crest}" alt="{away_team}">
      <div class="v3-team-name">{away_team}</div>
    </div>
  </div>

  <div class="v3-meta-row">{venue}</div>

  <div class="v3-xg-strip">
    <div class="v3-xg-block">
      <div class="v3-xg-label">Expected Goals</div>
      <div class="v3-xg-value-home">{home_xg:.2f}</div>
    </div>
    <div class="v3-xg-divider">xG</div>
    <div class="v3-xg-block">
      <div class="v3-xg-label">Expected Goals</div>
      <div class="v3-xg-value-away">{away_xg:.2f}</div>
    </div>
  </div>
  <div class="v3-xg-story">{xg_story}</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def v3_stats_table(stats: list[dict]) -> None:
    """V3 Stadium Energy version of the stats comparison bars with mono typography."""
    rows = []
    for s in stats:
        fmt = s.get("format", "int")
        hv = s["home_value"]
        av = s["away_value"]
        if fmt == "pct":
            h_display = f"{hv:.0f}%"
            a_display = f"{av:.0f}%"
        elif fmt == "float1":
            h_display = f"{hv:.1f}"
            a_display = f"{av:.1f}"
        else:
            h_display = str(int(hv))
            a_display = str(int(av))
        hp = s["home_pct"]
        ap = s["away_pct"]
        label = s["label"]
        row = (
            f'<div class="v3-stat-row">'
            f'<span class="v3-stat-val home">{h_display}</span>'
            f'<div class="v3-bar-wrap"><div class="v3-bar-home" style="width:{hp}%"></div></div>'
            f'<span class="v3-stat-label">{label}</span>'
            f'<div class="v3-bar-wrap"><div class="v3-bar-away" style="width:{ap}%"></div></div>'
            f'<span class="v3-stat-val away">{a_display}</span>'
            f'</div>'
        )
        rows.append(row)

    html = '<div style="max-width:700px;margin:0 auto 1.5rem;">' + "".join(rows) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def v3_rating_grid(ratings: list[dict], team_color: str = "#DA291C") -> None:
    """Render V3-style player rating cards.

    Each dict: {name, rating (float)}
    """
    cards = []
    for r in ratings:
        score = r["rating"]
        if score >= 8.0:
            cls = "v3-rating-green"
        elif score >= 7.0:
            cls = "v3-rating-gold"
        else:
            cls = "v3-rating-normal"
        name = r["name"].split(" ")[-1]  # surname only for space
        cards.append(
            f'<div class="v3-rating-card">'
            f'<span class="v3-rating-name">{name}</span>'
            f'<span class="v3-rating-score {cls}">{score:.1f}</span>'
            f'</div>'
        )
    html = '<div class="v3-rating-grid">' + "".join(cards) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def key_events_timeline(
    events_df: pd.DataFrame,
    home_team: str, away_team: str,
    home_id: str, away_id: str,
) -> None:
    """Render a styled vertical timeline of key match events."""
    if events_df.empty:
        st.info("No key events recorded.")
        return

    icon_map = {
        "Goal": "&#9917;",       # ⚽
        "Card": "&#128995;",     # 🟨
        "Sub On": "&#9650;",     # ▲
        "Sub Off": "&#9660;",    # ▼
    }

    items = []
    for _, ev in events_df.sort_values("minute").iterrows():
        is_home = ev["team_id"] == home_id
        color = AME_YELLOW if is_home else "#42A5F5"
        team = home_team if is_home else away_team
        icon = icon_map.get(ev["event_type"], "&#8226;")
        player = ev.get("player_name", "")
        # Compact single-line HTML to avoid Streamlit markdown parser issues
        item = (
            f'<div class="event-item">'
            f'<span class="event-minute">{ev["minute"]}\'</span>'
            f'<span class="event-dot" style="background:{color};"></span>'
            f'<span class="event-icon">{icon}</span>'
            f'<span class="event-detail">'
            f'<span class="player-name">{player}</span>'
            f'<span style="color:#888;"> ({team})</span>'
            f'</span></div>'
        )
        items.append(item)

    html = '<div class="event-timeline">' + "".join(items) + '</div>'
    st.markdown(html, unsafe_allow_html=True)
