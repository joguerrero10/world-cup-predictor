"""Repository layer: typed helpers that read/write domain objects to the DB.

Keeps SQLAlchemy out of the API and model code. Every function takes an open
Session so callers control the transaction boundary.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (EloHistory, FifaRanking, Match, ModelMetric,
                           Prediction, Simulation, Team, TournamentResult)


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
