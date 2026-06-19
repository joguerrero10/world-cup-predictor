"""
Walk-forward feature engineering.

Replays matches in chronological order and, for each match, records features
computed from the state BEFORE that match (so there is no look-ahead leakage),
then updates the state. The same frame is used to train the XGBoost form model
and to run honest backtests.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from app.models.elo import EloConfig, TeamElo, update_match
from app.models.form_model import outcome_from_goals


@dataclass
class MatchRow:
    home: str
    away: str
    home_goals: int
    away_goals: int
    match_type: str = "friendly"
    neutral: bool = False


def _ppg(results: deque) -> float:
    """Rolling points-per-game from a deque of 'W'/'D'/'L'."""
    if not results:
        return 1.5
    pts = sum(3 if r == "W" else 1 if r == "D" else 0 for r in results)
    return pts / len(results)


def _avg_goals(goals: deque) -> float:
    """Rolling average from a deque of ints. Neutral prior (1.3) when empty."""
    if not goals:
        return 1.3
    return sum(goals) / len(goals)


def walk_forward(matches: list[MatchRow], cfg: EloConfig | None = None,
                 form_window: int = 5) -> tuple[list[dict], list[int]]:
    """
    feature_rows keys: elo_diff, attack_diff, defense_diff, form_diff,
    fifa_diff, neutral, gf_diff, ga_diff.

    gf_diff / ga_diff: diferencia en promedio de goles a favor / en contra de
    los últimos `form_window` partidos (local menos visitante). Distingue un
    3-0 de un 1-0, cosa que form_diff (basado solo en W/D/L) no puede.
    """
    cfg = cfg or EloConfig()
    elo: dict[str, TeamElo] = defaultdict(TeamElo)
    form: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))
    goals_for: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))
    goals_against: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))
    rows: list[dict] = []
    outcomes: list[int] = []

    for m in matches:
        h, a = elo[m.home], elo[m.away]
        rows.append({
            "elo_diff": h.rating - a.rating,
            "attack_diff": h.attack - a.attack,
            "defense_diff": h.defense - a.defense,
            "form_diff": _ppg(form[m.home]) - _ppg(form[m.away]),
            "fifa_diff": 0.0,
            "neutral": 1.0 if m.neutral else 0.0,
            "gf_diff": _avg_goals(goals_for[m.home]) - _avg_goals(goals_for[m.away]),
            "ga_diff": _avg_goals(goals_against[m.home]) - _avg_goals(goals_against[m.away]),
        })
        outcomes.append(outcome_from_goals(m.home_goals, m.away_goals))

        nh, na = update_match(h, a, m.home_goals, m.away_goals, cfg,
                              m.match_type, m.neutral)
        elo[m.home], elo[m.away] = nh, na
        if m.home_goals > m.away_goals:
            form[m.home].append("W"); form[m.away].append("L")
        elif m.home_goals < m.away_goals:
            form[m.home].append("L"); form[m.away].append("W")
        else:
            form[m.home].append("D"); form[m.away].append("D")

        goals_for[m.home].append(m.home_goals)
        goals_for[m.away].append(m.away_goals)
        goals_against[m.home].append(m.away_goals)
        goals_against[m.away].append(m.home_goals)

    return rows, outcomes
