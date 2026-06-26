"""
Celery application para simulaciones y pipeline ETL automatizado.

Workers:
    celery -A app.celery_app worker --loglevel=info --queues=simulations,etl,default

Beat scheduler (actualizaciones automáticas):
    celery -A app.celery_app beat --loglevel=info
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "football_sim",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.simulation",
        "app.tasks.etl_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    task_routes={
        "app.tasks.simulation.*": {"queue": "simulations"},
        "app.tasks.etl_tasks.*": {"queue": "etl"},
    },

    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # ------------------------------------------------------------------
    # Celery Beat — schedule de actualizaciones automáticas
    # Ajustar cron según necesidades; por defecto:
    #   • Sync completo diario a las 03:00 UTC
    #   • Sync de partidos de cada liga cada 6 horas
    #   • Datos macro semanalmente (lunes 02:00 UTC)
    # ------------------------------------------------------------------
    beat_schedule={
        "sync-all-daily": {
            "task": "app.tasks.etl_tasks.sync_all",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"data_types": ["teams", "matches", "standings"]},
        },
        "sync-matches-6h": {
            "task": "app.tasks.etl_tasks.sync_competition",
            "schedule": crontab(minute=0, hour="*/6"),
            "kwargs": {"competition_slug": "premier_league", "data_types": ["matches"]},
        },
        "sync-ucl-6h": {
            "task": "app.tasks.etl_tasks.sync_competition",
            "schedule": crontab(minute=30, hour="*/6"),
            "kwargs": {"competition_slug": "ucl", "data_types": ["matches"]},
        },
        "sync-macro-weekly": {
            "task": "app.tasks.etl_tasks.sync_macro",
            "schedule": crontab(hour=2, minute=0, day_of_week=1),  # lunes
        },
        "retrain-weekly": {
            "task": "app.tasks.etl_tasks.retrain_models",
            "schedule": crontab(hour=4, minute=0, day_of_week=1),  # lunes después del sync
        },
    },
)
