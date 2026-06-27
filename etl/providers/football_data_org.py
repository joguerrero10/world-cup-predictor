"""
Proveedor football-data.org (v4).

Tier gratuito: 10 req/min, acceso a PL, BL1, PD, SA, FL1, CL, WC, EC.
API key gratuita en https://www.football-data.org/client/register

Variable de entorno requerida: FOOTBALL_DATA_API_KEY
"""
from __future__ import annotations

import os
import time
from datetime import date
from typing import Optional

import requests

from .base import (
    BaseProvider,
    MatchData,
    PlayerData,
    ProviderError,
    StandingData,
    TeamData,
)

BASE_URL = "https://api.football-data.org/v4"

# Slugs internos → códigos football-data.org
COMPETITION_CODES: dict[str, str] = {
    "premier_league": "PL",
    "laliga": "PD",
    "bundesliga": "BL1",
    "serie_a": "SA",
    "ligue_1": "FL1",
    "ucl": "CL",
    "fifa_wc_2026": "WC",
    "euro_2024": "EC",
}

# stage de FDO → match_type interno
STAGE_TO_MATCH_TYPE: dict[str, str] = {
    "GROUP_STAGE": "world_cup_group",
    "LAST_16": "world_cup_knockout",
    "QUARTER_FINALS": "world_cup_knockout",
    "SEMI_FINALS": "world_cup_knockout",
    "THIRD_PLACE": "world_cup_knockout",
    "FINAL": "world_cup_knockout",
    "REGULAR_SEASON": "friendly",        # jornada de liga → tratamos como friendly para los modelos
    "PLAYOFFS": "qualifier",
    "QUALIFICATION_ROUNDS": "qualifier",
    "PRELIMINARY_ROUND": "qualifier",
    "ROUND_OF_16": "continental",
    "ROUND_OF_8": "continental",
    "ROUND_OF_4": "continental",
    "CHAMPIONSHIP_ROUND": "continental",
}

POSITION_MAP: dict[str, str] = {
    "Goalkeeper": "GK",
    "Defence": "DEF",
    "Defender": "DEF",
    "Midfield": "MID",
    "Midfielder": "MID",
    "Offence": "FWD",
    "Forward": "FWD",
    "Attacker": "FWD",
}


