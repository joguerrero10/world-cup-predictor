"""
Capa de validación del pipeline ETL.

Valida DTOs antes de persistirlos. Nunca modifica datos, solo filtra
y registra inconsistencias para el audit log.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from etl.providers.base import MatchData, PlayerData, StandingData, TeamData

logger = logging.getLogger(__name__)

_MIN_DATE = date(1800, 1, 1)
_MAX_DATE = date(2030, 12, 31)
_MAX_GOALS = 30
_VALID_MATCH_TYPES = {
    "friendly", "qualifier", "world_cup_group", "world_cup_knockout", "continental",
}
_VALID_POSITIONS = {"GK", "DEF", "MID", "FWD"}
_VALID_STATUSES = {"FINISHED", "SCHEDULED", "IN_PLAY", "POSTPONED", "CANCELLED"}


class ValidationError:
    __slots__ = ("field", "value", "reason")

    def __init__(self, field: str, value, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.field}={self.value!r}: {self.reason}"


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    @property
    def valid(self) -> bool:
        return not self.errors

    def add(self, field: str, value, reason: str) -> None:
        self.errors.append(ValidationError(field, value, reason))

    def __repr__(self) -> str:
        if self.valid:
            return "ValidationResult(valid=True)"
        return f"ValidationResult(errors={[str(e) for e in self.errors]})"


# ---------------------------------------------------------------------------
# Validadores individuales
# ---------------------------------------------------------------------------

def validate_match(m: MatchData) -> ValidationResult:
    r = ValidationResult()

    if not m.home_team or not m.home_team.strip():
        r.add("home_team", m.home_team, "vacío o nulo")
    if not m.away_team or not m.away_team.strip():
        r.add("away_team", m.away_team, "vacío o nulo")
    if m.home_team and m.away_team and m.home_team.strip() == m.away_team.strip():
        r.add("teams", m.home_team, "home_team == away_team")

    if not isinstance(m.date, date):
        r.add("date", m.date, "no es un objeto date")
    elif not (_MIN_DATE <= m.date <= _MAX_DATE):
        r.add("date", m.date, f"fuera del rango [{_MIN_DATE}, {_MAX_DATE}]")

    if m.status == "FINISHED":
        if m.home_goals is None:
            r.add("home_goals", None, "FINISHED pero home_goals es nulo")
        elif m.home_goals < 0 or m.home_goals > _MAX_GOALS:
            r.add("home_goals", m.home_goals, f"fuera del rango [0, {_MAX_GOALS}]")
        if m.away_goals is None:
            r.add("away_goals", None, "FINISHED pero away_goals es nulo")
        elif m.away_goals < 0 or m.away_goals > _MAX_GOALS:
            r.add("away_goals", m.away_goals, f"fuera del rango [0, {_MAX_GOALS}]")

    if m.match_type not in _VALID_MATCH_TYPES:
        r.add("match_type", m.match_type, f"no válido; valores: {_VALID_MATCH_TYPES}")

    if m.status not in _VALID_STATUSES:
        r.add("status", m.status, f"no válido; valores: {_VALID_STATUSES}")

    if m.attendance is not None and m.attendance < 0:
        r.add("attendance", m.attendance, "negativo")

    if m.home_xg is not None and (m.home_xg < 0 or m.home_xg > 15):
        r.add("home_xg", m.home_xg, "fuera del rango [0, 15]")
    if m.away_xg is not None and (m.away_xg < 0 or m.away_xg > 15):
        r.add("away_xg", m.away_xg, "fuera del rango [0, 15]")

    return r


def validate_team(t: TeamData) -> ValidationResult:
    r = ValidationResult()
    if not t.name or not t.name.strip():
        r.add("name", t.name, "vacío o nulo")
    if t.gdp_per_capita is not None and t.gdp_per_capita < 0:
        r.add("gdp_per_capita", t.gdp_per_capita, "negativo")
    if t.population is not None and t.population < 0:
        r.add("population", t.population, "negativo")
    if t.football_culture is not None and not (0 <= t.football_culture <= 1):
        r.add("football_culture", t.football_culture, "fuera de [0, 1]")
    return r


def validate_player(p: PlayerData) -> ValidationResult:
    r = ValidationResult()
    if not p.name or not p.name.strip():
        r.add("name", p.name, "vacío o nulo")
    if not p.team_name or not p.team_name.strip():
        r.add("team_name", p.team_name, "vacío o nulo")
    if p.position and p.position not in _VALID_POSITIONS:
        r.add("position", p.position, f"no válido; valores: {_VALID_POSITIONS}")
    if p.birth_date is not None and not (_MIN_DATE <= p.birth_date <= _MAX_DATE):
        r.add("birth_date", p.birth_date, "fuera de rango")
    return r


def validate_standing(s: StandingData) -> ValidationResult:
    r = ValidationResult()
    if not s.team_name:
        r.add("team_name", s.team_name, "vacío")
    if s.points < 0:
        r.add("points", s.points, "negativo")
    if s.played < 0:
        r.add("played", s.played, "negativo")
    if s.position < 1:
        r.add("position", s.position, "debe ser ≥ 1")
    return r


# ---------------------------------------------------------------------------
# Filtros por lotes
# ---------------------------------------------------------------------------

def filter_matches(
    matches: list[MatchData],
    log_prefix: str = "",
) -> tuple[list[MatchData], list[str]]:
    """
    Devuelve (válidos, mensajes_de_error).
    Elimina duplicados (home, away, date) dentro del lote.
    """
    valid: list[MatchData] = []
    errors: list[str] = []
    seen: set[tuple] = set()

    for m in matches:
        res = validate_match(m)
        if not res.valid:
            msg = f"{log_prefix}match {m.home_team} vs {m.away_team} {m.date}: {res}"
            errors.append(msg)
            logger.debug(msg)
            continue

        key = (m.home_team, m.away_team, m.date)
        if key in seen:
            continue
        seen.add(key)
        valid.append(m)

    return valid, errors


def filter_teams(
    teams: list[TeamData],
    log_prefix: str = "",
) -> tuple[list[TeamData], list[str]]:
    valid: list[TeamData] = []
    errors: list[str] = []
    seen: set[str] = set()

    for t in teams:
        res = validate_team(t)
        if not res.valid:
            msg = f"{log_prefix}team '{t.name}': {res}"
            errors.append(msg)
            continue
        if t.name in seen:
            continue
        seen.add(t.name)
        valid.append(t)

    return valid, errors


def filter_players(
    players: list[PlayerData],
    log_prefix: str = "",
) -> tuple[list[PlayerData], list[str]]:
    valid: list[PlayerData] = []
    errors: list[str] = []
    seen: set[tuple] = set()

    for p in players:
        res = validate_player(p)
        if not res.valid:
            msg = f"{log_prefix}player '{p.name}' ({p.team_name}): {res}"
            errors.append(msg)
            continue
        key = (p.name, p.team_name)
        if key in seen:
            continue
        seen.add(key)
        valid.append(p)

    return valid, errors


def filter_standings(
    standings: list[StandingData],
    log_prefix: str = "",
) -> tuple[list[StandingData], list[str]]:
    valid: list[StandingData] = []
    errors: list[str] = []
    for s in standings:
        res = validate_standing(s)
        if not res.valid:
            errors.append(f"{log_prefix}standing '{s.team_name}': {res}")
            continue
        valid.append(s)
    return valid, errors
