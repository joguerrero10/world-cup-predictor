"""
Tareas Celery para simulaciones Monte Carlo.

Cuando el worker está activo, los jobs pesados se encolan aquí en lugar de
ejecutarse en un thread de FastAPI. Esto desacopla completamente el API del
tiempo de cómputo.

Integración con la API:
- POST /api/v1/simulation-jobs crea un SimulationJob en DB
- Si Celery está disponible, despacha run_simulation_job.delay(job_id)
- Si no está disponible (modo lightweight), usa threading (ver job_manager.py)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.simulation.run_simulation_job",
    max_retries=2,
    default_retry_delay=30,
    queue="simulations",
    time_limit=600,    # 10 minutos máximo por job
    soft_time_limit=540,
)
def run_simulation_job(self, job_id: int) -> dict:
    """
    Ejecuta un SimulationJob por su ID.

    1. Carga la config del job de la DB.
    2. Construye el modelo de predicción desde el estado global.
    3. Ejecuta simulate_fast() vectorizado.
    4. Persiste el resultado en la DB.
    """
    from app.db.database import SessionLocal
    from app.db.models import SimulationJob
    from app.simulation.monte_carlo_fast import simulate_fast, CompetitionGroup
    from app.models.competition import get_competition
    from app.models.elo import win_draw_loss_probs, TeamElo, EloConfig
    from app.services.bootstrap import build_engine_from_db, build_factors_from_db

    t0 = time.time()

    with SessionLocal() as db:
        job = db.get(SimulationJob, job_id)
        if job is None:
            return {"error": f"Job {job_id} no encontrado"}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.worker_id = self.request.id or "celery"
        db.commit()

        competition_cfg = get_competition(job.competition_id)
        cfg = job.config or {}

        # Rebuild Elo desde DB para cada worker (stateless)
        elo, dc, n_matches = build_engine_from_db(db)
        elo_cfg = EloConfig()

    def model_fn(home: str, away: str, neutral: bool):
        h = elo.get(home, TeamElo())
        a = elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, elo_cfg, neutral)

    teams_list = cfg.get("teams") or sorted(elo.keys())
    groups_cfg = cfg.get("groups")

    if groups_cfg:
        groups = [
            CompetitionGroup(name=gname, teams=gteams)
            for gname, gteams in groups_cfg.items()
        ]
    else:
        n_per_group = competition_cfg.teams_per_group or 4
        groups = [
            CompetitionGroup(
                name=str(i // n_per_group + 1),
                teams=teams_list[i:i + n_per_group],
            )
            for i in range(0, len(teams_list) - len(teams_list) % n_per_group, n_per_group)
        ]

    result = simulate_fast(
        groups=groups,
        model=model_fn,
        n_sims=job.n_sims,
        advance_per_group=competition_cfg.advance_per_group or 2,
        neutral=competition_cfg.neutral_venue_groups,
    )

    duration = time.time() - t0
    result_dict = result.to_dict()

    with SessionLocal() as db:
        job = db.get(SimulationJob, job_id)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.result_json = result_dict
        job.duration_seconds = duration
        db.commit()

    return result_dict
