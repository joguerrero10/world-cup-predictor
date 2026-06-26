"""
Gestor de trabajos de simulación asíncronos.

Para trabajos pesados (> 10K sims): encola el job en DB, lo ejecuta en
un thread/process background y actualiza el estado.

Para trabajos ligeros (< 10K sims): ejecución síncrona con timeout.

En producción con Celery+Redis: sustituir `_run_in_thread` por
`celery_task.delay(job_id)`.
"""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SimulationJob


class JobStatus:
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


def create_job(
    db: Session,
    competition_id: str,
    n_sims: int,
    model_name: str = "hybrid",
    config: dict | None = None,
) -> SimulationJob:
    """Crea un job en la DB con estado 'queued'."""
    job = SimulationJob(
        competition_id=competition_id,
        n_sims=n_sims,
        model_name=model_name,
        config=config or {},
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> SimulationJob | None:
    return db.get(SimulationJob, job_id)


def list_jobs(db: Session, limit: int = 50) -> list[SimulationJob]:
    from sqlalchemy import select, desc
    return list(db.scalars(
        select(SimulationJob).order_by(desc(SimulationJob.created_at)).limit(limit)
    ))


def submit_job(
    job_id: int,
    simulate_fn: Any,         # callable que recibe (job_config) -> dict
    db_factory: Any,          # callable que devuelve una nueva Session
) -> None:
    """
    Lanza el job en un thread background. No bloquea el hilo HTTP.

    En una arquitectura Celery real, aquí iría:
        celery_task.delay(job_id)
    En esta implementación ligera usamos threading para no bloquear FastAPI.
    """
    thread = threading.Thread(
        target=_worker,
        args=(job_id, simulate_fn, db_factory),
        daemon=True,
        name=f"sim-job-{job_id}",
    )
    thread.start()


def _worker(
    job_id: int,
    simulate_fn: Any,
    db_factory: Any,
) -> None:
    """Ejecuta la simulación en background y actualiza la DB."""
    with db_factory() as db:
        job = db.get(SimulationJob, job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

    t0 = time.time()
    try:
        result = simulate_fn(job_id)
        duration = time.time() - t0
        with db_factory() as db:
            job = db.get(SimulationJob, job_id)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result_json = result
            job.duration_seconds = duration
            db.commit()
    except Exception as e:
        duration = time.time() - t0
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        with db_factory() as db:
            job = db.get(SimulationJob, job_id)
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = err[:4000]
            job.duration_seconds = duration
            db.commit()
