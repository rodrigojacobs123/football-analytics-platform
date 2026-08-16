from __future__ import annotations
"""Wyscout "Player stats" exports (match-by-match, one player) for Player Report.

A different animal from the "Search results" exports the Scouting Hub eats:
here every ROW is one match of one player (~31 columns), which is what makes
consistency, form windows and development-curve analysis possible at all.

Format quirk: paired columns — "Dribbles / successful" holds attempts and the
next (unnamed) column holds the successful count. Parsing maps each pair to
``<base>`` / ``<base>_ok``.

Pure pandas: the page owns Streamlit and file I/O.
"""

import re

import pandas as pd

# "X / successful"-style paired columns → (attempts, successes) short names.
_PAIRED = {
    "Total actions / successful": "actions",
    "Shots / on target": "shots",
    "Passes / accurate": "passes",
    "Long passes / accurate": "long_passes",
    "Crosses / accurate": "crosses",
    "Dribbles / successful": "dribbles",
    "Duels / won": "duels",
    "Aerial duels / won": "aerials",
    "Losses / own half": "losses",
    "Recoveries / opp. half": "recoveries",
}

_NUMERIC = ["Minutes played", "Goals", "Assists", "xG", "Interceptions",
            "Yellow card", "Red card"] + [
    c for base in _PAIRED.values() for c in (base, f"{base}_ok")
]

# Competitions counted as senior football (vs academy/youth-international).
_SENIOR_PAT = re.compile(
    r"Premier League$|La Liga|Serie A|Bundesliga|Ligue 1|Liga MX|MLS|"
    r"FA Cup|EFL|Copa|Cup$|Champions|Europa|Conference", re.IGNORECASE)
_YOUTH_PAT = re.compile(r"U1\d|U2[0-3]|Youth|Junior|Academy|Premier League 2",
                        re.IGNORECASE)

TIER_SENIOR = "Senior"
TIER_YOUTH = "Formativo / juvenil"


def player_name_from_filename(filename: str) -> str:
    """'Player stats M. Dami Mane.xlsx' → 'M. Dami Mane'."""
    stem = re.sub(r"\.xlsx?$", "", filename, flags=re.IGNORECASE)
    return re.sub(r"^Player stats\s*", "", stem, flags=re.IGNORECASE).strip() or stem


def parse_player_stats(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Normalise one match-by-match export; adds tier, per-match helpers."""
    if "Match" not in df.columns or "Minutes played" not in df.columns:
        raise ValueError(
            f"'{source_name}' does not look like a Wyscout 'Player stats' "
            "export (missing 'Match'/'Minutes played')."
        )
    out = df.copy()
    cols = list(out.columns)
    ren: dict[str, str] = {}
    for main, base in _PAIRED.items():
        if main in cols:
            i = cols.index(main)
            ren[main] = base
            if i + 1 < len(cols) and str(cols[i + 1]).startswith("Unnamed"):
                ren[cols[i + 1]] = f"{base}_ok"
    out = out.rename(columns=ren)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    for c in _NUMERIC:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out = out[out["Minutes played"] > 0].dropna(subset=["Date"])
    out["Competition"] = out["Competition"].astype(str)
    out["tier"] = out["Competition"].map(
        lambda c: TIER_YOUTH if _YOUTH_PAT.search(c)
        else (TIER_SENIOR if _SENIOR_PAT.search(c) else TIER_SENIOR))
    out["ga"] = out["Goals"] + out["Assists"]
    out["source_file"] = source_name
    return out.sort_values("Date").reset_index(drop=True)


def infer_team(matches: pd.DataFrame) -> str:
    """The player's club = the team name present in most 'Match' strings."""
    counts: dict[str, int] = {}
    for m in matches["Match"].astype(str):
        m = re.sub(r"\s*\d+:\d+\s*$", "", m).strip()
        for team in (t.strip() for t in m.split(" - ")):
            if team:
                counts[team] = counts.get(team, 0) + 1
    return max(counts, key=counts.get) if counts else "?"


def filter_matches(matches: pd.DataFrame,
                   last_n: int | None = None,
                   competitions: list[str] | None = None,
                   date_range: tuple | None = None,
                   min_minutes: int = 0) -> pd.DataFrame:
    """Apply the page's filters. ``last_n`` counts backwards from the most
    recent match AFTER the other filters, so 'last 10 league matches' works."""
    out = matches.copy()
    if competitions:
        out = out[out["Competition"].isin(competitions)]
    if date_range:
        lo, hi = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out["Date"] >= lo) & (out["Date"] <= hi)]
    if min_minutes:
        out = out[out["Minutes played"] >= min_minutes]
    out = out.sort_values("Date")
    if last_n:
        out = out.tail(last_n)
    return out.reset_index(drop=True)


