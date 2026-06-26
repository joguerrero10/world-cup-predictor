"""
LeagueSimulator — Simulador genérico de ligas domésticas.

Soporta: Premier League, La Liga, Bundesliga, Serie A, Ligue 1.
Usa SOLO los clubes correctos de cada liga — nunca selecciones nacionales.

Características:
  - Round-robin doble (ida y vuelta) vectorizado.
  - Tabla de clasificación esperada por temporada.
  - Probabilidades por posición (campeón, top-4 UCL, relegación).
  - Goles esperados vía Poisson(lambda) por partido.
  - Multiprocessing automático para n_sims > 50_000.
"""
from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.simulation.base_simulator import BaseSimulator, BaseSimResult, MatchModel
from app.core.competition_registry import get_competition_teams
from app.models.competition import CompetitionConfig, get_competition


@dataclass
class TableRow:
    team: str
    position: float        # posición media
    pts: float             # puntos medios
    played: int
    gf: float              # goles a favor (media)
    ga: float              # goles en contra (media)
    gd: float              # diferencia de goles (media)
    won: float
    drawn: float
    lost: float


@dataclass
class LeagueResult(BaseSimResult):
    position_probs: dict[str, list[float]] = field(default_factory=dict)
    expected_table: list[TableRow] = field(default_factory=list)
    top_scorer_odds: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "position_probs": {
                team: [round(p, 4) for p in probs]
                for team, probs in self.position_probs.items()
            },
            "expected_table": [
                {
                    "position": round(r.position, 1),
                    "team": r.team,
                    "played": r.played,
                    "pts": round(r.pts, 1),
                    "won": round(r.won, 1),
                    "drawn": round(r.drawn, 1),
                    "lost": round(r.lost, 1),
                    "gf": round(r.gf, 1),
                    "ga": round(r.ga, 1),
                    "gd": round(r.gd, 1),
                }
                for r in self.expected_table
            ],
        })
        return d


