"""
Orquestador del pipeline ETL.

Flujo por sincronización:
  Extract → Transform → Validate → Load → Audit → [Retrain si hay nuevos partidos]

Resiliente: si todos los proveedores fallan para un tipo de dato,
conserva la última versión válida en DB y registra la advertencia.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.db.database import SessionLocal, init_db
from app.db import repositories as repo
from etl.providers.base import BaseProvider, MatchData, PlayerData, StandingData, TeamData
from etl.providers.registry import get_providers
from etl.providers.world_bank import WorldBankProvider
from etl.pipeline.transform import (
    normalize_match, normalize_player, normalize_standing, normalize_team,
)
from etl.pipeline.validate import (
    filter_matches, filter_players, filter_standings, filter_teams,
)

logger = logging.getLogger(__name__)

# Competiciones soportadas para sincronización automática
SYNC_COMPETITIONS = [
    "premier_league",
    "laliga",
    "bundesliga",
    "serie_a",
    "ligue_1",
    "ucl",
    "fifa_wc_2026",
]

# Umbral de partidos nuevos para disparar reentrenamiento automático
RETRAIN_THRESHOLD = 5


@dataclass
class SyncReport:
    competition_slug: Optional[str]
    data_type: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    records_fetched: int = 0
    records_valid: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    validation_errors: int = 0
    providers_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "running"

    @property
    def duration(self) -> float:
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def finish(self, status: str = "completed") -> None:
        self.completed_at = datetime.utcnow()
        self.status = status

    def to_dict(self) -> dict:
        return {
            "competition_slug": self.competition_slug,
            "data_type": self.data_type,
            "status": self.status,
            "duration_seconds": round(self.duration, 2),
            "records_fetched": self.records_fetched,
            "records_valid": self.records_valid,
            "records_inserted": self.records_inserted,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "validation_errors": self.validation_errors,
            "providers_used": self.providers_used,
            "errors": self.errors[:20],  # truncar para el informe
        }


class ETLPipeline:
    """
    Pipeline ETL multicompetición.

    Uso:
        pipeline = ETLPipeline()
        report = pipeline.sync_competition("premier_league", data_types=["matches", "standings"])
        full_report = pipeline.sync_all()
    """

    def __init__(self) -> None:
        init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync_competition(
        self,
        competition_slug: str,
        data_types: Optional[list[str]] = None,
        season: Optional[int] = None,
        force_retrain: bool = False,
    ) -> list[SyncReport]:
        """
        Sincroniza todos los tipos de datos de una competición.

        data_types: ["matches", "teams", "players", "standings"]
        Si es None, sincroniza matches + standings + teams.
        """
        data_types = data_types or ["teams", "matches", "standings"]
        reports: list[SyncReport] = []

        total_new_matches = 0
        for dt in data_types:
            report = self._run_sync(competition_slug, dt, season)
            reports.append(report)
            if dt == "matches":
                total_new_matches = report.records_inserted

        if total_new_matches >= RETRAIN_THRESHOLD or force_retrain:
            logger.info(
                "%d nuevos partidos → disparando reentrenamiento automático",
                total_new_matches,
            )
            self._trigger_retrain()

        return reports

    def sync_all(
        self,
        data_types: Optional[list[str]] = None,
        season: Optional[int] = None,
    ) -> dict[str, list[SyncReport]]:
        """Sincroniza todas las competiciones configuradas."""
        all_reports: dict[str, list[SyncReport]] = {}
        for slug in SYNC_COMPETITIONS:
            logger.info("Sincronizando competición: %s", slug)
            all_reports[slug] = self.sync_competition(slug, data_types, season)

        # Sincronizar datos macro (World Bank) una vez para todos los equipos
        macro_report = self._sync_macro()
        all_reports["_macro"] = [macro_report]

        return all_reports

    def sync_macro(self) -> SyncReport:
        """Actualiza datos macroeconómicos del Banco Mundial para todos los equipos."""
        return self._sync_macro()

    # ------------------------------------------------------------------
    # Internos por tipo de dato
    # ------------------------------------------------------------------

    def _run_sync(
        self,
        competition_slug: str,
        data_type: str,
        season: Optional[int],
    ) -> SyncReport:
        report = SyncReport(competition_slug=competition_slug, data_type=data_type)
        t0 = time.monotonic()

        with SessionLocal() as db:
            log = repo.start_update_log(db, data_type, competition_slug)
            db.commit()

            try:
                if data_type == "matches":
                    self._sync_matches(db, report, competition_slug, season)
                elif data_type == "teams":
                    self._sync_teams(db, report, competition_slug)
                elif data_type == "players":
                    self._sync_players(db, report, competition_slug)
                elif data_type == "standings":
                    self._sync_standings(db, report, competition_slug, season)
                else:
                    report.errors.append(f"Tipo de dato desconocido: {data_type}")
                    report.finish("failed")

                if report.status == "running":
                    report.finish("completed")
                db.commit()

            except Exception as exc:
                db.rollback()
                logger.exception("Error en pipeline %s/%s", competition_slug, data_type)
                report.errors.append(str(exc))
                report.finish("failed")

            # Audit en DB
            try:
                repo.finish_update_log(
                    db,
                    log,
                    status=report.status,
                    records_fetched=report.records_fetched,
                    records_inserted=report.records_inserted,
                    records_updated=report.records_updated,
                    records_skipped=report.records_skipped,
                    errors=report.validation_errors + len(report.errors),
                    error_detail="; ".join(report.errors[:5]) or None,
                    providers_used=report.providers_used,
                    duration_seconds=time.monotonic() - t0,
                )
                db.commit()
            except Exception:
                pass  # audit failure no debe detener el sistema

        return report

    def _sync_matches(
        self,
        db,
        report: SyncReport,
        competition_slug: str,
        season: Optional[int],
    ) -> None:
        raw: list[MatchData] = []
        providers = get_providers("matches")

        for provider in providers:
            t0 = time.monotonic()
            provider.clear_errors()
            fetched = provider.fetch_matches(competition_slug, season)
            duration = time.monotonic() - t0

            _log_provider(db, provider, "matches", competition_slug, fetched, duration)
            report.providers_used.append(provider.name)

            if fetched:
                raw.extend(fetched)
                break  # primer proveedor exitoso es suficiente
            if provider.errors:
                report.errors.extend(provider.errors)

        if not raw:
            logger.warning("Sin datos de partidos para %s", competition_slug)
            return

        # Transform
        normalized = [normalize_match(m) for m in raw]

        # Validate
        valid_matches, val_errors = filter_matches(normalized, f"[{competition_slug}] ")
        report.records_fetched = len(raw)
        report.records_valid = len(valid_matches)
        report.validation_errors += len(val_errors)

        # Load — solo insertar nuevos (dedup por home+away+fecha)
        ids = repo.team_id_map(db)
        inserted = 0
        skipped = 0

        for m in valid_matches:
            if m.status != "FINISHED":
                skipped += 1
                continue

            # Upsert equipos si no existen
            for name in (m.home_team, m.away_team):
                if name not in ids:
                    t = repo.upsert_team(db, name, data_source="etl_auto")
                    ids[name] = t.id

            home_id = ids[m.home_team]
            away_id = ids[m.away_team]

            if repo.match_exists(db, home_id, away_id, m.date):
                skipped += 1
                continue

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
                attendance=m.attendance,
                home_xg=m.home_xg,
                away_xg=m.away_xg,
            )
            inserted += 1

        report.records_inserted = inserted
        report.records_skipped = skipped
        logger.info(
            "[%s] matches → fetched=%d valid=%d inserted=%d skipped=%d",
            competition_slug, len(raw), len(valid_matches), inserted, skipped,
        )

    def _sync_teams(
        self,
        db,
        report: SyncReport,
        competition_slug: str,
    ) -> None:
        raw: list[TeamData] = []
        providers = get_providers("teams")

        for provider in providers:
            t0 = time.monotonic()
            provider.clear_errors()
            fetched = provider.fetch_teams(competition_slug)
            duration = time.monotonic() - t0
            _log_provider(db, provider, "teams", competition_slug, fetched, duration)
            report.providers_used.append(provider.name)

            if fetched:
                raw.extend(fetched)
                break
            if provider.errors:
                report.errors.extend(provider.errors)

        normalized = [normalize_team(t) for t in raw]
        valid_teams, val_errors = filter_teams(normalized, f"[{competition_slug}] ")
        report.records_fetched = len(raw)
        report.records_valid = len(valid_teams)
        report.validation_errors += len(val_errors)

        updated = 0
        for t in valid_teams:
            fields = {k: v for k, v in {
                "country": t.country,
                "confederation": t.confederation,
                "short_name": t.short_name,
                "is_host": t.is_host,
                "data_source": t.data_source,
            }.items() if v is not None}
            repo.upsert_team(db, t.name, **fields)
            updated += 1

        report.records_updated = updated

    def _sync_players(
        self,
        db,
        report: SyncReport,
        competition_slug: str,
    ) -> None:
        raw: list[PlayerData] = []
        providers = get_providers("players")

        for provider in providers:
            t0 = time.monotonic()
            provider.clear_errors()
            fetched = provider.fetch_players(competition_slug)
            duration = time.monotonic() - t0
            _log_provider(db, provider, "players", competition_slug, fetched, duration)
            report.providers_used.append(provider.name)
            if fetched:
                raw.extend(fetched)
                break
            if provider.errors:
                report.errors.extend(provider.errors)

        normalized = [normalize_player(p) for p in raw]
        valid_players, val_errors = filter_players(normalized)
        report.records_fetched = len(raw)
        report.records_valid = len(valid_players)
        report.validation_errors += len(val_errors)

        ids = repo.team_id_map(db)
        inserted = 0
        for p in valid_players:
            if p.team_name not in ids:
                team = repo.upsert_team(db, p.team_name, data_source="etl_auto")
                ids[p.team_name] = team.id

            from datetime import datetime as dt_cls
            repo.upsert_player(
                db,
                team_id=ids[p.team_name],
                name=p.name,
                position=p.position,
                nationality=p.nationality,
                birth_date=p.birth_date,
                data_source=p.data_source,
                last_synced_at=dt_cls.utcnow(),
            )
            inserted += 1

        report.records_inserted = inserted

    def _sync_standings(
        self,
        db,
        report: SyncReport,
        competition_slug: str,
        season: Optional[int],
    ) -> None:
        raw: list[StandingData] = []
        providers = get_providers("standings")

        for provider in providers:
            t0 = time.monotonic()
            provider.clear_errors()
            fetched = provider.fetch_standings(competition_slug, season)
            duration = time.monotonic() - t0
            _log_provider(db, provider, "standings", competition_slug, fetched, duration)
            report.providers_used.append(provider.name)
            if fetched:
                raw.extend(fetched)
                break
            if provider.errors:
                report.errors.extend(provider.errors)

        normalized = [normalize_standing(s) for s in raw]
        valid_standings, val_errors = filter_standings(normalized)
        report.records_fetched = len(raw)
        report.records_valid = len(valid_standings)
        report.validation_errors += len(val_errors)

        ids = repo.team_id_map(db)
        upserted = 0
        for s in valid_standings:
            if s.team_name not in ids:
                team = repo.upsert_team(db, s.team_name, data_source="etl_auto")
                ids[s.team_name] = team.id

            repo.upsert_standing(
                db,
                team_id=ids[s.team_name],
                competition_slug=s.competition_slug,
                season_year=s.season_year,
                position=s.position,
                played=s.played,
                won=s.won,
                drawn=s.drawn,
                lost=s.lost,
                goals_for=s.goals_for,
                goals_against=s.goals_against,
                points=s.points,
            )
            upserted += 1

        report.records_inserted = upserted

    def _sync_macro(self) -> SyncReport:
        report = SyncReport(competition_slug=None, data_type="macro_factors")

        wb = WorldBankProvider()
        if not wb.is_available():
            report.errors.append("WorldBankProvider no disponible")
            report.finish("failed")
            return report

        t0 = time.monotonic()
        try:
            macro = wb.fetch_macro_data()
        except Exception as exc:
            report.errors.append(f"WorldBank fetch error: {exc}")
            report.finish("failed")
            return report

        duration = time.monotonic() - t0
        report.providers_used.append("world_bank")

        with SessionLocal() as db:
            teams = repo.list_teams(db)
            report.records_fetched = len(macro)
            updated = 0
            for team in teams:
                enriched = wb.enrich_team(team.name, macro)
                fields: dict = {}
                if enriched.gdp_per_capita is not None and team.gdp_per_capita is None:
                    fields["gdp_per_capita"] = enriched.gdp_per_capita
                if enriched.population is not None and team.population is None:
                    fields["population"] = enriched.population
                if fields:
                    repo.upsert_team(db, team.name, **fields)
                    updated += 1
            db.commit()
            report.records_updated = updated

        report.finish("completed")
        return report

    # ------------------------------------------------------------------
    # Reentrenamiento automático
    # ------------------------------------------------------------------

    def _trigger_retrain(self) -> None:
        """Llama a load-from-db vía HTTP interno para reentrenar los modelos."""
        import os
        import requests as req

        api_url = os.getenv("API_URL", "http://localhost:8000")
        try:
            resp = req.post(f"{api_url}/load-from-db", timeout=120)
            resp.raise_for_status()
            logger.info("Reentrenamiento completado: %s", resp.json())
        except Exception as exc:
            logger.warning("Reentrenamiento falló (no crítico): %s", exc)


# ---------------------------------------------------------------------------
# Helper para audit de proveedor
# ---------------------------------------------------------------------------

def _log_provider(db, provider: BaseProvider, data_type: str, competition_slug: str, records, duration: float) -> None:
    try:
        repo.log_provider_call(
            db,
            provider_name=provider.name,
            data_type=data_type,
            competition_slug=competition_slug,
            records_fetched=len(records),
            records_valid=len(records),
            duration_seconds=duration,
            success=not provider.errors,
            error_message=("; ".join(provider.errors[:3]) if provider.errors else None),
        )
    except Exception:
        pass  # fallo de audit no interrumpe el pipeline
