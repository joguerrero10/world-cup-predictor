"""
GET /api/v1/teams — equipos con datos Elo, logo y metadata.

Estrategia de datos (en orden de prioridad):
  1. Seeds estáticos del competition_registry (siempre disponibles)
  2. Enriquecidos con filas de la tabla Team en BD (logo_url, stadium, etc.)
  3. Elo rating / rank desde STATE global de la API

Filtros disponibles:
  ?competition=premier_league   — solo equipos de esa competición
  ?team_type=club               — solo clubes (team_type=national → selecciones)
  ?search=Arsenal               — búsqueda por nombre
  ?limit=100
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.competition_registry import TeamType, _SEED
from app.db.database import SessionLocal
from app.db.models import Team

router = APIRouter(prefix="/teams", tags=["teams"])

_ALIASES = {
    "premier":  "premier_league",
    "epl":      "premier_league",
    "la_liga":  "laliga",
    "ligue1":   "ligue_1",
    "seriea":   "serie_a",
    "bl1":      "bundesliga",
    "worldcup": "fifa_wc_2026",
    "champions":"ucl",
}


def _db():
    with SessionLocal() as db:
        yield db


class TeamOut(BaseModel):
    id: int | None = None
    name: str
    short_name: str | None = None
    country: str | None = None
    team_type: str              # "club" | "national"
    competition_id: str | None = None
    competition_name: str | None = None
    logo_url: str | None = None
    stadium: str | None = None
    founded_year: int | None = None
    market_value_eur: float | None = None
    elo_rating: float | None = None
    elo_attack: float | None = None
    elo_defense: float | None = None
    elo_rank: int | None = None


def _comp_name(comp_id: str) -> str:
    from app.models.competition import COMPETITIONS
    cfg = COMPETITIONS.get(comp_id)
    return cfg.name if cfg else comp_id.replace("_", " ").title()


@router.get("/", response_model=list[TeamOut])
def get_teams(
    competition: Optional[str] = Query(None, description="Slug de competición"),
    team_type: Optional[str] = Query(None, description="club | national"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(_db),
):
    """
    Devuelve equipos con Elo rating actualizado y metadata (logo, estadio, etc.).

    Siempre devuelve datos aunque el ETL no haya corrido:
    usa los seeds del competition_registry como fallback.
    """
    comp_slug = None
    if competition:
        comp_slug = _ALIASES.get(competition.lower(), competition.lower())

    # ── 1. Recopilar equipos del registry ────────────────────────────────────
    if comp_slug:
        seed_list = _SEED.get(comp_slug, [])
        competition_entries = [(comp_slug, t) for t in seed_list]
    else:
        competition_entries = [
            (comp_id, t)
            for comp_id, teams in _SEED.items()
            for t in teams
        ]

    # Filtrar duplicados (mismo equipo en varias competiciones)
    seen: dict[str, tuple[str, object]] = {}
    for comp_id, rt in competition_entries:
        if rt.name not in seen:
            seen[rt.name] = (comp_id, rt)
    # Si se filtra por competición no hay duplicados, pero globalmente sí

    # Aplicar filtro team_type
    if team_type:
        want = TeamType.CLUB if team_type == "club" else TeamType.NATIONAL
        seen = {
            name: (cid, rt)
            for name, (cid, rt) in seen.items()
            if rt.team_type == want
        }

    # Aplicar búsqueda
    if search:
        q = search.lower()
        seen = {
            name: (cid, rt)
            for name, (cid, rt) in seen.items()
            if q in name.lower()
        }

    if not seen:
        return []

    # ── 2. Enriquecer con datos de BD ────────────────────────────────────────
    names = list(seen.keys())
    db_rows: dict[str, Team] = {}
    try:
        for row in db.scalars(select(Team).where(Team.name.in_(names))):
            db_rows[row.name] = row
    except Exception:
        pass

    # ── 3. Elo desde STATE ───────────────────────────────────────────────────
    elo_map: dict[str, tuple[float, float, float]] = {}
    try:
        from app.main import STATE
        for tname, e in STATE.elo.items():
            elo_map[tname] = (e.rating, e.attack, e.defense)
    except Exception:
        pass

    # Calcular ranks globales o por competición
    # Ordenar por elo_rating desc antes de asignar ranks
    def _elo_rating(name: str) -> float:
        if name in elo_map:
            return elo_map[name][0]
        # Fallback al seed
        _, rt = seen.get(name, ("", None))
        return getattr(rt, "elo_seed", 1500.0) if rt else 1500.0

    sorted_names = sorted(seen.keys(), key=_elo_rating, reverse=True)
    rank_map = {name: i + 1 for i, name in enumerate(sorted_names)}

    # ── 4. Construir respuesta ───────────────────────────────────────────────
    result: list[TeamOut] = []
    for name in sorted_names[:limit]:
        cid, rt = seen[name]
        db_row = db_rows.get(name)
        elo_tuple = elo_map.get(name)

        result.append(TeamOut(
            id=db_row.id if db_row else None,
            name=name,
            short_name=db_row.short_name if db_row else rt.short_name,
            country=db_row.country if db_row else rt.country,
            team_type=rt.team_type.value,
            competition_id=cid,
            competition_name=_comp_name(cid),
            logo_url=db_row.logo_url if db_row else None,
            stadium=db_row.stadium if db_row else None,
            founded_year=db_row.founded_year if db_row else None,
            market_value_eur=(
                db_row.market_value_eur
                if db_row and db_row.market_value_eur
                else rt.market_value_eur
            ),
            elo_rating=round(elo_tuple[0], 1) if elo_tuple else None,
            elo_attack=round(elo_tuple[1], 1) if elo_tuple else None,
            elo_defense=round(elo_tuple[2], 1) if elo_tuple else None,
            elo_rank=rank_map.get(name),
        ))

    return result
