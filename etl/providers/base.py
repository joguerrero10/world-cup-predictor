"""
Capa de abstracción de proveedores ETL.

Cada proveedor concreto implementa BaseProvider.
Los datos fluyen como dataclasses inmutables entre capas.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------

@dataclass
class MatchData:
    date: date
    competition_slug: str
    home_team: str
    away_team: str
    home_goals: Optional[int]
    away_goals: Optional[int]
    match_type: str = "friendly"
    neutral: bool = False
    matchday: Optional[int] = None
    round_name: Optional[str] = None
    venue: Optional[str] = None
    attendance: Optional[int] = None
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
    status: str = "FINISHED"
    external_id: Optional[str] = None


@dataclass
class TeamData:
    name: str
    country: Optional[str] = None
    confederation: Optional[str] = None
    short_name: Optional[str] = None
    gdp_per_capita: Optional[float] = None
    population: Optional[int] = None
    football_culture: Optional[float] = None
    avg_temp_c: Optional[float] = None
    is_host: bool = False
    data_source: Optional[str] = None


@dataclass
class PlayerData:
    name: str
    team_name: str
    position: Optional[str] = None          # GK|DEF|MID|FWD
    nationality: Optional[str] = None
    birth_date: Optional[date] = None
    shirt_number: Optional[int] = None
    market_value_eur: Optional[float] = None
    data_source: Optional[str] = None
    # Estadísticas por 90 min (opcionales, rellenadas por proveedores avanzados)
    goals_per_90: Optional[float] = None
    assists_per_90: Optional[float] = None
    xg_per_90: Optional[float] = None
    minutes_played: Optional[int] = None
    yellow_cards_per_90: Optional[float] = None
    red_cards_per_90: Optional[float] = None
    overall_rating: Optional[float] = None


@dataclass
class StandingData:
    competition_slug: str
    season_year: int
    team_name: str
    position: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int


@dataclass
class ProviderResult:
    """Resumen de lo que devolvió un proveedor en una llamada."""
    provider_name: str
    competition_slug: Optional[str]
    data_type: str
    records_fetched: int
    records_valid: int
    errors: list[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0
    raw_sample: Optional[Any] = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Se lanza cuando un proveedor falla de forma irrecuperable."""


class ProviderUnavailableError(ProviderError):
    """Se lanza cuando el proveedor no está configurado o no está disponible."""


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """
    Interfaz que todo proveedor de datos debe implementar.

    Reglas:
    - Nunca lanzar excepciones en fetch_*; capturar y devolver lista vacía.
    - Registrar errores en self._errors para que el pipeline los audite.
    - is_available() debe retornar False si faltan credenciales o config.
    """
    name: str = "base"

    def __init__(self) -> None:
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def _error(self, msg: str) -> None:
        logger.error("[%s] %s", self.name, msg)
        self._errors.append(msg)

    def _warn(self, msg: str) -> None:
        logger.warning("[%s] %s", self.name, msg)

    def clear_errors(self) -> None:
        self._errors.clear()

    @abstractmethod
    def is_available(self) -> bool:
        """True si el proveedor puede atender solicitudes ahora."""
        ...

    @abstractmethod
    def fetch_matches(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[MatchData]:
        """Devuelve partidos finalizados de la competición y temporada dadas."""
        ...

    @abstractmethod
    def fetch_teams(self, competition_slug: str) -> list[TeamData]:
        """Devuelve equipos participantes en la competición."""
        ...

    def fetch_players(self, competition_slug: str) -> list[PlayerData]:
        """Devuelve jugadores de los equipos de la competición. Opcional."""
        return []

    def fetch_standings(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[StandingData]:
        """Devuelve la clasificación actual. Opcional."""
        return []
