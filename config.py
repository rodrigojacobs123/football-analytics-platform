"""Central configuration for the Club América Sports Analytics Platform."""

import os
from pathlib import Path

# ── Data paths ──────────────────────────────────────────────────────────────
DATA_ROOT = Path(os.environ.get("AME_DATA_ROOT", "/Users/rodrigojacobs/Desktop/Final Project/testeo_ligas_norteamerica"))
DEFAULT_LEAGUE = "Mexico_Liga_MX"
DEFAULT_SEASON = "2025-2026"

# ── Club América identifiers ─────────────────────────────────────────────────
AME_TEAM_ID = "eu8c408f59yx7egaqossbv25e"
AME_TEAM_CODE = "AME"
AME_TEAM_NAME = "CF América"
AME_TEAM_FOLDER = "CF_América"
AME_VENUE = "Estadio Azteca"
AME_VENUE_ID = ""
AME_CREST_URL = (
    "https://omo.akamai.opta.net/image.php?h=www.scoresway.com"
    "&sport=football&entity=team&description=badges&dimensions=150"
    f"&id={AME_TEAM_ID}"
)

# ── Visual identity — synced with viz/theme.py THEMES["america"] ─────────
AME_YELLOW = "#FFD100"       # Primary (amarillo América)
AME_BLACK = "#04132E"        # Background (navy)
AME_BLUE = "#2E6BD6"         # Accent blue
AME_WHITE = "#EAF0FA"        # Text primary
AME_DARK_BG = "#04132E"      # Same as bg
AME_CARD_BG = "#0A1F44"      # Surface
AME_GRID = "#1E3461"         # Border / grid lines

# ── Opta event type IDs ────────────────────────────────────────────────────
EVENT_PASS = 1
EVENT_OFFSIDE_PASS = 2
EVENT_TAKE_ON = 3
EVENT_FOUL = 4
EVENT_OUT = 5
EVENT_CORNER = 6
EVENT_TACKLE = 7
EVENT_INTERCEPTION = 8
EVENT_TURNOVER = 9
EVENT_SAVE = 10
EVENT_CLAIM = 11
EVENT_CLEARANCE = 12
EVENT_MISS = 13
EVENT_POST = 14
EVENT_ATTEMPT_SAVED = 15
EVENT_GOAL = 16
EVENT_CARD = 17
EVENT_PLAYER_OFF = 18
EVENT_PLAYER_ON = 19
EVENT_PLAYER_RETIRED = 20
EVENT_BALL_RECOVERY = 49
EVENT_DISPOSSESSED = 50
EVENT_KEEPER_PICKUP = 52
EVENT_CHANCE_MISSED = 60
EVENT_BALL_TOUCH = 61
EVENT_BLOCKED_PASS = 74
EVENT_SHIELD_BALL = 83
EVENT_END = 30
EVENT_START = 32
EVENT_TEAM_SETUP = 34
EVENT_FORMATION_CHANGE = 40
EVENT_AERIAL = 44

# Shot-related type IDs (for filtering)
SHOT_TYPE_IDS = {EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED, EVENT_GOAL}

# ── Opta qualifier IDs ─────────────────────────────────────────────────────
QUAL_XG = 395
QUAL_XG_TEAM = 396
QUAL_BODY_PART = 72
QUAL_INVOLVED_PLAYER = 140
QUAL_PASS_END_X = 140
QUAL_PASS_END_Y = 141
QUAL_SHOT_DISTANCE = 230
QUAL_SHOT_ANGLE = 231
QUAL_FORMATION = 44
QUAL_FORMATION_TYPE = 130
QUAL_PLAYER_IDS = 30
QUAL_SHIRT_NUMBERS = 59
QUAL_PLAYER_POSITION = 131
QUAL_ASSIST = 76
QUAL_PENALTY = 9           # qualifier 9 = penalty kick (NOT Q22, which = "inside penalty area")
QUAL_OWN_GOAL = 28
QUAL_HEAD = 15
QUAL_RIGHT_FOOT = 72
QUAL_RELATED_EVENT = 55
QUAL_ZONE = 56

# ── Opta formation type ID → formation string (qualifier 130) ────────
# Empirically validated against Opta formation type mappings.
OPTA_FORMATION_MAP = {
    "1": "4-4-2",
    "2": "4-4-1-1",
    "4": "4-3-3",
    "5": "4-5-1",
    "6": "4-4-2",
    "7": "4-1-4-1",
    "8": "4-2-3-1",
    "9": "4-3-2-1",
    "10": "5-3-2",
    "11": "5-4-1",
    "12": "3-5-2",
    "13": "3-4-3",
    "14": "3-4-2-1",
    "15": "4-1-2-1-2",
    "16": "3-5-1-1",
    "17": "3-4-2-1",
    "18": "3-1-4-2",
    "19": "3-4-1-2",
    "20": "4-2-4-0",
    "21": "4-2-2-2",
    "23": "4-1-3-2",
}

# ── Set-piece analysis constants ──────────────────────────────────────────
QUAL_CORNER_TYPE = 56       # qualifier for corner delivery type
CORNER_TYPE_LABELS = {
    "Center": "Inswinging",
    "Back": "Short / Back",
    "Right": "Right Side",
    "Left": "Left Side",
}
SET_PIECE_WINDOW_SECS = 45  # seconds after corner/foul to attribute shots

# ── Qualifier value constants ───────────────────────────────────────────────
BODY_PART_MAP = {"Head": "Head", "Right": "Right Foot", "Left": "Left Foot"}

