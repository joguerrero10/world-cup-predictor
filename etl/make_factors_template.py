"""
Generate an EMPTY factors template CSV listing every team already in the database
(loaded from results.csv). You fill in the numeric columns with REAL data from
sources like the World Bank (GDP, population) and the official FIFA ranking.

    python -m etl.make_factors_template --out factors_template.csv

Then fill it and load it:
    python -m etl.load_factors --csv factors_template.csv

The numeric columns are left blank on purpose — no values are invented.
"""
from __future__ import annotations

import argparse
import csv

from app.db.database import SessionLocal
from app.db import repositories as repo

COLUMNS = ["team", "gdp_per_capita", "population", "fifa_points",
           "football_culture", "avg_temp_c", "is_host", "confederation"]


def make_template(out_path: str) -> dict:
    with SessionLocal() as db:
        teams = [t.name for t in repo.list_teams(db)]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for name in teams:
            # team name pre-filled; every other column blank for you to complete
            w.writerow([name, "", "", "", "", "", "", ""])
    return {"teams": len(teams), "file": out_path}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="factors_template.csv", help="Ruta de salida")
    args = ap.parse_args()
    print(make_template(args.out))
