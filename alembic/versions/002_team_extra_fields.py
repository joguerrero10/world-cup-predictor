"""Add logo_url, founded_year, stadium, market_value_eur to teams table.

Revision ID: 002_team_extra_fields
Revises: 001_enterprise
Create Date: 2026-06-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_team_extra_fields"
down_revision = "001_enterprise"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Usar batch mode para compatibilidad con SQLite en tests
    with op.batch_alter_table("teams") as batch:
        batch.add_column(sa.Column("logo_url", sa.Text, nullable=True))
        batch.add_column(sa.Column("founded_year", sa.Integer, nullable=True))
        batch.add_column(sa.Column("stadium", sa.String(200), nullable=True))
        batch.add_column(sa.Column("market_value_eur", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch:
        batch.drop_column("market_value_eur")
        batch.drop_column("stadium")
        batch.drop_column("founded_year")
        batch.drop_column("logo_url")
