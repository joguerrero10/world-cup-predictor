"""
Endpoints de clasificaciones — GET /standings/{competition}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Standing, Team

router = APIRouter(prefix="/standings", tags=["standings"])


def _db():
    with SessionLocal() as db:
        yield db


class StandingRow(BaseModel):
    position: int
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int
    form: str | None = None


@router.get("/{competition_id}", response_model=list[StandingRow])
def get_standings(
    competition_id: str,
    season: int | None = Query(None, description="Temporada (año inicio)"),
    db: Session = Depends(_db),
):
    """
    Devuelve la clasificación real de una liga.
    Los datos vienen del ETL (football-data.org, API-Football).
    """
    # Aliases
    _aliases = {
        "premier": "premier_league",
        "epl": "premier_league",
        "la_liga": "laliga",
        "ligue1": "ligue_1",
        "seriea": "serie_a",
        "bl1": "bundesliga",
    }
    slug = _aliases.get(competition_id.lower(), competition_id.lower())

    stmt = select(Standing).where(Standing.competition_slug == slug)
    if season is not None:
        stmt = stmt.where(Standing.season_year == season)
    stmt = stmt.order_by(Standing.position)

    rows = list(db.scalars(stmt))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sin clasificación para '{competition_id}' "
                f"{'temporada ' + str(season) if season else ''}. "
                "Ejecuta el ETL primero: POST /update-data"
            ),
        )

    # Mapear team_id → nombre
    team_ids = [r.team_id for r in rows]
    teams = {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(team_ids)))}

    return [
        StandingRow(
            position=r.position,
            team=teams.get(r.team_id, f"team_{r.team_id}"),
            played=r.played,
            won=r.won,
            drawn=r.drawn,
            lost=r.lost,
            goals_for=r.goals_for,
            goals_against=r.goals_against,
            goal_diff=r.goals_for - r.goals_against,
            points=r.points,
        )
        for r in rows
    ]