def aggregate_per90(matches: pd.DataFrame) -> dict[str, float]:
    """Windowed per-90 profile of whatever match set the filters produced."""
    m = float(matches["Minutes played"].sum())
    if m <= 0:
        return {}
    f = 90.0 / m

    def tot(col: str) -> float:
        return float(matches[col].sum()) if col in matches.columns else 0.0

    def pct(ok: str, att: str) -> float:
        return 100.0 * tot(ok) / tot(att) if tot(att) > 0 else 0.0

    return {
        "matches": len(matches), "minutes": int(m),
        "goals": int(tot("Goals")), "assists": int(tot("Assists")),
        "xg": round(tot("xG"), 2),
        "goals90": round(tot("Goals") * f, 2),
        "assists90": round(tot("Assists") * f, 2),
        "ga90": round((tot("Goals") + tot("Assists")) * f, 2),
        "xg90": round(tot("xG") * f, 2),
        "shots90": round(tot("shots") * f, 2), "shots_pct": round(pct("shots_ok", "shots"), 1),
        "dribbles90": round(tot("dribbles") * f, 2),
        "dribbles_pct": round(pct("dribbles_ok", "dribbles"), 1),
        "duels90": round(tot("duels") * f, 1), "duels_pct": round(pct("duels_ok", "duels"), 1),
        "aerials90": round(tot("aerials") * f, 2),
        "aerials_pct": round(pct("aerials_ok", "aerials"), 1),
        "passes90": round(tot("passes") * f, 1), "passes_pct": round(pct("passes_ok", "passes"), 1),
        "crosses90": round(tot("crosses") * f, 2),
        "long_passes90": round(tot("long_passes") * f, 2),
        "interceptions90": round(tot("Interceptions") * f, 2),
        "recoveries90": round(tot("recoveries") * f, 1),
        "losses90": round(tot("losses") * f, 1),
        "yellows": int(tot("Yellow card")), "reds": int(tot("Red card")),
    }


