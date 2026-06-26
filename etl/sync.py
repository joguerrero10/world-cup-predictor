"""
CLI de sincronización manual del pipeline ETL.

Uso:
    # Sincronización completa (todas las competiciones, todos los datos)
    python -m etl.sync

    # Solo una competición
    python -m etl.sync --competition premier_league

    # Solo un tipo de dato
    python -m etl.sync --type matches

    # Competición + temporada específica
    python -m etl.sync --competition bundesliga --season 2024

    # Solo datos macro (World Bank)
    python -m etl.sync --macro

    # Forzar reentrenamiento tras la sync
    python -m etl.sync --retrain

    # Ver estado del sistema (tablas, última sync)
    python -m etl.sync --status
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("etl.sync")


def _status() -> None:
    from app.db.database import SessionLocal, init_db
    from app.db import repositories as repo

    init_db()
    with SessionLocal() as db:
        teams = repo.list_teams(db)
        matches = repo.load_matches(db)
        logs = repo.list_update_logs(db, limit=10)

        print(f"\n{'='*60}")
        print("  ESTADO DEL SISTEMA ETL")
        print(f"{'='*60}")
        print(f"  Equipos en DB:     {len(teams)}")
        print(f"  Partidos en DB:    {len(matches)}")
        if matches:
            print(f"  Partido más reciente: {matches[-1].match_date}")
        print(f"\n  Últimas sincronizaciones:")
        for log in logs:
            dur = f"{log.duration_seconds:.1f}s" if log.duration_seconds else "?"
            print(
                f"    [{log.status:10s}] {log.data_type:15s} "
                f"{log.competition_slug or 'global':20s} "
                f"ins={log.records_inserted} "
                f"dur={dur} "
                f"{log.started_at.strftime('%Y-%m-%d %H:%M')}"
            )
        print()


def _print_report(reports, slug: str | None = None) -> None:
    if isinstance(reports, list):
        items = {slug or "sync": reports}
    else:
        items = reports

    total_inserted = 0
    total_errors = 0

    print(f"\n{'='*60}")
    print("  INFORME DE SINCRONIZACIÓN")
    print(f"{'='*60}")

    for comp_slug, comp_reports in items.items():
        if comp_slug == "_macro":
            comp_slug = "macro_factors"
        for r in comp_reports:
            status_icon = "✓" if r.status == "completed" else "✗"
            print(
                f"  {status_icon} {comp_slug:20s} {r.data_type:12s} "
                f"fetched={r.records_fetched:5d} "
                f"inserted={r.records_inserted:5d} "
                f"skipped={r.records_skipped:4d} "
                f"errors={r.validation_errors:3d} "
                f"{r.duration:.1f}s"
            )
            total_inserted += r.records_inserted
            total_errors += len(r.errors) + r.validation_errors
            if r.errors:
                for err in r.errors[:3]:
                    print(f"       ⚠ {err}")

    print(f"\n  Total insertados: {total_inserted}   Total errores: {total_errors}")

    # Recomendaciones
    if total_errors > 50:
        print("\n  ⚠ Recomendación: revisar provider_logs en DB para diagnóstico.")
    if total_inserted == 0:
        print("\n  ℹ Sin nuevos datos — todo está al día o los proveedores no devolvieron datos.")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Pipeline ETL de datos futbolísticos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--competition", "-c",
        metavar="SLUG",
        help="Slug de la competición (ej: premier_league, ucl, bundesliga)",
    )
    ap.add_argument(
        "--type", "-t",
        dest="data_type",
        choices=["matches", "teams", "players", "standings", "all"],
        default="all",
        help="Tipo de datos a sincronizar (default: all)",
    )
    ap.add_argument(
        "--season", "-s",
        type=int,
        metavar="YEAR",
        help="Año de inicio de temporada (ej: 2024)",
    )
    ap.add_argument(
        "--macro",
        action="store_true",
        help="Solo sincronizar datos macroeconómicos (World Bank)",
    )
    ap.add_argument(
        "--retrain",
        action="store_true",
        help="Forzar reentrenamiento de modelos al finalizar",
    )
    ap.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estado actual del sistema y salir",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON",
    )

    args = ap.parse_args()

    if args.status:
        _status()
        return

    from etl.pipeline.orchestrator import ETLPipeline

    pipeline = ETLPipeline()
    data_types = None if args.data_type == "all" else [args.data_type]

    if args.macro:
        report = pipeline.sync_macro()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, default=str))
        else:
            _print_report({"macro": [report]})
        return

    if args.competition:
        reports = pipeline.sync_competition(
            args.competition,
            data_types=data_types,
            season=args.season,
            force_retrain=args.retrain,
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in reports], indent=2, default=str))
        else:
            _print_report(reports, args.competition)
    else:
        all_reports = pipeline.sync_all(data_types=data_types, season=args.season)
        if args.retrain:
            logger.info("Forzando reentrenamiento...")
            pipeline._trigger_retrain()
        if args.json:
            print(json.dumps(
                {k: [r.to_dict() for r in v] for k, v in all_reports.items()},
                indent=2, default=str,
            ))
        else:
            _print_report(all_reports)


if __name__ == "__main__":
    main()
