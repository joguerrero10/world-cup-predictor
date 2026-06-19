"""
ETL: ingest historical international match results into the database.

Expects a CSV in the widely-used public format (e.g. the Kaggle
"International football results 1872-present" dataset), with columns:
    date, home_team, away_team, home_score, away_score, tournament, neutral

This script does NOT ship or fabricate any data — point it at a real file:
    python -m etl.load_results --csv path/to/results.csv

It creates teams on the fly and inserts matches, mapping the `tournament` column
to the engine's match_type vocabulary.
"""
from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd

from app.db.database import SessionLocal, init_db
from app.db import repositories as repo

REQUIRED_COLS = {"date", "home_team", "away_team", "home_score", "away_score"}


def map_match_type(tournament: str) -> str:
    t = (tournament or "").lower()
    if "friendly" in t:
        return "friendly"
    if "qualification" in t or "qualif" in t:
        return "qualifier"
    if "fifa world cup" in t and "qualif" not in t:
        # group vs knockout can't be inferred from this column alone -> group
        return "world_cup_group"
    if any(k in t for k in ("uefa euro", "copa am", "african cup", "afc asian", "gold cup")):
        return "continental"
    return "friendly"


def load(csv_path: str, limit: int | None = None) -> dict:
    df = pd.read_csv(csv_path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    df = df.dropna(subset=["home_score", "away_score"])
    if limit:
        df = df.tail(limit)

    init_db()
    inserted = 0
    with SessionLocal() as db:
        ids = repo.team_id_map(db)
        for _, row in df.iterrows():
            for name in (row["home_team"], row["away_team"]):
                if name not in ids:
                    ids[name] = repo.upsert_team(db, name).id
            d = datetime.fromisoformat(str(row["date"])).date()
            neutral = bool(row["neutral"]) if "neutral" in df.columns else False
            mtype = map_match_type(row.get("tournament", ""))
            repo.add_match(db, d, ids[row["home_team"]], ids[row["away_team"]],
                           int(row["home_score"]), int(row["away_score"]), mtype, neutral)
            inserted += 1
        db.commit()
    return {"teams": len(ids), "matches_inserted": inserted}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to results CSV")
    ap.add_argument("--limit", type=int, default=None, help="Only load the last N rows")
    args = ap.parse_args()
    print(load(args.csv, args.limit))
