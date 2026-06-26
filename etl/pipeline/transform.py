"""
Capa de transformación y normalización.

Convierte los DTOs crudos del proveedor al formato canónico esperado
por la base de datos.

El problema principal es que football-data.org usa nombres como
"Manchester United FC" mientras el CSV histórico usa "Manchester United".
Este módulo contiene el mapeo de normalización.
"""
from __future__ import annotations

import unicodedata

from etl.providers.base import MatchData, PlayerData, StandingData, TeamData

# ---------------------------------------------------------------------------
# Mapa de nombres: valor_del_proveedor → nombre_canónico_en_db
# ---------------------------------------------------------------------------

_CANONICAL: dict[str, str] = {
    # England
    "Manchester United FC": "Manchester United",
    "Manchester City FC": "Manchester City",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Liverpool FC": "Liverpool",
    "Tottenham Hotspur FC": "Tottenham Hotspur",
    "Tottenham Hotspur": "Tottenham Hotspur",
    "West Ham United FC": "West Ham United",
    "Newcastle United FC": "Newcastle United",
    "Aston Villa FC": "Aston Villa",
    "Everton FC": "Everton",
    "Leicester City FC": "Leicester City",
    "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
    "Brighton & Hove Albion FC": "Brighton & Hove Albion",
    "Fulham FC": "Fulham",
    "Crystal Palace FC": "Crystal Palace",
    "Brentford FC": "Brentford",
    "Nottingham Forest FC": "Nottingham Forest",
    "AFC Bournemouth": "Bournemouth",
    "Burnley FC": "Burnley",
    "Sheffield United FC": "Sheffield United",
    "Luton Town FC": "Luton Town",
    "Southampton FC": "Southampton",
    "Ipswich Town FC": "Ipswich Town",
    # Spain
    "FC Barcelona": "Barcelona",
    "Real Madrid CF": "Real Madrid",
    "Club Atlético de Madrid": "Atletico Madrid",
    "Athletic Club": "Athletic Bilbao",
    "Villarreal CF": "Villarreal",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "Valencia CF": "Valencia",
    "Sevilla FC": "Sevilla",
    "Real Betis Balompié": "Real Betis",
    "RC Celta de Vigo": "Celta Vigo",
    "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "Getafe CF": "Getafe",
    "UD Almería": "Almeria",
    "CA Osasuna": "Osasuna",
    "Girona FC": "Girona",
    "RCD Mallorca": "Mallorca",
    "UD Las Palmas": "Las Palmas",
    "Deportivo Alavés": "Alaves",
    "Real Valladolid CF": "Valladolid",
    "Cádiz CF": "Cadiz",
    # Germany
    "FC Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "RB Leipzig": "RB Leipzig",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "VfL Wolfsburg": "Wolfsburg",
    "1. FSV Mainz 05": "Mainz 05",
    "SC Freiburg": "Freiburg",
    "1. FC Union Berlin": "Union Berlin",
    "Borussia Mönchengladbach": "Borussia Monchengladbach",
    "FC Augsburg": "Augsburg",
    "TSG 1899 Hoffenheim": "Hoffenheim",
    "VfB Stuttgart": "Stuttgart",
    "SV Werder Bremen": "Werder Bremen",
    "VfL Bochum 1848": "Bochum",
    "Hamburger SV": "Hamburg",
    "Darmstadt 98": "Darmstadt",
    "FC Heidenheim 1846": "Heidenheim",
    # Italy
    "Juventus FC": "Juventus",
    "AC Milan": "AC Milan",
    "FC Internazionale Milano": "Internazionale",
    "Inter": "Internazionale",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "SSC Napoli": "Napoli",
    "Atalanta BC": "Atalanta",
    "ACF Fiorentina": "Fiorentina",
    "Bologna FC 1909": "Bologna",
    "Torino FC": "Torino",
    "US Sassuolo Calcio": "Sassuolo",
    "Udinese Calcio": "Udinese",
    "Cagliari Calcio": "Cagliari",
    "Genoa CFC": "Genoa",
    "AC Monza": "Monza",
    "US Lecce": "Lecce",
    "Hellas Verona FC": "Hellas Verona",
    "Frosinone Calcio": "Frosinone",
    "Empoli FC": "Empoli",
    # France
    "Paris Saint-Germain FC": "Paris Saint-Germain",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "Stade Rennais FC 1901": "Rennes",
    "Lille OSC": "Lille",
    "RC Lens": "Lens",
    "OGC Nice": "Nice",
    "Montpellier HSC": "Montpellier",
    "RC Strasbourg Alsace": "Strasbourg",
    "Stade Brestois 29": "Brest",
    "FC Nantes": "Nantes",
    "Stade de Reims": "Reims",
    "Toulouse FC": "Toulouse",
    "Le Havre AC": "Le Havre",
    # Champions League / International clubs
    "SL Benfica": "Benfica",
    "FC Porto": "Porto",
    "Sporting CP": "Sporting CP",
    "Club Brugge KV": "Club Brugge",
    "RSC Anderlecht": "Anderlecht",
    "AFC Ajax": "Ajax",
    "PSV Eindhoven": "PSV",
    "Feyenoord": "Feyenoord",
    "Celtic FC": "Celtic",
    "Rangers FC": "Rangers",
    "GNK Dinamo Zagreb": "Dinamo Zagreb",
    "FC Red Bull Salzburg": "Red Bull Salzburg",
    "FK Shakhtar Donetsk": "Shakhtar Donetsk",
    "FC Dynamo Kyiv": "Dynamo Kyiv",
    # National teams
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Chinese Taipei": "Taiwan",
    "United States": "United States",
    "Türkiye": "Turkey",
    "Côte d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde",
    "DR Congo": "DR Congo",
}

# Normalización ligera: minúsculas + sin acentos
def _normalize(name: str) -> str:
    name = name.strip()
    lowered = name.lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# Índice invertido normalizado para búsquedas fuzzy rápidas
_NORM_INDEX: dict[str, str] = {_normalize(k): v for k, v in _CANONICAL.items()}


def normalize_team_name(raw: str) -> str:
    """
    Convierte un nombre de equipo crudo al nombre canónico de la DB.

    1. Búsqueda exacta en el mapa canónico.
    2. Búsqueda normalizada (sin acentos, minúsculas).
    3. Si no hay match, devuelve el nombre original limpio.
    """
    raw = raw.strip()
    if not raw:
        return raw

    # Exact match
    if raw in _CANONICAL:
        return _CANONICAL[raw]

    # Normalized match
    norm = _normalize(raw)
    if norm in _NORM_INDEX:
        return _NORM_INDEX[norm]

    return raw


def normalize_match(m: MatchData) -> MatchData:
    from dataclasses import replace
    return replace(
        m,
        home_team=normalize_team_name(m.home_team),
        away_team=normalize_team_name(m.away_team),
    )


def normalize_team(t: TeamData) -> TeamData:
    from dataclasses import replace
    return replace(t, name=normalize_team_name(t.name))


def normalize_player(p: PlayerData) -> PlayerData:
    from dataclasses import replace
    return replace(p, team_name=normalize_team_name(p.team_name))


def normalize_standing(s: StandingData) -> StandingData:
    from dataclasses import replace
    return replace(s, team_name=normalize_team_name(s.team_name))