class LeagueSimulator(BaseSimulator):
    """
    Simulador de liga doméstica.

    Args:
        competition_id: "premier_league" | "laliga" | "bundesliga" | "serie_a" | "ligue_1"
        model:  función de probabilidades 1X2
        season: año de inicio de temporada
        db:     SQLAlchemy Session (None = datos estáticos)
    """

    LAMBDA_HOME = 1.55   # prior goles locales si no hay Dixon-Coles
    LAMBDA_AWAY = 1.15   # prior goles visitante

    def __init__(
        self,
        competition_id: str,
        model: MatchModel,
        season: Optional[int] = None,
        db=None,
        lambda_home: float = 1.55,
        lambda_away: float = 1.15,
    ):
        teams_obj = get_competition_teams(competition_id, season, db)
        teams = [t.name for t in teams_obj]
        self._config: CompetitionConfig = get_competition(competition_id)

        super().__init__(
            competition_id=competition_id,
            teams=teams,
            model=model,
            neutral=False,
        )
        self.lambda_home = lambda_home
        self.lambda_away = lambda_away

    def _build_schedule(self) -> list[tuple[int, int]]:
        """Round-robin doble (ida y vuelta)."""
        n = self._n
        pairs = []
        for i in range(n):
            for j in range(n):
                if i != j:
                    pairs.append((i, j))
        return pairs

    def _build_schedule_probs(
        self,
        prob_matrix: np.ndarray,
        schedule: list[tuple[int, int]],
    ) -> np.ndarray:
        """Precomputa umbrales acumulados para todos los partidos: (n_matches, 2)."""
        n_m = len(schedule)
        p_cum = np.zeros((n_m, 2), dtype=np.float64)
        for k, (hi, ai) in enumerate(schedule):
            ph = prob_matrix[hi, ai, 0]
            pd = prob_matrix[hi, ai, 1]
            p_cum[k, 0] = ph
            p_cum[k, 1] = ph + pd
        return p_cum

    def run(self, n_sims: int = 10_000, seed: Optional[int] = None) -> LeagueResult:
        import time
        t0 = time.perf_counter()

        if n_sims > self.MULTIPROC_THRESHOLD:
            result = self._run_parallel(n_sims, seed)
        else:
            result = self._run_chunk(n_sims, seed)

        elapsed = time.perf_counter() - t0
        result.elapsed_seconds = elapsed
        result.sims_per_second = n_sims / elapsed if elapsed > 0 else 0
        return result

    def _run_chunk(self, n_sims: int, seed=None) -> LeagueResult:
        rng = np.random.default_rng(seed)
        prob_matrix = self._build_prob_matrix()
        n = self._n
        schedule = self._build_schedule()
        n_m = len(schedule)
        p_cum = self._build_schedule_probs(prob_matrix, schedule)

        # Acumuladores (n, n_sims)
        pts  = np.zeros((n, n_sims), dtype=np.int32)
        gf   = np.zeros((n, n_sims), dtype=np.float32)
        ga   = np.zeros((n, n_sims), dtype=np.float32)
        won  = np.zeros((n, n_sims), dtype=np.int32)
        drwn = np.zeros((n, n_sims), dtype=np.int32)
        lost = np.zeros((n, n_sims), dtype=np.int32)

        # Simular todos los partidos en batch
        rands = rng.random((n_m, n_sims))
        outcomes = np.zeros((n_m, n_sims), dtype=np.int8)
        outcomes[rands >= p_cum[:, 0:1]] = 1
        outcomes[rands >= p_cum[:, 1:2]] = 2

        # Goles: Poisson por partido
        # Generamos para todos los partidos en batch (más eficiente que por partido)
        goals_h = rng.poisson(self.lambda_home, (n_m, n_sims)).astype(np.float32)
        goals_a = rng.poisson(self.lambda_away, (n_m, n_sims)).astype(np.float32)
        # Ajustar goles para que sean consistentes con outcomes (no estrictamente necesario
        # para la clasificación, pero da tabla de goles más realista)
        # home_win → goals_h > goals_a (no garantizado con Poisson independiente)
        # Usamos los goles raw para stats, y los outcomes para puntos

        for k, (hi, ai) in enumerate(schedule):
            res = outcomes[k]
            home_win = res == 0
            draw     = res == 1
            away_win = res == 2

            pts[hi] += home_win * 3
            pts[hi] += draw
            pts[ai] += draw
            pts[ai] += away_win * 3

            won[hi]  += home_win; won[ai]  += away_win
            drwn[hi] += draw;     drwn[ai] += draw
            lost[hi] += away_win; lost[ai] += home_win

            gf[hi] += goals_h[k]; ga[ai] += goals_h[k]
            gf[ai] += goals_a[k]; ga[hi] += goals_a[k]

        # Tabla de clasificación: ordenar por pts + gd (desempate)
        gd = gf - ga
        noise = rng.random((n, n_sims)).astype(np.float32) * 0.001
        rank_key = pts.astype(np.float64) + gd.astype(np.float64) * 0.001 + noise.astype(np.float64)
        ranked = np.argsort(-rank_key, axis=0)        # (n, n_sims) posición → índice
        position_of = np.argsort(ranked, axis=0)      # (n, n_sims) índice → posición

        # Hitos
        rel = self._config.relegation_spots
        ucl = self._config.ucl_spots
        uel = ucl + self._config.uel_spots
        eu  = uel + self._config.uecl_spots

        champ_cnt = np.zeros(n, dtype=np.int64)
        top4_cnt  = np.zeros(n, dtype=np.int64)
        top6_cnt  = np.zeros(n, dtype=np.int64)
        rel_cnt   = np.zeros(n, dtype=np.int64)
        pos_cnt   = np.zeros((n, n), dtype=np.int64)

        for ti in range(n):
            pos = position_of[ti]           # (n_sims,) 0-indexed
            champ_cnt[ti] = (pos == 0).sum()
            top4_cnt[ti]  = (pos < ucl).sum() if ucl > 0 else 0
            top6_cnt[ti]  = (pos < eu).sum() if eu > 0 else 0
            rel_cnt[ti]   = (pos >= n - rel).sum() if rel > 0 else 0
            for p in range(n):
                pos_cnt[ti, p] = (pos == p).sum()

        # Tabla esperada
        avg_pts  = pts.mean(axis=1)
        avg_gf   = gf.mean(axis=1)
        avg_ga   = ga.mean(axis=1)
        avg_pos  = position_of.mean(axis=1)
        avg_won  = won.mean(axis=1)
        avg_drwn = drwn.mean(axis=1)
        avg_lost = lost.mean(axis=1)
        n_matches_per_team = len(schedule) / n   # debería ser n-1 * 2

        order = np.argsort(avg_pts)[::-1]
        expected_table = [
            TableRow(
                team=self.teams[ti],
                position=float(avg_pos[ti]) + 1,
                pts=float(avg_pts[ti]),
                played=int(n_matches_per_team),
                gf=float(avg_gf[ti]),
                ga=float(avg_ga[ti]),
                gd=float(avg_gf[ti] - avg_ga[ti]),
                won=float(avg_won[ti]),
                drawn=float(avg_drwn[ti]),
                lost=float(avg_lost[ti]),
            )
            for ti in order
        ]

        pct = lambda arr: {self.teams[i]: float(arr[i] / n_sims) for i in range(n)}

        return LeagueResult(
            competition=self.competition_id,
            n_sims=n_sims,
            elapsed_seconds=0.0,
            sims_per_second=0.0,
            champion=pct(champ_cnt),
            top4=pct(top4_cnt),
            top6=pct(top6_cnt),
            relegated=pct(rel_cnt),
            expected_table=expected_table,
            position_probs={
                self.teams[i]: [float(pos_cnt[i, p] / n_sims) for p in range(n)]
                for i in range(n)
            },
        )

    def _run_parallel(self, n_sims: int, seed=None) -> LeagueResult:
        n_workers = min(self.MAX_WORKERS, mp.cpu_count() or 1)
        chunk = n_sims // n_workers
        sizes = [chunk] * n_workers
        sizes[-1] += n_sims - sum(sizes)
        seeds = list(np.random.SeedSequence(seed).spawn(n_workers))

        args = [(self, sz, s) for sz, s in zip(sizes, seeds)]
        with mp.Pool(n_workers) as pool:
            partials = pool.starmap(_league_chunk_worker, args)

        return _merge_league_results(partials, n_sims)


def _league_chunk_worker(sim: LeagueSimulator, n_sims: int, seed) -> LeagueResult:
    return sim._run_chunk(n_sims, seed)


def _merge_league_results(results: list[LeagueResult], total: int) -> LeagueResult:
    teams = list(results[0].champion.keys())
    n = len(teams)
    weights = [r.n_sims for r in results]

    def _w(attr: str) -> dict[str, float]:
        dicts = [getattr(r, attr) for r in results]
        return {
            t: sum(d.get(t, 0.0) * w for d, w in zip(dicts, weights)) / total
            for t in teams
        }

    def _w_pos() -> dict[str, list[float]]:
        out = {}
        for t in teams:
            out[t] = [
                sum(r.position_probs.get(t, [0]*n)[p] * r.n_sims for r in results) / total
                for p in range(n)
            ]
        return out

    return LeagueResult(
        competition=results[0].competition,
        n_sims=total,
        elapsed_seconds=0.0,
        sims_per_second=0.0,
        champion=_w("champion"),
        top4=_w("top4"),
        top6=_w("top6"),
        relegated=_w("relegated"),
        position_probs=_w_pos(),
        expected_table=results[0].expected_table,  # usa el primero como referencia
    )
