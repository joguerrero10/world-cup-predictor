"""
Endpoints de calendario (fixtures).

GET /fixtures/                 — todos los partidos en una ventana de fechas
GET /fixtures/{competition_id} — partidos de una competición específica

Datos reales vía ETL; sin fixtures ficticios hardcodeados.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Competition, Match, Season, Team

router = APIRouter(prefix="/fixtures", tags=["fixtures"])

_ALIASES = {
    "premier": "premier_league",
    "epl": "premier_league",
    "la_liga": "laliga",
    "ligue1": "ligue_1",
    "seriea": "serie_a",
    "bl1": "bundesliga",
    "worldcup": "fifa_wc_2026",
    "champions": "ucl",
}

_MATCH_TYPE_LABELS = {
    "friendly": "Amistoso",
    "world_cup_group": "Copa del Mundo — Fase de grupos",
    "world_cup_ko": "Copa del Mundo — Eliminación",
    "ucl_group": "Champions League — Grupos",
    "ucl_ko": "Champions League — Eliminación",
    "league": "Liga",
    "domestic_cup": "Copa Nacional",
}


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
    status: str   # FINISHED | LIVE | SCHEDULED | POSTPONED
    p_home: float | None = None
    p_draw: float | None = None
    p_away: float | None = None
    expected_goals_home: float | None = None
    expected_goals_away: float | None = None
    home_goals: int | None = None
    away_goals: int | None = None


def _derive_status(m: Match, today: date) -> str:
    if m.home_goals is not None:
        return "FINISHED"
    if m.match_date < today:
        return "POSTPONED"
    if m.match_date == today:
        return "LIVE"
    return "SCHEDULED"


def _build_team_map(db: Session, matches: list[Match]) -> dict[int, str]:
    ids = {m.home_team for m in matches} | {m.away_team for m in matches}
    if not ids:
        return {}
    return {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(ids)))}


def _build_comp_map(db: Session, matches: list[Match]) -> dict[int, str]:
    """season_id → competition name lookup, skips None season_ids."""
    season_ids = {m.season_id for m in matches if m.season_id is not None}
    if not season_ids:
        return {}
    rows = list(db.execute(
        select(Season.id, Competition.name)
        .join(Competition, Competition.id == Season.competition_id)
        .where(Season.id.in_(season_ids))
    ))
    return {sid: cname for sid, cname in rows}


# ─── GET / ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[FixtureOut])
def get_all_fixtures(
    competition: Optional[str] = Query(None, description="Slug de competición"),
    date_from: Optional[date] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="Fecha fin YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="FINISHED|LIVE|SCHEDULED|POSTPONED"),
    limit: int = Query(80, ge=1, le=200),
    with_predictions: bool = Query(False),
    db: Session = Depends(_db),
):
    """
    Devuelve partidos de todas las competiciones en una ventana de fechas.

    Sin filtro de competition → devuelve todas las competiciones.
    Sin filtro de fechas     → ventana por defecto: -3 días a +14 días.
    """
    today = date.today()
    _from = date_from or (today - timedelta(days=3))
    _to   = date_to   or (today + timedelta(days=14))

    stmt = select(Match).where(
        and_(Match.match_date >= _from, Match.match_date <= _to)
    )

    if competition:
        slug = _ALIASES.get(competition.lower(), competition.lower())
        comp_row = db.scalar(select(Competition).where(Competition.slug == slug))
        if comp_row is None:
            return []
        season_ids = list(db.scalars(
            select(Season.id).where(Season.competition_id == comp_row.id)
        ))
        if not season_ids:
            return []
        stmt = stmt.where(Match.season_id.in_(season_ids))

    stmt = stmt.order_by(Match.match_date, Match.id).limit(limit)
    matches = list(db.scalars(stmt))
    if not matches:
        return []

    teams    = _build_team_map(db, matches)
    comp_map = _build_comp_map(db, matches)
    preds    = _predict_batch(matches, teams) if with_predictions else {}

    result: list[FixtureOut] = []
    for m in matches:
        st = _derive_status(m, today)
        if status and st != status.upper():
            continue

        comp_name = (
            comp_map.get(m.season_id)
            if m.season_id
            else _MATCH_TYPE_LABELS.get(m.match_type, "Amistoso")
        ) or "Desconocido"

        pred = preds.get(m.id, {})
        result.append(FixtureOut(
            match_id=m.id,
            competition=comp_name,
            season="",
            date=str(m.match_date),
            matchday=m.matchday,
            round=m.round_name,
            home_team=teams.get(m.home_team, f"team_{m.home_team}"),
            away_team=teams.get(m.away_team, f"team_{m.away_team}"),
            venue=m.venue,
            status=st,
            p_home=pred.get("p_home"),
            p_draw=pred.get("p_draw"),
            p_away=pred.get("p_away"),
            home_goals=m.home_goals,
            away_goals=m.away_goals,
        ))

    return result


# ─── GET /{competition_id} ────────────────────────────────────────────────────

@router.get("/{competition_id}", response_model=list[FixtureOut])
def get_fixtures(
    competition_id: str,
    season: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    to_date: Optional[date] = Query(None, description="Fecha fin YYYY-MM-DD"),
    matchday: Optional[int] = Query(None),
    upcoming_only: bool = Query(False),
    limit: int = Query(40, ge=1, le=200),
    with_predictions: bool = Query(False),
    db: Session = Depends(_db),
):
    """Calendario de una competición específica (devuelve [] si no hay datos)."""
    today = date.today()
    slug = _ALIASES.get(competition_id.lower(), competition_id.lower())

    comp = db.scalar(select(Competition).where(Competition.slug == slug))
    if comp is None:
        return []

    stmt = (
        select(Match)
        .join(Season, Season.id == Match.season_id, isouter=True)
        .where(Season.competition_id == comp.id)
    )

    if season is not None:
        stmt = stmt.where(Season.year_start == season)
    if from_date is not None:
        stmt = stmt.where(Match.match_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Match.match_date <= to_date)
    if upcoming_only:
        stmt = stmt.where(
            and_(Match.home_goals.is_(None), Match.match_date >= today)
        )
    if matchday is not None:
        stmt = stmt.where(Match.matchday == matchday)

    stmt = stmt.order_by(Match.match_date).limit(limit)
    matches = list(db.scalars(stmt))
    if not matches:
        return []

    teams = _build_team_map(db, matches)
    preds = _predict_batch(matches, teams) if with_predictions else {}

    season_label = f"{season}/{season + 1}" if season else "2025/26"

    return [
        FixtureOut(
            match_id=m.id,
            competition=comp.name,
            season=season_label,
            date=str(m.match_date),
            matchday=m.matchday,
            round=m.round_name,
            home_team=teams.get(m.home_team, f"team_{m.home_team}"),
            away_team=teams.get(m.away_team, f"team_{m.away_team}"),
            venue=m.venue,
            status=_derive_status(m, today),
            p_home=(pred := preds.get(m.id, {})).get("p_home"),
            p_draw=pred.get("p_draw"),
            p_away=pred.get("p_away"),
            home_goals=m.home_goals,
            away_goals=m.away_goals,
        )
        for m in matches
    ]


# ─── Helper: predicciones batch ───────────────────────────────────────────────

def _predict_batch(matches: list[Match], teams: dict[int, str]) -> dict[int, dict]:
    try:
        from app.main import STATE
        from app.models.elo import TeamElo, win_draw_loss_probs
        from app.models.hybrid import blend_smart

        result: dict[int, dict] = {}
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
