"""
Expected Goals (xG) model — predicción de resultados basada en xG.

El modelo de xG convierte métricas de xG de equipo en probabilidades 1X2.

Enfoque:
  1. xG por equipo (ataque/defensa normalizado) → lambda de Poisson.
  2. Distribución conjunta de goles via Poisson bivariado (Dixon-Coles low-score fix).
  3. Suma marginal sobre la distribución → P(home_win), P(draw), P(away_win).

Fuentes de xG:
  - Understat: solo ligas europeas top (modelo publico).
  - StatsBomb: datos premium.
  - Estimado via regresión desde Dixon-Coles si no hay datos xG.

Las métricas xG por equipo/temporada se almacenan en la BD (tabla player_season_stats
o team_xg_stats cuando se añadan).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from scipy.stats import poisson


@dataclass
class TeamXGProfile:
    """Perfil ofensivo/defensivo xG por equipo."""
    name: str
    xg_for_per90: float = 1.30       # xG generado por 90 min (ataque)
    xg_against_per90: float = 1.10   # xG concedido por 90 min (defensa)
    xa_per90: float = 0.90           # xA (asistencias esperadas)
    shots_per90: float = 12.0        # disparos por 90 min
    shots_on_target_per90: float = 4.5
    conversion_rate: float = 0.115   # goles / disparos a portería
    n_matches: int = 0               # base estadística


class XGMatchPredictor:
    """
    Predicción 1X2 basada en Expected Goals.

    Convierte los perfiles xG de dos equipos en probabilidades de resultado
    usando distribuciones de Poisson + corrección de bajas puntuaciones.
    """

    HOME_XG_ADV = 0.15          # ventaja local en xG
    MAX_GOALS = 10              # goles máximos para la distribución
    RHO = -0.13                 # correlación Dixon-Coles (corrección bajas puntuaciones)

    def __init__(self):
        self.profiles: dict[str, TeamXGProfile] = {}

    def set_profile(self, profile: TeamXGProfile) -> None:
        self.profiles[profile.name] = profile

    def _lambda(
        self,
        attacking: TeamXGProfile,
        defending: TeamXGProfile,
        home: bool = True,
    ) -> float:
        """
        Lambda esperado = media geométrica de:
          - xG del ataque atacante (normalizado por xG promedio liga)
          - xG concedido por la defensa defensora (normalizado)
        + ventaja local si aplica.
        """
        league_avg_xg = 1.30  # prior de liga
        att_strength = attacking.xg_for_per90 / league_avg_xg
        def_weakness  = defending.xg_against_per90 / league_avg_xg

        lam = league_avg_xg * att_strength * def_weakness
        if home:
            lam += self.HOME_XG_ADV
        return max(lam, 0.01)

    def _dc_tau(self, x: int, y: int, lam: float, mu: float) -> float:
        """Corrección Dixon-Coles para bajas puntuaciones."""
        rho = self.RHO
        if x == 0 and y == 0:
            return 1.0 - lam * mu * rho
        if x == 0 and y == 1:
            return 1.0 + lam * rho
        if x == 1 and y == 0:
            return 1.0 + mu * rho
        if x == 1 and y == 1:
            return 1.0 - rho
        return 1.0

    def predict(
        self,
        home: str,
        away: str,
        neutral: bool = False,
    ) -> tuple[float, float, float]:
        """
        Retorna (p_home_win, p_draw, p_away_win) usando distribución Poisson.
        """
        p_h = self.profiles.get(home)
        p_a = self.profiles.get(away)

        if p_h is None or p_a is None:
            # Sin perfil xG: usar prior de liga
            p_h = p_h or TeamXGProfile(name=home)
            p_a = p_a or TeamXGProfile(name=away)

        lam = self._lambda(p_h, p_a, home=(not neutral))
        mu  = self._lambda(p_a, p_h, home=False)

        M = self.MAX_GOALS
        joint = np.zeros((M + 1, M + 1))

        for x in range(M + 1):
            for y in range(M + 1):
                tau = self._dc_tau(x, y, lam, mu)
                joint[x, y] = tau * poisson.pmf(x, lam) * poisson.pmf(y, mu)

        joint = np.maximum(joint, 0)
        joint /= joint.sum()

        p_home = float(np.tril(joint, -1).sum())
        p_draw = float(np.diag(joint).sum())
        p_away = float(np.triu(joint, 1).sum())

        s = p_home + p_draw + p_away
        if s > 0:
            p_home /= s; p_draw /= s; p_away /= s

        return p_home, p_draw, p_away

    def expected_goals(self, home: str, away: str, neutral: bool = False) -> tuple[float, float]:
        """Devuelve (lambda_home, lambda_away) esperados."""
        p_h = self.profiles.get(home, TeamXGProfile(name=home))
        p_a = self.profiles.get(away, TeamXGProfile(name=away))
        return (
            self._lambda(p_h, p_a, home=(not neutral)),
            self._lambda(p_a, p_h, home=False),
        )


def xg_from_dixon_coles(
    home: str,
    away: str,
    dc_params,
    neutral: bool = False,
) -> tuple[float, float]:
    """
    Estima xG usando los parámetros Dixon-Coles cuando no hay datos xG directos.
    dc_params: DixonColesParams con attack/defense por equipo.
    """
    if dc_params is None or home not in dc_params.attack:
        return 1.3, 1.1

    home_adv = 0.0 if neutral else dc_params.home_adv
    lam = math.exp(dc_params.attack.get(home, 0.0)
                   - dc_params.defense.get(away, 0.0)
                   + home_adv)
    mu  = math.exp(dc_params.attack.get(away, 0.0)
                   - dc_params.defense.get(home, 0.0))
    return lam, mu