# ── Shot outcome labels ─────────────────────────────────────────────────────
SHOT_OUTCOME_MAP = {
    EVENT_GOAL: "Goal",
    EVENT_ATTEMPT_SAVED: "Saved",
    EVENT_MISS: "Missed",
    EVENT_POST: "Post",
}

# ── Card type labels ────────────────────────────────────────────────────────
CARD_TYPE_MAP = {
    "YC": "Yellow Card",
    "Y2C": "Second Yellow",
    "RC": "Red Card",
}

# ── Liga MX "Grandes" team IDs (for defaults in comparison views) ──────────
BIG_SIX = {
    "CF América":                              "eu8c408f59yx7egaqossbv25e",
    "CD Guadalajara":                          "e603sojy77s4u0ypqds2v2a1g",
    "CF Cruz Azul":                            "1aw67co8uut64yckd3wbhy9t2",
    "Club Tigres UANL":                        "6hmo9mrlz73nwxkshwuu5vsfm",
    "CF Monterrey":                            "233335xtoe3e3phg3hp91xguq",
    "CF Pachuca":                              "cynfvfb31rml7xrlsnejf8r6j",
}

# ── Elo rating parameters ──────────────────────────────────────────────────
ELO_INITIAL = 1500
ELO_K_FACTOR = 20
ELO_HOME_ADVANTAGE = 50

# ── Poisson model parameters ───────────────────────────────────────────────
POISSON_MAX_GOALS = 8
MONTE_CARLO_SIMS = 100_000
HOME_FACTOR = 1.1
LEAGUE_AVG_GOALS_PER_TEAM = 1.35

# ── Enhanced prediction model constants ───────────────────────────────────
UCL_WEIGHT = 1.2                    # same-competition match weight for blending
DOMESTIC_WEIGHT = 0.8               # cross-competition domestic data weight
FORM_WINDOW = 5                     # recent matches for form calculation
FORM_DECAY = 0.85                   # exponential decay per match backward
DIXON_COLES_RHO = -0.13            # low-score correction (Dixon & Coles 1997)
XG_ADJUSTMENT_WEIGHT = 0.25        # how much xG luck shifts lambda
ELO_LAMBDA_SCALE = 0.001           # Elo diff → lambda multiplier
TACTICAL_DOMINANCE_WEIGHT = 0.10   # tactical metrics contribution
MIN_MATCHES_FOR_PREDICTION = 3     # minimum matches required for prediction

# ── Player rating parameters ───────────────────────────────────────────────
MIN_APPEARANCES_FOR_RATING = 5
MIN_MINUTES_FOR_RATING = 450  # ~5 full matches, avoids per-90 inflation
RATING_FLOOR = 40
RATING_CEILING = 99

# ── Available seasons (Liga MX) ─────────────────────────────────────────────
EPL_SEASONS = [
    "2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022",
    "2020-2021", "2019-2020", "2018-2019", "2017-2018", "2016-2017",
    "2015-2016", "2014-2015",
]

# ── Available competitions ─────────────────────────────────────────────────
COMPETITIONS = {
    # Mexico
    "Mexico_Liga_MX":              "Liga MX",
    "Mexico_Copa_MX":              "Copa MX",
    "Mexico_Supercopa_MX":         "Supercopa MX",
    # CONCACAF
    "Concacaf_Concacaf_Champions_Cup":   "CONCACAF Champions Cup",
    "Concacaf_Leagues_Cup":              "Leagues Cup",
    "Concacaf_Concacaf_Gold_Cup":        "Gold Cup",
    # North America
    "USA_MLS":                     "MLS",
    "Canada_Canadian_Premier_League": "Canadian Premier League",
}

# Competitions where Club América participates (for page guards)
AME_LEAGUES = {
    "Mexico_Liga_MX",
    "Mexico_Copa_MX",
    "Mexico_Supercopa_MX",
    "Concacaf_Concacaf_Champions_Cup",
    "Concacaf_Leagues_Cup",
}

# ── Position-specific rating categories ───────────────────────────────────
POSITION_CATEGORIES = {
    "Goalkeeper": ["Shot Stopping", "Distribution", "Command", "Reflexes", "Clean Sheets"],
    "Defender":   ["Tackling", "Aerial", "Positioning", "Ball Playing", "Physicality"],
    "Midfielder": ["Passing", "Creativity", "Ball Carrying", "Defensive Work", "Pressing"],
    "Forward":    ["Finishing", "Movement", "Chance Creation", "Dribbling", "Aerial Threat"],
    "Attacker":   ["Finishing", "Movement", "Chance Creation", "Dribbling", "Aerial Threat"],
}

POSITION_CATEGORY_DISPLAY = {
    "GK_ShotStop": "Shot Stopping", "GK_Dist": "Distribution",
    "GK_Command": "Command", "GK_Reflex": "Reflexes", "GK_CleanSheet": "Clean Sheets",
    "DEF_Tackle": "Tackling", "DEF_Aerial": "Aerial",
    "DEF_Position": "Positioning", "DEF_BallPlay": "Ball Playing", "DEF_Physical": "Physicality",
    "MID_Pass": "Passing", "MID_Create": "Creativity",
    "MID_Carry": "Ball Carrying", "MID_DefWork": "Defensive Work", "MID_Press": "Pressing",
    "FWD_Finish": "Finishing", "FWD_Move": "Movement",
    "FWD_Chance": "Chance Creation", "FWD_Dribble": "Dribbling", "FWD_AerialThreat": "Aerial Threat",
}
