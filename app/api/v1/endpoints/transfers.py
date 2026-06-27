"""
Endpoints de fichajes — GET /transfers

Fichajes REALES obtenidos del ETL (Transfermarkt, API-Football).
Los datos ficticios han sido eliminados completamente.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Transfer, Player, Team

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _db():
    with SessionLocal() as db:
        yield db


class TransferOut(BaseModel):
    id: int
    player: str
    from_team: str | None
    to_team: str
    date: str
    transfer_type: str
    fee_eur: float | None
    fee_display: str


def _fee_display(fee: Optional[float]) -> str:
    if fee is None:
        return "Free / Unknown"
    if fee == 0:
        return "Free Transfer"
    if fee >= 1e8:
        return f"€{fee/1e6:.0f}M"
    if fee >= 1e6:
        return f"€{fee/1e6:.1f}M"
    return f"€{fee/1e3:.0f}K"


@router.get("/", response_model=list[TransferOut])
def get_transfers(
    team: Optional[str] = Query(None, description="Filtrar por equipo (origen o destino)"),
    player: Optional[str] = Query(None),
    transfer_type: Optional[str] = Query(None, description="permanent|loan|free|end_loan"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    min_fee_eur: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(_db),
):
    """
    Devuelve fichajes reales del ETL.
    Sin datos inventados: solo lo que el ETL haya cargado desde Transfermarkt / API-Football.
    """
    stmt = (
        select(Transfer, Player.name.label("player_name"),
               Team.name.label("to_team_name"))
        .join(Player, Player.id == Transfer.player_id)
        .join(Team, Team.id == Transfer.to_team_id)
        .order_by(desc(Transfer.transfer_date))
    )

    if player:
        from sqlalchemy import func
        stmt = stmt.where(func.lower(Player.name).contains(player.lower()))
    if transfer_type:
        stmt = stmt.where(Transfer.transfer_type == transfer_type)
    if from_date:
        stmt = stmt.where(Transfer.transfer_date >= from_date)
    if to_date:
        stmt = stmt.where(Transfer.transfer_date <= to_date)
    if min_fee_eur:
        stmt = stmt.where(Transfer.fee_eur >= min_fee_eur)

    stmt = stmt.limit(limit)
    rows = db.execute(stmt).all()

    if not rows:
        return []

    # Mapear from_team (puede ser None si era free agent)
    from_team_ids = [r.Transfer.from_team_id for r in rows if r.Transfer.from_team_id]
    from_teams = {}
    if from_team_ids:
        from_teams = {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(from_team_ids)))}

    return [
        TransferOut(
            id=r.Transfer.id,
            player=r.player_name,
            from_team=from_teams.get(r.Transfer.from_team_id),
            to_team=r.to_team_name,
            date=str(r.Transfer.transfer_date),
            transfer_type=r.Transfer.transfer_type,
            fee_eur=r.Transfer.fee_eur,
            fee_display=_fee_display(r.Transfer.fee_eur),
        )
        for r in rows
    ]
