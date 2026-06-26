"""
Endpoints de sistema: health, update-data, elo-rankings.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    teams_loaded: int
    dc_ready: bool
    form_model_ready: bool
    klement_factors_loaded: int
    competitions_available: list[str]
    models_ready: dict[str, bool]
    last_data_sync: str | None


@router.get("/health", response_model=HealthResponse)
def health():
    """Health check completo del sistema."""
    from app.main import STATE
    from app.core.competition_registry import list_competitions

    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat() + "Z",
        teams_loaded=len(STATE.elo),
        dc_ready=STATE.dc is not None and STATE.dc.params is not None,
        form_model_ready=STATE.form_model is not None and STATE.form_model.fitted,
        klement_factors_loaded=len(STATE.factors),
        competitions_available=list_competitions(),
        models_ready={
            "elo": len(STATE.elo) > 0,
            "dixon_coles": STATE.dc is not None and STATE.dc.params is not None,
            "xgboost": STATE.form_model is not None,
            "klement": len(STATE.factors) > 0,
        },
        last_data_sync=None,
    )


class UpdateDataRequest(BaseModel):
    competition: Optional[str] = None     # None = todas
    data_types: list[str] = ["matches", "standings"]  # matches|standings|players|transfers
    season: Optional[int] = None


@router.post("/update-data")
async def update_data(
    req: UpdateDataRequest,
    background_tasks: BackgroundTasks,
):
    """
    Dispara actualización de datos desde proveedores externos.
    Retorna inmediatamente; la actualización corre en background.
    """
    competitions = [req.competition] if req.competition else [
        "premier_league", "laliga", "bundesliga", "serie_a", "ligue_1", "ucl"
    ]

    background_tasks.add_task(
        _run_update_background,
        competitions=competitions,
        data_types=req.data_types,
        season=req.season,
    )

    return {
        "status": "accepted",
        "message": f"Actualizando {len(competitions)} competiciones en background",
        "competitions": competitions,
        "data_types": req.data_types,
    }


def _run_update_background(
    competitions: list[str],
    data_types: list[str],
    season: Optional[int],
) -> None:
    """Tarea de background para actualizar datos."""
    from etl.pipeline.orchestrator import run_pipeline
    import logging
    logger = logging.getLogger(__name__)

    for comp in competitions:
        try:
            result = run_pipeline(
                competition_slug=comp,
                data_types=data_types,
                season=season,
            )
            logger.info("[update-data] %s: %s", comp, result)
        except Exception as e:
            logger.error("[update-data] Error en %s: %s", comp, e)

    # Recalcular modelos tras actualizar
    try:
        from app.db.database import SessionLocal
        from app.services.bootstrap import build_engine_from_db
        from app.main import STATE

        with SessionLocal() as db:
            elo, dc, n = build_engine_from_db(db)

        if n > 0:
            STATE.elo = elo
            STATE.dc = dc
            logger.info("[update-data] Modelos recalculados: %d equipos", len(elo))
    except Exception as e:
        logger.error("[update-data] Error recalculando modelos: %s", e)


@router.get("/elo-rankings")
def elo_rankings(
    competition: Optional[str] = Query(None, description="Filtrar por competición"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Rankings Elo de equipos.
    Si competition se especifica, muestra solo equipos de esa competición
    con sus ratings Elo (usando seed del registry si no hay datos históricos).
    """
    from app.main import STATE
    from app.models.elo import TeamElo
    from app.core.competition_registry import get_competition_teams, TeamType

    if competition:
        try:
            registry_teams = get_competition_teams(competition)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        rows = []
        for i, t in enumerate(sorted(registry_teams, key=lambda rt: -(STATE.elo.get(rt.name, TeamElo(rating=rt.elo_seed)).rating))):
            elo = STATE.elo.get(t.name, TeamElo(rating=t.elo_seed))
            rows.append({
                "rank": i + 1,
                "team": t.name,
                "country": t.country,
                "team_type": t.team_type.value,
                "rating": round(elo.rating, 1),
                "attack": round(elo.attack, 1),
                "defense": round(elo.defense, 1),
                "source": "db" if t.name in STATE.elo else "seed",
            })
        return rows[:limit]

    # Sin filtro: todos los equipos con Elo en STATE
    rows = sorted(STATE.elo.items(), key=lambda kv: kv[1].rating, reverse=True)
    return [
        {
            "rank": i + 1,
            "team": t,
            "rating": round(e.rating, 1),
            "attack": round(e.attack, 1),
            "defense": round(e.defense, 1),
        }
        for i, (t, e) in enumerate(rows[:limit])
    ]
