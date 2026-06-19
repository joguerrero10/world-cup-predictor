"""
Monte Carlo tournament simulator.

Given a function that returns 1X2 (and optionally score) probabilities for any
pair of teams, simulate group stages + knockouts (with penalty shootouts) many
times and aggregate champion / finalist / semifinalist / group-qualification
probabilities.

The match-probability function is injected, so the SAME simulator works with the
hybrid model, pure Elo, pure Dixon-Coles, etc.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

# A callable: (home, away, neutral) -> (p_home, p_draw, p_away)
MatchModel = Callable[[str, str, bool], tuple[float, float, float]]


@dataclass
class Group:
    name: str
    teams: list[str]


@dataclass
class SimResult:
    n_sims: int
    champion: dict[str, float]
    finalist: dict[str, float]
    semifinalist: dict[str, float]
    group_qualified: dict[str, float]


def _play(model: MatchModel, home: str, away: str, rng: np.random.Generator,
          neutral: bool = True, knockout: bool = False) -> str:
    """Return the winning team name. In group play a draw is possible (returns 'DRAW')."""
    ph, pd, pa = model(home, away, neutral)
    r = rng.random()
    if r < ph:
        return home
    if r < ph + pd:
        # draw: in knockouts go to a coin-flip shootout (50/50 by default)
        if knockout:
            return home if rng.random() < 0.5 else away
        return "DRAW"
    return away


def simulate(
    groups: Sequence[Group],
    model: MatchModel,
    n_sims: int = 10_000,
    advance_per_group: int = 2,
    seed: int | None = None,
) -> SimResult:
    """
    Round-robin groups (top `advance_per_group` advance), then single-elimination.
    Bracket is seeded by group order (winners vs runners-up, crossed) which is a
    simplification of FIFA's real bracket but adequate for probability estimates.
    """
    rng = np.random.default_rng(seed)
    champ = defaultdict(int)
    final = defaultdict(int)
    semi = defaultdict(int)
    qualified = defaultdict(int)

    for _ in range(n_sims):
        advancing: list[str] = []
        for g in groups:
            pts = {t: 0 for t in g.teams}
            for i in range(len(g.teams)):
                for j in range(i + 1, len(g.teams)):
                    w = _play(model, g.teams[i], g.teams[j], rng, neutral=True)
                    if w == "DRAW":
                        pts[g.teams[i]] += 1
                        pts[g.teams[j]] += 1
                    else:
                        pts[w] += 3
            ranked = sorted(g.teams, key=lambda t: (pts[t], rng.random()), reverse=True)
            top = ranked[:advance_per_group]
            advancing.extend(top)
            for t in top:
                qualified[t] += 1

        # Knockout: single elimination on the advancing list (already interleaved
        # winner/runner-up by group). Track final-4 and final-2.
        round_teams = advancing
        rounds_left = round_teams
        # Identify semifinalists (final 4) and finalists (final 2) as we go.
        while len(rounds_left) > 1:
            nxt = []
            for k in range(0, len(rounds_left), 2):
                if k + 1 >= len(rounds_left):
                    nxt.append(rounds_left[k])
                    continue
                w = _play(model, rounds_left[k], rounds_left[k + 1], rng,
                          neutral=True, knockout=True)
                nxt.append(w)
            if len(rounds_left) == 4:
                for t in rounds_left:
                    semi[t] += 1
            if len(rounds_left) == 2:
                for t in rounds_left:
                    final[t] += 1
            rounds_left = nxt
        if rounds_left:
            champ[rounds_left[0]] += 1

    all_teams = [t for g in groups for t in g.teams]
    pct = lambda d: {t: d.get(t, 0) / n_sims for t in all_teams}
    return SimResult(
        n_sims=n_sims,
        champion=pct(champ),
        finalist=pct(final),
        semifinalist=pct(semi),
        group_qualified=pct(qualified),
    )
