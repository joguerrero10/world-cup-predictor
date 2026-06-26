"""
Abstracción de competición: base para ligas, copas y torneos internacionales.

Soporta:
- Ligas nacionales con ida y vuelta (Premier League, La Liga, Serie A, Bundesliga, Ligue 1)
- Torneo con fase de grupos + eliminatoria (Copa del Mundo, Champions League)
- Solo eliminatoria (Copa del Rey, FA Cup)

Las reglas de clasificación y estructura de bracket son configurables per-competición.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class CompetitionType(str, Enum):
    LEAGUE = "league"                 # round-robin doble, tabla, ascenso/descenso
    KNOCKOUT = "knockout"             # eliminatoria pura
    GROUP_KNOCKOUT = "group_knockout" # grupos + eliminatoria (Mundial, UCL)


class CompetitionTier(str, Enum):
    INTERNATIONAL = "international"
    DOMESTIC_TOP  = "domestic_top"    # Primera división
    DOMESTIC_2    = "domestic_2"      # Segunda división
    CONTINENTAL   = "continental"     # UCL, UEL, Conference


@dataclass(frozen=True)
class CompetitionConfig:
    """Descripción estática de una competición (no cambia entre temporadas)."""

    id: str                           # slug único, e.g. "premier_league", "fifa_wc_2026"
    name: str                         # nombre legible
    competition_type: CompetitionType
    tier: CompetitionTier
    country: str                      # "International", "England", "Spain", ...
    n_teams: int
    advance_per_group: int = 2        # cuántos clasifican por grupo (si aplica)
    n_groups: int = 0                 # 0 si no hay grupos
    legs: int = 2                     # 1 = solo ida, 2 = ida y vuelta (UCL KO, ligas copa)
    relegation_spots: int = 0         # plazas de descenso
    ucl_spots: int = 0                # plazas Champions League
    uel_spots: int = 0                # plazas Europa League
    uecl_spots: int = 0               # plazas Conference League
    extra_time: bool = True           # prórroga en eliminatoria
    penalties: bool = True            # penales si hay empate en KO
    neutral_venue_groups: bool = True # grupos en sede neutral (Mundial)
    neutral_venue_knockout: bool = True

    @property
    def teams_per_group(self) -> int:
        if self.n_groups == 0:
            return 0
        return self.n_teams // self.n_groups


# ---------------------------------------------------------------------------
# Catálogo de competiciones predefinidas
# ---------------------------------------------------------------------------

COMPETITIONS: dict[str, CompetitionConfig] = {

    "fifa_wc_2026": CompetitionConfig(
        id="fifa_wc_2026",
        name="FIFA World Cup 2026",
        competition_type=CompetitionType.GROUP_KNOCKOUT,
        tier=CompetitionTier.INTERNATIONAL,
        country="International",
        n_teams=48,
        advance_per_group=2,
        n_groups=12,
        legs=1,
        relegation_spots=0,
        ucl_spots=0,
        neutral_venue_groups=True,
        neutral_venue_knockout=True,
    ),

    "premier_league": CompetitionConfig(
        id="premier_league",
        name="Premier League",
        competition_type=CompetitionType.LEAGUE,
        tier=CompetitionTier.DOMESTIC_TOP,
        country="England",
        n_teams=20,
        legs=2,
        relegation_spots=3,
        ucl_spots=4,
        uel_spots=1,
        uecl_spots=1,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
    ),

    "laliga": CompetitionConfig(
        id="laliga",
        name="LaLiga",
        competition_type=CompetitionType.LEAGUE,
        tier=CompetitionTier.DOMESTIC_TOP,
        country="Spain",
        n_teams=20,
        legs=2,
        relegation_spots=3,
        ucl_spots=4,
        uel_spots=1,
        uecl_spots=1,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
    ),

    "serie_a": CompetitionConfig(
        id="serie_a",
        name="Serie A",
        competition_type=CompetitionType.LEAGUE,
        tier=CompetitionTier.DOMESTIC_TOP,
        country="Italy",
        n_teams=20,
        legs=2,
        relegation_spots=3,
        ucl_spots=4,
        uel_spots=1,
        uecl_spots=1,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
    ),

    "bundesliga": CompetitionConfig(
        id="bundesliga",
        name="Bundesliga",
        competition_type=CompetitionType.LEAGUE,
        tier=CompetitionTier.DOMESTIC_TOP,
        country="Germany",
        n_teams=18,
        legs=2,
        relegation_spots=2,       # 16° juega playoff
        ucl_spots=4,
        uel_spots=1,
        uecl_spots=1,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
    ),

    "ligue_1": CompetitionConfig(
        id="ligue_1",
        name="Ligue 1",
        competition_type=CompetitionType.LEAGUE,
        tier=CompetitionTier.DOMESTIC_TOP,
        country="France",
        n_teams=18,
        legs=2,
        relegation_spots=3,
        ucl_spots=3,
        uel_spots=1,
        uecl_spots=1,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
    ),

    "ucl": CompetitionConfig(
        id="ucl",
        name="UEFA Champions League",
        competition_type=CompetitionType.GROUP_KNOCKOUT,
        tier=CompetitionTier.CONTINENTAL,
        country="Europe",
        n_teams=36,               # formato liga 2024/25
        advance_per_group=0,       # formato nuevo: top-8 directos, 9-24 a playoff
        n_groups=1,                # una sola liga (formato nuevo)
        legs=2,
        relegation_spots=0,
        neutral_venue_groups=False,
        neutral_venue_knockout=False,
        extra_time=True,
        penalties=True,
    ),
}


def get_competition(competition_id: str) -> CompetitionConfig:
    """Devuelve la config de una competición por ID. Lanza ValueError si no existe."""
    if competition_id not in COMPETITIONS:
        available = sorted(COMPETITIONS.keys())
        raise ValueError(
            f"Competición '{competition_id}' no encontrada. "
            f"Disponibles: {available}"
        )
    return COMPETITIONS[competition_id]


def list_competitions() -> list[CompetitionConfig]:
    return list(COMPETITIONS.values())


# ---------------------------------------------------------------------------
# Protocolo de modelo de partido (para type-checking sin acoplamiento)
# ---------------------------------------------------------------------------

@runtime_checkable
class MatchPredictor(Protocol):
    """Cualquier objeto que pueda predecir un partido 1X2."""

    def predict(
        self,
        home_team: str,
        away_team: str,
        neutral: bool = False,
        competition_id: str | None = None,
    ) -> tuple[float, float, float]:
        """Retorna (p_home_win, p_draw, p_away_win). Suma a 1.0."""
        ...
