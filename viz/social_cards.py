from __future__ import annotations
"""Social-media (X/Twitter) card images for the Player Report page.

Matplotlib-rendered 16:9 PNGs (1680×945) in the dark Club América palette,
sized so X shows them full-bleed without cropping. Pure rendering: takes the
already-computed aggregates/frames, returns PNG bytes.
"""

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import AME_YELLOW, AME_DARK_BG

_BG = AME_DARK_BG          # #04132E
_PANEL = "#0E1B36"
_TEXT = "#EAF0FA"
_MUTED = "#8899AA"
_RESULT_COLOR = {"V": "#4CAF50", "E": "#9E9E9E", "D": "#E53935", "": "#666666"}
_BRAND = "AME SPORTS ANALYTICS  ·  datos Wyscout"


def _new_card() -> plt.Figure:
    fig = plt.figure(figsize=(12, 6.75), dpi=140)   # 1680×945 px
    fig.patch.set_facecolor(_BG)
    return fig


def _finish(fig: plt.Figure) -> bytes:
    fig.text(0.045, 0.045, _BRAND, color=_MUTED, fontsize=9,
             fontweight="bold", alpha=0.9)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=_BG, bbox_inches=None)
    plt.close(fig)
    return buf.getvalue()


def _header(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.add_artist(plt.Rectangle((0.045, 0.855), 0.012, 0.09,
                                 color=AME_YELLOW, transform=fig.transFigure))
    fig.text(0.07, 0.885, title, color=_TEXT, fontsize=26, fontweight="bold")
    fig.text(0.07, 0.845, subtitle, color=_MUTED, fontsize=12)


def stat_card(player: str, team: str, window_desc: str,
              agg: dict, cons: dict) -> bytes:
    """Identity + big numbers card."""
    fig = _new_card()
    _header(fig, player, f"{team}  ·  {window_desc}")

    stats = [
        (f"{agg['ga90']}", "G+A / 90"),
        (f"{agg['xg90']}", "xG / 90"),
        (f"{agg['dribbles90']}", "regates / 90"),
        (f"{agg['dribbles_pct']:.0f}%", "regates exitosos"),
        (f"{agg['duels90']}", "duelos / 90"),
    ]
    for i, (val, label) in enumerate(stats):
        x = 0.07 + i * 0.185
        fig.add_artist(plt.Rectangle((x - 0.018, 0.42), 0.17, 0.30,
                                     color=_PANEL, transform=fig.transFigure))
        fig.text(x + 0.067, 0.60, val, color=AME_YELLOW, fontsize=30,
                 fontweight="bold", ha="center")
        fig.text(x + 0.067, 0.485, label, color=_MUTED, fontsize=11.5,
                 ha="center")

    foot = (f"{agg['matches']} partidos · {agg['minutes']}′ · "
            f"{agg['goals']} goles · {agg['assists']} asistencias · "
            f"G+A en el {cons['ga_matches_pct']:.0f}% de los partidos")
    fig.text(0.07, 0.30, foot, color=_TEXT, fontsize=14)
    fig.text(0.07, 0.22, f"{cons['starts']} titularidades (60′+) · "
                         f"racha máx. sin G+A: {cons['max_drought']} partidos",
             color=_MUTED, fontsize=12)
    return _finish(fig)


def form_card(player: str, team: str, ctx: pd.DataFrame,
              n_last: int = 12) -> bytes:
    """Last-N matches: G+A bars coloured by result, with match labels."""
    recent = ctx.sort_values("Date").tail(n_last)
    fig = _new_card()
    _header(fig, f"{player} — forma reciente",
            f"{team}  ·  últimos {len(recent)} partidos")

    ax = fig.add_axes([0.07, 0.22, 0.88, 0.52])
    ax.set_facecolor(_BG)
    colors = [_RESULT_COLOR.get(r, "#666") for r in recent["result"]]
    x = range(len(recent))
    ax.bar(x, recent["Minutes played"], color=colors, width=0.62, zorder=3)
    for i, (_, r) in enumerate(recent.iterrows()):
        opp = str(r["opponent"])[:14]
        mins = float(r["Minutes played"])
        ax.text(i, -8, opp, color=_MUTED, fontsize=9, rotation=38,
                ha="right", va="top")
        ax.text(i, mins / 2, f"{r['result']} {r['score']}", color=_BG,
                fontsize=8.5, fontweight="bold", ha="center", va="center",
                rotation=90, zorder=4)
        contrib = ([f"{int(r['Goals'])}G"] if r["Goals"] else []) + \
                  ([f"{int(r['Assists'])}A"] if r["Assists"] else [])
        if contrib:
            ax.text(i, mins + 6, "+".join(contrib), color=AME_YELLOW,
                    fontsize=13, fontweight="bold", ha="center")
    ax.set_ylim(0, max(125.0, float(recent["Minutes played"].max()) + 22))
    ax.set_xlim(-0.7, len(recent) - 0.3)
    ax.axis("off")
    ax.set_title("Minutos por partido · color = resultado · amarillo = contribución (G/A)",
                 color=_TEXT, fontsize=12, loc="left", pad=14)
    return _finish(fig)


def market_card(player: str, group_label: str, score: float, rank: int,
                pool_n: int, similar: list[dict], n_shared: int) -> bytes:
    """Market-rank headline + closest comparables."""
    fig = _new_card()
    _header(fig, f"{player} vs el mercado", group_label)

    fig.text(0.07, 0.62, f"#{rank}", color=AME_YELLOW, fontsize=64,
             fontweight="bold")
    fig.text(0.07, 0.53, f"de {pool_n} jugadores del pool", color=_TEXT,
             fontsize=15)
    fig.text(0.07, 0.46, f"Score {score} · {n_shared} métricas comparadas",
             color=_MUTED, fontsize=12)

    ax = fig.add_axes([0.47, 0.18, 0.48, 0.55])
    ax.set_facecolor(_BG)
    sims = similar[:5][::-1]
    names = [f"{s['Player']} ({s.get('Team', '?')})" for s in sims]
    vals = [s["similarity"] for s in sims]
    ax.barh(range(len(sims)), vals, color=AME_YELLOW, height=0.55, zorder=3)
    for i, (name, v) in enumerate(zip(names, vals)):
        ax.text(2, i, name, color=_BG, fontsize=10.5, fontweight="bold",
                va="center", zorder=4)
        ax.text(v + 1, i, f"{v:.0f}%", color=_TEXT, fontsize=10.5,
                va="center")
    ax.set_xlim(0, 105)
    ax.axis("off")
    ax.set_title("Perfiles más parecidos (similitud %)", color=_TEXT,
                 fontsize=12, loc="left", pad=14)
    return _finish(fig)


def hook_card(player: str, team: str, hook: dict) -> bytes:
    """One card per scout hook: the tweet stays short, the card carries the
    message. Icons are left to the tweet text — matplotlib has no color emoji."""
    import textwrap
    fig = _new_card()
    _header(fig, hook["title"], f"{player}  ·  {team}")
    body = textwrap.fill(hook["text"], width=54)
    fig.text(0.07, 0.68, body, color=_TEXT, fontsize=18, va="top",
             linespacing=1.7)
    if hook.get("short"):
        fig.add_artist(plt.Rectangle((0.045, 0.13), 0.91, 0.115,
                                     color=_PANEL, transform=fig.transFigure))
        fig.text(0.07, 0.205, textwrap.fill(hook["short"], width=80),
                 color=AME_YELLOW, fontsize=13, fontweight="bold", va="top")
    return _finish(fig)


def suggest_posts(player: str, team: str, window_desc: str, agg: dict,
                  cons: dict, market: dict | None) -> list[str]:
    """2-3 ready-to-paste post texts, each ≤ 240 chars (X free-tier margin)."""
    tags = "#Scouting #DataFútbol"
    posts = [
        (f"📊 {player} ({team}) — {window_desc}:\n"
         f"⚽ {agg['ga90']} G+A/90 · {agg['xg90']} xG/90\n"
         f"🎯 {agg['dribbles90']} regates/90 ({agg['dribbles_pct']:.0f}% éxito)\n"
         f"⚔️ {agg['duels90']} duelos/90\n{tags}"),
        (f"🔎 {player}: G+A en el {cons['ga_matches_pct']:.0f}% de sus "
         f"partidos, {cons['starts']} titularidades en la ventana analizada. "
         f"Racha máxima sin producción: {cons['max_drought']} partidos. "
         f"El volumen está; la pregunta es la regularidad. {tags}"),
    ]
    if market:
        posts.insert(1, (
            f"⚖️ ¿Dónde queda {player} en el mercado? Sería el "
            f"#{market['rank']} de {market['n']} ({market['label']}) de "
            f"nuestro pool, score {market['score']}. Perfil más parecido: "
            f"{market['similar'][0]['Player']} "
            f"({market['similar'][0]['similarity']:.0f}% similitud). {tags}"))
    return [p[:240] for p in posts]  # X free-tier margin
