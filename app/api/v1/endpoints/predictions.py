"""
Endpoints de predicción sincrónica.

GET /api/v1/predict-match         — predicción 1X2 + marcador + over/under
GET /api/v1/predict-player        — probabilidades a nivel de jugador
GET /api/v1/predict-season        — predicción de temporada completa (síncrono, < 30K sims)
GET /api/v1/team-probabilities    — probabilidades de torneo (síncrono)
GET /api/v1/league-table          — tabla de liga simulada
GET /api/v1/player-probabilities  — distribución de goles/asistencias por jugador
GET /api/v1/discipline-probabilities — probabilidades de tarjetas
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from app.api.v1.schemas import (
    MatchPredictionResponse,
    PlayerPredictionResponse,
    DisciplineResponse,
    SeasonPredictionResponse,
    TournamentProbsResponse,
    LeagueTableResponse,
    LeagueTableEntry,
)

router = APIRouter(tags=["predictions"])


def _get_state():
    from app.main import STATE
    return STATE


# ---------------------------------------------------------------------------
# GET /api/v1/predict-match
# ---------------------------------------------------------------------------

@router.get("/predict-match", response_model=MatchPredictionResponse)
def predict_match(
    home: str = Query(..., description="Nombre del equipo local"),
    away: str = Query(..., description="Nombre del equipo visitante"),
    neutral: bool = Query(True, description="Campo neutral"),
    model: Literal["hybrid", "elo", "dixon_coles", "klement"] = "hybrid",
    competition_id: str | None = Query(None),
):
    """
    Predice el resultado de un partido.

    Retorna probabilidades 1X2 y, cuando Dixon-Coles está disponible,
    también marcador más probable, over/under 2.5 y ambos anotan.
    """
    STATE = _get_state()

    from app.models.elo import win_draw_loss_probs, TeamElo
    from app.models.dixon_coles import DixonColes
    from app.models.klement import klement_score, klement_match_probs
    from app.models.hybrid import blend_smart

    if home not in STATE.elo and home not in STATE.factors:
        raise HTTPException(404, f"Equipo desconocido: {home}")
    if away not in STATE.elo and away not in STATE.factors:
        raise HTTPException(404, f"Equipo desconocido: {away}")

    def elo_p():
        h = STATE.elo.get(home, TeamElo())
        a = STATE.elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, STATE.elo_cfg, neutral)

    def dc_p():
        if STATE.dc is None or STATE.dc.params is None:
            return None
        if home not in STATE.dc.params.attack or away not in STATE.dc.params.attack:
            return None
        p = STATE.dc.match_probabilities(home, away, neutral)
        return p["home_win"], p["draw"], p["away_win"]

    def klement_p():
        if home not in STATE.factors or away not in STATE.factors:
            return None
        sh = klement_score(STATE.factors[home], STATE.k_weights)
        sa = klement_score(STATE.factors[away], STATE.k_weights)
        return klement_match_probs(sh, sa)

    def xgb_p():
        if STATE.form_model is None or not STATE.form_model.fitted:
            return None
        h_elo = STATE.elo.get(home, TeamElo())
        a_elo = STATE.elo.get(away, TeamElo())
        feats = {
            "elo_diff":     h_elo.rating  - a_elo.rating,
            "attack_diff":  h_elo.attack  - a_elo.attack,
            "defense_diff": h_elo.defense - a_elo.defense,
            "form_diff":    STATE.form.get(home, 1.5) - STATE.form.get(away, 1.5),
            "fifa_diff":    0.0,
            "neutral":      1.0 if neutral else 0.0,
        }
        return STATE.form_model.predict_one(feats)

    dc_probs = dc_p()

    if model == "elo":
        probs = elo_p()
        src = "elo"
    elif model == "dixon_coles":
        if dc_probs is None:
            raise HTTPException(409, "Dixon-Coles no entrenado. Llama a POST /retrain o /load-from-db.")
        probs = dc_probs
        src = "dixon_coles"
    elif model == "klement":
        probs = klement_p()
        if probs is None:
            raise HTTPException(409, "Factores Klement no cargados para estos equipos.")
        src = "klement"
    else:
        blend = blend_smart(
            dc=dc_probs,
            xgb=xgb_p(),
            elo=elo_p() if home in STATE.elo and away in STATE.elo else None,
            klement=klement_p(),
        )
        if blend is None:
            probs = elo_p()
            src = "elo_fallback"
        else:
            probs, src = blend

    if probs is None:
        raise HTTPException(409, "Sin datos suficientes para predecir.")

    # Extras Dixon-Coles si disponible
    extra: dict = {}
    if STATE.dc is not None and STATE.dc.params is not None:
        if home in STATE.dc.params.attack and away in STATE.dc.params.attack:
            dc_full = STATE.dc.match_probabilities(home, away, neutral)
            extra = {
                "most_likely_score": dc_full.get("most_likely_score"),
                "over_2_5": dc_full.get("over_2_5"),
                "under_2_5": dc_full.get("under_2_5"),
                "btts_yes": dc_full.get("btts_yes"),
                "btts_no":  dc_full.get("btts_no"),
            }

    # Persistir predicción (best-effort)
    try:
        from app.db.database import SessionLocal
        from app.db import repositories as repo
        with SessionLocal() as db:
            repo.save_prediction(db, src, float(probs[0]), float(probs[1]), float(probs[2]),
                                 extra={"home": home, "away": away, "neutral": neutral})
            db.commit()
    except Exception:
        pass

    return MatchPredictionResponse(
        home=home, away=away,
        home_win=float(probs[0]), draw=float(probs[1]), away_win=float(probs[2]),
        source=src,
        **extra,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/predict-player
# ---------------------------------------------------------------------------

@router.get("/predict-player", response_model=PlayerPredictionResponse)
def predict_player(
    player_name: str = Query(...),
    team: str = Query(...),
):
    """
    Probabilidades a nivel de jugador: goles esperados, asistencias, tarjetas.

    NOTA: Este endpoint requiere estadísticas de jugador cargadas vía ETL
    (goals_per_90, xg_per_90, yellow_cards_per_90). Si no están disponibles,
    indica data_status=pending en lugar de inventar valores.
    """
    try:
        from app.db.database import SessionLocal
        from app.db.models import Player, Team
        from sqlalchemy import select

        with SessionLocal() as db:
            team_row = db.scalar(select(Team).where(Team.name == team))
            if team_row is None:
                raise HTTPException(404, f"Equipo no encontrado: {team}")

            player_row = db.scalar(
                select(Player).where(
                    Player.team_id == team_row.id,
                    Player.name.ilike(f"%{player_name}%")
                )
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error de DB: {e}")

    if player_row is None:
        return PlayerPredictionResponse(
            player_name=player_name,
            team=team,
            data_status="unavailable",
        )

    has_stats = (
        player_row.goals_per_90 is not None
        or player_row.xg_per_90 is not None
    )

    if not has_stats:
        return PlayerPredictionResponse(
            player_name=player_row.name,
            team=team,
            data_status="pending",
        )

    # Proyección para 1 partido (90 minutos)
    return PlayerPredictionResponse(
        player_name=player_row.name,
        team=team,
        goals_expected=player_row.goals_per_90,
        assists_expected=player_row.assists_per_90,
        yellow_cards_expected=player_row.yellow_cards_per_90,
        red_card_prob=(player_row.red_cards_per_90 or 0.0),
        injury_risk=None,   # requiere modelo de lesiones — pendiente ETL
        data_status="available",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/predict-season
# ---------------------------------------------------------------------------

@router.get("/predict-season", response_model=SeasonPredictionResponse)
def predict_season(
    competition_id: str = Query(...),
    n_sims: int = Query(10_000, ge=1_000, le=100_000),
):
    """
    Predicción de temporada completa (síncrono, máximo 100K sims).
    Para más simulaciones, usa POST /api/v1/simulation-jobs.
    """
    from app.models.competition import get_competition, CompetitionType
    from app.simulation.league_sim import simulate_league

    try:
        comp = get_competition(competition_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if comp.competition_type != CompetitionType.LEAGUE:
        raise HTTPException(400, f"'{competition_id}' no es una liga. "
                                 "Usa /team-probabilities para torneos.")

    STATE = _get_state()
    if not STATE.elo:
        raise HTTPException(409, "No hay equipos cargados. Carga datos primero.")

    from app.models.elo import win_draw_loss_probs, TeamElo

    def model_fn(home: str, away: str, neutral: bool):
        h = STATE.elo.get(home, TeamElo())
        a = STATE.elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, STATE.elo_cfg, neutral)

    teams = sorted(STATE.elo.keys())[:comp.n_teams]

    result = simulate_league(
        teams=teams,
        model=model_fn,
        config=comp,
        n_sims=n_sims,
    )

    ucl_cutoff = comp.ucl_spots
    uel_cutoff = comp.ucl_spots + comp.uel_spots

    return SeasonPredictionResponse(
        competition_id=competition_id,
        n_sims=n_sims,
        champion=result.champion,
        relegated=result.relegated,
        ucl_qualification=result.top4,
        uel_qualification={
            t: result.top6.get(t, 0.0) - result.top4.get(t, 0.0)
            for t in result.teams
        },
    )


# ---------------------------------------------------------------------------
# GET /api/v1/team-probabilities  (torneo / Copa del Mundo)
# ---------------------------------------------------------------------------

@router.get("/team-probabilities", response_model=TournamentProbsResponse)
def team_probabilities(
    competition_id: str = Query("fifa_wc_2026"),
    n_sims: int = Query(10_000, ge=1_000, le=1_000_000),
):
    """
    Probabilidades de torneo (campeón, finalista, semifinalista, clasificación de grupos).
    Usa el motor MC vectorizado — 1M sims < 60s.
    """
    from app.models.competition import get_competition
    from app.simulation.monte_carlo_fast import simulate_fast, CompetitionGroup

    try:
        comp = get_competition(competition_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    STATE = _get_state()
    if not STATE.elo:
        raise HTTPException(409, "No hay equipos cargados.")

    from app.models.elo import win_draw_loss_probs, TeamElo

    def model_fn(home: str, away: str, neutral: bool):
        h = STATE.elo.get(home, TeamElo())
        a = STATE.elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, STATE.elo_cfg, neutral)

    teams = sorted(STATE.elo.keys(), key=lambda t: -STATE.elo[t].rating)[:comp.n_teams]
    n_per_group = comp.teams_per_group or 4

    groups = [
        CompetitionGroup(name=str(i // n_per_group + 1), teams=teams[i:i + n_per_group])
        for i in range(0, len(teams) - len(teams) % n_per_group, n_per_group)
    ]

    if not groups:
        raise HTTPException(409, "Necesitas al menos 4 equipos para formar grupos.")

    result = simulate_fast(
        groups=groups,
        model=model_fn,
        n_sims=n_sims,
        advance_per_group=comp.advance_per_group or 2,
        neutral=comp.neutral_venue_groups,
    )

    return TournamentProbsResponse(
        competition_id=competition_id,
        **result.to_dict(),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/league-table
# ---------------------------------------------------------------------------

@router.get("/league-table", response_model=LeagueTableResponse)
def league_table(
    competition_id: str = Query("premier_league"),
    n_sims: int = Query(10_000, ge=1_000, le=50_000),
):
    """Tabla de liga simulada con distribuciones de posición."""
    from app.models.competition import get_competition, CompetitionType
    from app.simulation.league_sim import simulate_league

    try:
        comp = get_competition(competition_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if comp.competition_type != CompetitionType.LEAGUE:
        raise HTTPException(400, "Este endpoint es para ligas. Usa /team-probabilities para torneos.")

    STATE = _get_state()
    if not STATE.elo:
        raise HTTPException(409, "No hay equipos cargados.")

    from app.models.elo import win_draw_loss_probs, TeamElo

    def model_fn(home: str, away: str, neutral: bool):
        h = STATE.elo.get(home, TeamElo())
        a = STATE.elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, STATE.elo_cfg, neutral)

    teams = sorted(STATE.elo.keys(), key=lambda t: -STATE.elo[t].rating)[:comp.n_teams]

    result = simulate_league(teams=teams, model=model_fn, config=comp, n_sims=n_sims)

    table = [
        LeagueTableEntry(
            position=i + 1,
            team=row.team,
            played=row.played,
            pts=row.pts,
            gf=row.gf,
            ga=row.ga,
            gd=row.gd,
            champion_prob=result.champion.get(row.team, 0.0),
            top4_prob=result.top4.get(row.team, 0.0),
            relegated_prob=result.relegated.get(row.team, 0.0),
        )
        for i, row in enumerate(result.expected_table)
    ]

    return LeagueTableResponse(
        competition_id=competition_id,
        n_sims=n_sims,
        table=table,
        position_distribution=result.position_probs,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/player-probabilities
# ---------------------------------------------------------------------------

@router.get("/player-probabilities")
def player_probabilities(
    team: str = Query(...),
    top_n: int = Query(5, ge=1, le=20),
):
    """
    Probabilidades de goles y asistencias para los top N jugadores de un equipo.
    Requiere estadísticas de jugador cargadas vía ETL.
    """
    from app.db.database import SessionLocal
    from app.db.models import Player, Team
    from sqlalchemy import select, desc

    with SessionLocal() as db:
        team_row = db.scalar(select(Team).where(Team.name == team))
        if team_row is None:
            raise HTTPException(404, f"Equipo no encontrado: {team}")

        players = list(db.scalars(
            select(Player)
            .where(Player.team_id == team_row.id)
            .order_by(desc(Player.goals_per_90.nulls_last()))
            .limit(top_n)
        ))

    if not players:
        return {
            "team": team,
            "players": [],
            "data_status": "pending",
            "message": "Sin estadísticas de jugadores. Ejecuta el ETL de jugadores primero.",
        }

    return {
        "team": team,
        "players": [
            {
                "name": p.name,
                "position": p.position,
                "goals_per_90": p.goals_per_90,
                "xg_per_90": p.xg_per_90,
                "assists_per_90": p.assists_per_90,
                "yellow_cards_per_90": p.yellow_cards_per_90,
                "is_injured": p.is_injured,
                "is_suspended": p.is_suspended,
                "data_status": "available" if p.goals_per_90 is not None else "pending",
            }
            for p in players
        ],
        "data_status": "partial" if any(p.goals_per_90 is None for p in players) else "available",
    }


# ---------------------------------------------------------------------------
# GET /api/v1/discipline-probabilities
# ---------------------------------------------------------------------------

@router.get("/discipline-probabilities", response_model=DisciplineResponse)
def discipline_probabilities(
    home: str = Query(...),
    away: str = Query(...),
):
    """
    Probabilidades de tarjetas para un partido.

    El modelo estadístico base usa las tasas históricas por equipo de la DB.
    Si no hay datos históricos suficientes, indica data_status=pending.

    NOTA: Un modelo de tarjetas por jugador requiere estadísticas de jugador
    cargadas vía ETL (yellow_cards_per_90, red_cards_per_90).
    """
    from app.db.database import SessionLocal
    from app.db.models import Player, Team, MatchEvent, Match
    from sqlalchemy import select, func

    with SessionLocal() as db:
        home_team = db.scalar(select(Team).where(Team.name == home))
        away_team = db.scalar(select(Team).where(Team.name == away))

        if not home_team or not away_team:
            raise HTTPException(404, f"Equipo(s) no encontrado(s): {home}, {away}")

        def _avg_yellows(team_id: int) -> float | None:
            # Promedio de tarjetas amarillas por partido (últimos 20)
            result = db.scalar(
                select(func.count(MatchEvent.id))
                .where(
                    MatchEvent.team_id == team_id,
                    MatchEvent.event_type == "yellow_card",
                )
            )
            match_count = db.scalar(
                select(func.count(Match.id))
                .where(
                    (Match.home_team == team_id) | (Match.away_team == team_id),
                    Match.home_goals.is_not(None),
                )
            )
            if not match_count:
                return None
            return float(result or 0) / match_count

        home_yellows = _avg_yellows(home_team.id)
        away_yellows = _avg_yellows(away_team.id)

    has_data = home_yellows is not None and away_yellows is not None
    data_status = "available" if has_data else "pending"

    # Valores estadísticos basados en promedios históricos del fútbol europeo
    # si no hay datos propios (explícitamente marcado como estimación)
    BASE_YELLOWS_PER_MATCH = 2.0  # promedio histórico Europa
    BASE_RED_PROB = 0.07           # ~7% de probabilidad de roja por partido

    h_y = home_yellows if home_yellows is not None else BASE_YELLOWS_PER_MATCH
    a_y = away_yellows if away_yellows is not None else BASE_YELLOWS_PER_MATCH

    return DisciplineResponse(
        home=home,
        away=away,
        home_yellow_expected=round(h_y, 2),
        away_yellow_expected=round(a_y, 2),
        home_red_prob=round(BASE_RED_PROB, 3),
        away_red_prob=round(BASE_RED_PROB, 3),
        both_teams_card=round(1 - (1 - BASE_RED_PROB) ** 2, 3),
        source="historical_average" if has_data else "prior_estimate",
        data_status=data_status,
    )
