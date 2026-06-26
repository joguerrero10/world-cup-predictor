"""
Proveedor World Bank (API pública, sin clave).

Endpoints:
  GDP per cápita: NY.GDP.PCAP.CD
  Población:      SP.POP.TOTL

Refactored desde etl/fetch_factors.py para seguir la interfaz BaseProvider.
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Optional

import requests

from .base import BaseProvider, MatchData, ProviderError, StandingData, TeamData

logger = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2/country/all/indicator"
GDP_INDICATOR = "NY.GDP.PCAP.CD"
POP_INDICATOR = "SP.POP.TOTL"

# Alias de nombres de equipo → nombre de país ISO (World Bank)
TEAM_TO_COUNTRY: dict[str, str] = {
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
    "United States": "United States",
    "USA": "United States",
    "South Korea": "Korea, Rep.",
    "North Korea": "Korea, Dem. People's Rep.",
    "Iran": "Iran, Islamic Rep.",
    "DR Congo": "Congo, Dem. Rep.",
    "Cape Verde": "Cabo Verde",
    "Ivory Coast": "Cote d'Ivoire",
    "Czech Republic": "Czechia",
    "Russia": "Russian Federation",
    "Syria": "Syrian Arab Republic",
    "Venezuela": "Venezuela, RB",
    "Egypt": "Egypt, Arab Rep.",
    "Yemen": "Yemen, Rep.",
    "Slovakia": "Slovak Republic",
    "Bolivia": "Bolivia",
    "Laos": "Lao PDR",
    "Vietnam": "Viet Nam",
    "Kosovo": "Kosovo",
    "Trinidad and Tobago": "Trinidad and Tobago",
}


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return s


class WorldBankProvider(BaseProvider):
    """
    Obtiene PIB per cápita y población del Banco Mundial.

    Se usa como complemento del proveedor principal para enriquecer
    los factores Klement de los equipos.
    """
    name = "world_bank"

    def is_available(self) -> bool:
        return True  # API pública, siempre disponible

    def fetch_matches(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[MatchData]:
        return []

    def fetch_teams(self, competition_slug: str) -> list[TeamData]:
        return []

    def fetch_standings(
        self,
        competition_slug: str,
        season: Optional[int] = None,
    ) -> list[StandingData]:
        return []

    # ------------------------------------------------------------------
    # API pública específica de este proveedor
    # ------------------------------------------------------------------

    def fetch_macro_data(self) -> dict[str, dict]:
        """
        Devuelve {country_name_normalizado: {gdp_per_capita, population}}.

        Llama dos veces a World Bank (GDP + POP) y fusiona los resultados.
        """
        gdp = self._fetch_indicator(GDP_INDICATOR)
        pop = self._fetch_indicator(POP_INDICATOR)

        merged: dict[str, dict] = {}
        all_countries = set(gdp) | set(pop)
        for country in all_countries:
            merged[country] = {
                "gdp_per_capita": gdp.get(country),
                "population": pop.get(country),
            }
        return merged

    def enrich_team(self, team_name: str, macro_data: dict[str, dict]) -> TeamData:
        """Devuelve un TeamData enriquecido con datos macro para un equipo."""
        country_key = TEAM_TO_COUNTRY.get(team_name, team_name)
        norm_key = _normalize(country_key)

        record = macro_data.get(norm_key, {})
        return TeamData(
            name=team_name,
            gdp_per_capita=record.get("gdp_per_capita"),
            population=record.get("population"),
            data_source=self.name,
        )

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _fetch_indicator(self, indicator: str) -> dict[str, Optional[float]]:
        """Llama a World Bank y devuelve {country_norm: valor_más_reciente}."""
        url = f"{WB_BASE}/{indicator}"
        params = {"format": "json", "per_page": "20000", "mrv": "1"}
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            self._error(f"World Bank {indicator}: {exc}")
            return {}

        if not isinstance(payload, list) or len(payload) < 2:
            self._error(f"Respuesta inesperada de World Bank para {indicator}")
            return {}

        result: dict[str, Optional[float]] = {}
        for entry in payload[1] or []:
            country_name = (entry.get("country") or {}).get("value", "")
            value = entry.get("value")
            if country_name:
                result[_normalize(country_name)] = float(value) if value is not None else None
        return result
