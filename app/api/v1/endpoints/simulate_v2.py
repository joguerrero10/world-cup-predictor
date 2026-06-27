"""
Endpoints de simulación v2 — competition-aware, totalmente separado por competición.

GET /simulate?competition=premier_league&n_sims=10000
  → Simula la liga con los clubes correctos de la Premier League

GET /simulate?competition=ucl&n_sims=50000
  → Simula la UCL con los 36 clubes europeos

GET /simulate?competition=fifa_wc_2026&n_sims=100000
  → Simula el Mundial 2026 con las 48 selecciones nacionales

En NINGÚN caso mezcla tipos de equipos.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.competition_registry import get_competition_teams, get_team_names
from app.models.competition import COMPETITIONS, get_competition, CompetitionType

router = APIRouter(prefix="/simulate", tags=["simulation"])

_VALID_COMPETITIONS = list(COMPETITIONS.keys())
_VALID_N_SIMS = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]


def _db():
    with SessionLocal() as db:
        yield db


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    competition: str = Field(..., description="ID de competición (ucl, premier_league, etc.)")
    n_sims: int = Field(10_000, ge=1_000, le=1_000_000)
    season: Optional[int] = Field(None, description="Año de inicio de temporada")
    model: Literal["hybrid", "elo", "dixon_coles", "ensemble"] = "hybrid"
    seed: Optional[int] = None


class SimulationResponse(BaseModel):
    competition: str
    competition_name: str
    n_sims: int
    teams: list[str]
    team_type: str
    elapsed_seconds: float
    sims_per_second: float
    champion: dict[str, float]
    finalist: dict[str, float]
    semifinalist: dict[str, float]
    top4: dict[str, float]
    top6: dict[str, float]
    relegated: dict[str, float]
    extra: dict


# ─── Helper: construir función de modelo ─────────────────────────────────────

def _build_model_fn(competition_id: str, db: Session, model_name: str):
    """
    Construye la función (home, away, neutral) -> (p_home, p_draw, p_away).
    Usa el STATE global de la API (Elo, Dixon-Coles, xG, etc.) con
    fallback Elo si no hay modelos entrenados para esa competición.
    """
    from app.main import STATE
    from app.models.elo import win_draw_loss_probs, TeamElo
    from app.models.hybrid import blend_smart

    comp_teams = get_team_names(competition_id, db=db)
    n_teams = len(comp_teams)

    # Construir lookup de Elo específico para esta competición
    # Los equipos sin datos Elo en el STATE usan el seed del registry
    from app.core.competition_registry import get_competition_teams
    registry_teams = {t.name: t for t in get_competition_teams(competition_id, db=db)}

    def _elo_probs(home: str, away: str, neutral: bool) -> tuple[float, float, float]:
        h_elo = STATE.elo.get(home)
        a_elo = STATE.elo.get(away)

        # Si no hay Elo en STATE, usar seed del registry
        if h_elo is None:
            seed_h = registry_teams.get(home)
            h_elo = TeamElo(
                rating=seed_h.elo_seed if seed_h else 1500.0
            )
        if a_elo is None:
            seed_a = registry_teams.get(away)
            a_elo = TeamElo(
                rating=seed_a.elo_seed if seed_a else 1500.0
            )

        return win_draw_loss_probs(h_elo.rating, a_elo.rating, STATE.elo_cfg, neutral)

    if model_name == "elo":
        return _elo_probs

    def _dc_probs(home: str, away: str, neutral: bool):
        if STATE.dc is None or STATE.dc.params is None:
            return None
        if home not in STATE.dc.params.attack or away not in STATE.dc.params.attack:
            return None
        p = STATE.dc.match_probabilities(home, away, neutral)
        return p["home_win"], p["draw"], p["away_win"]

    def _hybrid_probs(home: str, away: str, neutral: bool) -> tuple[float, float, float]:
        dc = _dc_probs(home, away, neutral)
        elo = _elo_probs(home, away, neutral)
        result, _ = blend_smart(dc=dc, xgb=None, elo=elo, klement=None)
        return result

    if model_name == "dixon_coles":
        def _dc_only(home: str, away: str, neutral: bool) -> tuple[float, float, float]:
            dc = _dc_probs(home, away, neutral)
            return dc if dc is not None else _elo_probs(home, away, neutral)
        return _dc_only

    return _hybrid_probs


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/", response_model=SimulationResponse)
async def simulate_competition(
    competition: str = Query(..., description="ID de competición"),
    n_sims: int = Query(10_000, ge=1_000, le=1_000_000),
    season: Optional[int] = Query(None),
    model: Literal["hybrid", "elo", "dixon_coles"] = Query("hybrid"),
    seed: Optional[int] = Query(None),
    db: Session = Depends(_db),
):
    """
    Simula una competición completa respetando sus reglas y equipos propios.

    competition=premier_league → solo clubes ingleses.
    competition=ucl → solo clubes europeos.
    competition=fifa_wc_2026 → solo selecciones nacionales.
    """
    comp_id = competition.strip().lower()

    # Aliases
    _aliases = {
        "worldcup": "fifa_wc_2026", "world_cup": "fifa_wc_2026",
        "premier": "premier_league", "champions": "ucl",
        "la_liga": "laliga", "ligue1": "ligue_1", "seriea": "serie_a",
    }
    comp_id = _aliases.get(comp_id, comp_id)

    if comp_id not in COMPETITIONS:
        available = sorted(COMPETITIONS.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Competición '{competition}' no encontrada. Disponibles: {available}",
        )

    cfg = get_competition(comp_id)
    model_fn = _build_model_fn(comp_id, db, model)

    # Ejecutar simulación en hilo (evita bloquear el event loop)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _run_simulation(comp_id, n_sims, season, model_fn, seed, db),
    )

    return result


def _run_simulation(
    comp_id: str,
    n_sims: int,
    season,
    model_fn,
    seed,
    db,
) -> SimulationResponse:
    """
    Ejecuta la simulación apropiada según el tipo de competición y normaliza
    la respuesta a un SimulationResponse uniforme.

    Cada simulador devuelve un dataclass distinto (WorldCupResult, UCLResult,
    LeagueResult). Este método mapea los campos específicos al esquema común.
    """
    cfg = get_competition(comp_id)
    team_names = get_team_names(comp_id, season, db)

    if not team_names:
        raise HTTPException(status_code=409, detail=f"Sin equipos para '{comp_id}'")

    from app.core.competition_registry import get_team_type
    team_type = get_team_type(comp_id)

    # ── Mundial 2026 ───────────────────────────────────────────────────────
    if comp_id == "fifa_wc_2026":
        from app.simulation.world_cup_simulator import WorldCupSimulator
        res = WorldCupSimulator(model=model_fn, season=season or 2026, db=db).run(
            n_sims=n_sims, seed=seed
        )
        return SimulationResponse(
            competition=comp_id,
            competition_name=cfg.name,
            n_sims=res.n_sims,
            teams=list(res.champion.keys()),
            team_type=team_type.value,
            elapsed_seconds=round(res.elapsed_seconds, 2),
            sims_per_second=round(res.sims_per_second, 0),
            champion=res.champion,
            finalist=res.finalist,
            semifinalist=res.semifinalist,
            top4={},
            top6={},
            relegated={},
            extra={
                "group_qualified":    res.group_qualified,
                "round_of_16":        res.round_of_16,
                "quarterfinal":       res.quarterfinal,
                "expected_group_pts": res.expected_group_pts,
            },
        )

    # ── Champions League ───────────────────────────────────────────────────
    if comp_id == "ucl":
        from app.simulation.champions_league_simulator import ChampionsLeagueSimulator
        res = ChampionsLeagueSimulator(model=model_fn, season=season or 2025, db=db).run(
            n_sims=n_sims, seed=seed
        )
        return SimulationResponse(
            competition=comp_id,
            competition_name=cfg.name,
            n_sims=res.n_sims,
            teams=list(res.champion.keys()),
            team_type=team_type.value,
            elapsed_seconds=round(res.elapsed_seconds, 2),
            sims_per_second=round(res.sims_per_second, 0),
            champion=res.champion,
            finalist=res.finalist,
            semifinalist=res.semifinalist,
            top4={},
            top6={},
            relegated={},
            extra={
                # group_qualified = alias de league_phase_top8 para el frontend
                "group_qualified":    res.league_phase_top8,
                "league_phase_top8":  res.league_phase_top8,
                "playoff_qual":       res.playoff_qual,
                "round_of_16":        res.round_of_16,
                "quarterfinal":       res.quarterfinal,
            },
        )

    # ── Ligas domésticas ──────────────────────────────────────────────────
    if cfg.competition_type == CompetitionType.LEAGUE:
        from app.simulation.league_simulator import LeagueSimulator
        res = LeagueSimulator(
            competition_id=comp_id, model=model_fn, season=season, db=db
        ).run(n_sims=n_sims, seed=seed)
        return SimulationResponse(
            competition=comp_id,
            competition_name=cfg.name,
            n_sims=res.n_sims,
            teams=list(res.champion.keys()),
            team_type=team_type.value,
            elapsed_seconds=round(res.elapsed_seconds, 2),
            sims_per_second=round(res.sims_per_second, 0),
            champion=res.champion,
            finalist={},
            semifinalist={},
            top4=res.top4,
            top6=getattr(res, "top6", {}),
            relegated=res.relegated,
            extra={
                "group_qualified": {},
                "position_probs":  getattr(res, "position_probs", {}),
            },
        )

    # ── Knockout genérico (fallback) ──────────────────────────────────────
    from app.simulation.world_cup_simulator import WorldCupSimulator
    res = WorldCupSimulator(model=model_fn, db=db).run(n_sims=n_sims, seed=seed)
    return SimulationResponse(
        competition=comp_id,
        competition_name=cfg.name,
        n_sims=res.n_sims,
        teams=list(res.champion.keys()),
        team_type=team_type.value,
        elapsed_seconds=round(res.elapsed_seconds, 2),
        sims_per_second=round(res.sims_per_second, 0),
        champion=res.champion,
        finalist=res.finalist,
        semifinalist=res.semifinalist,
        top4={},
        top6={},
        relegated={},
        extra={"group_qualified": getattr(res, "group_qualified", {})},
    )


@router.get("/competitions", summary="Listar competiciones simulables")
def list_simulable_competitions():
    """Devuelve qué competiciones pueden simularse y qué tipo de equipos usan."""
    from app.core.competition_registry import list_competitions, get_team_type, TeamType
    result = []
    for comp_id in list_competitions():
        cfg = COMPETITIONS.get(comp_id)
        if cfg is None:
            continue
        team_type = get_team_type(comp_id)
        result.append({
            "id": comp_id,
            "name": cfg.name,
            "type": cfg.competition_type.value,
            "team_type": team_type.value,
            "n_teams": cfg.n_teams,
            "note": (
                "Selecciones nacionales" if team_type == TeamType.NATIONAL
                else "Clubes profesionales"
            ),
        })
    return result
