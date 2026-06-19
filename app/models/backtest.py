"""
Walk-forward backtest for the XGBoost form model.

Trains on the first `train_frac` of chronological matches and evaluates on the
rest — never using future data to predict the past. Reports accuracy, Brier,
log-loss, calibration error, and (optionally) hypothetical ROI against supplied
historical odds.

NOTE ON ROI: backtested ROI is a diagnostic, not a promise of future returns, and
requires REAL historical closing odds aligned to each test match. None are
fabricated here; pass `odds` explicitly to enable the ROI column.
"""
from __future__ import annotations

import numpy as np

from app.models import metrics
from app.models.form_model import FormModel, build_features
from app.services.features import MatchRow, walk_forward


def backtest_form_model(
    matches: list[MatchRow],
    train_frac: float = 0.7,
    odds: np.ndarray | None = None,
    n_estimators: int = 300,
) -> dict:
    rows, outcomes = walk_forward(matches)
    X = build_features(rows)
    y = np.asarray(outcomes)
    n = len(y)
    split = int(train_frac * n)
    if split < 50 or n - split < 20:
        raise ValueError("Not enough matches for a meaningful split.")

    model = FormModel(n_estimators=n_estimators).fit(X[:split], y[:split])
    proba = model.predict_proba(X[split:])
    y_test = y[split:]

    result = {
        "n_train": split, "n_test": n - split,
        "accuracy": metrics.accuracy(proba, y_test),
        "brier_score": metrics.brier_score(proba, y_test),
        "log_loss": metrics.log_loss(proba, y_test),
        "calibration_err": metrics.calibration_error(proba, y_test),
    }
    if odds is not None:
        result["roi"] = metrics.roi_vs_odds(proba, y_test, np.asarray(odds)[split:])
    return result
