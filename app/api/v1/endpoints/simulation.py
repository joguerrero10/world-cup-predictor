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

    def _simulate(job_id: int) -> dict:
        """Función que ejecuta la simulación real en el worker."""
        from app.simulation.monte_carlo_fast import simulate_fast, CompetitionGroup
        from app.models.competition import get_competition
        from app.db.database import SessionLocal

        with SessionLocal() as wdb:
            j = wdb.get(type(job), job_id)
            cfg = j.config or {}
            competition_cfg = get_competition(j.competition_id)

        # Construir el modelo de predicción desde el STATE global del API
        from app.main import STATE
        from app.models.elo import win_draw_loss_probs

        def model_fn(home: str, away: str, neutral: bool):
            if home in STATE.elo and away in STATE.elo:
                return win_draw_loss_probs(
                    STATE.elo[home].rating, STATE.elo[away].rating,
                    STATE.elo_cfg, neutral
                )
            return (1/3, 1/3, 1/3)

        # Grupos: usar configuración del request o crear grupos automáticos
        teams_list = cfg.get("teams") or sorted(STATE.elo.keys())
        groups_cfg = cfg.get("groups")

        if groups_cfg:
            groups = [
                CompetitionGroup(name=gname, teams=gteams)
                for gname, gteams in groups_cfg.items()
            ]
        else:
            n = len(teams_list)
            n_per_group = competition_cfg.teams_per_group or 4
            groups = [
                CompetitionGroup(
                    name=str(i // n_per_group + 1),
                    teams=teams_list[i:i + n_per_group]
                )
                for i in range(0, n - n % n_per_group, n_per_group)
            ]

        if not groups:
            raise ValueError("No hay suficientes equipos para formar grupos.")

        result = simulate_fast(
            groups=groups,
            model=model_fn,
            n_sims=j.n_sims,
            advance_per_group=competition_cfg.advance_per_group or 2,
        )
        return result.to_dict()

    submit_job(job_id=job.id, simulate_fn=_simulate, db_factory=SessionLocal)

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
