"""
Proveedor de datos local (CSV).

Fuente de último recurso / arranque en frío.
Compatible con el formato Kaggle "International football results 1872-present".

CSV de resultados (data/results.csv):
  date,home_team,away_team,home_score,away_score,tournament,city,country,neutral

CSV de factores (data/factors.csv):
  team,gdp_per_capita,population,fifa_points,football_culture,avg_temp_c,is_host,confederation
"""
from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from .base import BaseProvider, MatchData, StandingData, TeamData

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

TOURNAMENT_TO_MATCH_TYPE: dict[str, str] = {
    "friendly": "friendly",
    "fifa world cup": "world_cup_group",
    "world cup": "world_cup_group",
    "qualification": "qualifier",
    "qualif": "qualifier",
    "continental": "continental",
    "uefa euro": "continental",
    "copa america": "continental",
    "africa cup": "continental",
    "afc asian": "continental",
    "gold cup": "continental",
}


def _map_tournament(tournament: str) -> str:
    t = (tournament or "").lower()
    for key, mtype in TOURNAMENT_TO_MATCH_TYPE.items():
        if key in t:
            if mtype == "world_cup_group" and "qualif" in t:
                return "qualifier"
            return mtype
    return "friendly"


class LocalCsvProvider(BaseProvider):
    """
    Lee partidos y factores desde archivos CSV locales.

    El competition_slug se usa solo como prefijo para filtrar
    si el CSV tiene una columna 'competition'; si no, devuelve todo.
    """
    name = "local_csv"

    def __init__(
        self,
        results_path: Optional[Path] = None,
        factors_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.results_path = results_path or DATA_DIR / "results.csv"
        self.factors_path = factors_path or DATA_DIR / "factors.csv"

    def is_available(self) -> bool:
        return self.results_path.exists()

    def fetch_matches(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[MatchData]:
        if not self.results_path.exists():
            self._error(f"Archivo no encontrado: {self.results_path}")
            return []

        try:
            df = pd.read_csv(self.results_path)
        except Exception as exc:
            self._error(f"Error leyendo CSV: {exc}")
            return []

        required = {"date", "home_team", "away_team", "home_score", "away_score"}
        missing = required - set(df.columns)
        if missing:
            self._error(f"CSV faltan columnas: {sorted(missing)}")
            return []

        df = df.dropna(subset=["home_score", "away_score"])

        if season:
            try:
                df["year"] = pd.to_datetime(df["date"]).dt.year
                df = df[df["year"] == season]
            except Exception:
                pass

        results: list[MatchData] = []
        for _, row in df.iterrows():
            try:
                match_date = date.fromisoformat(str(row["date"])[:10])
            except (ValueError, TypeError):
                continue

            tournament = str(row.get("tournament", "")) if "tournament" in df.columns else ""
            neutral_raw = row.get("neutral", False)
            neutral = bool(neutral_raw) if not isinstance(neutral_raw, bool) else neutral_raw

            results.append(MatchData(
                date=match_date,
                competition_slug=competition_slug,
                home_team=str(row["home_team"]).strip(),
                away_team=str(row["away_team"]).strip(),
                home_goals=int(row["home_score"]),
                away_goals=int(row["away_score"]),
                match_type=_map_tournament(tournament),
                neutral=neutral,
                matchday=None,
                round_name=tournament or None,
                venue=(str(row["city"]) if "city" in df.columns else None),
                status="FINISHED",
            ))
        return results

    def fetch_teams(self, competition_slug: str) -> list[TeamData]:
        if not self.factors_path.exists():
            return []

        try:
            df = pd.read_csv(self.factors_path)
        except Exception as exc:
            self._error(f"Error leyendo factors CSV: {exc}")
            return []

        if "team" not in df.columns:
            return []

        results: list[TeamData] = []
        for _, row in df.iterrows():
            name = str(row.get("team", "")).strip()
            if not name:
                continue
            results.append(TeamData(
                name=name,
                confederation=str(row.get("confederation", "")) or None,
                gdp_per_capita=_float_or_none(row.get("gdp_per_capita")),
                population=_int_or_none(row.get("population")),
                football_culture=_float_or_none(row.get("football_culture")),
                avg_temp_c=_float_or_none(row.get("avg_temp_c")),
                is_host=bool(row.get("is_host", False)),
                data_source=self.name,
            ))
        return results

    def fetch_standings(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[StandingData]:
        return []


def _float_or_none(val) -> Optional[float]:
    try:
        return float(val) if val is not None and str(val).strip() not in ("", "nan") else None
    except (ValueError, TypeError):
        return None


def _int_or_none(val) -> Optional[int]:
    try:
        return int(float(val)) if val is not None and str(val).strip() not in ("", "nan") else None
    except (ValueError, TypeError):
        return None
