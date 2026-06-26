"""
Tests de integración para la capa de pipeline ETL.

Usa SQLite en memoria para no depender de PostgreSQL.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from etl.providers.base import MatchData, StandingData, TeamData
from etl.pipeline.validate import (
    filter_matches, filter_standings, filter_teams,
    validate_match, validate_player, validate_standing, validate_team,
)
from etl.pipeline.transform import normalize_team_name, normalize_match


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

class TestValidateMatch:
    def _base(self, **kwargs) -> MatchData:
        defaults = dict(
            date=date(2024, 5, 10),
            competition_slug="premier_league",
            home_team="Arsenal",
            away_team="Chelsea",
            home_goals=2,
            away_goals=1,
            match_type="friendly",
            status="FINISHED",
        )
        defaults.update(kwargs)
        return MatchData(**defaults)

    def test_valid_match(self):
        r = validate_match(self._base())
        assert r.valid

    def test_empty_home_team(self):
        r = validate_match(self._base(home_team=""))
        assert not r.valid

    def test_same_teams(self):
        r = validate_match(self._base(home_team="Arsenal", away_team="Arsenal"))
        assert not r.valid

    def test_negative_goals(self):
        r = validate_match(self._base(home_goals=-1))
        assert not r.valid

    def test_excessive_goals(self):
        r = validate_match(self._base(home_goals=35))
        assert not r.valid

    def test_invalid_match_type(self):
        r = validate_match(self._base(match_type="invalid_type"))
        assert not r.valid

    def test_scheduled_no_score_ok(self):
        r = validate_match(self._base(status="SCHEDULED", home_goals=None, away_goals=None))
        assert r.valid

    def test_negative_attendance(self):
        r = validate_match(self._base(attendance=-1))
        assert not r.valid

    def test_xg_out_of_range(self):
        r = validate_match(self._base(home_xg=20.0))
        assert not r.valid


class TestValidateTeam:
    def test_valid_team(self):
        r = validate_team(TeamData(name="Arsenal"))
        assert r.valid

    def test_empty_name(self):
        r = validate_team(TeamData(name=""))
        assert not r.valid

    def test_invalid_football_culture(self):
        r = validate_team(TeamData(name="X", football_culture=1.5))
        assert not r.valid

    def test_negative_gdp(self):
        r = validate_team(TeamData(name="X", gdp_per_capita=-100))
        assert not r.valid


class TestFilterMatches:
    def _match(self, home, away, d=date(2024, 1, 1), goals=(1, 0)):
        return MatchData(
            date=d,
            competition_slug="test",
            home_team=home,
            away_team=away,
            home_goals=goals[0],
            away_goals=goals[1],
            match_type="friendly",
            status="FINISHED",
        )

    def test_dedup_within_batch(self):
        m1 = self._match("A", "B")
        m2 = self._match("A", "B")  # duplicado
        valid, errors = filter_matches([m1, m2])
        assert len(valid) == 1
        assert len(errors) == 0  # duplicados no son errores, se descartan silenciosamente

    def test_invalid_removed(self):
        good = self._match("A", "B")
        bad = self._match("", "B")
        valid, errors = filter_matches([good, bad])
        assert len(valid) == 1
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

class TestNormalizeTeamName:
    def test_exact_match(self):
        assert normalize_team_name("Manchester United FC") == "Manchester United"

    def test_exact_no_change(self):
        assert normalize_team_name("Arsenal") == "Arsenal"

    def test_unknown_name_unchanged(self):
        assert normalize_team_name("FC Faraway United") == "FC Faraway United"

    def test_strip_whitespace(self):
        assert normalize_team_name("  Arsenal  ") == "Arsenal"

    def test_fc_barcelona(self):
        assert normalize_team_name("FC Barcelona") == "Barcelona"

    def test_bayern(self):
        assert normalize_team_name("FC Bayern München") == "Bayern Munich"

    def test_inter_milan(self):
        assert normalize_team_name("FC Internazionale Milano") == "Internazionale"


class TestNormalizeMatch:
    def test_normalizes_both_teams(self):
        m = MatchData(
            date=date(2024, 1, 1),
            competition_slug="ucl",
            home_team="FC Barcelona",
            away_team="FC Internazionale Milano",
            home_goals=2,
            away_goals=0,
            match_type="continental",
            status="FINISHED",
        )
        n = normalize_match(m)
        assert n.home_team == "Barcelona"
        assert n.away_team == "Internazionale"
        assert n.home_goals == 2  # datos no modificados


# ---------------------------------------------------------------------------
# Pipeline integración con SQLite (sin Docker)
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """Base de datos SQLite temporal para tests de integración."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Reimportar para que tome el nuevo DATABASE_URL
    import importlib
    import app.db.database as db_mod
    importlib.reload(db_mod)

    from app.db.database import init_db
    init_db()
    return db_mod.SessionLocal


class TestLoadLayer:
    def test_upsert_team(self, sqlite_db):
        from app.db import repositories as repo
        with sqlite_db() as db:
            team = repo.upsert_team(db, "Test FC", country="Testland")
            db.commit()
            assert team.id is not None
            assert team.name == "Test FC"

            # segunda llamada → actualización
            team2 = repo.upsert_team(db, "Test FC", country="Updated")
            db.commit()
            assert team2.id == team.id
            assert team2.country == "Updated"

    def test_match_exists_false_initially(self, sqlite_db):
        from app.db import repositories as repo
        with sqlite_db() as db:
            team_a = repo.upsert_team(db, "Team A")
            team_b = repo.upsert_team(db, "Team B")
            db.commit()
            assert not repo.match_exists(db, team_a.id, team_b.id, date(2024, 1, 1))

    def test_add_match_full_and_dedup(self, sqlite_db):
        from app.db import repositories as repo
        with sqlite_db() as db:
            ta = repo.upsert_team(db, "Alpha")
            tb = repo.upsert_team(db, "Beta")
            db.commit()

            repo.add_match_full(db, date(2024, 6, 1), ta.id, tb.id, 2, 1)
            db.commit()

            # match_exists ahora debe ser True
            assert repo.match_exists(db, ta.id, tb.id, date(2024, 6, 1))

    def test_upsert_standing(self, sqlite_db):
        from app.db import repositories as repo
        with sqlite_db() as db:
            team = repo.upsert_team(db, "Standings FC")
            db.commit()

            repo.upsert_standing(
                db, team.id, "premier_league", 2024,
                position=1, played=10, won=8, drawn=1, lost=1,
                goals_for=25, goals_against=8, points=25,
            )
            db.commit()

            standings = repo.get_standings(db, "premier_league", 2024)
            assert len(standings) == 1
            assert standings[0].points == 25
