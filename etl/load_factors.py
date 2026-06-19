"""
ETL: load Klement socio-economic factors per country into the database.

Expected CSV columns (cabeceras exactas):
    team, gdp_per_capita, population, fifa_points,
    football_culture, avg_temp_c, is_host, confederation

  - team             : nombre EXACTO como aparece en la tabla teams (igual que en results.csv)
  - gdp_per_capita   : PIB per cápita en USD (fuente real: Banco Mundial)
  - population       : población total (fuente real: Banco Mundial / ONU)
  - fifa_points      : puntos del ranking FIFA oficial
  - football_culture : valor SUBJETIVO 0..1 que tú eliges (importancia del fútbol)
  - avg_temp_c       : temperatura media anual del país en °C (opcional)
  - is_host          : true/false si es país anfitrión (opcional, por defecto false)
  - confederation    : UEFA / CONMEBOL / CAF / AFC / CONCACAF / OFC (opcional)

Este script NO trae ni inventa datos: apúntalo a un CSV que tú rellenes con
fuentes reales:
    python -m etl.load_factors --csv factors.csv
"""
from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from app.db.database import SessionLocal, init_db
from app.db import repositories as repo

REQUIRED = {"team", "gdp_per_capita", "population"}


def _as_bool(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "si", "sí", "y"}


def load(csv_path: str) -> dict:
    df = pd.read_csv(csv_path, na_values=["", " ", "NA", "N/A", "nan", "None"])
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    df = df.dropna(subset=["team", "gdp_per_capita", "population"])

    init_db()
    updated = 0
    today = date.today()
    with SessionLocal() as db:
        for _, row in df.iterrows():
            fields = {
                "gdp_per_capita": float(row["gdp_per_capita"]),
                "population": int(row["population"]),
            }
            if "football_culture" in df.columns and pd.notna(row.get("football_culture")):
                fields["football_culture"] = float(row["football_culture"])
            if "avg_temp_c" in df.columns and pd.notna(row.get("avg_temp_c")):
                fields["avg_temp_c"] = float(row["avg_temp_c"])
            if "is_host" in df.columns and pd.notna(row.get("is_host")):
                fields["is_host"] = _as_bool(row["is_host"])
            if "confederation" in df.columns and pd.notna(row.get("confederation")):
                fields["confederation"] = str(row["confederation"]).strip()

            team = repo.upsert_team(db, str(row["team"]).strip(), **fields)
            # FIFA points are optional: only stored if provided (else Klement uses Elo)
            if "fifa_points" in df.columns and pd.notna(row.get("fifa_points")):
                repo.save_fifa_points(db, team.id, today, float(row["fifa_points"]))
            updated += 1
        db.commit()
    return {"teams_updated": updated}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Ruta al CSV de factores")
    args = ap.parse_args()
    print(load(args.csv))
