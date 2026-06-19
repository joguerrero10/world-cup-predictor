"""
Auto-llena el CSV de factores Klement desde FUENTES REALES y públicas:

  - PIB per cápita  (indicador NY.GDP.PCAP.CD) y
  - población total (indicador SP.POP.TOTL)
    -> descargados de la API del Banco Mundial (gratis, sin clave).

  - puntos FIFA + confederación
    -> de un CSV del ranking FIFA que descargas de Kaggle
       (cashncarry/fifaworldranking): columnas country_full, total_points,
       confederation, rank_date.

Uso (en TU máquina, que sí tiene internet abierto):
    python -m etl.fetch_factors --out factors.csv
    python -m etl.fetch_factors --out factors.csv --fifa-csv fifa_ranking.csv

El PIB y la población vienen directos del Banco Mundial; no se inventa nada. Los
equipos que el Banco Mundial no lista con el mismo nombre quedan con esos campos
en blanco para que los completes. football_culture, avg_temp_c e is_host se dejan
para que tú los pongas (el primero es subjetivo).
"""
from __future__ import annotations

import argparse
import csv
import unicodedata

import requests

from app.db.database import SessionLocal
from app.db import repositories as repo

WB_URL = "https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&mrnev=1&per_page=500"
GDP_IND = "NY.GDP.PCAP.CD"
POP_IND = "SP.POP.TOTL"

COLUMNS = ["team", "gdp_per_capita", "population", "fifa_points",
           "football_culture", "avg_temp_c", "is_host", "confederation"]


def _norm(s: str) -> str:
    """lowercase, strip accents and punctuation for fuzzy matching."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum() or c == " ").strip()


# football team name (normalised) -> World Bank country name (normalised)
ALIASES = {
    "usa": "united states", "united states": "united states",
    "south korea": "korea rep", "korea republic": "korea rep",
    "north korea": "korea dem peoples rep",
    "iran": "iran islamic rep", "ir iran": "iran islamic rep",
    "russia": "russian federation",
    "egypt": "egypt arab rep",
    "venezuela": "venezuela rb",
    "ivory coast": "cote divoire",
    "dr congo": "congo dem rep", "congo dr": "congo dem rep",
    "congo": "congo rep",
    "syria": "syrian arab republic",
    "slovakia": "slovak republic",
    "czech republic": "czechia", "czechia": "czechia",
    "turkey": "turkiye", "turkiye": "turkiye",
    "cape verde": "cabo verde",
    "gambia": "gambia the",
    "bahamas": "bahamas the",
    "brunei": "brunei darussalam",
    "laos": "lao pdr",
    "kyrgyzstan": "kyrgyz republic",
    "vietnam": "viet nam",
    "hong kong": "hong kong sar china",
    "macau": "macao sar china", "macao": "macao sar china",
    "st kitts and nevis": "st kitts and nevis",
    "st lucia": "st lucia",
    "st vincent and the grenadines": "st vincent and the grenadines",
    "swaziland": "eswatini",
}


def _parse_wb(payload: list) -> dict[str, float]:
    """Parse a World Bank indicator JSON response -> {normalised country: value}."""
    out: dict[str, float] = {}
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return out
    for row in payload[1]:
        val = row.get("value")
        name = (row.get("country") or {}).get("value")
        if val is not None and name:
            out[_norm(name)] = float(val)
    return out


def fetch_worldbank(indicator: str) -> dict[str, float]:
    r = requests.get(WB_URL.format(ind=indicator), timeout=90)
    r.raise_for_status()
    return _parse_wb(r.json())


def _lookup(team: str, wb: dict[str, float]) -> float | None:
    n = _norm(team)
    if n in wb:
        return wb[n]
    alias = ALIASES.get(n)
    if alias and alias in wb:
        return wb[alias]
    return None


def merge_fifa(path: str) -> dict[str, tuple[float, str]]:
    """Return {normalised country: (latest total_points, confederation)}."""
    import pandas as pd
    df = pd.read_csv(path)
    needed = {"country_full", "total_points"}
    if not needed <= set(df.columns):
        raise ValueError(f"FIFA CSV needs columns {needed}; has {list(df.columns)}")
    if "rank_date" in df.columns:
        df = df.sort_values("rank_date").groupby("country_full", as_index=False).last()
    out: dict[str, tuple[float, str]] = {}
    for _, row in df.iterrows():
        conf = str(row["confederation"]) if "confederation" in df.columns else ""
        out[_norm(row["country_full"])] = (float(row["total_points"]), conf)
    return out


def build(out_path: str, fifa_csv: str | None = None) -> dict:
    with SessionLocal() as db:
        teams = [t.name for t in repo.list_teams(db)]
    if not teams:
        raise RuntimeError("No teams in DB. Load results.csv first (etl.load_results).")

    gdp = fetch_worldbank(GDP_IND)
    pop = fetch_worldbank(POP_IND)
    fifa = merge_fifa(fifa_csv) if fifa_csv else {}

    filled_gdp = filled_fifa = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for name in teams:
            g = _lookup(name, gdp)
            p = _lookup(name, pop)
            fpts, conf = "", ""
            n = _norm(name)
            if n in fifa:
                fpts, conf = fifa[n]
            elif ALIASES.get(n) in fifa:
                fpts, conf = fifa[ALIASES[n]]
            if g is not None:
                filled_gdp += 1
            if fpts != "":
                filled_fifa += 1
            w.writerow([name,
                        "" if g is None else round(g, 2),
                        "" if p is None else int(p),
                        fpts, "", "", "", conf])
    return {"teams": len(teams), "gdp_population_filled": filled_gdp,
            "fifa_points_filled": filled_fifa, "file": out_path}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="factors.csv")
    ap.add_argument("--fifa-csv", default=None,
                    help="CSV del ranking FIFA (Kaggle cashncarry/fifaworldranking)")
    args = ap.parse_args()
    print(build(args.out, args.fifa_csv))
