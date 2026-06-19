"""
XGBoost match-outcome model (1X2).

Learns P(home win / draw / away win) from engineered features rather than the
simple points-per-game heuristic in hybrid.form_probs. Designed to slot into the
hybrid blend as the 'form' (or a standalone) component.

Features per match (all differences are home - away):
    elo_diff, attack_diff, defense_diff, form_diff, fifa_diff, neutral_flag
Extend `build_features` with rest days, travel, xG, etc. as data allows.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except Exception:  # pragma: no cover - dependency guard
    _HAS_XGB = False


FEATURES = ["elo_diff", "attack_diff", "defense_diff", "form_diff", "fifa_diff", "neutral", "gf_diff", "ga_diff"]
# Outcome encoding: 0 = home win, 1 = draw, 2 = away win
OUTCOME_HOME, OUTCOME_DRAW, OUTCOME_AWAY = 0, 1, 2


def build_features(rows: list[dict]) -> np.ndarray:
    """rows: list of dicts containing the FEATURES keys. Missing -> 0.0."""
    return np.array([[float(r.get(f, 0.0)) for f in FEATURES] for r in rows], dtype=float)


def outcome_from_goals(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return OUTCOME_HOME
    if home_goals < away_goals:
        return OUTCOME_AWAY
    return OUTCOME_DRAW


@dataclass
class FormModel:
    n_estimators: int = 300
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.9

    def __post_init__(self):
        if not _HAS_XGB:
            raise RuntimeError("xgboost not installed; pip install xgboost")
        self.clf = XGBClassifier(
            n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, subsample=self.subsample,
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            tree_method="hist", n_jobs=0,
        )
        self.fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None
            ) -> "FormModel":
        self.clf.fit(X, y, sample_weight=sample_weight)
        self.fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("Model not fitted.")
        p = self.clf.predict_proba(X)
        # XGBoost may drop classes if absent in training; pad to 3 columns.
        if p.shape[1] != 3:
            full = np.zeros((p.shape[0], 3))
            for j, c in enumerate(self.clf.classes_):
                full[:, int(c)] = p[:, j]
            p = full / full.sum(axis=1, keepdims=True)
        return p

    def predict_one(self, features: dict) -> tuple[float, float, float]:
        p = self.predict_proba(build_features([features]))[0]
        return float(p[0]), float(p[1]), float(p[2])

    def save(self, path: str) -> None:
        self.clf.save_model(path)

    def load(self, path: str) -> "FormModel":
        self.clf.load_model(path)
        self.fitted = True
        return self
