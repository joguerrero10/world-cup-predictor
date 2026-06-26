"""
Servicio standalone de scheduler ETL.

Lanza APScheduler en modo blocking como proceso independiente.
Útil cuando NO se usa Celery Beat (despliegues más simples).

Uso:
    python -m services.scheduler.main

Con Docker:
    docker compose up scheduler

Variables de entorno:
    DATABASE_URL   — connexión PostgreSQL
    REDIS_URL      — (opcional, para coordinación multi-instancia)
    LOG_LEVEL      — INFO (default)
"""
from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler")


def _wait_for_db(retries: int = 30, delay: float = 3.0) -> None:
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


def main() -> None:
    logger.info("Iniciando ETL Scheduler standalone...")
    _wait_for_db()

    from app.db.database import init_db
    init_db()

    from etl.scheduler.apscheduler_setup import create_scheduler
    scheduler = create_scheduler(mode="blocking")

    jobs = scheduler.get_jobs()
    logger.info("Scheduler configurado con %d jobs:", len(jobs))
    for j in jobs:
        logger.info("  %-40s → %s", j.name, j.next_run_time)

    try:
        logger.info("Scheduler iniciado. Ctrl+C para detener.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler detenido por señal.")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
