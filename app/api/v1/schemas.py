"""Pydantic schemas para la API v1."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Predicción de partido
# ---------------------------------------------------------------------------

class MatchPredictionRequest(BaseModel):
    home: str
    away: str
    neutral: bool = True
    model: str = "hybrid"
    competition_id: str | None = None


class MatchPredictionResponse(BaseModel):
    home: str
    away: str
    home_win: float
    draw: float
    away_win: float
    source: str
    # Extras si Dixon-Coles disponible
    most_likely_score: tuple[int, int] | None = None
    over_2_5: float | None = None
    under_2_5: float | None = None
    btts_yes: float | None = None
    btts_no: float | None = None


# ---------------------------------------------------------------------------
# Trabajos de simulación
# ---------------------------------------------------------------------------

class SimulationJobRequest(BaseModel):
    competition_id: str = Field(..., description="slug de competición: premier_league, fifa_wc_2026, etc.")
    n_sims: int = Field(10_000, ge=1_000, le=1_000_000)
    model: str = Field("hybrid", description="elo|dixon_coles|hybrid")
    teams: list[str] | None = Field(
        None,
        description="Lista de equipos. Si no se provee, usa todos los del sistema."
    )
    groups: dict[str, list[str]] | None = Field(
        None,
        description="Distribución de grupos (solo para competiciones con grupos)."
    )

    @field_validator("competition_id")
    @classmethod
    def validate_competition(cls, v: str) -> str:
        from app.models.competition import COMPETITIONS
        if v not in COMPETITIONS:
            raise ValueError(
                f"Competición '{v}' no existe. "
                f"Disponibles: {sorted(COMPETITIONS.keys())}"
            )
        return v


class SimulationJobStatus(BaseModel):
    id: int
    status: str
    competition_id: str
    n_sims: int
    model_name: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None


class SimulationJobResult(BaseModel):
    id: int
    status: str
    competition_id: str
    n_sims: int
    result: dict[str, Any] | None = None
    duration_seconds: float | None = None


# ---------------------------------------------------------------------------
# Tabla de liga
# ---------------------------------------------------------------------------

class LeagueTableEntry(BaseModel):
    position: int
    team: str
    played: float
    pts: float
    gf: float
    ga: float
    gd: float
    champion_prob: float
    top4_prob: float
    relegated_prob: float


class LeagueTableResponse(BaseModel):
    competition_id: str
    n_sims: int
    table: list[LeagueTableEntry]
    position_distribution: dict[str, list[float]]


# ---------------------------------------------------------------------------
# Predicción de temporada
# ---------------------------------------------------------------------------

class SeasonPredictionResponse(BaseModel):
    competition_id: str
    n_sims: int
    champion: dict[str, float]
    relegated: dict[str, float]
    ucl_qualification: dict[str, float]
    uel_qualification: dict[str, float]


# ---------------------------------------------------------------------------
# Probabilidades de equipos (torneo)
# ---------------------------------------------------------------------------

class TournamentProbsResponse(BaseModel):
    competition_id: str
    n_sims: int
    champion: dict[str, float]
    finalist: dict[str, float]
    semifinalist: dict[str, float]
    group_qualified: dict[str, float]


# ---------------------------------------------------------------------------
# Probabilidades de jugador
# ---------------------------------------------------------------------------

class PlayerPredictionResponse(BaseModel):
    player_name: str
    team: str
    goals_expected: float | None = None
    assists_expected: float | None = None
    yellow_cards_expected: float | None = None
    red_card_prob: float | None = None
    injury_risk: float | None = None
    data_status: str = "available"  # available|pending|unavailable


# ---------------------------------------------------------------------------
# Disciplina
# ---------------------------------------------------------------------------

class DisciplineResponse(BaseModel):
    home: str
    away: str
    home_yellow_expected: float
    away_yellow_expected: float
    home_red_prob: float
    away_red_prob: float
    both_teams_card: float
    source: str = "statistical_model"
    data_status: str


# ---------------------------------------------------------------------------
# Competiciones
# ---------------------------------------------------------------------------

class CompetitionInfo(BaseModel):
    id: str
    name: str
    competition_type: str
    tier: str
    country: str | None
    n_teams: int
    relegation_spots: int
    ucl_spots: int
