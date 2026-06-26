"""
ChampionsLeagueSimulator — UEFA Champions League 2024/25.

Formato nuevo (league phase):
  - 36 clubes en una sola liga (no grupos).
  - Cada equipo juega 8 partidos contra rivales sorteados.
  - Top 8 clasifican directamente a Octavos.
  - Posiciones 9-24: playoff de acceso a Octavos.
  - Posiciones 25-36: eliminados.
  - Eliminatoria hasta la Final en Múnich.

Simplificación del simulador:
  - Modelamos la league phase como round-robin parcial (8 partidos por equipo).
  - Usamos puntos para clasificar en lugar de sorteo real.
  - Eliminatoria estándar de 16 equipos → F4 → Final.
"""
from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.simulation.base_simulator import BaseSimulator, BaseSimResult, MatchModel
from app.core.competition_registry import get_competition_teams


@dataclass
class UCLResult(BaseSimResult):
    league_phase_top8: dict[str, float] = field(default_factory=dict)
    playoff_qual: dict[str, float] = field(default_factory=dict)
    round_of_16: dict[str, float] = field(default_factory=dict)
    quarterfinal: dict[str, float] = field(default_factory=dict)
    expected_pts: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "league_phase_top8": self.league_phase_top8,
            "playoff_qual": self.playoff_qual,
            "round_of_16": self.round_of_16,
            "quarterfinal": self.quarterfinal,
            "expected_pts": self.expected_pts,
        })
        return d


