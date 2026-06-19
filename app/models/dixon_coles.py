"""
Dixon-Coles model for football scorelines.

Reference: Dixon, M.J. & Coles, S.G. (1997), "Modelling Association Football
Scores and Inefficiencies in the Football Betting Market", Journal of the Royal
Statistical Society: Series C (Applied Statistics), 46(2), 265-280.

Model:
    home goals X ~ Poisson(lambda),  away goals Y ~ Poisson(mu)
    lambda = exp(attack_home - defence_away + gamma)   # gamma = home advantage
    mu     = exp(attack_away - defence_home)
    P(X=x, Y=y) = tau(x, y; lambda, mu, rho) * Pois(x; lambda) * Pois(y; mu)

The tau term inflates/deflates the four low-score cells (0-0, 0-1, 1-0, 1-1) that
an independent-Poisson model fits poorly. Parameters are estimated by maximum
likelihood, optionally with exponential time-decay weights (Dixon-Coles xi).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, lgamma, log
from typing import Sequence

import numpy as np
from scipy.optimize import minimize


def _pois_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(k * log(lam) - lam - lgamma(k + 1))


def tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles low-score correction."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


@dataclass
class DixonColesParams:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    home_adv: float
    rho: float


class DixonColes:
    def __init__(self, max_goals: int = 10):
        self.max_goals = max_goals
        self.params: DixonColesParams | None = None

    # ---- fitting -------------------------------------------------------------
    def fit(
        self,
        home_teams: Sequence[str],
        away_teams: Sequence[str],
        home_goals: Sequence[int],
        away_goals: Sequence[int],
        weights: Sequence[float] | None = None,
    ) -> DixonColesParams:
        teams = sorted(set(home_teams) | set(away_teams))
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        hg = np.asarray(home_goals, dtype=int)
        ag = np.asarray(away_goals, dtype=int)
        hi = np.array([idx[t] for t in home_teams])
        ai = np.array([idx[t] for t in away_teams])
        w = np.ones(len(hg)) if weights is None else np.asarray(weights, dtype=float)

        # Param vector: [attack(n), defense(n), home_adv, rho]
        # Identifiability constraint: mean(attack) = 0 (enforced via re-centering).
        x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [-0.05]])

        def neg_log_lik(p: np.ndarray) -> float:
            atk = p[:n] - p[:n].mean()      # center for identifiability
            dfn = p[n:2 * n] - p[n:2 * n].mean()
            gamma = p[2 * n]
            rho = p[2 * n + 1]
            lam = np.exp(atk[hi] - dfn[ai] + gamma)
            mu = np.exp(atk[ai] - dfn[hi])
            # Poisson log-pmf (vectorised)
            ll = (hg * np.log(lam) - lam - _gammaln(hg + 1)
                  + ag * np.log(mu) - mu - _gammaln(ag + 1))
            # tau term (only low scores differ from 1)
            t = _tau_vec(hg, ag, lam, mu, rho)
            t = np.clip(t, 1e-10, None)  # keep log finite
            ll = ll + np.log(t)
            return -np.sum(w * ll)

        res = minimize(neg_log_lik, x0, method="L-BFGS-B",
                       bounds=[(None, None)] * (2 * n) + [(None, None), (-0.2, 0.2)])
        p = res.x
        atk = p[:n] - p[:n].mean()
        dfn = p[n:2 * n] - p[n:2 * n].mean()
        self.params = DixonColesParams(
            teams=teams,
            attack={t: float(a) for t, a in zip(teams, atk)},
            defense={t: float(d) for t, d in zip(teams, dfn)},
            home_adv=float(p[2 * n]),
            rho=float(p[2 * n + 1]),
        )
        return self.params

    # ---- prediction ----------------------------------------------------------
    def score_matrix(self, home: str, away: str, neutral: bool = False) -> np.ndarray:
        """P(home_goals=x, away_goals=y) for x,y in 0..max_goals."""
        if self.params is None:
            raise RuntimeError("Model not fitted. Call fit() first.")
        p = self.params
        gamma = 0.0 if neutral else p.home_adv
        lam = exp(p.attack[home] - p.defense[away] + gamma)
        mu = exp(p.attack[away] - p.defense[home])
        m = self.max_goals + 1
        mat = np.zeros((m, m))
        for x in range(m):
            for y in range(m):
                mat[x, y] = tau(x, y, lam, mu, p.rho) * _pois_pmf(x, lam) * _pois_pmf(y, mu)
        s = mat.sum()
        return mat / s if s > 0 else mat  # renormalise (tau breaks exact normalisation)

    def match_probabilities(self, home: str, away: str, neutral: bool = False) -> dict:
        mat = self.score_matrix(home, away, neutral)
        p_home = float(np.tril(mat, -1).sum())   # home_goals > away_goals
        p_away = float(np.triu(mat, 1).sum())    # away_goals > home_goals
        p_draw = float(np.trace(mat))
        ij = np.unravel_index(np.argmax(mat), mat.shape)
        # over/under 2.5 and BTTS
        total = np.add.outer(np.arange(mat.shape[0]), np.arange(mat.shape[1]))
        over25 = float(mat[total >= 3].sum())
        btts = float(mat[1:, 1:].sum())
        return {
            "home_win": p_home, "draw": p_draw, "away_win": p_away,
            "most_likely_score": (int(ij[0]), int(ij[1])),
            "most_likely_score_prob": float(mat[ij]),
            "over_2_5": over25, "under_2_5": 1.0 - over25,
            "btts_yes": btts, "btts_no": 1.0 - btts,
        }


# --- vectorised helpers (module level for reuse) -----------------------------
def _gammaln(arr: np.ndarray) -> np.ndarray:
    from scipy.special import gammaln
    return gammaln(arr)


def _tau_vec(x: np.ndarray, y: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float) -> np.ndarray:
    t = np.ones_like(lam, dtype=float)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    t[m00] = 1.0 - lam[m00] * mu[m00] * rho
    t[m01] = 1.0 + lam[m01] * rho
    t[m10] = 1.0 + mu[m10] * rho
    t[m11] = 1.0 - rho
    return t


def time_decay_weights(days_ago: Sequence[float], xi: float = 0.0018) -> np.ndarray:
    """Dixon-Coles exponential down-weighting: w = exp(-xi * days_ago)."""
    return np.exp(-xi * np.asarray(days_ago, dtype=float))
