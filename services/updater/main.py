"""
Servicio standalone de actualización ETL.

Ejecuta la sincronización de datos para todas las competiciones configuradas.
Puede lanzarse como:

    python -m services.updater.main                 # sync completo
    python -m services.updater.main --competition premier_league
    python -m services.updater.main --types matches standings
    python -m services.updater.main --season 2025

En Docker Compose se ejecuta como servicio independiente o como job puntual.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("updater")

COMPETITIONS = [
    "premier_league",
    "laliga",
    "bundesliga",
    "serie_a",
    "ligue_1",
    "ucl",
    "fifa_wc_2026",
]

DATA_TYPES_ALL = ["teams", "matches", "standings", "players"]


def _wait_for_db(retries: int = 30, delay: float = 3.0) -> None:
    """Espera a que la base de datos esté lista."""
    from app.db.database import engine
    from sqlalchemy import text

    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Conexión a BD establecida.")
            return
        except Exception as e:
            logger.warning("BD no disponible (intento %d/%d): %s", attempt + 1, retries, e)
            time.sleep(delay)

    logger.error("No se pudo conectar a la BD tras %d intentos.", retries)
    sys.exit(1)


def run_sync(
    competitions: list[str],
    data_types: list[str],
    season: int | None,
    force_retrain: bool,
) -> None:
    from app.db.database import init_db
    from etl.pipeline.orchestrator import ETLPipeline

    _wait_for_db()
    init_db()

    pipeline = ETLPipeline()
    t0 = time.monotonic()

    total_inserted = 0
    total_updated = 0
    failed = []

    for comp in competitions:
        logger.info("Sincronizando: %s | tipos: %s", comp, data_types)
        try:
            reports = pipeline.sync_competition(
                competition_slug=comp,
                data_types=data_types,
                season=season,
                force_retrain=force_retrain,
            )
            for r in reports:
                if r.status != "completed":
                    logger.warning("[%s/%s] status=%s errors=%s", comp, r.data_type, r.status, r.errors[:3])
                else:
                    logger.info(
                        "[%s/%s] fetched=%d inserted=%d updated=%d skipped=%d (%.1fs)",
                        comp, r.data_type,
                        r.records_fetched, r.records_inserted,
                        r.records_updated, r.records_skipped,
                        r.duration,
                    )
                total_inserted += r.records_inserted
                total_updated += r.records_updated
        except Exception as exc:
            logger.exception("Error en competición %s: %s", comp, exc)
            failed.append(comp)

    elapsed = time.monotonic() - t0
    logger.info(
        "Sync completado en %.1fs — inserted=%d updated=%d failed=%s",
        elapsed, total_inserted, total_updated, failed or "ninguno",
    )

    if failed:
        sys.exit(1)


def run_macro_sync() -> None:
    """Actualiza datos macroeconómicos del World Bank."""
    from app.db.database import init_db
    from etl.pipeline.orchestrator import ETLPipeline

    _wait_for_db()
    init_db()

    pipeline = ETLPipeline()
    report = pipeline.sync_macro()
    logger.info(
        "Macro sync: status=%s updated=%d",
        report.status, report.records_updated,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL Updater — World Cup Predictor AI")
    parser.add_argument(
        "--competition", "-c",
        nargs="+",
        default=None,
        help="Competiciones a sincronizar (ej: premier_league ucl). Default: todas.",
    )
    parser.add_argument(
        "--types", "-t",
        nargs="+",
        default=["teams", "matches", "standings"],
        choices=DATA_TYPES_ALL,
        help="Tipos de datos a sincronizar.",
    )
    parser.add_argument(
        "--season", "-s",
        type=int,
        default=None,
        help="Año de inicio de temporada (ej: 2024). Default: temporada actual.",
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Forzar reentrenamiento de modelos tras la sincronización.",
    )
    parser.add_argument(
        "--macro",
        action="store_true",
        help="Solo sincronizar datos macroeconómicos del World Bank.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sincronizar todos los tipos de datos (teams, matches, standings, players).",
    )

    args = parser.parse_args()

    if args.macro:
        run_macro_sync()
        return

    competitions = args.competition or COMPETITIONS
    data_types = DATA_TYPES_ALL if args.all else args.types

    logger.info(
        "Iniciando ETL Updater — competitions=%s types=%s season=%s",
        competitions, data_types, args.season or "auto",
    )

    run_sync(
        competitions=competitions,
        data_types=data_types,
        season=args.season,
        force_retrain=args.retrain,
    )


if __name__ == "__main__":
    main()
