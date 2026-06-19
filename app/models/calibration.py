"""
Probability calibration for 1X2 forecasts.

Raw model probabilities are often mis-calibrated (a "70%" that only happens 55% of
the time). This wraps any model's output and corrects it against historical
outcomes using per-class isotonic regression, then renormalises to sum to 1.
"""
from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


class IsotonicCalibrator:
    """One-vs-rest isotonic calibration for a 3-class probability vector."""

    def __init__(self):
        self.models: list[IsotonicRegression] = []

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "IsotonicCalibrator":
        probs = np.asarray(probs, dtype=float)
        outcomes = np.asarray(outcomes, dtype=int)
        self.models = []
        for k in range(probs.shape[1]):
            ir = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            ir.fit(probs[:, k], (outcomes == k).astype(float))
            self.models.append(ir)
        return self

    def transform(self, probs: np.ndarray) -> np.ndarray:
        probs = np.asarray(probs, dtype=float)
        out = np.column_stack([m.predict(probs[:, k]) for k, m in enumerate(self.models)])
        out = np.clip(out, 1e-9, None)
        return out / out.sum(axis=1, keepdims=True)

    def fit_transform(self, probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
        return self.fit(probs, outcomes).transform(probs)


class PlattCalibrator:
    """Multinomial logistic recalibration (Platt scaling, multiclass)."""

    def __init__(self):
        # sklearn >=1.7 is multinomial by default; the old multi_class arg was removed.
        self.lr = LogisticRegression(max_iter=1000)
        self.fitted = False

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "PlattCalibrator":
        # use log-probabilities as features for numerical stability
        feats = np.log(np.clip(probs, 1e-9, 1.0))
        self.lr.fit(feats, outcomes)
        self.fitted = True
        return self

    def transform(self, probs: np.ndarray) -> np.ndarray:
        feats = np.log(np.clip(probs, 1e-9, 1.0))
        p = self.lr.predict_proba(feats)
        # pad missing classes if any were absent in training
        if p.shape[1] != 3:
            full = np.zeros((p.shape[0], 3))
            for j, c in enumerate(self.lr.classes_):
                full[:, int(c)] = p[:, j]
            p = full / full.sum(axis=1, keepdims=True)
        return p