def form_series(matches: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Per-match frame with rolling per-90 form lines for the timeline chart."""
    out = matches.sort_values("Date").copy()
    roll_min = out["Minutes played"].rolling(window, min_periods=1).sum()
    for src, dst in (("ga", "ga90_roll"), ("xG", "xg90_roll"),
                     ("dribbles", "dribbles90_roll"), ("duels", "duels90_roll")):
        if src in out.columns:
            out[dst] = (out[src].rolling(window, min_periods=1).sum()
                        * 90.0 / roll_min.replace(0, pd.NA)).astype(float).round(2)
    out["opponent"] = out["Match"].astype(str).str.replace(
        r"\s*\d+:\d+\s*$", "", regex=True)
    return out


def consistency(matches: pd.DataFrame) -> dict[str, float]:
    """Reliability numbers only a match-by-match feed can produce."""
    if matches.empty:
        return {}
    ga = matches.sort_values("Date")["ga"]
    droughts = (ga == 0).astype(int).groupby((ga > 0).cumsum()).sum()
    return {
        "ga_matches_pct": round(100.0 * (ga > 0).mean(), 1),
        "max_drought": int(droughts.max()) if len(droughts) else 0,
        "starts": int((matches["Minutes played"] >= 60).sum()),
        "full_matches": int((matches["Minutes played"] >= 90).sum()),
        "avg_minutes": round(float(matches["Minutes played"].mean()), 1),
    }


def competition_split(matches: pd.DataFrame) -> pd.DataFrame:
    """Per-competition aggregate rows (matches, minutes, G, A, xG, per-90s)."""
    rows = []
    for comp, sub in matches.groupby("Competition"):
        m = sub["Minutes played"].sum()
        f = 90.0 / m if m else 0.0
        rows.append({
            "Competición": comp, "PJ": len(sub), "Min": int(m),
            "Goles": int(sub["Goals"].sum()), "Asist": int(sub["Assists"].sum()),
            "xG": round(sub["xG"].sum(), 2),
            "G+A/90": round((sub["Goals"].sum() + sub["Assists"].sum()) * f, 2),
            "xG/90": round(sub["xG"].sum() * f, 2),
        })
    return (pd.DataFrame(rows).sort_values("Min", ascending=False)
            .reset_index(drop=True))


# Reference values for a top-5-league attacking starter — APPROXIMATE
# benchmarks for narrative framing, NOT computed percentiles (this export has
# no peer sample). Every consumer must label them as such.
ATTACKER_REFERENCE = {
    "ga90": 0.40, "xg90": 0.25, "shots90": 2.3, "dribbles90": 2.2,
    "dribbles_pct": 50.0, "duels_pct": 42.0, "passes_pct": 80.0,
    "aerials_pct": 35.0, "losses90": 10.0,
}


def strengths_weaknesses(agg: dict) -> tuple[list[str], list[str]]:
    """Rule-based reading of the windowed profile vs ATTACKER_REFERENCE."""
    if not agg:
        return [], []
    S, W = [], []
    if agg["dribbles90"] >= 3.5:
        S.append(f"Regateador de gran volumen: {agg['dribbles90']}/90 "
                 f"al {agg['dribbles_pct']:.0f}% de éxito.")
    if agg["duels90"] >= 18:
        S.append(f"Encara y disputa sin descanso: {agg['duels90']} duelos/90.")
    if agg["recoveries90"] >= 3:
        S.append(f"Trabajo sin balón real: {agg['recoveries90']} recuperaciones/90 "
                 f"y {agg['interceptions90']}/90 intercepciones.")
    if agg["xg90"] > 0 and abs(agg["goals90"] - agg["xg90"]) <= 0.06:
        S.append(f"Finalización honesta: convierte en línea con su xG "
                 f"({agg['goals90']} G/90 vs {agg['xg90']} xG/90).")
    elif agg["goals90"] > agg["xg90"] + 0.06:
        S.append(f"Sobre-rendimiento del xG: {agg['goals90']} G/90 sobre "
                 f"{agg['xg90']} xG/90 (vigilar sostenibilidad).")
    if agg["shots_pct"] >= 45:
        S.append(f"Buena puntería: {agg['shots_pct']:.0f}% de tiros a puerta.")

    ref = ATTACKER_REFERENCE
    if agg["ga90"] < ref["ga90"] * 0.6:
        W.append(f"Producción final baja: {agg['ga90']} G+A/90 vs ~{ref['ga90']} "
                 "esperable en un titular ofensivo de liga top.")
    if agg["losses90"] > ref["losses90"]:
        W.append(f"Pérdidas altas: {agg['losses90']}/90 — el precio de su verticalidad.")
    if agg["aerials_pct"] < ref["aerials_pct"] and agg["aerials90"] >= 1:
        W.append(f"Juego aéreo débil ({agg['aerials_pct']:.0f}%): no usarlo "
                 "como referencia en área.")
    if agg["passes_pct"] < ref["passes_pct"] - 5:
        W.append(f"Precisión de pase mejorable ({agg['passes_pct']:.0f}%) con "
                 f"volumen bajo ({agg['passes90']}/90): perfil directo, no organizador.")
    if agg["duels_pct"] < ref["duels_pct"] - 4:
        W.append(f"Solo gana el {agg['duels_pct']:.0f}% de sus duelos — asume "
                 "mucho riesgo por acción.")
    return S, W


def video_checklist(agg: dict, cons: dict) -> list[str]:
    """What the data can NOT confirm — the scout's to-watch list."""
    if not agg:
        return []
    out = []
    if agg["losses90"] > 9:
        out.append("Las pérdidas: ¿regates fallidos en último tercio (aceptable) "
                   "o pérdidas en salida bajo presión (grave)?")
    if agg["dribbles90"] >= 3 and agg["ga90"] < 0.3:
        out.append("Toma de decisión tras el regate: supera al rival y luego qué — "
                   "el gap entre conducción y producción sugiere que la última "
                   "decisión es el cuello de botella.")
    if cons.get("max_drought", 0) >= 8:
        out.append(f"Ver 3-4 partidos de su racha de {cons['max_drought']} sin "
                   "G+A: ¿falta de llegada, definición, o rol táctico?")
    if agg["recoveries90"] >= 3:
        out.append("Comportamiento en presión alta: sus recuperaciones sugieren "
                   "motor; confirmar intensidad y timing.")
    if agg["duels_pct"] < 42:
        out.append(f"Duelos al {agg['duels_pct']:.0f}%: ¿le falta cuerpo o elige "
                   "mal cuándo encarar?")
    out.append("Lenguaje corporal y reacción a la pérdida (dato ausente en Wyscout).")
    return out
