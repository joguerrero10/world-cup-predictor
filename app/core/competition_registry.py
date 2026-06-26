"""
Competition Registry: resolución de equipos por competición + temporada.

PROBLEMA QUE RESUELVE:
  - Antes: top_elo_teams() devuelve los mismos equipos para TODAS las competiciones.
    → Champions League mostraba selecciones nacionales.
    → Premier League mostraba países.

  - Ahora: get_competition_teams(competition, season) devuelve exactamente
    los equipos correctos para cada competición, separando clubes de selecciones.

ESTRATEGIA:
  1. Datos estáticos de seed (siempre disponibles, usados como fallback).
  2. Datos de BD (SeasonTeam join teams) si el ETL ya cargó la temporada.
  3. Los equipos están tipados como CLUB o NATIONAL según la competición.

USO:
    from app.core.competition_registry import get_competition_teams
    teams = get_competition_teams("ucl", season=2025)     # clubes europeos
    teams = get_competition_teams("premier_league")       # clubes ingleses
    teams = get_competition_teams("fifa_wc_2026")         # selecciones nacionales
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session


class TeamType(str, Enum):
    CLUB = "club"
    NATIONAL = "national"


@dataclass
class RegistryTeam:
    name: str
    short_name: str
    country: str
    team_type: TeamType
    group: Optional[str] = None        # Grupo A/B/C en fases de grupos
    elo_seed: float = 1500.0           # Rating Elo inicial
    fifa_rank: Optional[int] = None    # Ranking FIFA (selecciones)
    uefa_rank: Optional[int] = None    # Ranking UEFA (clubes)
    market_value_eur: Optional[float] = None


# ---------------------------------------------------------------------------
# DATOS ESTÁTICOS DE SEED — siempre disponibles (no requieren ETL ni DB)
# ---------------------------------------------------------------------------

_SEED: dict[str, list[RegistryTeam]] = {

    # ─── FIFA WORLD CUP 2026 (48 selecciones, 12 grupos) ───────────────────
    "fifa_wc_2026": [
        # GRUPO A — Norteamérica (sede compartida)
        RegistryTeam("United States",  "USA", "USA",     TeamType.NATIONAL, "A", 1650, 13),
        RegistryTeam("Mexico",         "MEX", "Mexico",  TeamType.NATIONAL, "A", 1700, 15),
        RegistryTeam("Canada",         "CAN", "Canada",  TeamType.NATIONAL, "A", 1620, 47),
        RegistryTeam("Honduras",       "HON", "Honduras",TeamType.NATIONAL, "A", 1510, 77),
        # GRUPO B
        RegistryTeam("Argentina",      "ARG", "Argentina",TeamType.NATIONAL,"B", 2100, 1),
        RegistryTeam("Chile",          "CHI", "Chile",   TeamType.NATIONAL, "B", 1720, 22),
        RegistryTeam("Peru",           "PER", "Peru",    TeamType.NATIONAL, "B", 1640, 40),
        RegistryTeam("Australia",      "AUS", "Australia",TeamType.NATIONAL,"B", 1630, 24),
        # GRUPO C
        RegistryTeam("France",         "FRA", "France",  TeamType.NATIONAL, "C", 2000, 2),
        RegistryTeam("Morocco",        "MAR", "Morocco", TeamType.NATIONAL, "C", 1820, 14),
        RegistryTeam("Senegal",        "SEN", "Senegal", TeamType.NATIONAL, "C", 1740, 20),
        RegistryTeam("DR Congo",       "COD", "Congo DR",TeamType.NATIONAL, "C", 1570, 50),
        # GRUPO D
        RegistryTeam("England",        "ENG", "England", TeamType.NATIONAL, "D", 1960, 5),
        RegistryTeam("Netherlands",    "NED", "Netherlands",TeamType.NATIONAL,"D",1920,7),
        RegistryTeam("Iran",           "IRN", "Iran",    TeamType.NATIONAL, "D", 1710, 23),
        RegistryTeam("Panama",         "PAN", "Panama",  TeamType.NATIONAL, "D", 1590, 60),
        # GRUPO E
        RegistryTeam("Spain",          "ESP", "Spain",   TeamType.NATIONAL, "E", 2010, 3),
        RegistryTeam("Croatia",        "CRO", "Croatia", TeamType.NATIONAL, "E", 1850, 10),
        RegistryTeam("South Korea",    "KOR", "South Korea",TeamType.NATIONAL,"E",1710,25),
        RegistryTeam("Ecuador",        "ECU", "Ecuador", TeamType.NATIONAL, "E", 1650, 43),
        # GRUPO F
        RegistryTeam("Brazil",         "BRA", "Brazil",  TeamType.NATIONAL, "F", 2050, 4),
        RegistryTeam("Colombia",       "COL", "Colombia",TeamType.NATIONAL, "F", 1780, 19),
        RegistryTeam("Paraguay",       "PAR", "Paraguay",TeamType.NATIONAL, "F", 1620, 65),
        RegistryTeam("Costa Rica",     "CRC", "Costa Rica",TeamType.NATIONAL,"F",1580,52),
        # GRUPO G
        RegistryTeam("Germany",        "GER", "Germany", TeamType.NATIONAL, "G", 1950, 12),
        RegistryTeam("Portugal",       "POR", "Portugal",TeamType.NATIONAL, "G", 1950, 6),
        RegistryTeam("Turkey",         "TUR", "Turkey",  TeamType.NATIONAL, "G", 1780, 32),
        RegistryTeam("Albania",        "ALB", "Albania", TeamType.NATIONAL, "G", 1600, 65),
        # GRUPO H
        RegistryTeam("Belgium",        "BEL", "Belgium", TeamType.NATIONAL, "H", 1870, 3),
        RegistryTeam("Japan",          "JPN", "Japan",   TeamType.NATIONAL, "H", 1760, 17),
        RegistryTeam("Saudi Arabia",   "KSA", "Saudi Arabia",TeamType.NATIONAL,"H",1670,58),
        RegistryTeam("New Zealand",    "NZL", "New Zealand",TeamType.NATIONAL,"H",1520,98),
        # GRUPO I
        RegistryTeam("Italy",          "ITA", "Italy",   TeamType.NATIONAL, "I", 1930, 9),
        RegistryTeam("Uruguay",        "URU", "Uruguay", TeamType.NATIONAL, "I", 1860, 18),
        RegistryTeam("Venezuela",      "VEN", "Venezuela",TeamType.NATIONAL, "I", 1600, 62),
        RegistryTeam("Cameroon",       "CMR", "Cameroon",TeamType.NATIONAL, "I", 1640, 38),
        # GRUPO J
        RegistryTeam("Switzerland",    "SUI", "Switzerland",TeamType.NATIONAL,"J",1830,21),
        RegistryTeam("Austria",        "AUT", "Austria", TeamType.NATIONAL, "J", 1790, 27),
        RegistryTeam("Egypt",          "EGY", "Egypt",   TeamType.NATIONAL, "J", 1680, 35),
        RegistryTeam("Nigeria",        "NGA", "Nigeria", TeamType.NATIONAL, "J", 1700, 39),
        # GRUPO K
        RegistryTeam("Denmark",        "DEN", "Denmark", TeamType.NATIONAL, "K", 1850, 16),
        RegistryTeam("Serbia",         "SRB", "Serbia",  TeamType.NATIONAL, "K", 1790, 28),
        RegistryTeam("Algeria",        "ALG", "Algeria", TeamType.NATIONAL, "K", 1710, 36),
        RegistryTeam("Cuba",           "CUB", "Cuba",    TeamType.NATIONAL, "K", 1480, 105),
        # GRUPO L
        RegistryTeam("Poland",         "POL", "Poland",  TeamType.NATIONAL, "L", 1760, 29),
        RegistryTeam("Ivory Coast",    "CIV", "Ivory Coast",TeamType.NATIONAL,"L",1740,41),
        RegistryTeam("South Africa",   "RSA", "South Africa",TeamType.NATIONAL,"L",1630,60),
        RegistryTeam("Guatemala",      "GUA", "Guatemala",TeamType.NATIONAL, "L", 1530, 88),
    ],

    # ─── UEFA CHAMPIONS LEAGUE 2024/25 (36 clubes, formato liga) ──────────
    "ucl": [
        RegistryTeam("Real Madrid",       "RMA", "Spain",       TeamType.CLUB, elo_seed=2050, uefa_rank=1),
        RegistryTeam("Manchester City",   "MCI", "England",     TeamType.CLUB, elo_seed=1990, uefa_rank=2),
        RegistryTeam("Bayern Munich",     "BAY", "Germany",     TeamType.CLUB, elo_seed=1960, uefa_rank=3),
        RegistryTeam("Paris SG",          "PSG", "France",      TeamType.CLUB, elo_seed=1940, uefa_rank=4),
        RegistryTeam("Arsenal",           "ARS", "England",     TeamType.CLUB, elo_seed=1920, uefa_rank=5),
        RegistryTeam("Barcelona",         "BAR", "Spain",       TeamType.CLUB, elo_seed=1930, uefa_rank=6),
        RegistryTeam("Atlético Madrid",   "ATM", "Spain",       TeamType.CLUB, elo_seed=1880, uefa_rank=7),
        RegistryTeam("Liverpool",         "LIV", "England",     TeamType.CLUB, elo_seed=1950, uefa_rank=8),
        RegistryTeam("Inter Milan",       "INT", "Italy",       TeamType.CLUB, elo_seed=1870, uefa_rank=9),
        RegistryTeam("Borussia Dortmund", "BVB", "Germany",     TeamType.CLUB, elo_seed=1830, uefa_rank=10),
        RegistryTeam("RB Leipzig",        "RBL", "Germany",     TeamType.CLUB, elo_seed=1800, uefa_rank=11),
        RegistryTeam("Bayer Leverkusen",  "B04", "Germany",     TeamType.CLUB, elo_seed=1850, uefa_rank=12),
        RegistryTeam("Napoli",            "NAP", "Italy",       TeamType.CLUB, elo_seed=1800, uefa_rank=13),
        RegistryTeam("Benfica",           "BEN", "Portugal",    TeamType.CLUB, elo_seed=1780, uefa_rank=14),
        RegistryTeam("Porto",             "POR", "Portugal",    TeamType.CLUB, elo_seed=1760, uefa_rank=15),
        RegistryTeam("Sporting CP",       "SPO", "Portugal",    TeamType.CLUB, elo_seed=1740, uefa_rank=16),
        RegistryTeam("Atalanta",          "ATA", "Italy",       TeamType.CLUB, elo_seed=1810, uefa_rank=17),
        RegistryTeam("AC Milan",          "MIL", "Italy",       TeamType.CLUB, elo_seed=1820, uefa_rank=18),
        RegistryTeam("Juventus",          "JUV", "Italy",       TeamType.CLUB, elo_seed=1780, uefa_rank=19),
        RegistryTeam("Feyenoord",         "FEY", "Netherlands", TeamType.CLUB, elo_seed=1760, uefa_rank=20),
        RegistryTeam("Celtic",            "CEL", "Scotland",    TeamType.CLUB, elo_seed=1700, uefa_rank=25),
        RegistryTeam("PSV Eindhoven",     "PSV", "Netherlands", TeamType.CLUB, elo_seed=1750, uefa_rank=21),
        RegistryTeam("Club Brugge",       "CLU", "Belgium",     TeamType.CLUB, elo_seed=1700, uefa_rank=22),
        RegistryTeam("Shakhtar Donetsk",  "SHA", "Ukraine",     TeamType.CLUB, elo_seed=1690, uefa_rank=23),
        RegistryTeam("Monaco",            "MON", "France",      TeamType.CLUB, elo_seed=1720, uefa_rank=24),
        RegistryTeam("Aston Villa",       "AVL", "England",     TeamType.CLUB, elo_seed=1810, uefa_rank=26),
        RegistryTeam("Bologna",           "BOL", "Italy",       TeamType.CLUB, elo_seed=1700, uefa_rank=27),
        RegistryTeam("Girona",            "GIR", "Spain",       TeamType.CLUB, elo_seed=1710, uefa_rank=28),
        RegistryTeam("Stuttgart",         "VFB", "Germany",     TeamType.CLUB, elo_seed=1700, uefa_rank=29),
        RegistryTeam("Sturm Graz",        "STU", "Austria",     TeamType.CLUB, elo_seed=1650, uefa_rank=30),
        RegistryTeam("Brest",             "BRE", "France",      TeamType.CLUB, elo_seed=1660, uefa_rank=31),
        RegistryTeam("Slavia Prague",     "SLA", "Czech Rep.",  TeamType.CLUB, elo_seed=1640, uefa_rank=32),
        RegistryTeam("Young Boys",        "YB",  "Switzerland", TeamType.CLUB, elo_seed=1620, uefa_rank=33),
        RegistryTeam("Red Star Belgrade", "RSB", "Serbia",      TeamType.CLUB, elo_seed=1630, uefa_rank=34),
        RegistryTeam("Sparta Prague",     "SPA", "Czech Rep.",  TeamType.CLUB, elo_seed=1620, uefa_rank=35),
        RegistryTeam("RB Salzburg",       "SAL", "Austria",     TeamType.CLUB, elo_seed=1640, uefa_rank=36),
    ],

    # ─── PREMIER LEAGUE 2024/25 (20 clubes ingleses) ─────────────────────
    "premier_league": [
        RegistryTeam("Liverpool",           "LIV", "England", TeamType.CLUB, elo_seed=1950),
        RegistryTeam("Arsenal",             "ARS", "England", TeamType.CLUB, elo_seed=1920),
        RegistryTeam("Manchester City",     "MCI", "England", TeamType.CLUB, elo_seed=1990),
        RegistryTeam("Chelsea",             "CHE", "England", TeamType.CLUB, elo_seed=1860),
        RegistryTeam("Aston Villa",         "AVL", "England", TeamType.CLUB, elo_seed=1810),
        RegistryTeam("Tottenham",           "TOT", "England", TeamType.CLUB, elo_seed=1800),
        RegistryTeam("Newcastle United",    "NEW", "England", TeamType.CLUB, elo_seed=1800),
        RegistryTeam("Manchester United",   "MUN", "England", TeamType.CLUB, elo_seed=1780),
        RegistryTeam("West Ham United",     "WHU", "England", TeamType.CLUB, elo_seed=1730),
        RegistryTeam("Brighton",            "BHA", "England", TeamType.CLUB, elo_seed=1750),
        RegistryTeam("Brentford",           "BRE", "England", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Fulham",              "FUL", "England", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Wolverhampton",       "WOL", "England", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Crystal Palace",      "CRY", "England", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Everton",             "EVE", "England", TeamType.CLUB, elo_seed=1660),
        RegistryTeam("Nottingham Forest",   "NFO", "England", TeamType.CLUB, elo_seed=1670),
        RegistryTeam("Bournemouth",         "BOU", "England", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Leicester City",      "LEI", "England", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Ipswich Town",        "IPS", "England", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("Southampton",         "SOU", "England", TeamType.CLUB, elo_seed=1580),
    ],

    # ─── LA LIGA 2024/25 (20 clubes españoles) ───────────────────────────
    "laliga": [
        RegistryTeam("Real Madrid",       "RMA", "Spain", TeamType.CLUB, elo_seed=2050),
        RegistryTeam("Barcelona",         "BAR", "Spain", TeamType.CLUB, elo_seed=1930),
        RegistryTeam("Atlético Madrid",   "ATM", "Spain", TeamType.CLUB, elo_seed=1880),
        RegistryTeam("Athletic Bilbao",   "ATH", "Spain", TeamType.CLUB, elo_seed=1780),
        RegistryTeam("Real Betis",        "BET", "Spain", TeamType.CLUB, elo_seed=1750),
        RegistryTeam("Villarreal",        "VIL", "Spain", TeamType.CLUB, elo_seed=1760),
        RegistryTeam("Real Sociedad",     "RSO", "Spain", TeamType.CLUB, elo_seed=1740),
        RegistryTeam("Girona",            "GIR", "Spain", TeamType.CLUB, elo_seed=1710),
        RegistryTeam("Valencia",          "VAL", "Spain", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Sevilla",           "SEV", "Spain", TeamType.CLUB, elo_seed=1720),
        RegistryTeam("Osasuna",           "OSA", "Spain", TeamType.CLUB, elo_seed=1670),
        RegistryTeam("Getafe",            "GET", "Spain", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Mallorca",          "MAL", "Spain", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Rayo Vallecano",    "RAY", "Spain", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Celta Vigo",        "CEL", "Spain", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Las Palmas",        "LPA", "Spain", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Deportivo Alavés",  "ALA", "Spain", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Leganés",           "LEG", "Spain", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("Espanyol",          "ESP", "Spain", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("Valladolid",        "VLL", "Spain", TeamType.CLUB, elo_seed=1580),
    ],

    # ─── BUNDESLIGA 2024/25 (18 clubes alemanes) ─────────────────────────
    "bundesliga": [
        RegistryTeam("Bayern Munich",     "BAY", "Germany", TeamType.CLUB, elo_seed=1960),
        RegistryTeam("Bayer Leverkusen",  "B04", "Germany", TeamType.CLUB, elo_seed=1850),
        RegistryTeam("Borussia Dortmund", "BVB", "Germany", TeamType.CLUB, elo_seed=1830),
        RegistryTeam("RB Leipzig",        "RBL", "Germany", TeamType.CLUB, elo_seed=1800),
        RegistryTeam("Stuttgart",         "VFB", "Germany", TeamType.CLUB, elo_seed=1750),
        RegistryTeam("Eintracht Frankfurt","SGE","Germany",  TeamType.CLUB, elo_seed=1740),
        RegistryTeam("Wolfsburg",         "WOB", "Germany", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Borussia M'gladbach","BMG","Germany",  TeamType.CLUB, elo_seed=1690),
        RegistryTeam("Werder Bremen",     "SVW", "Germany", TeamType.CLUB, elo_seed=1690),
        RegistryTeam("Augsburg",          "FCA", "Germany", TeamType.CLUB, elo_seed=1660),
        RegistryTeam("Union Berlin",      "FCU", "Germany", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Freiburg",          "SCF", "Germany", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Hoffenheim",        "TSG", "Germany", TeamType.CLUB, elo_seed=1660),
        RegistryTeam("Bochum",            "BOC", "Germany", TeamType.CLUB, elo_seed=1620),
        RegistryTeam("Mainz",             "M05", "Germany", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Heidenheim",        "FCH", "Germany", TeamType.CLUB, elo_seed=1630),
        RegistryTeam("Holstein Kiel",     "KIE", "Germany", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("St. Pauli",         "STP", "Germany", TeamType.CLUB, elo_seed=1610),
    ],

    # ─── SERIE A 2024/25 (20 clubes italianos) ───────────────────────────
    "serie_a": [
        RegistryTeam("Inter Milan",       "INT", "Italy", TeamType.CLUB, elo_seed=1870),
        RegistryTeam("AC Milan",          "MIL", "Italy", TeamType.CLUB, elo_seed=1820),
        RegistryTeam("Juventus",          "JUV", "Italy", TeamType.CLUB, elo_seed=1780),
        RegistryTeam("Napoli",            "NAP", "Italy", TeamType.CLUB, elo_seed=1800),
        RegistryTeam("Atalanta",          "ATA", "Italy", TeamType.CLUB, elo_seed=1810),
        RegistryTeam("Roma",              "ROM", "Italy", TeamType.CLUB, elo_seed=1760),
        RegistryTeam("Lazio",             "LAZ", "Italy", TeamType.CLUB, elo_seed=1750),
        RegistryTeam("Fiorentina",        "FIO", "Italy", TeamType.CLUB, elo_seed=1730),
        RegistryTeam("Bologna",           "BOL", "Italy", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Torino",            "TOR", "Italy", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Udinese",           "UDI", "Italy", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Genoa",             "GEN", "Italy", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Cagliari",          "CAG", "Italy", TeamType.CLUB, elo_seed=1630),
        RegistryTeam("Hellas Verona",     "HEL", "Italy", TeamType.CLUB, elo_seed=1620),
        RegistryTeam("Sassuolo",          "SAS", "Italy", TeamType.CLUB, elo_seed=1620),
        RegistryTeam("Lecce",             "LEC", "Italy", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Parma",             "PAR", "Italy", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Empoli",            "EMP", "Italy", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("Venezia",           "VEN", "Italy", TeamType.CLUB, elo_seed=1590),
        RegistryTeam("Monza",             "MON", "Italy", TeamType.CLUB, elo_seed=1630),
    ],

    # ─── LIGUE 1 2024/25 (18 clubes franceses) ───────────────────────────
    "ligue_1": [
        RegistryTeam("Paris SG",          "PSG", "France", TeamType.CLUB, elo_seed=1940),
        RegistryTeam("Monaco",            "MON", "France", TeamType.CLUB, elo_seed=1720),
        RegistryTeam("Brest",             "BRE", "France", TeamType.CLUB, elo_seed=1660),
        RegistryTeam("Lille",             "LIL", "France", TeamType.CLUB, elo_seed=1730),
        RegistryTeam("Lyon",              "OL",  "France", TeamType.CLUB, elo_seed=1720),
        RegistryTeam("Nice",              "NIC", "France", TeamType.CLUB, elo_seed=1700),
        RegistryTeam("Marseille",         "OM",  "France", TeamType.CLUB, elo_seed=1710),
        RegistryTeam("Rennes",            "REN", "France", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Lens",              "LEN", "France", TeamType.CLUB, elo_seed=1680),
        RegistryTeam("Strasbourg",        "STR", "France", TeamType.CLUB, elo_seed=1650),
        RegistryTeam("Reims",             "REI", "France", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Toulouse",          "TOU", "France", TeamType.CLUB, elo_seed=1640),
        RegistryTeam("Le Havre",          "HAV", "France", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Montpellier",       "MPL", "France", TeamType.CLUB, elo_seed=1610),
        RegistryTeam("Nantes",            "NAN", "France", TeamType.CLUB, elo_seed=1620),
        RegistryTeam("Auxerre",           "AUX", "France", TeamType.CLUB, elo_seed=1600),
        RegistryTeam("Saint-Étienne",     "SET", "France", TeamType.CLUB, elo_seed=1590),
        RegistryTeam("Angers",            "ANG", "France", TeamType.CLUB, elo_seed=1580),
    ],
}

# Alias de slugs (compatibilidad con slugs históricos del codebase)
_SLUG_ALIASES: dict[str, str] = {
    "worldcup":       "fifa_wc_2026",
    "world_cup":      "fifa_wc_2026",
    "wc2026":         "fifa_wc_2026",
    "champions":      "ucl",
    "ucl_2024":       "ucl",
    "premier":        "premier_league",
    "epl":            "premier_league",
    "laliga":         "laliga",
    "la_liga":        "laliga",
    "bundesliga":     "bundesliga",
    "bl1":            "bundesliga",
    "serie_a":        "serie_a",
    "seriea":         "serie_a",
    "ligue_1":        "ligue_1",
    "ligue1":         "ligue_1",
}


def _resolve_slug(slug: str) -> str:
    """Normaliza el slug: minúsculas + aliasing."""
    s = slug.strip().lower()
    return _SLUG_ALIASES.get(s, s)


def _load_from_db(db: Session, slug: str, season: Optional[int]) -> list[RegistryTeam]:
    """Carga equipos desde season_teams + teams si la temporada está en BD."""
    try:
        from app.db.models import SeasonTeam, Season, Competition, Team

        stmt = (
            select(Team, SeasonTeam)
            .join(SeasonTeam, SeasonTeam.team_id == Team.id)
            .join(Season, Season.id == SeasonTeam.season_id)
            .join(Competition, Competition.id == Season.competition_id)
            .where(Competition.slug == slug)
        )
        if season is not None:
            stmt = stmt.where(Season.year_start == season)

        rows = db.execute(stmt).all()
        if not rows:
            return []

        result = []
        for team, st in rows:
            result.append(RegistryTeam(
                name=team.name,
                short_name=team.short_name or team.name[:3].upper(),
                country=team.country or "Unknown",
                team_type=TeamType.CLUB if st.group_name is None else TeamType.NATIONAL,
                group=st.group_name,
                elo_seed=1500.0,
            ))
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def get_competition_teams(
    competition: str,
    season: Optional[int] = None,
    db: Optional[Session] = None,
) -> list[RegistryTeam]:
    """
    Devuelve los equipos para una competición específica.

    Prioridad:
      1. Base de datos (si db y season_teams disponibles).
      2. Datos estáticos de seed (siempre disponibles).

    Args:
        competition: slug de competición ("ucl", "premier_league", "fifa_wc_2026", ...)
        season:      año de inicio de temporada (None = más reciente disponible)
        db:          SQLAlchemy Session (None = solo datos estáticos)

    Returns:
        Lista de RegistryTeam con nombre, tipo, grupo y Elo seed.

    Raises:
        ValueError si la competición no existe en el registry.
    """
    slug = _resolve_slug(competition)

    if db is not None:
        db_teams = _load_from_db(db, slug, season)
        if db_teams:
            return db_teams

    if slug not in _SEED:
        available = sorted(_SEED.keys())
        raise ValueError(
            f"Competición '{competition}' (slug='{slug}') no encontrada en el registry. "
            f"Disponibles: {available}"
        )

    return list(_SEED[slug])


def get_team_names(
    competition: str,
    season: Optional[int] = None,
    db: Optional[Session] = None,
) -> list[str]:
    """Versión abreviada: solo nombres de equipos."""
    return [t.name for t in get_competition_teams(competition, season, db)]


def get_competition_groups(
    competition: str,
    season: Optional[int] = None,
    db: Optional[Session] = None,
) -> dict[str, list[str]]:
    """
    Devuelve grupos como dict: {grupo: [equipo1, equipo2, ...]}.
    Solo válido para competiciones con fase de grupos (Mundial, UCL pre-2024).
    """
    teams = get_competition_teams(competition, season, db)
    groups: dict[str, list[str]] = {}
    for t in teams:
        if t.group:
            groups.setdefault(t.group, []).append(t.name)
    return groups


def list_competitions() -> list[str]:
    """Slugs de todas las competiciones con datos estáticos."""
    return sorted(_SEED.keys())


def get_team_type(competition: str) -> TeamType:
    """Devuelve el tipo de equipo que usa la competición."""
    slug = _resolve_slug(competition)
    teams = _SEED.get(slug, [])
    if not teams:
        return TeamType.CLUB
    return teams[0].team_type
