"""
Stage-3 checks: calibration, walk-forward backtest, DB warm-start, new endpoints.
Run: python -m tests.verify_stage3
"""
import os
import sys
import warnings
from datetime import date, timedelta

import numpy as np

warnings.filterwarnings("ignore")
_TMP_DB = "/tmp/wcp_stage3_test.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

from app.models.calibration import IsotonicCalibrator, PlattCalibrator
from app.models.backtest import backtest_form_model
from app.models import metrics
from app.services.features import MatchRow, walk_forward


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        check.failed = True
check.failed = False


def _synth_matches(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    teams = ["A", "B", "C", "D", "E", "F", "G", "H"]
    # Wider strength separation -> clearer learnable signal for the backtest.
    strength = {t: s for t, s in zip(teams, [2.4, 2.0, 1.6, 1.3, 1.0, 0.8, 0.6, 0.4])}
    rows = []
    for _ in range(n):
        h, a = rng.choice(teams, 2, replace=False)
        rows.append(MatchRow(h, a, int(rng.poisson(strength[h] + 0.25)),
                             int(rng.poisson(strength[a])), "qualifier", False))
    return rows


def test_calibration():
    rng = np.random.default_rng(1)
    N = 3000
    outcomes = rng.integers(0, 3, N)
    # Build deliberately OVER-CONFIDENT probabilities (poorly calibrated).
    base = np.full((N, 3), 0.1)
    base[np.arange(N), outcomes] = 0.8
    # corrupt half so confidence doesn't match reality
    flip = rng.random(N) < 0.4
    base[flip] = np.roll(base[flip], 1, axis=1)
    base = base / base.sum(axis=1, keepdims=True)

    ece_before = metrics.calibration_error(base, outcomes)
    iso = IsotonicCalibrator().fit(base, outcomes)
    cal = iso.transform(base)
    ece_after = metrics.calibration_error(cal, outcomes)
    check("Isotonic calibrated probs sum to 1", np.allclose(cal.sum(axis=1), 1.0, atol=1e-6))
    check(f"Isotonic reduces calibration error ({ece_before:.3f} -> {ece_after:.3f})",
          ece_after <= ece_before + 1e-9)
    platt = PlattCalibrator().fit(base, outcomes)
    cp = platt.transform(base)
    check("Platt calibrated probs sum to ~1", np.allclose(cp.sum(axis=1), 1.0, atol=1e-6))


def test_walk_forward_no_leakage():
    rows = _synth_matches(300)
    feats, outcomes = walk_forward(rows)
    check("walk_forward returns one row per match", len(feats) == len(rows) == len(outcomes))
    # first-ever match: both teams start equal so elo_diff must be 0 (no future info)
    check("first match has zero elo_diff (no leakage)", abs(feats[0]["elo_diff"]) < 1e-9)


def test_backtest():
    rows = _synth_matches(3000)
    res = backtest_form_model(rows, train_frac=0.7, n_estimators=200)
    check(f"backtest accuracy beats 1/3 ({res['accuracy']:.3f})", res["accuracy"] > 0.34)
    check("backtest log_loss below uniform (1.0986)", res["log_loss"] < 1.0986)
    check("backtest reports all metric keys",
          {"accuracy", "brier_score", "log_loss", "calibration_err"} <= set(res))
    # ROI path: provide synthetic fair-ish odds so the column is exercised
    odds = np.full((len(rows), 3), 3.0)
    res2 = backtest_form_model(rows, train_frac=0.7, n_estimators=120, odds=odds)
    check("backtest includes ROI when odds supplied", "roi" in res2)


def test_endpoints_warm_start():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import SessionLocal
    from app.db import repositories as repo

    rows = _synth_matches(800, seed=5)
    with TestClient(app) as c:
        # seed DB directly via repositories
        with SessionLocal() as db:
            ids = {}
            for m in rows:
                for t in (m.home, m.away):
                    if t not in ids:
                        ids[t] = repo.upsert_team(db, t).id
            d0 = date(2000, 1, 1)
            for i, m in enumerate(rows):
                repo.add_match(db, d0 + timedelta(days=i), ids[m.home], ids[m.away],
                               m.home_goals, m.away_goals, m.match_type, m.neutral)
            db.commit()

        r = c.post("/load-from-db").json()
        check("/load-from-db loads matches", r.get("matches") == len(rows))
        check("/load-from-db fits Dixon-Coles", r.get("dixon_coles_fitted") is True)

        tr = c.post("/train-form-model").json()
        check("/train-form-model trains on history", tr.get("total_matches") == len(rows))

        h = c.get("/health").json()
        check("/health reports readiness flags",
              h["dc_ready"] and h["form_model_ready"] and h["teams_loaded"] > 0)

        pred = c.get("/predict-match", params={"home": "A", "away": "H"}).json()
        check("predict works after warm-start path",
              abs(pred["home_win"] + pred["draw"] + pred["away_win"] - 1.0) < 1e-6)


if __name__ == "__main__":
    test_calibration()
    test_walk_forward_no_leakage()
    test_backtest()
    test_endpoints_warm_start()
    print("\nRESULT:", "SOME TESTS FAILED" if check.failed else "ALL CHECKS PASSED")
    sys.exit(1 if check.failed else 0)
