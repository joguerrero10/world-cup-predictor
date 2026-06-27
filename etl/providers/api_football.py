"""
Proveedor API-Football (api-football.com / RapidAPI).

Plan gratuito: 100 requests/día.
Plan Pro: sin límite con API key de pago.

Variable de entorno: API_FOOTBALL_KEY

Endpoint base: https://v3.football.api-sports.io

Cubre:
  - Partidos (resultados + fixtures)
  - Clasificaciones
  - Jugadores y estadísticas
  - Lesiones
  - Fichajes
  - Formaciones y alineaciones
"""
from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

# Cache TTL (segundos)
_CACHE_TTL_LIVE = 3_600        # 1 hora — partidos recientes / en juego
_CACHE_TTL_HISTORICAL = 86_400  # 24 horas — temporadas pasadas

# Backoff exponencial en rate-limit
_MAX_RETRIES = 4
_BACKOFF_BASE = 65    # segundos iniciales en 429
_BACKOFF_MAX = 600    # techo: 10 minutos

BASE_URL = "https://v3.football.api-sports.io"

# IDs de liga en API-Football
LEAGUE_IDS: dict[str, int] = {
    "premier_league": 39,
    "laliga": 140,
    "bundesliga": 78,
    "serie_a": 135,
    "ligue_1": 61,
    "ucl": 2,
    "uel": 3,
    "fifa_wc_2026": 1,
    "euro_2024": 4,
    "copa_del_rey": 143,
    "fa_cup": 45,
    "dfb_pokal": 81,
    "coppa_italia": 137,
    "coupe_de_france": 66,
}

STATUS_MAP: dict[str, str] = {
    "FT": "FINISHED",
    "AET": "FINISHED",
    "PEN": "FINISHED",
    "NS": "SCHEDULED",
    "1H": "IN_PLAY",
    "HT": "IN_PLAY",
    "2H": "IN_PLAY",
    "ET": "IN_PLAY",
    "P": "IN_PLAY",
    "PST": "POSTPONED",
    "CANC": "CANCELLED",
    "ABD": "ABANDONED",
}

MATCH_TYPE_MAP: dict[str, str] = {
    "Group Stage": "world_cup_group",
    "1st Round": "world_cup_group",
    "2nd Round": "world_cup_group",
    "3rd Round": "world_cup_group",
    "Regular Season": "friendly",
    "Round of 16": "world_cup_knockout",
    "Quarter-finals": "world_cup_knockout",
    "Semi-finals": "world_cup_knockout",
    "Final": "world_cup_knockout",
    "League Phase": "continental",
    "Playoffs": "qualifier",
}

POSITION_MAP: dict[str, str] = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfielder": "MID",
    "Attacker": "FWD",
}


