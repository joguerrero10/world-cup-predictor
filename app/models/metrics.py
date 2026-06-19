"""
Evaluation metrics for 1X2 probabilistic forecasts, plus the 'Klement 2.0'
weight optimiser that learns hybrid weights from historical results.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

# A forecast is a length-3 vector (home, draw, away); outcome is index 0/1/2.


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Multiclass Brier score (lower is better). probs: (N,3), outcomes: (N,) in {0,1,2}."""
    onehot = np.eye(3)[outcomes]
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-15) -> float:
    p = np.clip(probs[np.arange(len(outcomes)), outcomes], eps, 1.0)
    return float(-np.mean(np.log(p)))


def accuracy(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean(np.argmax(probs, axis=1) == outcomes))


def calibration_error(probs: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> float:
    """Expected Calibration Error on the predicted-class confidence."""
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == outcomes).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for i in range(bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1])
        if m.sum() == 0:
            continue
        ece += (m.mean()) * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def roi_vs_odds(probs: np.ndarray, outcomes: np.ndarray, decimal_odds: np.ndarray,
                stake: float = 1.0) -> float:
    """
    Hypothetical ROI from flat-staking the model's most likely outcome at the
    given historical decimal odds. decimal_odds: (N,3). Returns net ROI fraction.
    NOTE: backtested ROI is not predictive of future returns. Treat as diagnostic.
    """
    picks = probs.argmax(axis=1)
    n = len(outcomes)
    profit = 0.0
    for i in range(n):
        if picks[i] == outcomes[i]:
            profit += stake * (decimal_odds[i, picks[i]] - 1.0)
        else:
            profit -= stake
    return float(profit / (n * stake))


# --- Klement 2.0: learn hybrid weights from history --------------------------

def optimise_weights(
    sub_model_probs: dict[str, np.ndarray],
    outcomes: np.ndarray,
    objective: str = "log_loss",
) -> dict[str, float]:
    """
    Find blend weights over the sub-models that minimise the chosen objective on
    historical data.

    sub_model_probs: {"klement": (N,3), "elo": (N,3), "dixon_coles": (N,3),
                      "form": (N,3)}  -- one probability matrix per sub-model.
    outcomes: (N,) actual results in {0,1,2}.

    Returns weights that sum to 1. Weights are constrained to the simplex via a
    softmax reparameterisation, so the optimiser is unconstrained and stable.

    This is the data-driven replacement for fixed 30/40/20/10 weights. It needs
    REAL historical match data and REAL sub-model predictions; none are fabricated
    here. Supply your own 1998-2022 dataset to reproduce a Klement-2.0 fit.
    """
    names = list(sub_model_probs.keys())
    stacks = np.stack([sub_model_probs[k] for k in names], axis=0)  # (M, N, 3)
    obj_fn = {"log_loss": log_loss, "brier_score": brier_score}[objective]

    def loss(theta: np.ndarray) -> float:
        w = np.exp(theta - theta.max())
        w = w / w.sum()
        blended = np.tensordot(w, stacks, axes=(0, 0))  # (N,3)
        blended = blended / blended.sum(axis=1, keepdims=True)
        return obj_fn(blended, outcomes)

    res = minimize(loss, np.zeros(len(names)), method="Nelder-Mead")
    w = np.exp(res.x - res.x.max())
    w = w / w.sum()
    return {k: float(v) for k, v in zip(names, w)}
