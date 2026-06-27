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


def job_players_sync():
    """
    Job semanal: sincroniza estadísticas de jugadores de todas las competiciones.

    Guarda goals_per_90, assists_per_90, xg_per_90, minutes_played,
    yellow_cards_per_90, red_cards_per_90, overall_rating en la BD.
    """
    from etl.pipeline.orchestrator import ETLPipeline
    logger.info("[players_sync] Iniciando sync semanal de jugadores")
    try:
        pipeline = ETLPipeline()
        results = pipeline.sync_all(data_types=["players"])
        logger.info("[players_sync] Completado: %s", results)
    except Exception as e:
        logger.error("[players_sync] Error: %s", e)


def job_transfers_sync():
    """
    Job diario: sincroniza fichajes recientes de todas las competiciones.

    Usa el proveedor ETL para cargar transferencias en la tabla Transfer.
    """
    from etl.pipeline.orchestrator import ETLPipeline
    logger.info("[transfers_sync] Iniciando sync de fichajes")
    try:
        pipeline = ETLPipeline()
        results = pipeline.sync_all(data_types=["transfers"])
        logger.info("[transfers_sync] Completado: %s", results)
    except Exception as e:
        logger.error("[transfers_sync] Error: %s", e)


def job_live_fixtures():
    """
    Job horario: sincroniza fixtures del día actual y ventana ±48h.

    Para cada competición activa:
    - Inserta partidos SCHEDULED (goals=None) si no existen en BD
    - Actualiza partidos que tenían goals=None cuando ya tienen resultado
    Así el endpoint GET /fixtures/ puede devolver datos reales sin ETL manual.
    """
    from datetime import datetime, timedelta

    from app.db.database import SessionLocal
    from app.db import repositories as repo

    logger.info("[live_fixtures] Iniciando sincronización de fixtures")

    try:
        from etl.providers.api_football import APIFootballProvider
        provider = APIFootballProvider()
    except Exception as e:
        logger.warning("[live_fixtures] No se pudo inicializar APIFootballProvider: %s", e)
        return

    if not provider.is_available():
        logger.warning("[live_fixtures] API_FOOTBALL_KEY no configurado, saltando job")
        return

    now = datetime.utcnow()
    date_from = (now - timedelta(hours=2)).date()
    date_to = (now + timedelta(hours=48)).date()

    total_inserted = 0
    total_updated = 0

    try:
        with SessionLocal() as db:
            team_ids: dict[str, int] = repo.team_id_map(db)

            for comp in COMPETITIONS:
                try:
                    matches = provider.fetch_matches(
                        comp,
                        season=now.year,
                        date_from=date_from,
                        date_to=date_to,
                    )
                    if not matches:
                        continue

                    season_id = repo.find_or_create_season(db, comp, now.year)

                    for m in matches:
                        for tname in (m.home_team, m.away_team):
                            if tname and tname not in team_ids:
                                t = repo.upsert_team(db, tname, data_source="etl_live")
                                team_ids[tname] = t.id

                        home_id = team_ids.get(m.home_team)
                        away_id = team_ids.get(m.away_team)
                        if not home_id or not away_id:
                            continue

                        existing = repo.find_match(db, home_id, away_id, m.date)

                        if existing is None:
                            repo.add_match_full(
                                db,
                                match_date=m.date,
                                home_id=home_id,
                                away_id=away_id,
                                home_goals=m.home_goals,
                                away_goals=m.away_goals,
                                match_type=m.match_type,
                                neutral=m.neutral,
                                matchday=m.matchday,
                                round_name=m.round_name,
                                venue=m.venue,
                                season_id=season_id,
                            )
                            total_inserted += 1
                        elif (
                            existing.home_goals is None
                            and m.home_goals is not None
                            and m.away_goals is not None
                        ):
                            repo.update_match_result(
                                db,
                                existing,
                                m.home_goals,
                                m.away_goals,
                                getattr(m, "home_xg", None),
                                getattr(m, "away_xg", None),
                            )
                            total_updated += 1

                except Exception as comp_err:
                    logger.error("[live_fixtures] Error en %s: %s", comp, comp_err)

            db.commit()

        logger.info(
            "[live_fixtures] Completado: +%d insertados, %d actualizados",
            total_inserted, total_updated,
        )
    except Exception as e:
        logger.error("[live_fixtures] Error general: %s", e)