class APIFootballProvider(BaseProvider):
    """
    Proveedor API-Football v3.

    Respeta el rate limit del plan gratuito (100 req/día).
    En producción usar plan Pro para actualización horaria.
    """

    name = "api_football"
    _MIN_INTERVAL = 2.0     # segundos entre requests (30/min máximo)

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_rapidapi: bool = False,
        redis_url: Optional[str] = None,
    ):
        super().__init__()
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        self.use_rapidapi = use_rapidapi

        self._session = requests.Session()
        if use_rapidapi:
            self._session.headers.update({
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "v3.football.api-sports.io",
            })
            self._base_url = "https://v3.football.api-sports.io"
        else:
            self._session.headers.update({
                "x-apisports-key": self.api_key,
            })
            self._base_url = BASE_URL

        self._last_request_at: float = 0.0
        self._daily_count: int = 0
        self._redis = self._init_redis(redis_url or os.getenv("REDIS_URL", ""))

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Redis cache
    # ------------------------------------------------------------------

    @staticmethod
    def _init_redis(redis_url: str):
        if not redis_url:
            return None
        try:
            import redis as _rlib
            client = _rlib.from_url(redis_url, socket_connect_timeout=2, decode_responses=True)
            client.ping()
            return client
        except Exception as exc:
            logger.warning("[api_football] Redis no disponible (%s), cache desactivado.", exc)
            return None

    def _cache_key(self, endpoint: str, params: Optional[dict]) -> str:
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
        return f"apif:{endpoint}:{sorted_params}"

    def _cache_get(self, key: str) -> Optional[dict]:
        if self._redis is None:
            return None
        try:
            val = self._redis.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    def _cache_set(self, key: str, data: dict, ttl: int) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(key, ttl, json.dumps(data, default=str))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # HTTP con backoff exponencial + cache
    # ------------------------------------------------------------------

    def _get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        cache_ttl: int = _CACHE_TTL_LIVE,
    ) -> dict:
        cache_key = self._cache_key(endpoint, params)

        # 1. Intentar cache
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("[api_football] cache HIT: %s", cache_key)
            return cached

        # 2. Rate-limit local (intervalo mínimo entre requests)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)

        url = f"{self._base_url}/{endpoint}"
        backoff = _BACKOFF_BASE

        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.get(url, params=params, timeout=30)
                self._last_request_at = time.monotonic()
                self._daily_count += 1

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", backoff))
                    self._warn(
                        f"Rate limit (intento {attempt + 1}/{_MAX_RETRIES}). "
                        f"Esperando {wait}s..."
                    )
                    time.sleep(wait)
                    backoff = min(backoff * 2, _BACKOFF_MAX)
                    continue

                resp.raise_for_status()
                data = resp.json()

                errors = data.get("errors", [])
                if errors and errors not in ([], {}):
                    raise ProviderError(f"API error: {errors}")

                # Guardar en cache solo respuestas válidas
                self._cache_set(cache_key, data, cache_ttl)
                return data

            except ProviderError:
                raise
            except requests.Timeout:
                raise ProviderError(f"Timeout en {url}")
            except requests.ConnectionError as exc:
                raise ProviderError(f"Error de conexión: {exc}")
            except requests.HTTPError as exc:
                raise ProviderError(f"HTTP {exc.response.status_code}: {url}")

        raise ProviderError(f"Rate limit: max {_MAX_RETRIES} reintentos agotados para {url}")

    def _league_id(self, slug: str) -> Optional[int]:
        lid = LEAGUE_IDS.get(slug)
        if lid is None:
            self._warn(f"No hay league_id para '{slug}'")
        return lid

    # ------------------------------------------------------------------
    # fetch_matches
    # ------------------------------------------------------------------

    def fetch_matches(
        self,
        competition_slug: str,
        season: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[MatchData]:
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        _season = season or date.today().year
        params: dict = {
            "league": lid,
            "season": _season,
            "status": "FT",
        }
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["to"] = date_to.isoformat()

        # Datos históricos tienen TTL más largo (ya no cambian)
        is_historical = _season < date.today().year
        cache_ttl = _CACHE_TTL_HISTORICAL if is_historical else _CACHE_TTL_LIVE

        try:
            data = self._get("fixtures", params, cache_ttl=cache_ttl)
        except ProviderError as e:
            self._error(f"fetch_matches({competition_slug}, season={_season}): {e}")
            return []

        results: list[MatchData] = []
        for f in data.get("response", []):
            parsed = self._parse_fixture(f, competition_slug)
            if parsed:
                results.append(parsed)

        return results

    def fetch_upcoming_fixtures(
        self,
        competition_slug: str,
        season: Optional[int] = None,
        next_n: int = 10,
    ) -> list[MatchData]:
        """Devuelve los próximos N partidos (no jugados aún)."""
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        params = {
            "league": lid,
            "season": season or date.today().year,
            "next": next_n,
        }
        try:
            data = self._get("fixtures", params)
        except ProviderError as e:
            self._error(f"fetch_upcoming({competition_slug}): {e}")
            return []

        return [
            m for f in data.get("response", [])
            if (m := self._parse_fixture(f, competition_slug)) is not None
        ]

    # ------------------------------------------------------------------
    # fetch_teams
    # ------------------------------------------------------------------

    def fetch_teams(self, competition_slug: str, season: Optional[int] = None) -> list[TeamData]:
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        params = {
            "league": lid,
            "season": season or date.today().year,
        }
        try:
            data = self._get("teams", params)
        except ProviderError as e:
            self._error(f"fetch_teams({competition_slug}): {e}")
            return []

        result: list[TeamData] = []
        for t in data.get("response", []):
            team_info  = t.get("team", {})
            venue_info = t.get("venue", {})
            name = team_info.get("name", "").strip()
            if not name:
                continue
            result.append(TeamData(
                name=name,
                short_name=team_info.get("code"),
                country=team_info.get("country"),
                logo_url=team_info.get("logo"),
                founded_year=team_info.get("founded"),
                stadium=venue_info.get("name"),
                data_source=self.name,
            ))
        return result

    # ------------------------------------------------------------------
    # fetch_standings
    # ------------------------------------------------------------------

    def fetch_standings(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[StandingData]:
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        params = {
            "league": lid,
            "season": season or date.today().year,
        }
        try:
            data = self._get("standings", params)
        except ProviderError as e:
            self._error(f"fetch_standings({competition_slug}): {e}")
            return []

        results: list[StandingData] = []
        for block in data.get("response", []):
            league_data = block.get("league", {})
            season_year = int(str(league_data.get("season", date.today().year)))
            for group in league_data.get("standings", []):
                for row in group:
                    team_name = row.get("team", {}).get("name", "").strip()
                    if not team_name:
                        continue
                    all_ = row.get("all", {})
                    goals = all_.get("goals", {})
                    results.append(StandingData(
                        competition_slug=competition_slug,
                        season_year=season_year,
                        team_name=team_name,
                        position=row.get("rank", 0),
                        played=all_.get("played", 0),
                        won=all_.get("win", 0),
                        drawn=all_.get("draw", 0),
                        lost=all_.get("lose", 0),
                        goals_for=goals.get("for", 0),
                        goals_against=goals.get("against", 0),
                        points=row.get("points", 0),
                    ))

        return results

    # ------------------------------------------------------------------
    # fetch_players
    # ------------------------------------------------------------------

    def fetch_players(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[PlayerData]:
        """Carga jugadores con estadísticas (requiere múltiples páginas)."""
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        _season = season or date.today().year
        all_players: list[PlayerData] = []
        page = 1

        while True:
            params = {"league": lid, "season": _season, "page": page}
            try:
                data = self._get("players", params)
            except ProviderError as e:
                self._error(f"fetch_players page {page}: {e}")
                break

            response = data.get("response", [])
            if not response:
                break

            for item in response:
                parsed = self._parse_player(item)
                if parsed:
                    all_players.append(parsed)

            paging = data.get("paging", {})
            if page >= paging.get("total", 1):
                break
            page += 1

        return all_players

    # ------------------------------------------------------------------
    # fetch_injuries
    # ------------------------------------------------------------------

    def fetch_injuries(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[dict]:
        """Devuelve lista de lesiones actuales (dict raw para el ETL)."""
        lid = self._league_id(competition_slug)
        if not lid:
            return []

        params = {"league": lid, "season": season or date.today().year}
        try:
            data = self._get("injuries", params)
        except ProviderError as e:
            self._error(f"fetch_injuries({competition_slug}): {e}")
            return []

        return data.get("response", [])

    # ------------------------------------------------------------------
    # fetch_transfers
    # ------------------------------------------------------------------

    def fetch_transfers_by_team(self, team_api_id: int) -> list[dict]:
        """Devuelve transferencias de un equipo (dict raw)."""
        try:
            data = self._get("transfers", {"team": team_api_id})
            return data.get("response", [])
        except ProviderError as e:
            self._error(f"fetch_transfers({team_api_id}): {e}")
            return []

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_fixture(self, f: dict, competition_slug: str) -> Optional[MatchData]:
        fixture = f.get("fixture", {})
        score = f.get("score", {}).get("fulltime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")

        status_short = fixture.get("status", {}).get("short", "")
        is_finished = STATUS_MAP.get(status_short) == "FINISHED"

        date_str = (fixture.get("date") or "")[:10]
        try:
            match_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

        teams_data = f.get("teams", {})
        home_name = teams_data.get("home", {}).get("name", "").strip()
        away_name = teams_data.get("away", {}).get("name", "").strip()
        if not home_name or not away_name:
            return None

        league = f.get("league", {})
        round_name = league.get("round", "Regular Season")
        match_type = MATCH_TYPE_MAP.get(round_name, "friendly")

        return MatchData(
            date=match_date,
            competition_slug=competition_slug,
            home_team=home_name,
            away_team=away_name,
            home_goals=int(home_goals) if is_finished and home_goals is not None else None,
            away_goals=int(away_goals) if is_finished and away_goals is not None else None,
            match_type=match_type,
            neutral=False,
            matchday=league.get("round", "").split("-")[-1].strip()
                     if "Regular Season" in round_name else None,
            round_name=round_name,
            venue=fixture.get("venue", {}).get("name"),
            status=STATUS_MAP.get(status_short, "UNKNOWN"),
            external_id=str(fixture.get("id", "")),
        )

    def _parse_player(self, item: dict) -> Optional[PlayerData]:
        p = item.get("player", {})
        name = (p.get("name") or "").strip()
        if not name:
            return None

        stats_list = item.get("statistics", [{}])
        stats = stats_list[0] if stats_list else {}

        team_name = stats.get("team", {}).get("name", "").strip()
        position = POSITION_MAP.get(stats.get("games", {}).get("position", ""), None)

        birth_date: Optional[date] = None
        bd = p.get("birth", {}).get("date")
        if bd:
            try:
                birth_date = date.fromisoformat(str(bd)[:10])
            except ValueError:
                pass

        goals_g = stats.get("goals", {})
        shots_g = stats.get("shots", {})
        passes_g = stats.get("passes", {})
        games_g = stats.get("games", {})
        cards_g = stats.get("cards", {})

        minutes = games_g.get("minutes") or 0
        appearances = games_g.get("appearences") or 1
        per90 = minutes / 90.0 if minutes > 0 else 1.0

        # xG y rating (disponibles en el plan Pro de API-Football)
        xg_total = stats.get("goals", {}).get("expected")
        raw_rating = games_g.get("rating")

        xg_per_90: Optional[float] = None
        if xg_total is not None and per90 > 0:
            try:
                xg_per_90 = round(float(xg_total) / per90, 3)
            except (TypeError, ValueError):
                pass

        overall_rating: Optional[float] = None
        if raw_rating is not None:
            try:
                overall_rating = round(float(raw_rating), 2)
            except (TypeError, ValueError):
                pass

        return PlayerData(
            name=name,
            team_name=team_name,
            position=position,
            nationality=p.get("nationality"),
            birth_date=birth_date,
            shirt_number=p.get("id"),
            data_source=self.name,
            goals_per_90=round((goals_g.get("total") or 0) / per90, 3) if per90 > 0 else None,
            assists_per_90=round((goals_g.get("assists") or 0) / per90, 3) if per90 > 0 else None,
            xg_per_90=xg_per_90,
            minutes_played=minutes,
            yellow_cards_per_90=round((cards_g.get("yellow") or 0) / per90, 3) if per90 > 0 else None,
            red_cards_per_90=round((cards_g.get("red") or 0) / per90, 3) if per90 > 0 else None,
            overall_rating=overall_rating,
        )
