"""
Correctness checks for the core models. Run: python -m tests.verify
These are real assertions about mathematical properties, not mock data.
"""
import sys
import numpy as np

from app.models.elo import EloConfig, TeamElo, update_match, expected_score, win_draw_loss_probs
from app.models.dixon_coles import DixonColes
from app.models.monte_carlo import Group, simulate
from app.models import metrics, klement, hybrid


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        check.failed = True
check.failed = False


def test_elo():
    cfg = EloConfig()
    # equal ratings, neutral venue -> 0.5 expectation
    check("Elo equal/neutral expectation == 0.5",
          abs(expected_score(1500, 1500, cfg, neutral=True) - 0.5) < 1e-9)
    # home advantage raises home expectation above 0.5
    check("Elo home advantage > 0.5",
          expected_score(1500, 1500, cfg, neutral=False) > 0.5)
    # global rating is zero-sum after a match
    h, a = TeamElo(1500), TeamElo(1500)
    nh, na = update_match(h, a, 2, 0, cfg, "world_cup_group", neutral=True)
    check("Elo global rating zero-sum",
          abs((nh.rating - 1500) + (na.rating - 1500)) < 1e-9)
    # winner gains, loser loses
    check("Elo winner gains rating", nh.rating > 1500 and na.rating < 1500)
    # 1X2 sums to 1
    p = win_draw_loss_probs(1600, 1400, cfg)
    check("Elo 1X2 sums to 1", abs(sum(p) - 1.0) < 1e-9)


def test_dixon_coles():
    # synthetic but structured data: 'Strong' scores more than 'Weak'
    rng = np.random.default_rng(0)
    teams = ["Strong", "Mid", "Weak"]
    strength = {"Strong": 1.4, "Mid": 1.0, "Weak": 0.6}
    H, A, HG, AG = [], [], [], []
    for _ in range(600):
        h, a = rng.choice(teams, 2, replace=False)
        H.append(h); A.append(a)
        HG.append(rng.poisson(strength[h] + 0.3))   # +0.3 home effect
        AG.append(rng.poisson(strength[a]))
    dc = DixonColes(max_goals=8)
    dc.fit(H, A, HG, AG)
    mat = dc.score_matrix("Strong", "Weak")
    check("DC score matrix sums to ~1", abs(mat.sum() - 1.0) < 1e-6)
    probs = dc.match_probabilities("Strong", "Weak")
    check("DC 1X2 sums to ~1",
          abs(probs["home_win"] + probs["draw"] + probs["away_win"] - 1.0) < 1e-6)
    check("DC recovers Strong > Weak (home favourite)",
          probs["home_win"] > probs["away_win"])
    check("DC home advantage param positive", dc.params.home_adv > 0)
    check("DC over/under partition", abs(probs["over_2_5"] + probs["under_2_5"] - 1.0) < 1e-9)


def test_metrics_and_optimiser():
    rng = np.random.default_rng(1)
    N = 500
    outcomes = rng.integers(0, 3, N)
    # a "good" model that puts mass on the truth, and a "bad" uniform one
    good = np.full((N, 3), 0.1); good[np.arange(N), outcomes] = 0.8
    bad = np.full((N, 3), 1 / 3)
    check("Brier: good < bad", metrics.brier_score(good, outcomes) < metrics.brier_score(bad, outcomes))
    check("LogLoss: good < bad", metrics.log_loss(good, outcomes) < metrics.log_loss(bad, outcomes))
    check("Accuracy good high", metrics.accuracy(good, outcomes) > 0.9)
    # optimiser should up-weight the informative sub-model
    w = metrics.optimise_weights({"good": good, "bad": bad}, outcomes, "log_loss")
    check("Klement2.0 up-weights informative model", w["good"] > w["bad"])
    check("Klement2.0 weights sum to 1", abs(sum(w.values()) - 1.0) < 1e-6)


def test_hybrid_and_klement():
    kw = klement.KlementWeights()
    strong = klement.TeamFactors(45000, 8e7, 1900, 0.95, 18, False, "UEFA")
    weak = klement.TeamFactors(4000, 5e6, 1200, 0.6, 28, False, "CAF")
    check("Klement: stronger factors -> higher score",
          klement.klement_score(strong, kw) > klement.klement_score(weak, kw))
    p = hybrid.blend((.5, .25, .25), (.5, .25, .25), (.5, .25, .25), (.5, .25, .25),
                     hybrid.HybridWeights())
    check("Hybrid blend sums to 1", abs(sum(p) - 1.0) < 1e-9)


def test_monte_carlo():
    # Two groups; make team A dominant via a deterministic-ish model.
    strength = {"A": 0.9, "B": 0.5, "C": 0.45, "D": 0.4,
                "E": 0.6, "F": 0.5, "G": 0.45, "H": 0.4}
    def model(h, a, neutral):
        e = strength[h] / (strength[h] + strength[a])
        pd = 0.22
        return (1 - pd) * e, pd, (1 - pd) * (1 - e)
    groups = [Group("1", ["A", "B", "C", "D"]), Group("2", ["E", "F", "G", "H"])]
    res = simulate(groups, model, n_sims=3000, seed=42)
    total = sum(res.champion.values())
    check("MC champion probs sum to ~1", abs(total - 1.0) < 1e-9)
    check("MC strongest team most likely champion",
          max(res.champion, key=res.champion.get) == "A")
    check("MC qualification prob in [0,1] for all",
          all(0 <= v <= 1 for v in res.group_qualified.values()))


if __name__ == "__main__":
    test_elo()
    test_dixon_coles()
    test_metrics_and_optimiser()
    test_hybrid_and_klement()
    test_monte_carlo()
    print("\nRESULT:", "SOME TESTS FAILED" if check.failed else "ALL CHECKS PASSED")
    sys.exit(1 if check.failed else 0)