class FootballDataProvider(BaseProvider):
    """
    Proveedor football-data.org.

    Respeta el rate limit del tier gratuito (10 req/min).
    En caso de 429 espera automáticamente antes de reintentar.
    """
    name = "football_data_org"
    _MIN_INTERVAL = 6.2  # segundos entre requests (≈9.6 req/min, con margen)

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__()
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({
            "X-Auth-Token": self.api_key,
        })
        self._last_request_at: float = 0.0

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)

        url = f"{BASE_URL}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=30)
            self._last_request_at = time.monotonic()

            if resp.status_code == 429:
                wait = int(resp.headers.get("X-RequestCounter-Reset", 65))
                self._warn(f"Rate-limited, esperando {wait}s")
                time.sleep(wait)
                resp = self._session.get(url, params=params, timeout=30)
                self._last_request_at = time.monotonic()

            if resp.status_code == 403:
                raise ProviderError(
                    f"Acceso denegado (tier insuficiente o key inválida): {path}"
                )

            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise ProviderError(f"Timeout en {url}")
        except requests.ConnectionError as exc:
            raise ProviderError(f"Error de conexión en {url}: {exc}") from exc
        except requests.HTTPError as exc:
            raise ProviderError(f"HTTP {exc.response.status_code} en {url}") from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_matches(
        self,
        competition_slug: str,
        season: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[MatchData]:
        code = COMPETITION_CODES.get(competition_slug)
        if not code:
            self._warn(f"Sin código para competición '{competition_slug}'")
            return []

        params: dict = {"status": "FINISHED"}
        if season:
            params["season"] = season
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()

        try:
            data = self._get(f"/competitions/{code}/matches", params)
        except ProviderError as exc:
            self._error(f"fetch_matches({competition_slug}): {exc}")
            return []

        results: list[MatchData] = []
        for m in data.get("matches", []):
            parsed = self._parse_match(m, competition_slug)
            if parsed:
                results.append(parsed)

        return results

    def fetch_teams(self, competition_slug: str) -> list[TeamData]:
        code = COMPETITION_CODES.get(competition_slug)
        if not code:
            return []

        try:
            data = self._get(f"/competitions/{code}/teams")
        except ProviderError as exc:
            self._error(f"fetch_teams({competition_slug}): {exc}")
            return []

        results: list[TeamData] = []
        for t in data.get("teams", []):
            name = t.get("name", "").strip()
            if not name:
                continue
            results.append(TeamData(
                name=name,
                country=t.get("area", {}).get("name"),
                short_name=t.get("shortName") or t.get("tla"),
                data_source=self.name,
            ))
        return results

    def fetch_players(self, competition_slug: str) -> list[PlayerData]:
        code = COMPETITION_CODES.get(competition_slug)
        if not code:
            return []

        try:
            data = self._get(f"/competitions/{code}/teams")
        except ProviderError as exc:
            self._error(f"fetch_players({competition_slug}): {exc}")
            return []

        results: list[PlayerData] = []
        for t in data.get("teams", []):
            team_name = t.get("name", "").strip()
            for p in t.get("squad", []):
                player = self._parse_player(p, team_name)
                if player:
                    results.append(player)
        return results

    def fetch_standings(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[StandingData]:
        code = COMPETITION_CODES.get(competition_slug)
        if not code:
            return []

        params: dict = {}
        if season:
            params["season"] = season

        try:
            data = self._get(f"/competitions/{code}/standings", params)
        except ProviderError as exc:
            self._error(f"fetch_standings({competition_slug}): {exc}")
            return []

        season_start = data.get("season", {}).get("startDate", "2024-01-01")
        try:
            season_year = int(str(season_start)[:4])
        except (ValueError, TypeError):
            season_year = 2024

        results: list[StandingData] = []
        for block in data.get("standings", []):
            if block.get("type") != "TOTAL":
                continue
            for row in block.get("table", []):
                team_name = row.get("team", {}).get("name", "").strip()
                if not team_name:
                    continue
                results.append(StandingData(
                    competition_slug=competition_slug,
                    season_year=season_year,
                    team_name=team_name,
                    position=row.get("position", 0),
                    played=row.get("playedGames", 0),
                    won=row.get("won", 0),
                    drawn=row.get("draw", 0),
                    lost=row.get("lost", 0),
                    goals_for=row.get("goalsFor", 0),
                    goals_against=row.get("goalsAgainst", 0),
                    points=row.get("points", 0),
                ))
        return results

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_match(self, m: dict, competition_slug: str) -> Optional[MatchData]:
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        home_goals = ft.get("home")
        away_goals = ft.get("away")

        if home_goals is None or away_goals is None:
            return None

        date_str = (m.get("utcDate") or "")[:10]
        try:
            match_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

        home_name = (m.get("homeTeam") or {}).get("name", "").strip()
        away_name = (m.get("awayTeam") or {}).get("name", "").strip()
        if not home_name or not away_name:
            return None

        stage = m.get("stage", "REGULAR_SEASON") or "REGULAR_SEASON"
        match_type = STAGE_TO_MATCH_TYPE.get(stage, "friendly")

        return MatchData(
            date=match_date,
            competition_slug=competition_slug,
            home_team=home_name,
            away_team=away_name,
            home_goals=int(home_goals),
            away_goals=int(away_goals),
            match_type=match_type,
            neutral=False,
            matchday=m.get("matchday"),
            round_name=stage,
            venue=m.get("venue"),
            status=m.get("status", "FINISHED"),
            external_id=str(m.get("id", "")),
        )

    def _parse_player(self, p: dict, team_name: str) -> Optional[PlayerData]:
        name = (p.get("name") or "").strip()
        if not name:
            return None

        birth_date: Optional[date] = None
        bd_str = p.get("dateOfBirth")
        if bd_str:
            try:
                birth_date = date.fromisoformat(str(bd_str)[:10])
            except (ValueError, TypeError):
                pass

        raw_pos = p.get("position") or ""
        position = POSITION_MAP.get(raw_pos, raw_pos[:3].upper() if raw_pos else None)

        return PlayerData(
            name=name,
            team_name=team_name,
            position=position,
            nationality=p.get("nationality"),
            birth_date=birth_date,
            shirt_number=p.get("shirtNumber"),
            data_source=self.name,
        )
