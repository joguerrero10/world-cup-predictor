"""
Clase base para todos los simuladores de competición.

Define la interfaz común + utilidades compartidas de vectorización NumPy.
Cada simulador concreto implementa _run_single() y puede sobrescribir run().
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

MatchModel = Callable[[str, str, bool], tuple[float, float, float]]


@dataclass
class BaseSimResult:
    competition: str
    n_sims: int
    elapsed_seconds: float
    sims_per_second: float
    champion: dict[str, float] = field(default_factory=dict)
    finalist: dict[str, float] = field(default_factory=dict)
    semifinalist: dict[str, float] = field(default_factory=dict)
    top4: dict[str, float] = field(default_factory=dict)
    top6: dict[str, float] = field(default_factory=dict)
    relegated: dict[str, float] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "competition": self.competition,
            "n_sims": self.n_sims,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "sims_per_second": round(self.sims_per_second, 0),
            "champion": self.champion,
            "finalist": self.finalist,
            "semifinalist": self.semifinalist,
            "top4": self.top4,
            "top6": self.top6,
            "relegated": self.relegated,
            **self.extra,
        }


class BaseSimulator(ABC):
    """
    Simulador base con:
    - Precálculo de matriz de probabilidades.
    - División automática de trabajo en chunks.
    - Paralelismo vía multiprocessing.Pool cuando n_sims > 50_000.
    """

    MULTIPROC_THRESHOLD = 50_000
    MAX_WORKERS = min(os.cpu_count() or 1, 8)

    def __init__(
        self,
        competition_id: str,
        teams: list[str],
        model: MatchModel,
        neutral: bool = False,
    ):
        self.competition_id = competition_id
        self.teams = teams
        self.model = model
        self.neutral = neutral
        self._n = len(teams)
        self._idx: dict[str, int] = {t: i for i, t in enumerate(teams)}
        self._prob_matrix: Optional[np.ndarray] = None

    def _build_prob_matrix(self) -> np.ndarray:
        """Precalcula (N, N, 3) con todas las probabilidades 1X2."""
        if self._prob_matrix is not None:
            return self._prob_matrix

        n = self._n
        matrix = np.zeros((n, n, 3), dtype=np.float64)
        for i, home in enumerate(self.teams):
            for j, away in enumerate(self.teams):
                if i == j:
                    continue
                ph, pd, pa = self.model(home, away, self.neutral)
                s = ph + pd + pa
                if s > 0:
                    matrix[i, j] = [ph / s, pd / s, pa / s]
                else:
                    matrix[i, j] = [1 / 3, 1 / 3, 1 / 3]

        self._prob_matrix = matrix
        return matrix

    def _ko_round_vectorized(
        self,
        bracket: np.ndarray,           # (n_teams, n_sims)
        prob_matrix: np.ndarray,
        rng: np.random.Generator,
        penalties_50_50: bool = True,
    ) -> np.ndarray:
        """
        Simula una ronda de eliminatoria.
        bracket: (n_teams, n_sims) — n_teams debe ser par.
        Retorna: (n_teams/2, n_sims) — ganadores.
        """
        n_pairs = bracket.shape[0] // 2
        n_sims = bracket.shape[1]

        home_idx = bracket[0::2, :]    # (n_pairs, n_sims)
        away_idx = bracket[1::2, :]    # (n_pairs, n_sims)

        flat_h = home_idx.ravel()
        flat_a = away_idx.ravel()

        probs = prob_matrix[flat_h, flat_a]     # (n_pairs*n_sims, 3)
        p_home = probs[:, 0].reshape(n_pairs, n_sims)
        p_draw = probs[:, 1].reshape(n_pairs, n_sims)

        if penalties_50_50:
            p_home_ko = p_home + p_draw * 0.5
        else:
            p_home_ko = p_home

        rands = rng.random((n_pairs, n_sims))
        home_wins = rands < p_home_ko
        return np.where(home_wins, home_idx, away_idx)

    def _simulate_full_knockout(
        self,
        bracket: np.ndarray,           # (n_teams, n_sims)
        prob_matrix: np.ndarray,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Simula eliminatoria completa hasta campeón.
        Retorna (champion, finalists, semifinalists, quarterfinalists).
        """
        n_total, n_sims = bracket.shape

        round_teams = bracket.copy()
        semi_arr   = np.full((4, n_sims), -1, dtype=np.int64)
        final_arr  = np.full((2, n_sims), -1, dtype=np.int64)
        champ_arr  = np.full(n_sims, -1, dtype=np.int64)

        while round_teams.shape[0] > 1:
            n = round_teams.shape[0]
            if n == 4:
                semi_arr = round_teams.copy()
            elif n == 2:
                final_arr = round_teams.copy()

            round_teams = self._ko_round_vectorized(round_teams, prob_matrix, rng)

        if round_teams.shape[0] == 1:
            champ_arr = round_teams[0]

        return champ_arr, final_arr, semi_arr, np.empty((0, n_sims), dtype=np.int64)

    @abstractmethod
    def run(self, n_sims: int, seed: Optional[int] = None) -> BaseSimResult:
        """Ejecuta la simulación completa."""
        ...

    def _timed_run(self, n_sims: int, seed: Optional[int] = None) -> BaseSimResult:
        t0 = time.perf_counter()
        result = self.run(n_sims, seed)
        elapsed = time.perf_counter() - t0
        result.elapsed_seconds = elapsed
        result.sims_per_second = n_sims / elapsed if elapsed > 0 else 0
        return result
