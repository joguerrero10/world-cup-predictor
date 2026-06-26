"""
FASE 6 — Benchmark: Monte Carlo original vs. vectorizado.

Mide tiempo de simulación para 10K, 100K y 1M simulaciones
con ambos motores y reporta speedup.

Uso:
    python -m tests.benchmark_mc
    python -m tests.benchmark_mc --sims 1000000 --groups 12 --teams-per-group 4

El motor ORIGINAL (monte_carlo.py) usa Python puro con bucles anidados.
El motor FAST (monte_carlo_fast.py) usa NumPy vectorizado sobre n_sims.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np


def _build_groups_and_model(n_groups: int, teams_per_group: int):
    """Genera grupos sintéticos y un modelo de predicción determinístico."""
    from app.models.monte_carlo import Group as OrigGroup
    from app.simulation.monte_carlo_fast import CompetitionGroup as FastGroup

    # Generar equipos con ratings sintéticos (1200-2000)
    all_teams = [f"T{i:02d}" for i in range(n_groups * teams_per_group)]
    rng = np.random.default_rng(42)
    ratings = dict(zip(all_teams, rng.uniform(1200, 2000, len(all_teams))))

    def model(home: str, away: str, neutral: bool = True):
        """Modelo Elo simplificado (determinístico)."""
        dr = ratings[home] - ratings[away]
        e = 1 / (1 + 10 ** (-dr / 400))
        p_draw = max(0.05, 0.26 * (1 - abs(e - 0.5) * 2))
        rest = 1 - p_draw
        return rest * e, p_draw, rest * (1 - e)

    orig_groups = [
        OrigGroup(str(i + 1), all_teams[i * teams_per_group:(i + 1) * teams_per_group])
        for i in range(n_groups)
    ]
    fast_groups = [
        FastGroup(str(i + 1), all_teams[i * teams_per_group:(i + 1) * teams_per_group])
        for i in range(n_groups)
    ]

    return orig_groups, fast_groups, model


def run_original(groups, model, n_sims: int) -> float:
    from app.models.monte_carlo import simulate
    t0 = time.perf_counter()
    result = simulate(groups, model, n_sims=n_sims, seed=0)
    dt = time.perf_counter() - t0
    return dt, result


def run_fast(groups, model, n_sims: int, n_workers: int = 1) -> float:
    from app.simulation.monte_carlo_fast import simulate_fast
    t0 = time.perf_counter()
    result = simulate_fast(groups, model, n_sims=n_sims, seed=0, n_workers=n_workers)
    dt = time.perf_counter() - t0
    return dt, result


def benchmark(n_sims_list: list[int], n_groups: int, teams_per_group: int, n_workers: int):
    orig_groups, fast_groups, model = _build_groups_and_model(n_groups, teams_per_group)

    print(f"\n{'='*70}")
    print(f"BENCHMARK Monte Carlo — {n_groups} grupos × {teams_per_group} equipos")
    print(f"{'='*70}")
    print(f"{'Sims':>12} | {'Original (s)':>14} | {'Fast 1 núcleo (s)':>18} | {'Speedup 1x':>12} | {'Sims/s fast':>12}")
    print("-" * 70)

    for n_sims in n_sims_list:
        # Original (para n_sims grandes, limitar a 100K para no tardar horas)
        if n_sims <= 100_000:
            dt_orig, _ = run_original(orig_groups, model, n_sims)
            orig_str = f"{dt_orig:>14.2f}"
            speedup_str = f"{dt_orig / max(0.001, 0.001):>12.1f}"
        else:
            dt_orig = None
            orig_str = f"{'(omitido)':>14}"

        dt_fast, _ = run_fast(fast_groups, model, n_sims, n_workers=1)

        if dt_orig is not None:
            speedup = dt_orig / dt_fast
            speedup_str = f"{speedup:>12.1f}x"
        else:
            speedup_str = f"{'N/A':>12}"

        sims_per_sec = n_sims / dt_fast
        print(f"{n_sims:>12,} | {orig_str} | {dt_fast:>18.3f} | {speedup_str} | {sims_per_sec:>12,.0f}")

    print(f"\n{'─'*70}")
    print(f"{'Nota':}: Motor fast usa NumPy vectorizado. Original usa bucles Python.")
    print(f"{'─'*70}")

    # Objetivo final: 1M sims en < 60 segundos
    print("\n[TARGET CHECK] 1,000,000 sims en < 60s:")
    try:
        dt_1m, _ = run_fast(fast_groups, model, 1_000_000, n_workers=1)
        status = "✓ PASS" if dt_1m < 60 else "✗ FAIL"
        print(f"  Single-core: {dt_1m:.1f}s  {status}")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    ap = argparse.ArgumentParser(description="Benchmark Monte Carlo engines")
    ap.add_argument("--sims", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    ap.add_argument("--groups", type=int, default=12)
    ap.add_argument("--teams-per-group", type=int, default=4)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    benchmark(
        n_sims_list=args.sims,
        n_groups=args.groups,
        teams_per_group=args.teams_per_group,
        n_workers=args.workers,
    )


if __name__ == "__main__":
    main()
