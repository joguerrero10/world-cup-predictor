"""
Bayesian Elo — actualización bayesiana de ratings con incertidumbre.

Extiende el Elo clásico con:
  - Distribución a priori sobre el rating (Gaussiana).
  - Actualización bayesiana del rating Y de la incertidumbre.
  - K-factor dinámico basado en incertidumbre (equipos nuevos → K más alto).
  - Intervalos de credibilidad (HDI 90%) por equipo.

Referencia: Glickman (1999) "Parameter estimation in large dynamic paired
comparison experiments", Journal of Applied Statistics.
(Nota: Glicko-2 extiende este modelo; ver glicko2.py)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

Result = Literal["home", "draw", "away"]


@dataclass
class BayesianRating:
    mu: float = 1500.0          # media del rating
    sigma: float = 200.0        # desviación estándar (incertidumbre)
    n_games: int = 0            # partidos jugados


class BayesianElo:
    """
    Sistema Elo con actualización bayesiana.

    La incertidumbre sigma decrece con cada partido jugado y crece
    si el equipo no juega (drift temporal, similar a Glicko).
    """

    Q_FACTOR = 400.0            # divisor Elo estándar
    HOME_ADV = 100.0            # ventaja local en puntos Elo
    BASE_K = 40.0               # K base
    K_UNCERTAINTY_SCALE = 2.0   # equipos con alta sigma → K más alto
    SIGMA_DECAY = 0.995         # decay de sigma por partido jugado
    SIGMA_DRIFT = 1.005         # drift de sigma por semana sin jugar
    MIN_SIGMA = 50.0
    MAX_SIGMA = 350.0
    DRAW_BASE = 0.25            # prob base de empate

    def __init__(self):
        self.ratings: dict[str, BayesianRating] = {}

    def _get_or_create(self, team: str) -> BayesianRating:
        if team not in self.ratings:
            self.ratings[team] = BayesianRating()
        return self.ratings[team]

    def expected_score(self, home: str, away: str, neutral: bool = False) -> float:
        """Probabilidad esperada de victoria local."""
        r_h = self._get_or_create(home)
        r_a = self._get_or_create(away)
        adv = 0.0 if neutral else self.HOME_ADV
        dr = (r_h.mu - r_a.mu) + adv
        return 1.0 / (1.0 + 10.0 ** (-dr / self.Q_FACTOR))

    def win_draw_loss(
        self,
        home: str,
        away: str,
        neutral: bool = False,
    ) -> tuple[float, float, float]:
        """1X2 con estimación bayesiana de empate."""
        r_h = self._get_or_create(home)
        r_a = self._get_or_create(away)

        # Incertidumbre combinada → amplía la masa de empate
        sigma_combined = math.sqrt(r_h.sigma ** 2 + r_a.sigma ** 2)
        draw_mass = self.DRAW_BASE + 0.05 * min(sigma_combined / 200.0, 1.0)

        e = self.expected_score(home, away, neutral)
        gap = abs(e - 0.5)
        p_draw = max(0.06, draw_mass * (1.0 - gap * 2.0))
        rest = 1.0 - p_draw
        p_home = rest * e
        p_away = rest * (1.0 - e)
        return p_home, p_draw, p_away

    def update(
        self,
        home: str,
        away: str,
        home_goals: int,
        away_goals: int,
        match_type: str = "friendly",
        neutral: bool = False,
        importance: dict[str, float] | None = None,
    ) -> None:
        """Actualiza los ratings tras un partido."""
        r_h = self._get_or_create(home)
        r_a = self._get_or_create(away)

        _importance = importance or {
            "friendly": 1.0, "qualifier": 1.5,
            "continental": 2.0, "world_cup_group": 2.5,
            "world_cup_knockout": 3.0,
        }
        importance_mult = _importance.get(match_type, 1.0)

        # K dinámico: equipos más inciertos reciben K más alto
        k_h = self.BASE_K * importance_mult * (1.0 + self.K_UNCERTAINTY_SCALE * r_h.sigma / 200.0)
        k_a = self.BASE_K * importance_mult * (1.0 + self.K_UNCERTAINTY_SCALE * r_a.sigma / 200.0)

        # Goal-difference multiplier
        gd = abs(home_goals - away_goals)
        g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11.0 + gd) / 8.0)

        e_h = self.expected_score(home, away, neutral)
        e_a = 1.0 - e_h

        # Resultado real
        if home_goals > away_goals:
            w_h, w_a = 1.0, 0.0
        elif home_goals < away_goals:
            w_h, w_a = 0.0, 1.0
        else:
            w_h, w_a = 0.5, 0.5

        delta_h = k_h * g * (w_h - e_h)
        delta_a = k_a * g * (w_a - e_a)

        r_h.mu += delta_h
        r_a.mu += delta_a

        # Reducir incertidumbre con cada partido (más información = menos sigma)
        r_h.sigma = max(self.MIN_SIGMA, r_h.sigma * self.SIGMA_DECAY)
        r_a.sigma = max(self.MIN_SIGMA, r_a.sigma * self.SIGMA_DECAY)
        r_h.n_games += 1
        r_a.n_games += 1

    def credible_interval(self, team: str, hdi: float = 0.90) -> tuple[float, float]:
        """Intervalo de credibilidad HDI para el rating de un equipo."""
        r = self._get_or_create(team)
        z = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}.get(hdi, 1.645)
        return r.mu - z * r.sigma, r.mu + z * r.sigma

    def rankings(self) -> list[dict]:
        """Tabla de rankings ordenada por media de rating."""
        rows = sorted(self.ratings.items(), key=lambda kv: kv[1].mu, reverse=True)
        return [
            {
                "rank": i + 1,
                "team": name,
                "rating": round(r.mu, 1),
                "sigma": round(r.sigma, 1),
                "games": r.n_games,
                "ci_low": round(r.mu - 1.645 * r.sigma, 1),
                "ci_high": round(r.mu + 1.645 * r.sigma, 1),
            }
            for i, (name, r) in enumerate(rows)
        ]