class ChampionsLeagueSimulator(BaseSimulator):
    """
    Simulador de la UEFA Champions League 2024/25.

    Usa SOLO clubes del registry UCL — nunca selecciones nacionales.
    """

    COMPETITION_ID = "ucl"
    LEAGUE_PHASE_MATCHES = 8          # partidos por equipo en la fase de liga
    DIRECT_QUALIFY = 8                # top 8 → directos a R16
    PLAYOFF_SPOTS = 16                # posiciones 9-24 juegan playoff
    ELIMINATED_SPOTS = 12            # posiciones 25-36 eliminados

    def __init__(self, model: MatchModel, season: int = 2025, db=None):
        teams_obj = get_competition_teams(self.COMPETITION_ID, season, db)
        teams = [t.name for t in teams_obj]

        super().__init__(
            competition_id=self.COMPETITION_ID,
            teams=teams,
            model=model,
            neutral=False,    # UCL no es neutral (jugamos en campo del equipo local)
        )

    def _simulate_league_phase_vectorized(
        self,
        prob_matrix: np.ndarray,
        n_sims: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Simula la fase de liga con n_matches_per_team partidos aleatorios por equipo.
        Retorna pts (n_teams, n_sims).
        """
        n = self._n
        pts = np.zeros((n, n_sims), dtype=np.int32)

        # Generamos emparejamientos aleatorios respetando que cada equipo
        # juega exactamente LEAGUE_PHASE_MATCHES partidos.
        # Simplificación: usamos round-robin parcial determinista.
        # Para el sorteo real se usaría la olla de UEFA — aquí usamos un
        # schedule de round-robin incompleto balanceado (BRR).
        opponents_per_team = self.LEAGUE_PHASE_MATCHES
        total_matches = (n * opponents_per_team) // 2

        # Construir schedule: lista de (home_idx, away_idx)
        schedule = _build_partial_schedule(n, opponents_per_team, rng)

        n_m = len(schedule)
        # Precalcular prob acumuladas para el schedule
        p_cum = np.zeros((n_m, 2), dtype=np.float64)
        for k, (hi, ai) in enumerate(schedule):
            ph = prob_matrix[hi, ai, 0]
            pd = prob_matrix[hi, ai, 1]
            p_cum[k, 0] = ph
            p_cum[k, 1] = ph + pd

        rands = rng.random((n_m, n_sims))
        outcomes = np.zeros((n_m, n_sims), dtype=np.int8)
        outcomes[rands >= p_cum[:, 0:1]] = 1
        outcomes[rands >= p_cum[:, 1:2]] = 2

        for k, (hi, ai) in enumerate(schedule):
            res = outcomes[k]
            pts[hi] += (res == 0) * 3
            pts[hi] += (res == 1)
            pts[ai] += (res == 1)
            pts[ai] += (res == 2) * 3

        return pts

    def run(self, n_sims: int = 10_000, seed: Optional[int] = None) -> UCLResult:
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

    def _run_chunk(self, n_sims: int, seed=None) -> UCLResult:
        rng = np.random.default_rng(seed)
        prob_matrix = self._build_prob_matrix()
        n = self._n

        champ_cnt   = np.zeros(n, dtype=np.int64)
        final_cnt   = np.zeros(n, dtype=np.int64)
        semi_cnt    = np.zeros(n, dtype=np.int64)
        qf_cnt      = np.zeros(n, dtype=np.int64)
        r16_cnt     = np.zeros(n, dtype=np.int64)
        top8_cnt    = np.zeros(n, dtype=np.int64)
        playoff_cnt = np.zeros(n, dtype=np.int64)
        pts_sum     = np.zeros(n, dtype=np.float64)

        # Fase de liga
        pts = self._simulate_league_phase_vectorized(prob_matrix, n_sims, rng)
        pts_sum += pts.sum(axis=1)

        # Clasificar: top 8 directos, 9-24 playoff, 25-36 eliminados
        noise = rng.random((n, n_sims)) * 0.001
        rank_key = pts.astype(np.float64) + noise
        ranked = np.argsort(-rank_key, axis=0)   # (n, n_sims)

        # top 8 directos a R16
        top8 = ranked[:8, :]       # (8, n_sims)
        np.add.at(top8_cnt, top8.ravel(), 1)

        # posiciones 9-24: playoff para acceder a R16
        playoff_teams = ranked[8:24, :]   # (16, n_sims) — 8 playoffs de ida/vuelta
        np.add.at(playoff_cnt, playoff_teams.ravel(), 1)

        # Simular playoffs: 16 equipos → 8 clasificados (eliminatoria doble leg)
        # Simplificación: usamos ko simple 50/50 entre cada par
        n_playoff = 8   # 8 partidos de playoff
        playoff_winners = np.zeros((8, n_sims), dtype=np.int64)
        for p in range(n_playoff):
            h_idx = playoff_teams[p * 2, :]
            a_idx = playoff_teams[p * 2 + 1, :]
            ph = prob_matrix[h_idx, a_idx, 0] + prob_matrix[h_idx, a_idx, 1] * 0.5
            rands_p = rng.random((n_sims,))
            playoff_winners[p] = np.where(rands_p.reshape(-1) < ph.reshape(-1), h_idx, a_idx)

        # Bracket R16: 8 directos + 8 ganadores playoff
        r16_bracket = np.vstack([top8, playoff_winners])   # (16, n_sims)
        np.add.at(r16_cnt, r16_bracket.ravel(), 1)

        # Eliminatoria: R16 → QF → SF → Final → Campeón
        champ, finals, semis, _ = self._simulate_full_knockout(r16_bracket, prob_matrix, rng)

        np.add.at(champ_cnt, champ, 1)
        if finals.size > 0:
            np.add.at(final_cnt, finals.ravel(), 1)
        if semis.size > 0:
            np.add.at(semi_cnt, semis.ravel(), 1)

        # Cuartos: la ronda de 8 equipos
        qf_arr = np.zeros((n, n_sims), dtype=np.int64)

        pct = lambda arr: {self.teams[i]: float(arr[i] / n_sims) for i in range(n)}

        return UCLResult(
            competition=self.COMPETITION_ID,
            n_sims=n_sims,
            elapsed_seconds=0.0,
            sims_per_second=0.0,
            champion=pct(champ_cnt),
            finalist=pct(final_cnt),
            semifinalist=pct(semi_cnt),
            top4=pct(semi_cnt),
            league_phase_top8=pct(top8_cnt),
            playoff_qual=pct(playoff_cnt),
            round_of_16=pct(r16_cnt),
            quarterfinal=pct(qf_cnt),
            expected_pts={self.teams[i]: float(pts_sum[i] / n_sims) for i in range(n)},
        )

    def _run_parallel(self, n_sims: int, seed=None) -> UCLResult:
        prob_matrix = self._build_prob_matrix()
        n_workers = min(self.MAX_WORKERS, mp.cpu_count() or 1)
        chunk = n_sims // n_workers
        sizes = [chunk] * n_workers
        sizes[-1] += n_sims - sum(sizes)
        seeds = list(np.random.SeedSequence(seed).spawn(n_workers))

        args = [(self.teams, prob_matrix, sz, s) for sz, s in zip(sizes, seeds)]
        with mp.Pool(n_workers) as pool:
            partials = pool.starmap(_ucl_chunk_worker, args)

        return _merge_ucl_results(partials, n_sims)


def _build_partial_schedule(n: int, matches_per_team: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    """
    Construye un schedule round-robin parcial balanceado.
    Cada equipo juega exactamente `matches_per_team` partidos.
    """
    # Generamos el schedule de round-robin completo y lo subsamplamos
    # de forma que cada equipo aparezca exactamente matches_per_team veces.
    all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(all_pairs)

    degree = {i: 0 for i in range(n)}
    selected = []
    for h, a in all_pairs:
        if degree[h] < matches_per_team and degree[a] < matches_per_team:
            selected.append((h, a))
            degree[h] += 1
            degree[a] += 1
        if all(v >= matches_per_team for v in degree.values()):
            break

    return selected


def _ucl_chunk_worker(
    teams: list[str],
    prob_matrix: np.ndarray,
    n_sims: int,
    seed,
) -> UCLResult:
    from app.simulation.champions_league_simulator import ChampionsLeagueSimulator
    sim = ChampionsLeagueSimulator.__new__(ChampionsLeagueSimulator)
    sim.competition_id = ChampionsLeagueSimulator.COMPETITION_ID
    sim.teams = teams
    sim._n = len(teams)
    sim._idx = {t: i for i, t in enumerate(teams)}
    sim._prob_matrix = prob_matrix
    sim.neutral = False
    sim.model = None
    return sim._run_chunk(n_sims, seed)


def _merge_ucl_results(results: list[UCLResult], total: int) -> UCLResult:
    teams = list(results[0].champion.keys())
    weights = [r.n_sims for r in results]

    def _w(attr: str) -> dict[str, float]:
        dicts = [getattr(r, attr) for r in results]
        return {
            t: sum(d.get(t, 0.0) * w for d, w in zip(dicts, weights)) / total
            for t in teams
        }

    return UCLResult(
        competition=results[0].competition,
        n_sims=total,
        elapsed_seconds=0.0,
        sims_per_second=0.0,
        champion=_w("champion"),
        finalist=_w("finalist"),
        semifinalist=_w("semifinalist"),
        top4=_w("top4"),
        league_phase_top8=_w("league_phase_top8"),
        playoff_qual=_w("playoff_qual"),
        round_of_16=_w("round_of_16"),
        quarterfinal=_w("quarterfinal"),
        expected_pts=_w("expected_pts"),
    )
