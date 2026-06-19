"""
Dynamic Elo rating engine for international football.

Implements the World Football Elo Ratings formulation
(https://en.wikipedia.org/wiki/World_Football_Elo_Ratings):

    expected_home = 1 / (1 + 10 ** (-dr / 400))
    dr = (R_home - R_away) + home_advantage
    R_new = R_old + K * G * (W - expected)

where:
    K = base K-factor, scaled by match importance
    G = goal-difference index (margin-of-victory multiplier)
    W = match result from the team's perspective (1 win / 0.5 draw / 0 loss)

We additionally track *offensive* and *defensive* sub-ratings. NOTE: the
attack/defence split is an extension, NOT part of the canonical World Football
Elo system. It is a goals-for / goals-against variant and is documented as such.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Result = Literal["home", "draw", "away"]


@dataclass
class EloConfig:
    base_k: float = 40.0          # base K-factor (configurable per requirements)
    home_advantage: float = 100.0 # rating points added to the home side
    divisor: float = 400.0        # standard Elo divisor
    # Match-importance multipliers applied to K. Values are conventional choices,
    # broadly in line with FIFA/Elo practice; tune them against your own data.
    importance: dict[str, float] = field(default_factory=lambda: {
        "friendly": 1.0,
        "qualifier": 1.5,
        "continental": 2.0,
        "world_cup_group": 2.5,
        "world_cup_knockout": 3.0,
    })


@dataclass
class TeamElo:
    rating: float = 1500.0      # global Elo
    attack: float = 1500.0      # extension: goals-for tendency
    defense: float = 1500.0     # extension: goals-against tendency (higher = leakier)


def expected_score(r_home: float, r_away: float, cfg: EloConfig, neutral: bool = False) -> float:
    """Expected score for the HOME team in [0, 1]."""
    adv = 0.0 if neutral else cfg.home_advantage
    dr = (r_home - r_away) + adv
    return 1.0 / (1.0 + 10.0 ** (-dr / cfg.divisor))


def goal_difference_index(goal_diff: int) -> float:
    """G multiplier. goal_diff is |home_goals - away_goals|."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    # 3+ goals: (11 + gd) / 8
    return (11.0 + gd) / 8.0


def result_value(home_goals: int, away_goals: int) -> tuple[float, float]:
    """Return (W_home, W_away) using 1 / 0.5 / 0 convention."""
    if home_goals > away_goals:
        return 1.0, 0.0
    if home_goals < away_goals:
        return 0.0, 1.0
    return 0.5, 0.5


def update_match(
    home: TeamElo,
    away: TeamElo,
    home_goals: int,
    away_goals: int,
    cfg: EloConfig,
    match_type: str = "friendly",
    neutral: bool = False,
) -> tuple[TeamElo, TeamElo]:
    """
    Return NEW TeamElo objects for home and away after one match.
    Pure function: inputs are not mutated.
    """
    k = cfg.base_k * cfg.importance.get(match_type, 1.0)
    g = goal_difference_index(home_goals - away_goals)

    exp_home = expected_score(home.rating, away.rating, cfg, neutral)
    exp_away = 1.0 - exp_home
    w_home, w_away = result_value(home_goals, away_goals)

    delta_home = k * g * (w_home - exp_home)
    delta_away = k * g * (w_away - exp_away)

    # Global rating: this is zero-sum by construction (delta_home == -delta_away).
    new_home = TeamElo(rating=home.rating + delta_home)
    new_away = TeamElo(rating=away.rating + delta_away)

    # Attack/defence extension: bounded EWMA around a 1500 baseline. The naive
    # "K * goal_residual" accumulates without bound, so we use a small learning
    # rate plus mean reversion. This stays sane but is still a heuristic — for
    # principled attack/defence strength, prefer the Dixon-Coles alpha/beta params.
    lr, rev, base = 6.0, 0.02, 1500.0
    exp_goals = 1.35
    def _upd(prev: float, scored: int) -> float:
        return (1 - rev) * prev + rev * base + lr * (scored - exp_goals)
    new_home.attack = _upd(home.attack, home_goals)
    new_away.attack = _upd(away.attack, away_goals)
    new_home.defense = _upd(home.defense, away_goals)   # goals conceded
    new_away.defense = _upd(away.defense, home_goals)
    return new_home, new_away


def win_draw_loss_probs(
    r_home: float, r_away: float, cfg: EloConfig, neutral: bool = False,
    draw_base: float = 0.26,
) -> tuple[float, float, float]:
    """
    Convert an Elo expectation into a 1X2 distribution.

    Elo natively gives only an expected SCORE, not a draw probability. We use a
    common heuristic: allocate a draw mass that shrinks as the rating gap grows,
    then split the remainder by the Elo expectation. This is an approximation —
    Dixon-Coles gives a principled draw probability and is preferred where data exists.
    """
    e = expected_score(r_home, r_away, cfg, neutral)
    gap = abs(e - 0.5)
    p_draw = max(0.05, draw_base * (1.0 - gap * 2.0))
    rest = 1.0 - p_draw
    p_home = rest * e
    p_away = rest * (1.0 - e)
    return p_home, p_draw, p_away
