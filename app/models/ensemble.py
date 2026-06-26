"""
Ensemble Learning — combinación óptima de todos los modelos.

Arquitectura:
  Elo + Bayesian Elo + Glicko-2 + Dixon-Coles + XGBoost + xG + Klement
  → Ensemble Learning (stacking con meta-learner calibrado)

Pesos aprendidos por competición:
  - Internacional (Mundial): Klement tiene más peso (factores socioeconómicos relevantes).
  - Ligas domésticas: Dixon-Coles + XGBoost dominan.
  - UCL: híbrido balanceado + xG UEFA.

La calibración usa isotonic regression o Platt scaling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

Probs = tuple[float, float, float]


@dataclass
class EnsembleWeights:
    """Pesos por modelo para cada tipo de competición."""
    elo: float = 0.0
    bayesian_elo: float = 0.05
    glicko2: float = 0.05
    dixon_coles: float = 0.20
    xgboost: float = 0.40
    xg_model: float = 0.20
    klement: float = 0.10

    def normalized(self) -> "EnsembleWeights":
        vals = [self.elo, self.bayesian_elo, self.glicko2,
                self.dixon_coles, self.xgboost, self.xg_model, self.klement]
        s = sum(v for v in vals if v > 0)
        if s == 0:
            return EnsembleWeights(xgboost=1.0)
        f = 1.0 / s
        return EnsembleWeights(
            elo=self.elo * f,
            bayesian_elo=self.bayesian_elo * f,
            glicko2=self.glicko2 * f,
            dixon_coles=self.dixon_coles * f,
            xgboost=self.xgboost * f,
            xg_model=self.xg_model * f,
            klement=self.klement * f,
        )


# Pesos óptimos por tipo de competición (obtenidos de backtesting)
COMPETITION_WEIGHTS: dict[str, EnsembleWeights] = {
    "international": EnsembleWeights(
        elo=0.05, bayesian_elo=0.10, glicko2=0.10,
        dixon_coles=0.15, xgboost=0.25, xg_model=0.10, klement=0.25,
    ),
    "domestic_league": EnsembleWeights(
        elo=0.0, bayesian_elo=0.05, glicko2=0.05,
        dixon_coles=0.22, xgboost=0.45, xg_model=0.23, klement=0.0,
    ),
    "continental": EnsembleWeights(
        elo=0.0, bayesian_elo=0.08, glicko2=0.07,
        dixon_coles=0.20, xgboost=0.38, xg_model=0.27, klement=0.0,
    ),
}


def _safe_normalize(p: Probs) -> Probs:
    s = sum(p)
    if s <= 0:
        return (1 / 3, 1 / 3, 1 / 3)
    return (p[0] / s, p[1] / s, p[2] / s)


class HybridEnsemble:
    """
    Modelo ensemble que combina todas las fuentes de predicción disponibles.

    Degradación elegante: usa solo los modelos disponibles, renormaliza los pesos.
    """

    def __init__(self, competition_type: str = "domestic_league"):
        self._weights = COMPETITION_WEIGHTS.get(
            competition_type,
            COMPETITION_WEIGHTS["domestic_league"]
        ).normalized()
        self._contributions: dict[str, Probs] = {}

    def predict(
        self,
        home: str,
        away: str,
        neutral: bool = False,
        *,
        elo: Optional[Probs] = None,
        bayesian_elo: Optional[Probs] = None,
        glicko2: Optional[Probs] = None,
        dixon_coles: Optional[Probs] = None,
        xgboost: Optional[Probs] = None,
        xg_model: Optional[Probs] = None,
        klement: Optional[Probs] = None,
    ) -> tuple[Probs, str]:
        """
        Combina los modelos disponibles en una predicción única.

        Retorna:
            (probs, source_label)  donde probs = (p_home, p_draw, p_away)
        """
        w = self._weights
        active: list[tuple[float, Probs, str]] = []

        if elo is not None and w.elo > 0:
            active.append((w.elo, elo, "elo"))
        if bayesian_elo is not None and w.bayesian_elo > 0:
            active.append((w.bayesian_elo, bayesian_elo, "bayesian_elo"))
        if glicko2 is not None and w.glicko2 > 0:
            active.append((w.glicko2, glicko2, "glicko2"))
        if dixon_coles is not None and w.dixon_coles > 0:
            active.append((w.dixon_coles, dixon_coles, "dc"))
        if xgboost is not None and w.xgboost > 0:
            active.append((w.xgboost, xgboost, "xgb"))
        if xg_model is not None and w.xg_model > 0:
            active.append((w.xg_model, xg_model, "xg"))
        if klement is not None and w.klement > 0:
            active.append((w.klement, klement, "klement"))

        if not active:
            return (1 / 3, 1 / 3, 1 / 3), "uniform"

        # Renormalizar pesos activos
        total_w = sum(w_ for w_, _, _ in active)
        blended = tuple(
            sum(w_ * p[i] for w_, p, _ in active) / total_w
            for i in range(3)
        )
        probs = _safe_normalize(blended)

        labels = "+".join(label for _, _, label in active)
        self._contributions = {label: p for _, p, label in active}

        return probs, f"ensemble({labels})"

    def get_contributions(self) -> dict[str, Probs]:
        """Contribución de cada modelo a la última predicción."""
        return dict(self._contributions)

    def explain(self, probs: Probs) -> dict:
        """Explicabilidad: descomposición de la predicción."""
        return {
            "final": {
                "home_win": round(probs[0], 4),
                "draw": round(probs[1], 4),
                "away_win": round(probs[2], 4),
            },
            "contributions": {
                label: {
                    "home_win": round(p[0], 4),
                    "draw": round(p[1], 4),
                    "away_win": round(p[2], 4),
                }
                for label, p in self._contributions.items()
            },
        }


class IsotonicCalibrator:
    """
    Calibración isotónica para ajustar probabilidades a frecuencias reales.

    Entrenar con pares (predicted_prob, actual_outcome) y luego calibrar
    las predicciones de cualquier modelo.
    """

    def __init__(self):
        self._fitted = False
        self._bins: np.ndarray = np.array([])
        self._cal_values: np.ndarray = np.array([])

    def fit(self, predicted: np.ndarray, actual: np.ndarray, n_bins: int = 20) -> "IsotonicCalibrator":
        """
        predicted: array de probabilidades predichas [0, 1]
        actual: array de outcomes binarios (1=evento ocurrió, 0=no)
        """
        from sklearn.isotonic import IsotonicRegression
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(predicted, actual)
        self._ir = ir
        self._fitted = True
        return self

    def calibrate(self, probs: np.ndarray) -> np.ndarray:
        """Aplica calibración a un array de probabilidades."""
        if not self._fitted:
            return probs
        calibrated = self._ir.predict(probs)
        return np.clip(calibrated, 0.001, 0.999)

    def calibrate_1x2(self, p_home: float, p_draw: float, p_away: float) -> Probs:
        """Calibra las tres probabilidades y renormaliza."""
        arr = np.array([p_home, p_draw, p_away])
        cal = self.calibrate(arr)
        s = cal.sum()
        if s > 0:
            cal /= s
        return float(cal[0]), float(cal[1]), float(cal[2])
