"""
Endpoints de simulación asíncrona.

POST /api/v1/simulation-jobs          — crear job
GET  /api/v1/simulation-jobs          — listar jobs
GET  /api/v1/simulation-jobs/{id}     — estado del job
GET  /api/v1/simulation-jobs/{id}/result — resultado del job
DELETE /api/v1/simulation-jobs/{id}   — cancelar (si queued)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    SimulationJobRequest, SimulationJobStatus, SimulationJobResult
)
from app.db.database import get_session
from app.services.job_manager import (
    create_job, get_job, list_jobs, submit_job, JobStatus
)

router = APIRouter(prefix="/simulation-jobs", tags=["simulation"])


def _job_to_status(job) -> SimulationJobStatus:
    return SimulationJobStatus(
        id=job.id,
        status=job.status,
        competition_id=job.competition_id,
        n_sims=job.n_sims,
        model_name=job.model_name,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
    )


@router.post("", response_model=SimulationJobStatus, status_code=202)
def create_simulation_job(
    req: SimulationJobRequest,
    db: Session = Depends(get_session),
):
    """
    Encola una simulación Monte Carlo. Retorna inmediatamente con el job_id.
    Llama a GET /simulation-jobs/{id}/status para consultar el progreso.
    """
    from app.db.database import SessionLocal

    job = create_job(
        db=db,
        competition_id=req.competition_id,
        n_sims=req.n_sims,
        model_name=req.model,
        config={
            "teams": req.teams,
            "groups": req.groups,
        },
    )

    # Capturar IDs antes de pasar al closure para evitar referencias a objetos ORM
    _job_id = job.id
    _competition_id = req.competition_id
    _n_sims = req.n_sims
    _model = req.model or "hybrid"

    def _simulate(job_id: int) -> dict:
        """
        Ejecuta la simulación usando el simulador correcto para cada competición.

        Delega a simulate_v2._run_simulation que ya tiene el dispatch correcto:
          - fifa_wc_2026  → WorldCupSimulator (48 selecciones, 12 grupos)
          - ucl           → ChampionsLeagueSimulator (36 clubes, fase de liga)
          - premier_league/laliga/etc → LeagueSimulator (round-robin)
        """
        from app.db.database import SessionLocal
        from app.db.models import SimulationJob
        from app.api.v1.endpoints.simulate_v2 import _build_model_fn, _run_simulation

        with SessionLocal() as wdb:
            j = wdb.get(SimulationJob, job_id)
            if j is None:
                raise ValueError(f"Job {job_id} no encontrado en la BD")

            competition_id = j.competition_id
            n_sims         = j.n_sims
            model_name     = j.model_name or "hybrid"
            season         = (j.config or {}).get("season")
            seed           = (j.config or {}).get("seed")

            model_fn   = _build_model_fn(competition_id, wdb, model_name)
            sim_result = _run_simulation(
                comp_id=competition_id,
                n_sims=n_sims,
                season=season,
                model_fn=model_fn,
                seed=seed,
                db=wdb,
            )

        return sim_result.model_dump()

    submit_job(job_id=_job_id, simulate_fn=_simulate, db_factory=SessionLocal)

    return _job_to_status(job)


@router.get("", response_model=list[SimulationJobStatus])
def list_simulation_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """Lista los trabajos de simulación más recientes."""
    return [_job_to_status(j) for j in list_jobs(db, limit=limit)]


@router.get("/{job_id}", response_model=SimulationJobStatus)
def get_simulation_job_status(
    job_id: int,
    db: Session = Depends(get_session),
):
    """Estado actual de un trabajo de simulación."""
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} no encontrado.")
    return _job_to_status(job)


@router.get("/{job_id}/result", response_model=SimulationJobResult)
def get_simulation_job_result(
    job_id: int,
    db: Session = Depends(get_session),
):
    """
    Resultado completo de un job de simulación.
    Retorna 202 si todavía está en progreso.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(404, f"Job {job_id} no encontrado.")

    if job.status == JobStatus.QUEUED:
        raise HTTPException(202, "Job en cola, aún no iniciado.")
    if job.status == JobStatus.RUNNING:
        raise HTTPException(202, "Simulación en progreso.")
    if job.status == JobStatus.FAILED:
        raise HTTPException(500, f"Simulación falló: {job.error_message}")

    return SimulationJobResult(
        id=job.id,
        status=job.status,
        competition_id=job.competition_id,
        n_sims=job.n_sims,
        result=job.result_json,
        duration_seconds=job.duration_seconds,
    )
