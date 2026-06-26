"""
Verificación de corrección del motor Monte Carlo vectorizado.

Comprueba que:
1. Las probabilidades de campeón suman ~1
2. El equipo más fuerte es el campeón más probable
3. Los resultados son estadísticamente consistentes con el motor original
4. El simulador de liga produce distribuciones válidas
"""
from __future__ import annotations

import sys
import numpy as np

from app.simulation.monte_carlo_fast import simulate_fast, CompetitionGroup
from app.models.competition import get_competition


def check(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        check.failed = True

check.failed = False


def _simple_model(ratings: dict):
    def model(home: str, away: str, neutral: bool = True):
        dr = ratings[home] - ratings[away]
        e = 1 / (1 + 10 ** (-dr / 400))
        pd = max(0.05, 0.26 * (1 - abs(e - 0.5) * 2))
        rest = 1 - pd
        return rest * e, pd, rest * (1 - e)
    return model


def test_fast_mc_basic():
    """Corrección básica del motor vectorizado."""
    teams = ["A", "B", "C", "D", "E", "F", "G", "H"]
    ratings = {t: s for t, s in zip(teams, [2000, 1800, 1600, 1400, 1200, 1100, 1050, 1000])}
    model = _simple_model(ratings)

    groups = [
        CompetitionGroup("1", ["A", "B", "C", "D"]),
        CompetitionGroup("2", ["E", "F", "G", "H"]),
    ]

    result = simulate_fast(groups, model, n_sims=50_000, seed=42)

    total_champ = sum(result.champion.values())
    check("MC fast: champion probs sum to ~1", abs(total_champ - 1.0) < 1e-6)

    best = max(result.champion, key=result.champion.get)
    check("MC fast: strongest team most likely champion", best == "A")

    check("MC fast: all champion probs in [0,1]",
          all(0 <= v <= 1 for v in result.champion.values()))
    check("MC fast: all finalist probs in [0,1]",
          all(0 <= v <= 1 for v in result.finalist.values()))
    check("MC fast: all qualified probs in [0,1]",
          all(0 <= v <= 1 for v in result.group_qualified.values()))

    # El campeón debe tener prob más alta que el semifinalista
    a_champ = result.champion.get("A", 0)
    a_semi = result.semifinalist.get("A", 0)
    check("MC fast: p(champion) <= p(semifinalist) for best team",
          a_champ <= a_semi + 1e-6)

    # Equipo débil debe tener muy baja prob de campeón
    h_champ = result.champion.get("H", 0)
    check("MC fast: weakest team has low champion prob", h_champ < 0.05)


def test_fast_mc_consistency_with_original():
    """
    El motor fast debe producir resultados estadísticamente
    consistentes con el motor original para el mismo seed y modelo.
    """
    from app.models.monte_carlo import Group as OrigGroup, simulate as orig_simulate

    teams = ["Strong", "Mid1", "Mid2", "Weak"]
    ratings = {"Strong": 1900, "Mid1": 1600, "Mid2": 1500, "Weak": 1200}
    model = _simple_model(ratings)

    n_sims = 30_000

    orig_groups = [OrigGroup("1", teams)]
    fast_groups = [CompetitionGroup("1", teams)]

    orig_result = orig_simulate(orig_groups, model, n_sims=n_sims, seed=0,
                                advance_per_group=2)
    fast_result = simulate_fast(fast_groups, model, n_sims=n_sims, seed=0,
                                advance_per_group=2)

    # Verificar que ambos motores coinciden en quién es favorito
    orig_best = max(orig_result.champion, key=orig_result.champion.get)
    fast_best = max(fast_result.champion, key=fast_result.champion.get)
    check("MC fast vs original: same champion favorite", orig_best == fast_best)

    # Las probabilidades deben ser similares (Monte Carlo tiene varianza aleatoria,
    # así que toleramos 5% de diferencia)
    for team in teams:
        orig_p = orig_result.champion.get(team, 0)
        fast_p = fast_result.champion.get(team, 0)
        diff = abs(orig_p - fast_p)
        check(f"MC fast vs original: {team} champion diff < 5%", diff < 0.05)


def test_fast_mc_48teams():
    """Prueba de escala: 48 equipos, 12 grupos (Copa del Mundo 2026)."""
    n_teams = 48
    teams = [f"T{i:02d}" for i in range(n_teams)]
    rng = np.random.default_rng(7)
    ratings = dict(zip(teams, rng.uniform(1200, 2000, n_teams)))
    model = _simple_model(ratings)

    groups = [
        CompetitionGroup(str(i + 1), teams[i * 4:(i + 1) * 4])
        for i in range(12)
    ]

    result = simulate_fast(groups, model, n_sims=10_000, advance_per_group=2, seed=1)

    total_champ = sum(result.champion.values())
    check("MC fast 48-team: champion probs sum ~1", abs(total_champ - 1.0) < 1e-4)

    teams_in_result = set(result.champion.keys())
    check("MC fast 48-team: all 48 teams in result", len(teams_in_result) == n_teams)


def test_competition_catalog():
    """Verifica que el catálogo de competiciones está bien configurado."""
    for comp_id in ["fifa_wc_2026", "premier_league", "laliga", "serie_a",
                    "bundesliga", "ligue_1", "ucl"]:
        try:
            comp = get_competition(comp_id)
            check(f"Competition '{comp_id}' exists", True)
            check(f"Competition '{comp_id}' has valid n_teams",
                  comp.n_teams > 0)
        except Exception as e:
            check(f"Competition '{comp_id}' exists", False)


def test_league_sim():
    """Verifica el simulador de liga."""
    from app.simulation.league_sim import simulate_league
    from app.models.competition import get_competition

    comp = get_competition("premier_league")
    teams = [f"Club_{i:02d}" for i in range(20)]
    rng_r = np.random.default_rng(10)
    ratings = dict(zip(teams, rng_r.uniform(1300, 1900, 20)))
    model = _simple_model(ratings)

    result = simulate_league(teams=teams, model=model, config=comp, n_sims=5_000, seed=0)

    check("League sim: champion probs sum ~1",
          abs(sum(result.champion.values()) - 1.0) < 1e-6)
    check("League sim: relegated probs all in [0,1]",
          all(0 <= v <= 1 for v in result.relegated.values()))
    check("League sim: 20 teams in table",
          len(result.expected_table) == 20)
    check("League sim: position probs per team sum ~1",
          all(abs(sum(probs) - 1.0) < 1e-4 for probs in result.position_probs.values()))
    # El equipo más fuerte debe ser el más probable campeón
    best_team = max(ratings, key=ratings.get)
    best_champ = max(result.champion, key=result.champion.get)
    check("League sim: strongest team most likely champion",
          best_team == best_champ)


if __name__ == "__main__":
    test_fast_mc_basic()
    test_fast_mc_consistency_with_original()
    test_fast_mc_48teams()
    test_competition_catalog()
    test_league_sim()
    print("\nRESULT:", "SOME TESTS FAILED" if check.failed else "ALL CHECKS PASSED")
    sys.exit(1 if check.failed else 0)
