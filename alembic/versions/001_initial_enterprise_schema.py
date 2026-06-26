"""Initial enterprise schema — multicompetición platform.

Revision ID: 001_enterprise
Revises: None
Create Date: 2026-06-26

Esta migración crea todas las tablas de la plataforma enterprise.
Incluye:
  - competitions, seasons, season_teams
  - teams (clubs + selecciones unificados)
  - players con estadísticas completas
  - matches, match_events, lineups, lineup_players
  - transfers, injuries
  - standings, elo_history, fifa_rankings
  - simulation_jobs, predictions, model_metrics
  - update_logs, provider_logs
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_enterprise"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── competitions ──────────────────────────────────────────────────────────
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("competition_type", sa.String, nullable=False),
        sa.Column("tier", sa.String, nullable=False),
        sa.Column("country", sa.String, nullable=True),
        sa.Column("n_teams", sa.Integer, nullable=False),
        sa.Column("relegation_spots", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ucl_spots", sa.Integer, nullable=False, server_default="0"),
        sa.Column("uel_spots", sa.Integer, nullable=False, server_default="0"),
        sa.Column("legs", sa.Integer, nullable=False, server_default="2"),
    )
    op.create_index("ix_competitions_slug", "competitions", ["slug"], unique=True)

    # ── seasons ───────────────────────────────────────────────────────────────
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("competition_id", sa.Integer, sa.ForeignKey("competitions.id"), nullable=False),
        sa.Column("year_start", sa.Integer, nullable=False),
        sa.Column("year_end", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="upcoming"),
        sa.Column("data_sync_status", sa.String, nullable=False, server_default="pending"),
        sa.UniqueConstraint("competition_id", "year_start", name="uq_season"),
    )

    # ── teams ─────────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("short_name", sa.String(10), nullable=True),
        sa.Column("country", sa.String, nullable=True),
        sa.Column("confederation", sa.String, nullable=True),
        sa.Column("gdp_per_capita", sa.Float, nullable=True),
        sa.Column("population", sa.BigInteger, nullable=True),
        sa.Column("football_culture", sa.Float, nullable=True),
        sa.Column("avg_temp_c", sa.Float, nullable=True),
        sa.Column("is_host", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("data_source", sa.String, nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_teams_name", "teams", ["name"])

    # ── season_teams ──────────────────────────────────────────────────────────
    op.create_table(
        "season_teams",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("season_id", sa.Integer, sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("group_name", sa.String, nullable=True),
        sa.Column("final_position", sa.Integer, nullable=True),
        sa.Column("is_promoted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_relegated", sa.Boolean, nullable=False, server_default="false"),
        sa.UniqueConstraint("season_id", "team_id", name="uq_season_team"),
    )

    # ── players ───────────────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("position", sa.String, nullable=True),
        sa.Column("birth_date", sa.Date, nullable=True),
        sa.Column("nationality", sa.String, nullable=True),
        sa.Column("overall_rating", sa.Float, nullable=True),
        sa.Column("goals_per_90", sa.Float, nullable=True),
        sa.Column("xg_per_90", sa.Float, nullable=True),
        sa.Column("assists_per_90", sa.Float, nullable=True),
        sa.Column("yellow_cards_per_90", sa.Float, nullable=True),
        sa.Column("red_cards_per_90", sa.Float, nullable=True),
        sa.Column("minutes_played", sa.Integer, nullable=True),
        sa.Column("market_value_eur", sa.Float, nullable=True),
        sa.Column("is_injured", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_suspended", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("yellow_cards_season", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_source", sa.String, nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
    )
    op.create_index("idx_players_team", "players", ["team_id"])

    # ── matches ───────────────────────────────────────────────────────────────
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("season_id", sa.Integer, sa.ForeignKey("seasons.id"), nullable=True),
        sa.Column("match_date", sa.Date, nullable=False),
        sa.Column("home_team", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("away_team", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("home_goals", sa.Integer, nullable=True),
        sa.Column("away_goals", sa.Integer, nullable=True),
        sa.Column("home_goals_ht", sa.Integer, nullable=True),
        sa.Column("away_goals_ht", sa.Integer, nullable=True),
        sa.Column("match_type", sa.String, nullable=False, server_default="friendly"),
        sa.Column("neutral", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("matchday", sa.Integer, nullable=True),
        sa.Column("round_name", sa.String, nullable=True),
        sa.Column("venue", sa.String, nullable=True),
        sa.Column("attendance", sa.Integer, nullable=True),
        sa.Column("home_xg", sa.Float, nullable=True),
        sa.Column("away_xg", sa.Float, nullable=True),
    )
    op.create_index("idx_matches_date", "matches", ["match_date"])
    op.create_index("idx_matches_season", "matches", ["season_id"])
    op.create_index("idx_matches_home", "matches", ["home_team"])
    op.create_index("idx_matches_away", "matches", ["away_team"])

    # ── match_events ──────────────────────────────────────────────────────────
    op.create_table(
        "match_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=True),
        sa.Column("assist_player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=True),
        sa.Column("minute", sa.Integer, nullable=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("extra", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_events_match", "match_events", ["match_id"])
    op.create_index("idx_events_player", "match_events", ["player_id"])

    # ── lineups ───────────────────────────────────────────────────────────────
    op.create_table(
        "lineups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("formation", sa.String, nullable=True),
        sa.Column("coach", sa.String, nullable=True),
    )
    op.create_table(
        "lineup_players",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("lineup_id", sa.Integer, sa.ForeignKey("lineups.id"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("is_starter", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("shirt_number", sa.Integer, nullable=True),
        sa.Column("position_played", sa.String, nullable=True),
        sa.Column("minutes_played", sa.Integer, nullable=True),
        sa.Column("rating", sa.Float, nullable=True),
    )

    # ── transfers ─────────────────────────────────────────────────────────────
    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("from_team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("to_team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("transfer_date", sa.Date, nullable=False),
        sa.Column("transfer_type", sa.String, nullable=False),
        sa.Column("fee_eur", sa.Float, nullable=True),
        sa.Column("data_source", sa.String, nullable=True),
        sa.Column("data_sync_status", sa.String, nullable=False, server_default="pending"),
    )
    op.create_index("idx_transfers_player", "transfers", ["player_id"])
    op.create_index("idx_transfers_date", "transfers", ["transfer_date"])

    # ── injuries ──────────────────────────────────────────────────────────────
    op.create_table(
        "injuries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("injury_date", sa.Date, nullable=False),
        sa.Column("expected_return", sa.Date, nullable=True),
        sa.Column("actual_return", sa.Date, nullable=True),
        sa.Column("injury_type", sa.String, nullable=True),
        sa.Column("severity", sa.String, nullable=False, server_default="moderate"),
        sa.Column("performance_impact", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("data_source", sa.String, nullable=True),
        sa.Column("data_sync_status", sa.String, nullable=False, server_default="pending"),
    )
    op.create_index("idx_injuries_player", "injuries", ["player_id"])

    # ── standings ─────────────────────────────────────────────────────────────
    op.create_table(
        "standings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("competition_slug", sa.String, nullable=False),
        sa.Column("season_year", sa.Integer, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("played", sa.Integer, nullable=False, server_default="0"),
        sa.Column("won", sa.Integer, nullable=False, server_default="0"),
        sa.Column("drawn", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("goals_for", sa.Integer, nullable=False, server_default="0"),
        sa.Column("goals_against", sa.Integer, nullable=False, server_default="0"),
        sa.Column("points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "competition_slug", "season_year", name="uq_standing"),
    )
    op.create_index("idx_standings_comp_season", "standings", ["competition_slug", "season_year"])

    # ── elo_history ───────────────────────────────────────────────────────────
    op.create_table(
        "elo_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("rating", sa.Float, nullable=False),
        sa.Column("attack", sa.Float, nullable=False),
        sa.Column("defense", sa.Float, nullable=False),
    )
    op.create_index("idx_elo_team_date", "elo_history", ["team_id", "as_of"])

    # ── fifa_rankings ─────────────────────────────────────────────────────────
    op.create_table(
        "fifa_rankings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("points", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=True),
    )

    # ── macroeconomic_data ────────────────────────────────────────────────────
    op.create_table(
        "macroeconomic_data",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("gdp_per_capita", sa.Float, nullable=True),
        sa.Column("population", sa.BigInteger, nullable=True),
    )

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id"), nullable=True),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("p_home", sa.Float, nullable=False),
        sa.Column("p_draw", sa.Float, nullable=False),
        sa.Column("p_away", sa.Float, nullable=False),
        sa.Column("extra", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_pred_match", "predictions", ["match_id"])

    # ── simulations + tournament_results (legacy) ─────────────────────────────
    op.create_table(
        "simulations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("n_sims", sa.Integer, nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=True),
    )
    op.create_table(
        "tournament_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("simulation_id", sa.Integer, sa.ForeignKey("simulations.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("p_champion", sa.Float, nullable=False),
        sa.Column("p_finalist", sa.Float, nullable=False),
        sa.Column("p_semifinalist", sa.Float, nullable=False),
        sa.Column("p_group_qualify", sa.Float, nullable=False),
    )

    # ── simulation_jobs ───────────────────────────────────────────────────────
    op.create_table(
        "simulation_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="queued"),
        sa.Column("competition_id", sa.String, nullable=False),
        sa.Column("n_sims", sa.Integer, nullable=False),
        sa.Column("model_name", sa.String, nullable=False, server_default="hybrid"),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("result_json", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("worker_id", sa.String, nullable=True),
    )
    op.create_index("idx_sim_jobs_status", "simulation_jobs", ["status"])
    op.create_index("idx_sim_jobs_created", "simulation_jobs", ["created_at"])

    # ── model_metrics ─────────────────────────────────────────────────────────
    op.create_table(
        "model_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("evaluated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("competition_id", sa.String, nullable=True),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("brier_score", sa.Float, nullable=True),
        sa.Column("log_loss", sa.Float, nullable=True),
        sa.Column("calibration_err", sa.Float, nullable=True),
        sa.Column("roi", sa.Float, nullable=True),
    )

    # ── update_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "update_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("competition_slug", sa.String, nullable=True),
        sa.Column("data_type", sa.String, nullable=False),
        sa.Column("records_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="running"),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("providers_used", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_update_logs_started", "update_logs", ["started_at"])
    op.create_index("idx_update_logs_status", "update_logs", ["status"])

    # ── provider_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "provider_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("logged_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("provider_name", sa.String, nullable=False),
        sa.Column("competition_slug", sa.String, nullable=True),
        sa.Column("data_type", sa.String, nullable=False),
        sa.Column("records_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_valid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("idx_provider_logs_provider", "provider_logs", ["provider_name"])
    op.create_index("idx_provider_logs_logged", "provider_logs", ["logged_at"])


def downgrade() -> None:
    tables = [
        "provider_logs", "update_logs", "model_metrics", "simulation_jobs",
        "tournament_results", "simulations", "predictions", "macroeconomic_data",
        "fifa_rankings", "elo_history", "standings", "injuries", "transfers",
        "lineup_players", "lineups", "match_events", "matches", "players",
        "season_teams", "teams", "seasons", "competitions",
    ]
    for table in tables:
        op.drop_table(table)
