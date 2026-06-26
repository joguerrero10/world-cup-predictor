"""
WorldCupSimulator — Simulador específico del FIFA World Cup 2026.

Formato real:
  - 48 equipos, 12 grupos de 4
  - Top 2 de cada grupo + 8 mejores terceros → 32 equipos
  - Fase eliminatoria: Octavos → Cuartos → Semis → Final
  - Penalty shootout en empate (50/50 simplificado)

Optimizaciones:
  - Matrices de probabilidad precalculadas fuera del bucle hot.
  - Todos los números aleatorios generados en una sola llamada numpy.
  - Multiprocessing automático para n_sims > 50_000.

Performance objetivo: 1M simulaciones en < 30 segundos (8 núcleos).
"""
from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from app.simulation.base_simulator import BaseSimulator, BaseSimResult, MatchModel
from app.core.competition_registry import get_competition_teams, get_competition_groups


@dataclass
class WorldCupResult(BaseSimResult):
    group_qualified: dict[str, float] = field(default_factory=dict)
    round_of_16: dict[str, float] = field(default_factory=dict)
    quarterfinal: dict[str, float] = field(default_factory=dict)
    expected_group_pts: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "group_qualified": self.group_qualified,
            "round_of_16": self.round_of_16,
            "quarterfinal": self.quarterfinal,
            "expected_group_pts": self.expected_group_pts,
        })
        return d


