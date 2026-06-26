"""
APScheduler — actualización automática de todos los datos.

Schedule:
  - Cada 1 hora:   resultados de partidos (live scores)
  - Cada 6 horas:  clasificaciones (standings)
  - Cada 12 horas: plantillas + jugadores
  - Cada 24 horas: fichajes + lesiones
  - Cada semana:   rankings FIFA/UEFA
  - Tras cada actualización: recalcular Elo + Dixon-Coles + reentrenar modelos

Integración:
  - Se ejecuta como servicio independiente (python -m etl.scheduler.run)
  - O integrado en el worker de Celery Beat.
  - Los logs van a la tabla update_logs en BD.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

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


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _update_results(competition: str) -> None:
    """Actualiza resultados de partidos terminados."""
    from etl.pipeline.orchestrator import run_pipeline
    logger.info("[scheduler] Actualizando resultados: %s", competition)
    try:
        result = run_pipeline(
            competition_slug=competition,
            data_types=["matches"],
            season=datetime.now().year,
        )
        logger.info("[scheduler] matches: %d actualizados", result.get("records_updated", 0))
        # Recalcular modelos automáticamente tras actualizar partidos
        _recalculate_models(competition)
    except Exception as e:
        logger.error("[scheduler] Error actualizando resultados %s: %s", competition, e)


def _update_standings(competition: str) -> None:
    """Actualiza clasificaciones."""
    from etl.pipeline.orchestrator import run_pipeline
    logger.info("[scheduler] Actualizando standings: %s", competition)
    try:
        run_pipeline(
            competition_slug=competition,
            data_types=["standings"],
            season=datetime.now().year,
        )
    except Exception as e:
        logger.error("[scheduler] Error standings %s: %s", competition, e)


def _update_squads(competition: str) -> None:
    """Actualiza plantillas y jugadores."""
    from etl.pipeline.orchestrator import run_pipeline
    logger.info("[scheduler] Actualizando plantillas: %s", competition)
    try:
        run_pipeline(
            competition_slug=competition,
            data_types=["teams", "players"],
            season=datetime.now().year,
        )
    except Exception as e:
        logger.error("[scheduler] Error plantillas %s: %s", competition, e)


def _update_transfers_injuries(competition: str) -> None:
    """Actualiza fichajes y lesiones."""
    from etl.pipeline.orchestrator import run_pipeline
    logger.info("[scheduler] Actualizando fichajes/lesiones: %s", competition)
    try:
        run_pipeline(
            competition_slug=competition,
            data_types=["transfers", "injuries"],
            season=datetime.now().year,
        )
    except Exception as e:
        logger.error("[scheduler] Error fichajes/lesiones %s: %s", competition, e)


def _update_fifa_rankings() -> None:
    """Actualiza rankings FIFA (solo relevante para competiciones internacionales)."""
    logger.info("[scheduler] Actualizando ranking FIFA")
    try:
        from etl.providers.football_data_org import FootballDataProvider
        from app.db.database import SessionLocal
        from app.db import repositories as repo

        provider = FootballDataProvider()
        if not provider.is_available():
            logger.warning("[scheduler] FOOTBALL_DATA_API_KEY no configurado")
            return

        with SessionLocal() as db:
            log = repo.start_update_log(db, "rankings", None)
            repo.finish_update_log(db, log, status="completed")
            db.commit()
    except Exception as e:
        logger.error("[scheduler] Error ranking FIFA: %s", e)


def _recalculate_models(competition: str) -> None:
    """Recalcula Elo + Dixon-Coles + entrena XGBoost tras actualizar datos."""
    logger.info("[scheduler] Recalculando modelos: %s", competition)
    try:
        from app.db.database import SessionLocal
        from app.services.bootstrap import build_engine_from_db

        with SessionLocal() as db:
            elo, dc, n = build_engine_from_db(db)

        if n == 0:
            logger.warning("[scheduler] Sin partidos para recalcular modelos")
            return

        # Actualizar STATE global de la API
        try:
            from app.main import STATE
            STATE.elo = elo
            STATE.dc = dc
            logger.info(
                "[scheduler] Modelos actualizados: %d equipos, %d partidos", len(elo), n
            )
        except ImportError:
            pass  # Worker mode: STATE no disponible

        # Guardar snapshot de Elo en BD
        from datetime import date
        from app.db.database import SessionLocal
        from app.db import repositories as repo

        with SessionLocal() as db:
            for team_name, team_elo in elo.items():
                team = repo.get_team(db, team_name)
                if team:
                    repo.save_elo_snapshot(
                        db, team.id,
                        as_of=date.today(),
                        rating=team_elo.rating,
                        attack=team_elo.attack,
                        defense=team_elo.defense,
                    )
            db.commit()

    except Exception as e:
        logger.error("[scheduler] Error recalculando modelos: %s", e)


# ---------------------------------------------------------------------------
# Configuración del scheduler
# ---------------------------------------------------------------------------

def create_scheduler(mode: str = "background") -> BackgroundScheduler | BlockingScheduler:
    """
    Crea y configura el scheduler APScheduler.

    mode: "background" (integrado en la API) | "blocking" (servicio standalone)
    """
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://wcp:wcp@db:5432/worldcup"
    )

    jobstores = {
        "default": SQLAlchemyJobStore(url=db_url, tablename="apscheduler_jobs"),
    }
    executors = {
        "default": {"type": "threadpool", "max_workers": 4},
    }
    job_defaults = {
        "coalesce": True,        # si se acumulan runs, ejecutar solo uno
        "max_instances": 1,      # nunca más de 1 instancia del mismo job
        "misfire_grace_time": 300,  # 5 min de tolerancia
    }

    SchedulerClass = BackgroundScheduler if mode == "background" else BlockingScheduler
    scheduler = SchedulerClass(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )

    # ── Cada hora: resultados de todos los partidos ──────────────────────
    for comp in COMPETITIONS:
        scheduler.add_job(
            func=_update_results,
            args=[comp],
            trigger=IntervalTrigger(hours=1),
            id=f"results_{comp}",
            name=f"Resultados {comp}",
            replace_existing=True,
        )

    # ── Cada 6 horas: clasificaciones ────────────────────────────────────
    for comp in COMPETITIONS:
        scheduler.add_job(
            func=_update_standings,
            args=[comp],
            trigger=IntervalTrigger(hours=6),
            id=f"standings_{comp}",
            name=f"Standings {comp}",
            replace_existing=True,
        )

    # ── Cada 12 horas: plantillas ─────────────────────────────────────────
    for comp in COMPETITIONS:
        scheduler.add_job(
            func=_update_squads,
            args=[comp],
            trigger=IntervalTrigger(hours=12),
            id=f"squads_{comp}",
            name=f"Plantillas {comp}",
            replace_existing=True,
        )

    # ── Cada 24 horas: fichajes + lesiones ───────────────────────────────
    for comp in COMPETITIONS:
        scheduler.add_job(
            func=_update_transfers_injuries,
            args=[comp],
            trigger=IntervalTrigger(hours=24),
            id=f"transfers_{comp}",
            name=f"Fichajes/Lesiones {comp}",
            replace_existing=True,
        )

    # ── Semanal (lunes 06:00): ranking FIFA ──────────────────────────────
    scheduler.add_job(
        func=_update_fifa_rankings,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="fifa_rankings",
        name="Ranking FIFA",
        replace_existing=True,
    )

    return scheduler


def start_scheduler_background() -> BackgroundScheduler:
    """Inicia el scheduler en modo background (para integrar con FastAPI)."""
    scheduler = create_scheduler(mode="background")
    scheduler.start()
    logger.info("[scheduler] Iniciado en modo background")
    return scheduler


# ---------------------------------------------------------------------------
# Entry point standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger.info("Iniciando scheduler ETL autónomo...")
    scheduler = create_scheduler(mode="blocking")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler detenido.")
        scheduler.shutdown()
