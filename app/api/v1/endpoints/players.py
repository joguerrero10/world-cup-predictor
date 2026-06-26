"""
Endpoints de jugadores — GET /players, GET /players/{id}
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Player, Team

router = APIRouter(prefix="/players", tags=["players"])


def _db():
    with SessionLocal() as db:
        yield db


class PlayerOut(BaseModel):
    id: int
    name: str
    team: str
    position: str | None
    nationality: str | None
    birth_date: str | None
    age: int | None
    overall_rating: float | None
    market_value_eur: float | None
    goals_per_90: float | None
    xg_per_90: float | None
    assists_per_90: float | None
    minutes_played: int | None
    yellow_cards_per_90: float | None
    red_cards_per_90: float | None
    is_injured: bool
    is_suspended: bool


def _age(birth_date: Optional[date]) -> Optional[int]:
    if birth_date is None:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


@router.get("/", response_model=list[PlayerOut])
def list_players(
    team: Optional[str] = Query(None, description="Filtrar por nombre de equipo"),
    position: Optional[str] = Query(None, description="GK|DEF|MID|FWD"),
    nationality: Optional[str] = Query(None),
    injured: Optional[bool] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=100),
    sort_by: str = Query("overall_rating", description="overall_rating|goals_per_90|market_value_eur"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(_db),
):
    """Lista jugadores con filtros. Datos reales del ETL (Transfermarkt, FBref)."""
    stmt = select(Player, Team.name.label("team_name")).join(Team, Team.id == Player.team_id)

    if team:
        stmt = stmt.where(func.lower(Team.name).contains(team.lower()))
    if position:
        stmt = stmt.where(Player.position == position.upper())
    if nationality:
        stmt = stmt.where(func.lower(Player.nationality).contains(nationality.lower()))
    if injured is not None:
        stmt = stmt.where(Player.is_injured == injured)
    if min_rating is not None:
        stmt = stmt.where(Player.overall_rating >= min_rating)

    sort_col = {
        "overall_rating": Player.overall_rating,
        "goals_per_90": Player.goals_per_90,
        "market_value_eur": Player.market_value_eur,
        "name": Player.name,
    }.get(sort_by, Player.overall_rating)

    stmt = stmt.order_by(sort_col.desc().nullslast()).offset(offset).limit(limit)
    rows = db.execute(stmt).all()

    return [
        PlayerOut(
            id=p.id,
            name=p.name,
            team=team_name,
            position=p.position,
            nationality=p.nationality,
            birth_date=str(p.birth_date) if p.birth_date else None,
            age=_age(p.birth_date),
            overall_rating=p.overall_rating,
            market_value_eur=p.market_value_eur,
            goals_per_90=p.goals_per_90,
            xg_per_90=p.xg_per_90,
            assists_per_90=p.assists_per_90,
            minutes_played=p.minutes_played,
            yellow_cards_per_90=p.yellow_cards_per_90,
            red_cards_per_90=p.red_cards_per_90,
            is_injured=p.is_injured,
            is_suspended=p.is_suspended,
        )
        for p, team_name in rows
    ]


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: Session = Depends(_db)):
    row = db.execute(
        select(Player, Team.name.label("team_name"))
        .join(Team, Team.id == Player.team_id)
        .where(Player.id == player_id)
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Jugador {player_id} no encontrado.")

    p, team_name = row
    return PlayerOut(
        id=p.id,
        name=p.name,
        team=team_name,
        position=p.position,
        nationality=p.nationality,
        birth_date=str(p.birth_date) if p.birth_date else None,
        age=_age(p.birth_date),
        overall_rating=p.overall_rating,
        market_value_eur=p.market_value_eur,
        goals_per_90=p.goals_per_90,
        xg_per_90=p.xg_per_90,
        assists_per_90=p.assists_per_90,
        minutes_played=p.minutes_played,
        yellow_cards_per_90=p.yellow_cards_per_90,
        red_cards_per_90=p.red_cards_per_90,
        is_injured=p.is_injured,
        is_suspended=p.is_suspended,
    )
