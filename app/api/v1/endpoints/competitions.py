"""
Endpoints de competiciones — GET /competitions, GET /competitions/{id}/teams, etc.

Este módulo REEMPLAZA el comportamiento erróneo de devolver los mismos equipos
para todas las competiciones. Ahora cada competición devuelve sus equipos correctos.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.competition_registry import (
    get_competition_teams,
    get_competition_groups,
    list_competitions,
    get_team_type,
    RegistryTeam,
    TeamType,
)
from app.models.competition import COMPETITIONS, list_competitions as list_comp_configs

router = APIRouter(prefix="/competitions", tags=["competitions"])


def _db():
    with SessionLocal() as db:
        yield db


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CompetitionOut(BaseModel):
    id: str
    name: str
    competition_type: str
    tier: str
    country: str
    n_teams: int
    relegation_spots: int
    ucl_spots: int
    uel_spots: int
    legs: int


class TeamOut(BaseModel):
    name: str
    short_name: str
    country: str
    team_type: str
    group: str | None
    elo_seed: float
    fifa_rank: int | None
    uefa_rank: int | None


class GroupOut(BaseModel):
    group: str
    teams: list[str]


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[CompetitionOut])
def list_all_competitions():
    """Lista todas las competiciones disponibles con su configuración."""
    return [
        CompetitionOut(
            id=cfg.id,
            name=cfg.name,
            competition_type=cfg.competition_type.value,
            tier=cfg.tier.value,
            country=cfg.country,
            n_teams=cfg.n_teams,
            relegation_spots=cfg.relegation_spots,
            ucl_spots=cfg.ucl_spots,
            uel_spots=cfg.uel_spots,
            legs=cfg.legs,
        )
        for cfg in list_comp_configs()
    ]


@router.get("/{competition_id}/teams", response_model=list[TeamOut])
def get_teams_for_competition(
    competition_id: str,
    season: int | None = Query(None, description="Año de inicio de temporada (ej: 2024)"),
    db: Session = Depends(_db),
):
    """
    Devuelve los equipos de una competición específica.

    - competition="ucl"          → clubes europeos (Real Madrid, Bayern, etc.)
    - competition="premier_league" → clubes ingleses (Liverpool, Arsenal, etc.)
    - competition="fifa_wc_2026"  → selecciones nacionales (Argentina, Brasil, etc.)

    NUNCA mezcla selecciones con clubes.
    """
    try:
        teams = get_competition_teams(competition_id, season, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return [
        TeamOut(
            name=t.name,
            short_name=t.short_name,
            country=t.country,
            team_type=t.team_type.value,
            group=t.group,
            elo_seed=t.elo_seed,
            fifa_rank=t.fifa_rank,
            uefa_rank=t.uefa_rank,
        )
        for t in teams
    ]


@router.get("/{competition_id}/groups", response_model=list[GroupOut])
def get_competition_group_draw(
    competition_id: str,
    season: int | None = Query(None),
    db: Session = Depends(_db),
):
    """
    Devuelve los grupos de una competición.
    Solo disponible para competiciones con fase de grupos (Mundial, UCL pre-2024).
    """
    try:
        groups = get_competition_groups(competition_id, season, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not groups:
        raise HTTPException(
            status_code=400,
            detail=f"La competición '{competition_id}' no tiene fase de grupos.",
        )

    return [GroupOut(group=g, teams=t) for g, t in sorted(groups.items())]


@router.get("/{competition_id}/type")
def get_competition_team_type(competition_id: str):
    """Indica si la competición usa clubes o selecciones nacionales."""
    try:
        team_type = get_team_type(competition_id)
        return {
            "competition": competition_id,
            "team_type": team_type.value,
            "description": (
                "Selecciones nacionales" if team_type == TeamType.NATIONAL
                else "Clubes de fútbol"
            ),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
