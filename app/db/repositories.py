"""Repository layer: typed helpers that read/write domain objects to the DB.

Keeps SQLAlchemy out of the API and model code. Every function takes an open
Session so callers control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import (
    EloHistory, FifaRanking, Match, ModelMetric,
    Player, Prediction, ProviderLog, Simulation, Standing,
    Team, TournamentResult, UpdateLog,
)


# ---- teams ------------------------------------------------------------------

def upsert_team(db: Session, name: str, **fields) -> Team:
    team = db.scalar(select(Team).where(Team.name == name))
    if team is None:
        team = Team(name=name, **fields)
        db.add(team)
        db.flush()
    else:
        for k, v in fields.items():
            setattr(team, k, v)
    return team


def get_team(db: Session, name: str) -> Team | None:
    return db.scalar(select(Team).where(Team.name == name))


def list_teams(db: Session) -> list[Team]:
    return list(db.scalars(select(Team).order_by(Team.name)))


def team_id_map(db: Session) -> dict[str, int]:
    return {t.name: t.id for t in list_teams(db)}


# ---- matches ----------------------------------------------------------------

def add_match(db: Session, match_date: date, home_id: int, away_id: int,
              home_goals: int, away_goals: int, match_type: str = "friendly",
              neutral: bool = False) -> Match:
    m = Match(match_date=match_date, home_team=home_id, away_team=away_id,
              home_goals=home_goals, away_goals=away_goals,
              match_type=match_type, neutral=neutral)
    db.add(m)
    db.flush()
    return m


def load_matches(db: Session) -> list[Match]:
    return list(db.scalars(select(Match).order_by(Match.match_date)))


# ---- elo snapshots ----------------------------------------------------------

def save_elo_snapshot(db: Session, team_id: int, as_of: date,
                      rating: float, attack: float, defense: float) -> EloHistory:
    row = EloHistory(team_id=team_id, as_of=as_of, rating=rating,
                     attack=attack, defense=defense)
    db.add(row)
    db.flush()
    return row


def latest_elo(db: Session) -> dict[int, EloHistory]:
    """Most recent Elo snapshot per team."""
    out: dict[int, EloHistory] = {}
    for row in db.scalars(select(EloHistory).order_by(EloHistory.as_of)):
        out[row.team_id] = row  # later dates overwrite -> keeps latest
    return out


# ---- predictions ------------------------------------------------------------

def save_prediction(db: Session, model: str, p_home: float, p_draw: float,
                    p_away: float, match_id: int | None = None,
                    extra: dict | None = None) -> Prediction:
    p = Prediction(model=model, p_home=p_home, p_draw=p_draw, p_away=p_away,
                   match_id=match_id, extra=extra)
    db.add(p)
    db.flush()
    return p


# ---- simulations + results --------------------------------------------------

def save_simulation(db: Session, n_sims: int, config: dict,
                    champion: dict[str, float], finalist: dict[str, float],
                    semifinalist: dict[str, float],
                    group_qualified: dict[str, float]) -> Simulation:
    sim = Simulation(n_sims=n_sims, config=config)
    db.add(sim)
    db.flush()
    ids = team_id_map(db)
    for name, p_champ in champion.items():
        if name not in ids:
            continue
        db.add(TournamentResult(
            simulation_id=sim.id, team_id=ids[name],
            p_champion=p_champ, p_finalist=finalist.get(name, 0.0),
            p_semifinalist=semifinalist.get(name, 0.0),
            p_group_qualify=group_qualified.get(name, 0.0)))
    db.flush()
    return sim


# ---- metrics ----------------------------------------------------------------

def save_metrics(db: Session, model: str, **scores) -> ModelMetric:
    row = ModelMetric(model=model, **scores)
    db.add(row)
    db.flush()
    return row


def latest_metrics(db: Session) -> list[ModelMetric]:
    return list(db.scalars(select(ModelMetric).order_by(ModelMetric.evaluated_at.desc())))


# ---- FIFA ranking points ----------------------------------------------------

def save_fifa_points(db: Session, team_id: int, as_of: date, points: float,
                     rank: int | None = None) -> FifaRanking:
    row = FifaRanking(team_id=team_id, as_of=as_of, points=points, rank=rank)
    db.add(row)
    db.flush()
    return row


def latest_fifa_points(db: Session) -> dict[int, float]:
    """Most recent FIFA points per team_id."""
    out: dict[int, float] = {}
    for row in db.scalars(select(FifaRanking).order_by(FifaRanking.as_of)):
        out[row.team_id] = row.points  # later dates overwrite -> keeps latest
    return out


# ---- match dedup ------------------------------------------------------------

def match_exists(
    db: Session,
    home_id: int,
    away_id: int,
    match_date: date,
) -> bool:
    return db.scalar(
        select(Match.id).where(
            and_(
                Match.home_team == home_id,
                Match.away_team == away_id,
                Match.match_date == match_date,
            )
        )
    ) is not None


def find_match(
    db: Session,
    home_id: int,
    away_id: int,
    match_date: date,
) -> "Match | None":
    """Devuelve el Match si existe, None si no."""
    return db.scalar(
        select(Match).where(
            and_(
                Match.home_team == home_id,
                Match.away_team == away_id,
                Match.match_date == match_date,
            )
        )
    )


def update_match_result(
    db: Session,
    match: "Match",
    home_goals: int,
    away_goals: int,
    home_xg: Optional[float] = None,
    away_xg: Optional[float] = None,
) -> "Match":
    """Actualiza el resultado de un partido SCHEDULED → FINISHED."""
    match.home_goals = home_goals
    match.away_goals = away_goals
    if home_xg is not None:
        match.home_xg = home_xg
    if away_xg is not None:
        match.away_xg = away_xg
    db.flush()
    return match


def find_or_create_season(
    db: Session,
    competition_slug: str,
    year: int,
) -> Optional[int]:
    """
    Devuelve season.id para la competición y año dados.
    Crea Competition y Season en BD si no existen.
    """
    from sqlalchemy import select as _sel
    from app.db.models import Competition as Comp, Season as Seas
    from app.models.competition import COMPETITIONS

    comp_row = db.scalar(_sel(Comp).where(Comp.slug == competition_slug))
    if comp_row is None:
        cfg = COMPETITIONS.get(competition_slug)
        if cfg is None:
            return None
        comp_row = Comp(
            slug=competition_slug,
            name=cfg.name,
            competition_type=cfg.competition_type.value,
            tier=cfg.tier.value,
            country=getattr(cfg, "country", None),
            n_teams=cfg.n_teams,
            relegation_spots=cfg.relegation_spots,
            ucl_spots=cfg.ucl_spots,
        )
        db.add(comp_row)
        db.flush()

    season_row = db.scalar(
        _sel(Seas).where(
            and_(Seas.competition_id == comp_row.id, Seas.year_start == year)
        )
    )
    if season_row is None:
        season_row = Seas(
            competition_id=comp_row.id,
            year_start=year,
            year_end=year + 1,
            status="active",
        )
        db.add(season_row)
        db.flush()

    return season_row.id


def add_match_full(
    db: Session,
    match_date: date,
    home_id: int,
    away_id: int,
    home_goals: Optional[int] = None,   # None = partido no jugado / programado
    away_goals: Optional[int] = None,
    match_type: str = "friendly",
    neutral: bool = False,
    matchday: Optional[int] = None,
    round_name: Optional[str] = None,
    venue: Optional[str] = None,
    attendance: Optional[int] = None,
    home_xg: Optional[float] = None,
    away_xg: Optional[float] = None,
    season_id: Optional[int] = None,
) -> Match:
    m = Match(
        match_date=match_date,
        home_team=home_id,
        away_team=away_id,
        home_goals=home_goals,
        away_goals=away_goals,
        match_type=match_type,
        neutral=neutral,
        matchday=matchday,
        round_name=round_name,
        venue=venue,
        attendance=attendance,
        home_xg=home_xg,
        away_xg=away_xg,
        season_id=season_id,
    )
    db.add(m)
    db.flush()
    return m


# ---- players ----------------------------------------------------------------

def upsert_player(
    db: Session,
    team_id: int,
    name: str,
    **fields,
) -> Player:
    player = db.scalar(
        select(Player).where(
            and_(Player.team_id == team_id, Player.name == name)
        )
    )
    if player is None:
        player = Player(team_id=team_id, name=name, **fields)
        db.add(player)
        db.flush()
    else:
        for k, v in fields.items():
            if v is not None:
                setattr(player, k, v)
    return player


# ---- standings --------------------------------------------------------------

def upsert_standing(
    db: Session,
    team_id: int,
    competition_slug: str,
    season_year: int,
    **fields,
) -> Standing:
    row = db.scalar(
        select(Standing).where(
            and_(
                Standing.team_id == team_id,
                Standing.competition_slug == competition_slug,
                Standing.season_year == season_year,
            )
        )
    )
    if row is None:
        row = Standing(
            team_id=team_id,
            competition_slug=competition_slug,
            season_year=season_year,
            **fields,
        )
        db.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
        row.last_updated = datetime.utcnow()
    db.flush()
    return row


def get_standings(
    db: Session,
    competition_slug: str,
    season_year: Optional[int] = None,
) -> list[Standing]:
    q = select(Standing).where(Standing.competition_slug == competition_slug)
    if season_year:
        q = q.where(Standing.season_year == season_year)
    return list(db.scalars(q.order_by(Standing.position)))


# ---- update logs ------------------------------------------------------------

def start_update_log(
    db: Session,
    data_type: str,
    competition_slug: Optional[str] = None,
) -> UpdateLog:
    log = UpdateLog(data_type=data_type, competition_slug=competition_slug, status="running")
    db.add(log)
    db.flush()
    return log


def finish_update_log(
    db: Session,
    log: UpdateLog,
    status: str,
    records_fetched: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    records_skipped: int = 0,
    errors: int = 0,
    error_detail: Optional[str] = None,
    providers_used: Optional[list] = None,
    duration_seconds: Optional[float] = None,
) -> UpdateLog:
    log.completed_at = datetime.utcnow()
    log.status = status
    log.records_fetched = records_fetched
    log.records_inserted = records_inserted
    log.records_updated = records_updated
    log.records_skipped = records_skipped
    log.errors = errors
    log.error_detail = error_detail
    log.providers_used = providers_used or []
    log.duration_seconds = duration_seconds
    db.flush()
    return log


def list_update_logs(db: Session, limit: int = 100) -> list[UpdateLog]:
    return list(
        db.scalars(
            select(UpdateLog)
            .order_by(UpdateLog.started_at.desc())
            .limit(limit)
        )
    )


# ---- provider logs ----------------------------------------------------------

def log_provider_call(
    db: Session,
    provider_name: str,
    data_type: str,
    competition_slug: Optional[str],
    records_fetched: int,
    records_valid: int,
    duration_seconds: float,
    success: bool = True,
    error_message: Optional[str] = None,
) -> ProviderLog:
    row = ProviderLog(
        provider_name=provider_name,
        data_type=data_type,
        competition_slug=competition_slug,
        records_fetched=records_fetched,
        records_valid=records_valid,
        duration_seconds=duration_seconds,
        success=success,
        error_message=error_message,
    )
    db.add(row)
    db.flush()
    return row
