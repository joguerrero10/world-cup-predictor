"""
Tests unitarios para la capa de proveedores ETL.

No realizan llamadas reales a APIs externas — todo está mockeado.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from etl.providers.base import MatchData, TeamData, PlayerData, StandingData
from etl.providers.football_data_org import FootballDataProvider
from etl.providers.local_csv import LocalCsvProvider
from etl.providers.world_bank import WorldBankProvider


# ---------------------------------------------------------------------------
# football_data_org
# ---------------------------------------------------------------------------

class TestFootballDataProvider:
    def setup_method(self):
        self.provider = FootballDataProvider(api_key="test-key-123")

    def test_is_available_with_key(self):
        assert self.provider.is_available() is True

    def test_is_not_available_without_key(self):
        p = FootballDataProvider(api_key="")
        assert p.is_available() is False

    def test_fetch_matches_unknown_competition(self):
        result = self.provider.fetch_matches("unknown_league")
        assert result == []

    @patch("etl.providers.football_data_org.requests.Session.get")
    def test_fetch_matches_parses_correctly(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "matches": [
                {
                    "id": 1234,
                    "utcDate": "2024-10-05T14:00:00Z",
                    "status": "FINISHED",
                    "stage": "REGULAR_SEASON",
                    "matchday": 7,
                    "homeTeam": {"name": "Manchester City FC"},
                    "awayTeam": {"name": "Arsenal FC"},
                    "score": {
                        "fullTime": {"home": 2, "away": 1},
                        "halfTime": {"home": 1, "away": 0},
                    },
                }
            ]
        }
        mock_get.return_value = mock_resp

        results = self.provider.fetch_matches("premier_league")
        assert len(results) == 1
        m = results[0]
        assert m.home_team == "Manchester City FC"
        assert m.away_team == "Arsenal FC"
        assert m.home_goals == 2
        assert m.away_goals == 1
        assert m.date == date(2024, 10, 5)
        assert m.matchday == 7
        assert m.external_id == "1234"

    @patch("etl.providers.football_data_org.requests.Session.get")
    def test_fetch_matches_skips_no_score(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "matches": [
                {
                    "id": 9999,
                    "utcDate": "2024-12-01T15:00:00Z",
                    "status": "SCHEDULED",
                    "stage": "REGULAR_SEASON",
                    "homeTeam": {"name": "Liverpool FC"},
                    "awayTeam": {"name": "Chelsea FC"},
                    "score": {"fullTime": {"home": None, "away": None}},
                }
            ]
        }
        mock_get.return_value = mock_resp

        results = self.provider.fetch_matches("premier_league")
        assert len(results) == 0

    @patch("etl.providers.football_data_org.requests.Session.get")
    def test_fetch_standings_parses_correctly(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "season": {"startDate": "2024-08-16"},
            "standings": [
                {
                    "type": "TOTAL",
                    "table": [
                        {
                            "position": 1,
                            "team": {"name": "Manchester City FC"},
                            "playedGames": 10,
                            "won": 8,
                            "draw": 1,
                            "lost": 1,
                            "goalsFor": 25,
                            "goalsAgainst": 8,
                            "points": 25,
                        }
                    ],
                }
            ],
        }
        mock_get.return_value = mock_resp

        results = self.provider.fetch_standings("premier_league")
        assert len(results) == 1
        s = results[0]
        assert s.team_name == "Manchester City FC"
        assert s.position == 1
        assert s.points == 25
        assert s.season_year == 2024

    @patch("etl.providers.football_data_org.requests.Session.get")
    def test_rate_limit_handled(self, mock_get):
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers = {"X-RequestCounter-Reset": "1"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"matches": []}

        mock_get.side_effect = [rate_resp, ok_resp]

        with patch("time.sleep"):
            results = self.provider.fetch_matches("premier_league")
        assert results == []


# ---------------------------------------------------------------------------
# local_csv
# ---------------------------------------------------------------------------

class TestLocalCsvProvider:
    def test_is_available_when_file_exists(self, tmp_path):
        csv_file = tmp_path / "results.csv"
        csv_file.write_text(
            "date,home_team,away_team,home_score,away_score,tournament,neutral\n"
            "2024-01-15,Team A,Team B,2,1,Premier League,FALSE\n"
        )
        provider = LocalCsvProvider(results_path=csv_file)
        assert provider.is_available() is True

    def test_is_not_available_when_file_missing(self, tmp_path):
        provider = LocalCsvProvider(results_path=tmp_path / "nonexistent.csv")
        assert provider.is_available() is False

    def test_fetch_matches_parses_correctly(self, tmp_path):
        csv_file = tmp_path / "results.csv"
        csv_file.write_text(
            "date,home_team,away_team,home_score,away_score,tournament,neutral\n"
            "2024-03-10,England,France,2,0,Friendly,FALSE\n"
            "2024-03-15,Brazil,Argentina,1,1,FIFA World Cup,FALSE\n"
        )
        provider = LocalCsvProvider(results_path=csv_file)
        results = provider.fetch_matches("international")

        assert len(results) == 2
        assert results[0].home_team == "England"
        assert results[0].home_goals == 2
        assert results[0].match_type == "friendly"
        assert results[1].match_type == "world_cup_group"

    def test_fetch_matches_missing_columns(self, tmp_path):
        csv_file = tmp_path / "results.csv"
        csv_file.write_text("team1,team2,score\nA,B,2-1\n")
        provider = LocalCsvProvider(results_path=csv_file)
        results = provider.fetch_matches("test")
        assert results == []
        assert len(provider.errors) > 0

    def test_fetch_matches_season_filter(self, tmp_path):
        csv_file = tmp_path / "results.csv"
        csv_file.write_text(
            "date,home_team,away_team,home_score,away_score,tournament,neutral\n"
            "2023-05-01,A,B,1,0,Friendly,FALSE\n"
            "2024-05-01,C,D,2,1,Friendly,FALSE\n"
        )
        provider = LocalCsvProvider(results_path=csv_file)
        results = provider.fetch_matches("test", season=2024)
        assert len(results) == 1
        assert results[0].home_team == "C"


# ---------------------------------------------------------------------------
# world_bank
# ---------------------------------------------------------------------------

class TestWorldBankProvider:
    def test_is_always_available(self):
        provider = WorldBankProvider()
        assert provider.is_available() is True

    @patch("etl.providers.world_bank.requests.get")
    def test_fetch_macro_data(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"page": 1, "total": 1},
            [
                {"country": {"value": "Germany"}, "value": 48000.0},
                {"country": {"value": "France"}, "value": 42000.0},
            ],
        ]
        mock_get.return_value = mock_resp

        provider = WorldBankProvider()
        data = provider._fetch_indicator("NY.GDP.PCAP.CD")
        assert "germany" in data
        assert data["germany"] == 48000.0

    @patch("etl.providers.world_bank.requests.get")
    def test_fetch_macro_data_handles_error(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        provider = WorldBankProvider()
        data = provider._fetch_indicator("NY.GDP.PCAP.CD")
        assert data == {}
        assert len(provider.errors) > 0
