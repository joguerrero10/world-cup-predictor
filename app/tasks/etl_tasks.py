"""
Tareas Celery para el pipeline ETL automatizado.

Ejecución manual:
    celery -A app.celery_app call app.tasks.etl_tasks.sync_competition \
        --args='["premier_league"]'

Celery Beat ejecuta estas tareas según el schedule en celery_app.py.
"""
from __future__ import annotations

import logging

from celery import shared_task

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.etl_tasks.sync_competition",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 min entre reintentos
    time_limit=1800,          # 30 min máximo por competición
    queue="etl",
    acks_late=True,
)
def sync_competition(self, competition_slug: str, data_types: list[str] | None = None, season: int | None = None):
    """Sincroniza una competición específica."""
    from etl.pipeline.orchestrator import ETLPipeline
    try:
        pipeline = ETLPipeline()
        reports = pipeline.sync_competition(competition_slug, data_types, season)
        return [r.to_dict() for r in reports]
    except Exception as exc:
        logger.exception("sync_competition(%s) falló: %s", competition_slug, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.etl_tasks.sync_all",
    bind=True,
    max_retries=1,
    time_limit=7200,   # 2 horas máximo para sync completo
    queue="etl",
    acks_late=True,
)
def sync_all(self, data_types: list[str] | None = None):
    """Sincroniza todas las competiciones configuradas."""
    from etl.pipeline.orchestrator import ETLPipeline
    try:
        pipeline = ETLPipeline()
        all_reports = pipeline.sync_all(data_types)
        summary = {slug: [r.to_dict() for r in reports] for slug, reports in all_reports.items()}
        logger.info("sync_all completado: %d competiciones", len(summary))
        return summary
    except Exception as exc:
        logger.exception("sync_all falló: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.etl_tasks.sync_macro",
    bind=True,
    max_retries=2,
    time_limit=600,
    queue="etl",
    acks_late=True,
)
def sync_macro(self):
    """Actualiza datos macroeconómicos desde World Bank."""
    from etl.pipeline.orchestrator import ETLPipeline
    try:
        pipeline = ETLPipeline()
        report = pipeline.sync_macro()
        return report.to_dict()
    except Exception as exc:
        logger.exception("sync_macro falló: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.etl_tasks.retrain_models",
    bind=True,
    max_retries=1,
    time_limit=600,
    queue="etl",
    acks_late=True,
)
def retrain_models(self):
    """Fuerza reentrenamiento de Elo + Dixon-Coles desde DB."""
    import os
    import requests
    api_url = os.getenv("API_URL", "http://api:8000")
    try:
        resp = requests.post(f"{api_url}/load-from-db", timeout=300)
        resp.raise_for_status()
        result = resp.json()
        logger.info("Reentrenamiento completado: %s", result)
        return result
    except Exception as exc:
        logger.exception("retrain_models falló: %s", exc)
        raise self.retry(exc=exc)
