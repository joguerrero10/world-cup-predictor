"""
Stage-2 checks: database repositories (SQLite) and the XGBoost form model.
Run: python -m tests.verify_stage2
"""
import os
import sys
from datetime import date

import numpy as np

# Force an isolated in-memory SQLite DB BEFORE importing the db package.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.db.database import init_db, SessionLocal
from app.db import repositories as repo
from app.models.form_model import FormModel, build_features, outcome_from_goals, FEATURES
from app.models import metrics


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        check.failed = True
check.failed = False


def test_db_roundtrip():
    init_db()
    db = SessionLocal()
    try:
        a = repo.upsert_team(db, "Brazil", confederation="CONMEBOL", population=215_000_000)
        b = repo.upsert_team(db, "Ghana", confederation="CAF", population=33_000_000)
        # upsert is idempotent on name
        a2 = repo.upsert_team(db, "Brazil", gdp_per_capita=9000.0)
        check("upsert_team is idempotent on name", a.id == a2.id)
        check("upsert_team updates fields", repo.get_team(db, "Brazil").gdp_per_capita == 9000.0)

        m = repo.add_match(db, date(2022, 11, 24), a.id, b.id, 2, 0, "world_cup_group", True)
        check("match persisted", len(repo.load_matches(db)) == 1)

        repo.save_elo_snapshot(db, a.id, date(2022, 1, 1), 1800, 1600, 1400)
        repo.save_elo_snapshot(db, a.id, date(2023, 1, 1), 1850, 1620, 1410)
        latest = repo.latest_elo(db)
        check("latest_elo keeps most recent", abs(latest[a.id].rating - 1850) < 1e-9)

        repo.save_prediction(db, "hybrid", 0.6, 0.25, 0.15, match_id=m.id,
                             extra={"note": "test", "weights": [0.3, 0.4, 0.2, 0.1]})
        check("prediction with JSON extra persists", True)  # no exception == pass

        sim = repo.save_simulation(
            db, 10000, {"engine": "elo"},
            champion={"Brazil": 0.4, "Ghana": 0.01},
            finalist={"Brazil": 0.6}, semifinalist={"Brazil": 0.8},
            group_qualified={"Brazil": 0.95, "Ghana": 0.3})
        check("simulation + tournament_results persist", sim.id is not None)

        repo.save_metrics(db, "hybrid", accuracy=0.55, brier_score=0.18, log_loss=0.9)
        check("metrics persist and read back",
              repo.latest_metrics(db)[0].model == "hybrid")
        db.commit()
    finally:
        db.close()


def test_xgb_form_model():
    rng = np.random.default_rng(7)
    N = 4000
    # Generate features and a TRUE outcome that depends on them, so a real model
    # must beat the uniform baseline. No fabricated 'results' are claimed as real;
    # this is a synthetic learnability check only.
    elo_diff = rng.normal(0, 120, N)
    form_diff = rng.normal(0, 0.8, N)
    fifa_diff = rng.normal(0, 150, N)
    attack_diff = rng.normal(0, 100, N)
    defense_diff = rng.normal(0, 100, N)
    neutral = rng.integers(0, 2, N)
    # Latent home strength -> outcome via softmax-ish rule
    s = 0.004 * elo_diff + 0.3 * form_diff + 0.002 * fifa_diff + 0.003 * attack_diff
    y = np.empty(N, dtype=int)
    for i in range(N):
        ph = 1 / (1 + np.exp(-s[i]))
        r = rng.random()
        if r < 0.25:          # draw band
            y[i] = 1
        elif r < 0.25 + 0.75 * ph:
            y[i] = 0
        else:
            y[i] = 2
    rows = [{"elo_diff": elo_diff[i], "form_diff": form_diff[i], "fifa_diff": fifa_diff[i],
             "attack_diff": attack_diff[i], "defense_diff": defense_diff[i],
             "neutral": neutral[i]} for i in range(N)]
    X = build_features(rows)
    split = int(0.8 * N)
    model = FormModel(n_estimators=200).fit(X[:split], y[:split])
    proba = model.predict_proba(X[split:])
    check("xgb proba rows sum to 1", np.allclose(proba.sum(axis=1), 1.0, atol=1e-5))
    check("xgb proba has 3 classes", proba.shape[1] == 3)
    # Must beat a uniform baseline on log-loss
    uniform = np.full_like(proba, 1 / 3)
    ll_model = metrics.log_loss(proba, y[split:])
    ll_unif = metrics.log_loss(uniform, y[split:])
    check(f"xgb beats uniform baseline (logloss {ll_model:.3f} < {ll_unif:.3f})",
          ll_model < ll_unif)
    check("predict_one returns a valid distribution",
          abs(sum(model.predict_one(rows[0])) - 1.0) < 1e-5)


if __name__ == "__main__":
    test_db_roundtrip()
    test_xgb_form_model()
    print("\nRESULT:", "SOME TESTS FAILED" if check.failed else "ALL CHECKS PASSED")
    sys.exit(1 if check.failed else 0)
