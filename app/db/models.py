"""SQLAlchemy 2.0 ORM models (mirrors app/db/schema.sql).

Uses a portable JSON type: JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite
for tests), so the same models run in production and in the test suite.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

# JSONB on Postgres, JSON elsewhere.
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    confederation: Mapped[str | None] = mapped_column(String, nullable=True)
    gdp_per_capita: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    football_culture: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_date: Mapped[date] = mapped_column(Date)
    home_team: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_type: Mapped[str] = mapped_column(String, default="friendly")
    neutral: Mapped[bool] = mapped_column(Boolean, default=False)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String)
    position: Mapped[str | None] = mapped_column(String, nullable=True)


class EloHistory(Base):
    __tablename__ = "elo_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    as_of: Mapped[date] = mapped_column(Date)
    rating: Mapped[float] = mapped_column(Float)
    attack: Mapped[float] = mapped_column(Float)
    defense: Mapped[float] = mapped_column(Float)


class FifaRanking(Base):
    __tablename__ = "fifa_rankings"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    as_of: Mapped[date] = mapped_column(Date)
    points: Mapped[float] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MacroeconomicData(Base):
    __tablename__ = "macroeconomic_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    year: Mapped[int] = mapped_column(Integer)
    gdp_per_capita: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    n_sims: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    model: Mapped[str] = mapped_column(String)
    p_home: Mapped[float] = mapped_column(Float)
    p_draw: Mapped[float] = mapped_column(Float)
    p_away: Mapped[float] = mapped_column(Float)
    extra: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)


class TournamentResult(Base):
    __tablename__ = "tournament_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    p_champion: Mapped[float] = mapped_column(Float)
    p_finalist: Mapped[float] = mapped_column(Float)
    p_semifinalist: Mapped[float] = mapped_column(Float)
    p_group_qualify: Mapped[float] = mapped_column(Float)


class ModelMetric(Base):
    __tablename__ = "model_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    model: Mapped[str] = mapped_column(String)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    log_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_err: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)
