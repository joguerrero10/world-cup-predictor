"""
Glicko-2 — Sistema de rating más preciso que Elo.

Referencia: Glickman (2001) "Dynamic paired comparison models with stochastic variances",
Journal of Applied Statistics, 28(6), 673-689.

Escala Glicko-2:
  - Rating μ (equivalente a Elo ÷ 173.7178)
  - Desviación RD φ (incertidumbre)
  - Volatilidad σ (consistencia del jugador/equipo)

Diferencias clave vs Elo:
  - RD crece cuando el equipo no juega (incertidumbre temporal).
  - Volatilidad σ captura si el equipo tiene resultados inesperados.
  - Actualización periódica por rating period (temporada, mes, etc.).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# Constantes del sistema Glicko-2
_Q = math.log(10) / 400.0    # factor de conversión Glicko → Glicko-2
_ELO_TO_G2 = 173.7178         # escala: rating_g2 = (rating_elo - 1500) / 173.7178


@dataclass
class Glicko2Rating:
    mu: float = 0.0           # rating (escala Glicko-2, μ=0 ≡ Elo 1500)
    phi: float = 2.014761     # RD (desviación estándar), φ=2.01 ≡ RD 350
    sigma: float = 0.06       # volatilidad
    n_games: int = 0

    @property
    def elo(self) -> float:
        """Rating en escala Elo (1500-base)."""
        return self.mu * _ELO_TO_G2 + 1500.0

    @property
    def rd(self) -> float:
        """Rating Deviation en escala Glicko-1 original."""
        return self.phi * _ELO_TO_G2

    @classmethod
    def from_elo(cls, elo: float, rd: float = 200.0, sigma: float = 0.06) -> "Glicko2Rating":
        return cls(
            mu=(elo - 1500.0) / _ELO_TO_G2,
            phi=rd / _ELO_TO_G2,
            sigma=sigma,
        )


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi ** 2 / math.pi ** 2)


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _expected_outcome(r: Glicko2Rating, opp: Glicko2Rating, home: bool = True) -> float:
    """Probabilidad esperada de victoria (sin empate)."""
    home_adv = 0.5 if home else -0.5   # ligera ventaja local en escala g2
    return _e(r.mu + home_adv, opp.mu, opp.phi)


class Glicko2System:
    """
    Sistema Glicko-2 para rating de equipos de fútbol.

    Uso:
        system = Glicko2System()
        system.update_period(results_of_the_month)
        probs = system.win_draw_loss("Liverpool", "Arsenal")
    """

    TAU = 0.5           # constraint de cambio de volatilidad (0.3-1.2 típico)
    C = 63.2            # drift de RD por período sin jugar (en escala Elo)
    HOME_ADV_ELO = 80.0 # ventaja local en puntos Elo
    DRAW_BASE = 0.25
    EPSILON = 1e-6

    def __init__(self, tau: float = 0.5):
        self.tau = tau
        self.ratings: dict[str, Glicko2Rating] = {}

    def _get_or_create(self, team: str) -> Glicko2Rating:
        if team not in self.ratings:
            self.ratings[team] = Glicko2Rating()
        return self.ratings[team]

    def win_draw_loss(
        self,
        home: str,
        away: str,
        neutral: bool = False,
    ) -> tuple[float, float, float]:
        """Probabilidades 1X2."""
        r_h = self._get_or_create(home)
        r_a = self._get_or_create(away)

        home_adv_g2 = 0.0 if neutral else self.HOME_ADV_ELO / _ELO_TO_G2
        e_h = _e(r_h.mu + home_adv_g2, r_a.mu, r_a.phi)
        gap = abs(e_h - 0.5)

        # RD combinado → más incertidumbre = más empates
        phi_combined = math.sqrt(r_h.phi ** 2 + r_a.phi ** 2)
        draw_mass = min(self.DRAW_BASE + 0.03 * phi_combined, 0.40)
        p_draw = max(0.06, draw_mass * (1.0 - gap * 2.0))
        rest = 1.0 - p_draw
        return rest * e_h, p_draw, rest * (1.0 - e_h)

    def update_period(
        self,
        results: Sequence[tuple[str, str, float]],
        home_advantage: float = 80.0,
    ) -> None:
        """
        Actualiza todos los ratings para un período completo.

        Args:
            results: lista de (home_team, away_team, score)
                     score: 1.0=home_win, 0.5=draw, 0.0=away_win
            home_advantage: puntos Elo de ventaja local
        """
        # Acumular resultados por equipo para el período
        period_results: dict[str, list[tuple[Glicko2Rating, float]]] = {}
        home_adv_g2 = home_advantage / _ELO_TO_G2

        for home, away, score in results:
            r_h = self._get_or_create(home)
            r_a = self._get_or_create(away)
            period_results.setdefault(home, []).append((r_a, score))
            period_results.setdefault(away, []).append((r_h, 1.0 - score))

        # Aplicar drift a equipos que no jugaron este período
        for team in self.ratings:
            if team not in period_results:
                r = self.ratings[team]
                # RD aumenta con el tiempo (incertidumbre temporal)
                phi_new = math.sqrt(r.phi ** 2 + (self.C / _ELO_TO_G2) ** 2)
                r.phi = min(phi_new, 350.0 / _ELO_TO_G2)

        # Actualizar los que sí jugaron
        for team, opponents_scores in period_results.items():
            self._update_team(team, opponents_scores, home_adv_g2)

    def _update_team(
        self,
        team: str,
        opponents_scores: list[tuple[Glicko2Rating, float]],
        home_adv_g2: float = 0.0,
    ) -> None:
        """Aplica la actualización Glicko-2 a un equipo para un período."""
        r = self.ratings[team]

        if not opponents_scores:
            # Sin partidos: solo drift de RD
            phi_star = math.sqrt(r.phi ** 2 + r.sigma ** 2)
            r.phi = phi_star
            return

        # Paso 1: calcular v (varianza de las actualizaciones)
        v_inv = sum(
            _g(opp.phi) ** 2 * _e(r.mu, opp.mu, opp.phi) * (1.0 - _e(r.mu, opp.mu, opp.phi))
            for opp, _ in opponents_scores
        )
        v = 1.0 / v_inv if v_inv > self.EPSILON else 1e6

        # Paso 2: delta (mejora estimada)
        delta = v * sum(
            _g(opp.phi) * (s - _e(r.mu, opp.mu, opp.phi))
            for opp, s in opponents_scores
        )

        # Paso 3: nueva volatilidad σ' (Illinois algorithm)
        a = math.log(r.sigma ** 2)
        phi_sq = r.phi ** 2
        delta_sq = delta ** 2
        tau_sq = self.tau ** 2

        def f(x: float) -> float:
            ex = math.exp(x)
            denom = (phi_sq + v + ex)
            return (
                ex * (delta_sq - phi_sq - v - ex) / (2.0 * denom ** 2)
                - (x - a) / tau_sq
            )

        A = a
        B = math.log(delta_sq - phi_sq - v) if delta_sq > phi_sq + v else a - self.tau
        f_A, f_B = f(A), f(B)
        for _ in range(100):
            C = A + (A - B) * f_A / (f_B - f_A)
            f_C = f(C)
            if f_C * f_B < 0:
                A, f_A = B, f_B
            else:
                f_A /= 2
            B, f_B = C, f_C
            if abs(B - A) < self.EPSILON:
                break
        sigma_new = math.exp(A / 2.0)

        # Paso 4: phi* = sqrt(phi² + sigma'²)
        phi_star = math.sqrt(r.phi ** 2 + sigma_new ** 2)

        # Paso 5: nueva phi y mu
        phi_new = 1.0 / math.sqrt(1.0 / phi_star ** 2 + 1.0 / v)
        mu_new = r.mu + phi_new ** 2 * sum(
            _g(opp.phi) * (s - _e(r.mu, opp.mu, opp.phi))
            for opp, s in opponents_scores
        )

        r.mu = mu_new
        r.phi = phi_new
        r.sigma = sigma_new
        r.n_games += len(opponents_scores)

    def rankings(self) -> list[dict]:
        rows = sorted(self.ratings.items(), key=lambda kv: kv[1].elo, reverse=True)
        return [
            {
                "rank": i + 1,
                "team": name,
                "elo": round(r.elo, 1),
                "rd": round(r.rd, 1),
                "sigma": round(r.sigma, 4),
                "games": r.n_games,
                "ci_low": round(r.elo - 1.96 * r.rd, 1),
                "ci_high": round(r.elo + 1.96 * r.rd, 1),
            }
            for i, (name, r) in enumerate(rows)
        ]
