"""
SQLAlchemy 2.0 ORM models — plataforma multicompetición.

Mantiene compatibilidad total con el schema original y añade:
- Competition, Season, SeasonTeam (multicompetición)
- Player ampliado con estadísticas (goles, xG, tarjetas, velocidad)
- Transfer, Injury, Card (fichajes, lesiones, disciplina)
- Lineup, LineupPlayer (alineaciones y once inicial)
- MatchEvent (eventos de partido: goles, tarjetas, sustituciones)
- SimulationJob (trabajos de simulación asíncronos con estado)
- SimulationResult (resultados persistidos por job)

JSONB en PostgreSQL, JSON en SQLite (tests).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, func, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Competiciones y temporadas
# ---------------------------------------------------------------------------

class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)        # "premier_league"
    name: Mapped[str] = mapped_column(String)                     # "Premier League"
    competition_type: Mapped[str] = mapped_column(String)         # league|knockout|group_knockout
    tier: Mapped[str] = mapped_column(String)                     # domestic_top|continental|international
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    n_teams: Mapped[int] = mapped_column(Integer)
    relegation_spots: Mapped[int] = mapped_column(Integer, default=0)
    ucl_spots: Mapped[int] = mapped_column(Integer, default=0)
    uel_spots: Mapped[int] = mapped_column(Integer, default=0)
    legs: Mapped[int] = mapped_column(Integer, default=2)

    seasons: Mapped[list["Season"]] = relationship(back_populates="competition")


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    year_start: Mapped[int] = mapped_column(Integer)              # 2024
    year_end: Mapped[int] = mapped_column(Integer)                # 2025
    status: Mapped[str] = mapped_column(String, default="upcoming")  # upcoming|active|completed
    data_sync_status: Mapped[str] = mapped_column(String, default="pending")  # pending|synced|stale

    competition: Mapped["Competition"] = relationship(back_populates="seasons")
    season_teams: Mapped[list["SeasonTeam"]] = relationship(back_populates="season")
    matches: Mapped[list["Match"]] = relationship(back_populates="season")

    __table_args__ = (
        UniqueConstraint("competition_id", "year_start", name="uq_season"),
    )


class SeasonTeam(Base):
    """Equipos que participan en una temporada específica."""
    __tablename__ = "season_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)  # "A", "B", ...
    final_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_relegated: Mapped[bool] = mapped_column(Boolean, default=False)

    season: Mapped["Season"] = relationship(back_populates="season_teams")
    team: Mapped["Team"] = relationship()

    __table_args__ = (
        UniqueConstraint("season_id", "team_id", name="uq_season_team"),
    )


# ---------------------------------------------------------------------------
# Equipos (expandido)
# ---------------------------------------------------------------------------

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    short_name: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    confederation: Mapped[str | None] = mapped_column(String, nullable=True)
    # Factores Klement
    gdp_per_capita: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    football_culture: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    # Metadatos de sincronización
    data_source: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    players: Mapped[list["Player"]] = relationship(back_populates="team")


# ---------------------------------------------------------------------------
# Jugadores (ampliado)
# ---------------------------------------------------------------------------

class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String)
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    # GK / DEF / MID / FWD
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String, nullable=True)

    # Estadísticas por 90 minutos (actualizadas vía ETL)
    overall_rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    goals_per_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_per_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    assists_per_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    yellow_cards_per_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    red_cards_per_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_value_eur: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Estado actual
    is_injured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    yellow_cards_season: Mapped[int] = mapped_column(Integer, default=0)

    # Sincronización
    data_source: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="players")

    __table_args__ = (
        Index("idx_players_team", "team_id"),
    )


# ---------------------------------------------------------------------------
# Transferencias
# ---------------------------------------------------------------------------

class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    from_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    to_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    transfer_date: Mapped[date] = mapped_column(Date)
    transfer_type: Mapped[str] = mapped_column(String)  # permanent|loan|free|end_loan
    fee_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String, nullable=True)
    data_sync_status: Mapped[str] = mapped_column(String, default="pending")


# ---------------------------------------------------------------------------
# Partidos (expandido con season y competition context)
# ---------------------------------------------------------------------------

class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id"), nullable=True)
    match_date: Mapped[date] = mapped_column(Date)
    home_team: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)  # medio tiempo
    away_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_type: Mapped[str] = mapped_column(String, default="friendly")
    neutral: Mapped[bool] = mapped_column(Boolean, default=False)
    matchday: Mapped[int | None] = mapped_column(Integer, nullable=True)    # jornada
    round_name: Mapped[str | None] = mapped_column(String, nullable=True)   # "Quarterfinal"
    venue: Mapped[str | None] = mapped_column(String, nullable=True)
    attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # xG post-partido (de fuente externa si disponible)
    home_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_xg: Mapped[float | None] = mapped_column(Float, nullable=True)

    season: Mapped["Season | None"] = relationship(back_populates="matches")
    events: Mapped[list["MatchEvent"]] = relationship(back_populates="match")
    lineups: Mapped[list["Lineup"]] = relationship(back_populates="match")

    __table_args__ = (
        Index("idx_matches_date", "match_date"),
        Index("idx_matches_season", "season_id"),
    )


# ---------------------------------------------------------------------------
# Eventos de partido
# ---------------------------------------------------------------------------

class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    assist_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    # goal|yellow_card|red_card|second_yellow|substitution|penalty_goal|own_goal
    extra: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    match: Mapped["Match"] = relationship(back_populates="events")

    __table_args__ = (
        Index("idx_events_match", "match_id"),
        Index("idx_events_player", "player_id"),
    )


# ---------------------------------------------------------------------------
# Alineaciones
# ---------------------------------------------------------------------------

class Lineup(Base):
    __tablename__ = "lineups"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    formation: Mapped[str | None] = mapped_column(String, nullable=True)  # "4-3-3"
    coach: Mapped[str | None] = mapped_column(String, nullable=True)

    match: Mapped["Match"] = relationship(back_populates="lineups")
    players: Mapped[list["LineupPlayer"]] = relationship(back_populates="lineup")


class LineupPlayer(Base):
    __tablename__ = "lineup_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    lineup_id: Mapped[int] = mapped_column(ForeignKey("lineups.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    is_starter: Mapped[bool] = mapped_column(Boolean, default=True)
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_played: Mapped[str | None] = mapped_column(String, nullable=True)
    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # nota de partido (0-10)

    lineup: Mapped["Lineup"] = relationship(back_populates="players")


# ---------------------------------------------------------------------------
# Lesiones
# ---------------------------------------------------------------------------

class Injury(Base):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    injury_date: Mapped[date] = mapped_column(Date)
    expected_return: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_return: Mapped[date | None] = mapped_column(Date, nullable=True)
    injury_type: Mapped[str | None] = mapped_column(String, nullable=True)  # "hamstring", "knee"
    severity: Mapped[str] = mapped_column(String, default="moderate")  # minor|moderate|severe
    performance_impact: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1 reducción del rendimiento
    data_source: Mapped[str | None] = mapped_column(String, nullable=True)
    data_sync_status: Mapped[str] = mapped_column(String, default="pending")

    __table_args__ = (
        Index("idx_injuries_player", "player_id"),
    )


# ---------------------------------------------------------------------------
# Trabajos de simulación asíncronos
# ---------------------------------------------------------------------------

class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String, default="queued")
    # queued|running|completed|failed

    competition_id: Mapped[str] = mapped_column(String)   # slug de la competición
    n_sims: Mapped[int] = mapped_column(Integer)
    model_name: Mapped[str] = mapped_column(String, default="hybrid")
    config: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    # Resultado serializado como JSON (evita tabla extra para resultados pequeños)
    result_json: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Métricas de ejecución
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("idx_sim_jobs_status", "status"),
        Index("idx_sim_jobs_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# Tablas existentes (sin cambios — compatibilidad hacia atrás)
# ---------------------------------------------------------------------------

class EloHistory(Base):
    __tablename__ = "elo_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    as_of: Mapped[date] = mapped_column(Date)
    rating: Mapped[float] = mapped_column(Float)
    attack: Mapped[float] = mapped_column(Float)
    defense: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        Index("idx_elo_team_date", "team_id", "as_of"),
    )


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
    """Tabla original de simulaciones (mantenida para compatibilidad)."""
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

    __table_args__ = (
        Index("idx_pred_match", "match_id"),
    )


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
    competition_id: Mapped[str | None] = mapped_column(String, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    log_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_err: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)
