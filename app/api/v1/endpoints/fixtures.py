"""
Endpoints de calendario (fixtures) — GET /fixtures/{competition}

Muestra próximos partidos con predicciones automáticas para cada encuentro.
Los fixtures reales vienen del ETL; los ficticios están ELIMINADOS.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Match, Team, Season, Competition

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


def _db():
    with SessionLocal() as db:
        yield db


class FixtureOut(BaseModel):
    match_id: int
    competition: str
    season: str
    date: str
    matchday: int | None
    round: str | None
    home_team: str
    away_team: str
    venue: str | None
    status: str
    # Predicción (None si no hay modelo cargado)
    p_home: float | None = None
    p_draw: float | None = None
    p_away: float | None = None
    expected_goals_home: float | None = None
    expected_goals_away: float | None = None
    # Resultado (si ya se jugó)
    home_goals: int | None = None
    away_goals: int | None = None


@router.get("/{competition_id}", response_model=list[FixtureOut])
def get_fixtures(
    competition_id: str,
    season: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    matchday: Optional[int] = Query(None),
    upcoming_only: bool = Query(False, description="Solo partidos pendientes"),
    limit: int = Query(20, ge=1, le=100),
    with_predictions: bool = Query(False, description="Añadir predicciones 1X2"),
    db: Session = Depends(_db),
):
    """
    Devuelve el calendario real de una competición.

    Los datos son de football-data.org / API-Football (vía ETL).
    Los fixtures ficticios han sido eliminados.
    """
    _aliases = {
        "premier": "premier_league",
        "epl": "premier_league",
        "la_liga": "laliga",
        "ligue1": "ligue_1",
        "seriea": "serie_a",
        "bl1": "bundesliga",
        "worldcup": "fifa_wc_2026",
        "champions": "ucl",
    }
    slug = _aliases.get(competition_id.lower(), competition_id.lower())

    # Buscar la competición y temporada en BD
    comp = db.scalar(select(Competition).where(Competition.slug == slug))
    if comp is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Competición '{competition_id}' no encontrada en BD. "
                "Asegúrate de ejecutar el ETL: POST /update-data"
            ),
        )

    # Consultar matches ligados a esta competición
    stmt = (
        select(Match)
        .join(Season, Season.id == Match.season_id, isouter=True)
        .where(
            or_(
                Season.competition_id == comp.id,
                Match.season_id.is_(None),
            )
        )
    )

    if season is not None:
        stmt = stmt.where(Season.year_start == season)
    if from_date is not None:
        stmt = stmt.where(Match.match_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Match.match_date <= to_date)
    if upcoming_only:
        stmt = stmt.where(
            and_(
                Match.home_goals.is_(None),
                Match.match_date >= date.today(),
            )
        )
    if matchday is not None:
        stmt = stmt.where(Match.matchday == matchday)

    stmt = stmt.order_by(Match.match_date).limit(limit)
    matches = list(db.scalars(stmt))

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sin fixtures para '{competition_id}'. "
                "Ejecuta: POST /update-data?competition=" + slug
            ),
        )

    # Mapear equipos
    team_ids = set()
    for m in matches:
        team_ids.add(m.home_team)
        team_ids.add(m.away_team)
    teams = {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(team_ids)))}

    # Predicciones (opcional)
    predictions = {}
    if with_predictions:
        predictions = _predict_batch(matches, teams)

    season_label = str(season) + "/" + str(season + 1) if season else "2024/25"

    result = []
    for m in matches:
        home_name = teams.get(m.home_team, f"team_{m.home_team}")
        away_name = teams.get(m.away_team, f"team_{m.away_team}")
        pred = predictions.get(m.id, {})

        status = "played" if m.home_goals is not None else "scheduled"

        result.append(FixtureOut(
            match_id=m.id,
            competition=comp.name,
            season=season_label,
            date=str(m.match_date),
            matchday=m.matchday,
            round=m.round_name,
            home_team=home_name,
            away_team=away_name,
            venue=m.venue,
            status=status,
            p_home=pred.get("p_home"),
            p_draw=pred.get("p_draw"),
            p_away=pred.get("p_away"),
            expected_goals_home=pred.get("xg_home"),
            expected_goals_away=pred.get("xg_away"),
            home_goals=m.home_goals,
            away_goals=m.away_goals,
        ))

    return result


def _predict_batch(matches, teams: dict) -> dict:
    """Genera predicciones 1X2 para una lista de partidos."""
    try:
        from app.main import STATE
        from app.models.elo import win_draw_loss_probs, TeamElo
        from app.models.hybrid import blend_smart

        result = {}
        for m in matches:
            h = teams.get(m.home_team, "")
            a = teams.get(m.away_team, "")
            if not h or not a:
                continue

            h_elo = STATE.elo.get(h, TeamElo())
            a_elo = STATE.elo.get(a, TeamElo())
            elo_p = win_draw_loss_probs(h_elo.rating, a_elo.rating, STATE.elo_cfg, m.neutral)

            dc_p = None
            if STATE.dc and STATE.dc.params:
                if h in STATE.dc.params.attack and a in STATE.dc.params.attack:
                    p = STATE.dc.match_probabilities(h, a, m.neutral)
                    dc_p = p["home_win"], p["draw"], p["away_win"]

            probs, _ = blend_smart(dc=dc_p, xgb=None, elo=elo_p, klement=None)
            result[m.id] = {
                "p_home": round(probs[0], 4),
                "p_draw": round(probs[1], 4),
                "p_away": round(probs[2], 4),
            }
        return result
    except Exception:
        return {}