class WorldCupSimulator(BaseSimulator):
    """
    Simulador del Mundial FIFA 2026 (48 equipos, 12 grupos).

    Args:
        model: función (home, away, neutral) -> (p_home, p_draw, p_away)
        season: año (default 2026)
        db:     SQLAlchemy Session (None = usa datos estáticos)
    """

    COMPETITION_ID = "fifa_wc_2026"
    N_GROUPS = 12
    TEAMS_PER_GROUP = 4
    ADVANCE_PER_GROUP = 2        # top 2 de cada grupo
    N_THIRD_PLACE_ADVANCE = 8   # 8 mejores terceros

    def __init__(
        self,
        model: MatchModel,
        season: int = 2026,
        db=None,
    ):
        groups_dict = get_competition_groups(self.COMPETITION_ID, season, db)
        self._groups: dict[str, list[str]] = groups_dict or self._default_groups()
        all_teams = [t for teams in self._groups.values() for t in teams]

        super().__init__(
            competition_id=self.COMPETITION_ID,
            teams=all_teams,
            model=model,
            neutral=True,  # Mundial es sede neutral
        )
        self._group_list = sorted(self._groups.keys())

    def _default_groups(self) -> dict[str, list[str]]:
        return get_competition_groups(self.COMPETITION_ID)

    # ------------------------------------------------------------------
    # Simulación de fase de grupos (vectorizada)
    # ------------------------------------------------------------------

    def _simulate_groups_vectorized(
        self,
        prob_matrix: np.ndarray,
        n_sims: int,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Simula todos los grupos a la vez.

        Retorna:
          advancing  (24, n_sims) — índices de los 24 clasificados (2 por grupo)
          thirds     (12, n_sims) — índices de los 12 terceros
          qual_mask  (n_teams, n_sims) — bool si clasificó
          group_pts  (n_teams, n_sims) — puntos acumulados
        """
        n_teams = len(self.teams)
        qual_mask  = np.zeros((n_teams, n_sims), dtype=bool)
        group_pts  = np.zeros((n_teams, n_sims), dtype=np.int32)

        winners_list   = []   # (n_groups, n_sims) — índice del 1º de cada grupo
        runners_list   = []   # índices de 2º
        thirds_list    = []   # índices de 3º

        for group_name in self._group_list:
            group_teams = self._groups[group_name]
            g_idx = np.array([self._idx[t] for t in group_teams], dtype=np.int64)
            g = len(g_idx)

            # Todos los partidos del grupo (round-robin)
            pairs = [(i, j) for i in range(g) for j in range(i + 1, g)]
            n_m = len(pairs)

            # Probabilidades acumuladas para searchsorted
            p_cum = np.zeros((n_m, 2), dtype=np.float64)
            for k, (li, ri) in enumerate(pairs):
                ph = prob_matrix[g_idx[li], g_idx[ri], 0]
                pd = prob_matrix[g_idx[li], g_idx[ri], 1]
                p_cum[k, 0] = ph
                p_cum[k, 1] = ph + pd

            # Simular todos los partidos del grupo en batch
            rands = rng.random((n_m, n_sims))
            outcomes = np.zeros((n_m, n_sims), dtype=np.int8)
            outcomes[rands >= p_cum[:, 0:1]] = 1
            outcomes[rands >= p_cum[:, 1:2]] = 2

            # Acumular puntos locales: (g, n_sims)
            pts_local = np.zeros((g, n_sims), dtype=np.int32)
            for k, (li, ri) in enumerate(pairs):
                res = outcomes[k]
                pts_local[li] += (res == 0) * 3     # home win
                pts_local[li] += (res == 1)          # draw
                pts_local[ri] += (res == 1)          # draw
                pts_local[ri] += (res == 2) * 3      # away win

            # Acumular en tabla global
            for local_i, gi in enumerate(g_idx):
                group_pts[gi] += pts_local[local_i]

            # Ordenar dentro del grupo (desempate aleatorio)
            noise = rng.random((g, n_sims)) * 0.001
            rank_key = pts_local.astype(np.float64) + noise
            ranked = np.argsort(-rank_key, axis=0)   # (g, n_sims)

            # Mapa posición → índice global
            w_global = g_idx[ranked[0, :]]    # (n_sims,) ganadores
            r_global = g_idx[ranked[1, :]]    # runners-up
            t_global = g_idx[ranked[2, :]]    # terceros

            winners_list.append(w_global)
            runners_list.append(r_global)
            thirds_list.append(t_global)

            # Marcar clasificados (1º y 2º)
            for sim_i in range(n_sims):
                qual_mask[w_global[sim_i], sim_i] = True
                qual_mask[r_global[sim_i], sim_i] = True

        # Stack en arrays 2D
        winners_arr = np.stack(winners_list, axis=0)   # (n_groups, n_sims)
        runners_arr = np.stack(runners_list, axis=0)
        thirds_arr  = np.stack(thirds_list, axis=0)    # (n_groups, n_sims)

        # Interleaving del bracket: G1-W, G2-W, ..., G1-R, G2-R, ...
        # El orden real del bracket del Mundial sigue un sorteo, simplificamos
        advancing = np.vstack([winners_arr, runners_arr])  # (24, n_sims)

        # Seleccionar los 8 mejores terceros por puntos
        # pts_thirds: (n_groups, n_sims)
        pts_thirds = np.zeros((self.N_GROUPS, n_sims), dtype=np.int32)
        for gi_idx in range(self.N_GROUPS):
            t_gidx = thirds_arr[gi_idx]   # (n_sims,) índices globales de los terceros
            pts_thirds[gi_idx] = group_pts[t_gidx, np.arange(n_sims)]

        # top 8 terceros por puntos (con ruido para desempate)
        noise3 = rng.random((self.N_GROUPS, n_sims)) * 0.001
        rank_thirds = np.argsort(-(pts_thirds.astype(np.float64) + noise3), axis=0)
        best_thirds_local = rank_thirds[:self.N_THIRD_PLACE_ADVANCE, :]   # (8, n_sims)
        best_thirds_global = np.zeros_like(best_thirds_local)
        for r in range(self.N_THIRD_PLACE_ADVANCE):
            for s in range(n_sims):
                group_local_i = best_thirds_local[r, s]
                best_thirds_global[r, s] = thirds_arr[group_local_i, s]
            qual_mask[best_thirds_global[r, :], np.arange(n_sims)] = True

        # bracket final: 24 (top2) + 8 (mejores 3ros) = 32 equipos
        full_bracket = np.vstack([advancing, best_thirds_global])  # (32, n_sims)

        return full_bracket, thirds_arr, qual_mask, group_pts

    # ------------------------------------------------------------------
    # run() — API principal
    # ------------------------------------------------------------------

    def run(self, n_sims: int = 10_000, seed: Optional[int] = None) -> WorldCupResult:
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

    def _run_chunk(self, n_sims: int, seed=None) -> WorldCupResult:
        """Ejecuta n_sims en un solo proceso."""
        rng = np.random.default_rng(seed)
        prob_matrix = self._build_prob_matrix()
        n_teams = len(self.teams)

        # Contadores
        champ_cnt  = np.zeros(n_teams, dtype=np.int64)
        final_cnt  = np.zeros(n_teams, dtype=np.int64)
        semi_cnt   = np.zeros(n_teams, dtype=np.int64)
        r16_cnt    = np.zeros(n_teams, dtype=np.int64)
        qual_cnt   = np.zeros(n_teams, dtype=np.int64)
        pts_sum    = np.zeros(n_teams, dtype=np.float64)

        # Fase de grupos
        bracket, thirds_arr, qual_mask, group_pts = self._simulate_groups_vectorized(
            prob_matrix, n_sims, rng
        )

        # Acumular clasificados de grupo
        for ti in range(n_teams):
            qual_cnt[ti] += qual_mask[ti].sum()

        pts_sum += group_pts.sum(axis=1)

        # R16 → track quiénes entran al bracket
        np.add.at(r16_cnt, bracket.ravel(), 1)

        # Simulación eliminatoria: R16 → QF → SF → Final → Campeón
        champ, finals, semis, _ = self._simulate_full_knockout(bracket, prob_matrix, rng)

        np.add.at(champ_cnt, champ, 1)
        if finals.shape[0] > 0:
            np.add.at(final_cnt, finals.ravel(), 1)
        if semis.shape[0] > 0:
            np.add.at(semi_cnt, semis.ravel(), 1)

        pct = lambda arr: {self.teams[i]: float(arr[i] / n_sims) for i in range(n_teams)}

        return WorldCupResult(
            competition=self.COMPETITION_ID,
            n_sims=n_sims,
            elapsed_seconds=0.0,
            sims_per_second=0.0,
            champion=pct(champ_cnt),
            finalist=pct(final_cnt),
            semifinalist=pct(semi_cnt),
            top4=pct(semi_cnt),
            group_qualified=pct(qual_cnt),
            round_of_16={self.teams[i]: float(r16_cnt[i] / n_sims) for i in range(n_teams)},
            quarterfinal=pct(semi_cnt),
            expected_group_pts={self.teams[i]: float(pts_sum[i] / n_sims) for i in range(n_teams)},
        )

    def _run_parallel(self, n_sims: int, seed=None) -> WorldCupResult:
        """Divide el trabajo en workers."""
        n_workers = min(self.MAX_WORKERS, mp.cpu_count() or 1)
        chunk = n_sims // n_workers
        sizes = [chunk] * n_workers
        sizes[-1] += n_sims - sum(sizes)

        seeds = list(np.random.SeedSequence(seed).spawn(n_workers))

        args = [(self, sz, s) for sz, s in zip(sizes, seeds)]
        with mp.Pool(n_workers) as pool:
            partials = pool.starmap(_wc_chunk_worker, args)

        return _merge_wc_results(partials, n_sims)


def _wc_chunk_worker(sim: WorldCupSimulator, n_sims: int, seed) -> WorldCupResult:
    return sim._run_chunk(n_sims, seed)


def _merge_wc_results(results: list[WorldCupResult], total: int) -> WorldCupResult:
    teams = list(results[0].champion.keys())
    weights = [r.n_sims for r in results]

    def _w(attr: str) -> dict[str, float]:
        dicts = [getattr(r, attr) for r in results]
        return {
            t: sum(d.get(t, 0.0) * w for d, w in zip(dicts, weights)) / total
            for t in teams
        }

    return WorldCupResult(
        competition=results[0].competition,
        n_sims=total,
        elapsed_seconds=0.0,
        sims_per_second=0.0,
        champion=_w("champion"),
        finalist=_w("finalist"),
        semifinalist=_w("semifinalist"),
        top4=_w("top4"),
        group_qualified=_w("group_qualified"),
        round_of_16=_w("round_of_16"),
        quarterfinal=_w("quarterfinal"),
        expected_group_pts=_w("expected_group_pts"),
    )
