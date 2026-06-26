"""
Celery application para trabajos de simulación pesados.

Configuración mínima para conectar con Redis. Los workers se lanzan con:
    celery -A app.celery_app worker --loglevel=info --concurrency=4

Los trabajos de simulación se registran en app.tasks.simulation.
"""
from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "football_sim",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.simulation"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.simulation.*": {"queue": "simulations"},
    },
    worker_prefetch_multiplier=1,   # un job por worker a la vez (sims son CPU-bound)
    task_acks_late=True,            # confirma solo tras completar (no perder jobs)
    task_reject_on_worker_lost=True,
)
