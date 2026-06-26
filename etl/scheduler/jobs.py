"""
Definición de jobs del scheduler ETL.

Permite lanzar la sincronización completa o parcial directamente
sin pasar por Celery (útil para testing o scripts manuales).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

COMPETITIONS = [
    "premier_league",
    "laliga",
    "bundesliga",
    "serie_a",
    "ligue_1",
    "ucl",
    "fifa_wc_2026",
]


def job_daily_full_sync():
    """Job diario: sincronización completa de todas las competiciones."""
    from etl.pipeline.orchestrator import ETLPipeline
    logger.info("Iniciando sync diaria completa")
    pipeline = ETLPipeline()
    return pipeline.sync_all(data_types=["teams", "matches", "standings"])


def job_matches_only():
    """Job de alta frecuencia: solo partidos recientes."""
    from etl.pipeline.orchestrator import ETLPipeline
    logger.info("Iniciando sync de partidos")
    pipeline = ETLPipeline()
    return pipeline.sync_all(data_types=["matches"])


def job_macro_weekly():
    """Job semanal: actualizar datos macroeconómicos."""
    from etl.pipeline.orchestrator import ETLPipeline
    logger.info("Iniciando sync macro")
    pipeline = ETLPipeline()
    return pipeline.sync_macro()


def job_retrain():
    """Job de reentrenamiento manual de modelos."""
    from etl.pipeline.orchestrator import ETLPipeline
    pipeline = ETLPipeline()
    pipeline._trigger_retrain()
