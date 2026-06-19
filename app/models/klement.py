"""
Klement-inspired strength score.

IMPORTANT HONESTY NOTE
----------------------
Joachim Klement's published model reportedly uses GDP per capita, population,
temperature/climate, FIFA ranking points and host advantage (with a luck term),
and is based on Hoffmann, Ging & Ramasamy (2002). His *exact coefficients are
proprietary and not public*. The function below is a TRANSPARENT APPROXIMATION
that uses the same family of inputs with explicit, tunable weights. It is not
Klement's real formula and will not reproduce his exact numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class TeamFactors:
    gdp_per_capita: float        # USD
    population: float            # persons
    fifa_points: float           # FIFA ranking points
    football_culture: float      # 0..1 subjective importance of football in country
    avg_temp_c: float = 20.0     # mean temperature, climate-fit proxy
    is_host: bool = False
    confederation: str = "UEFA"


@dataclass
class KlementWeights:
    # Weights are TUNABLE. Defaults are illustrative, not derived from Klement.
    gdp: float = 0.25
    population: float = 0.20
    fifa: float = 0.30
    culture: float = 0.15
    climate: float = 0.05
    host_bonus: float = 0.05
    # diminishing-returns cap on GDP (Klement notes wealth helps only up to a point)
    gdp_saturation: float = 60000.0


def klement_score(f: TeamFactors, w: KlementWeights, host_temp_c: float = 20.0) -> float:
    """Return a unitless strength score in roughly [0, 1]. Higher = stronger."""
    # GDP with diminishing returns (saturating curve)
    gdp_term = 1.0 - math.exp(-f.gdp_per_capita / w.gdp_saturation)
    # population on a log scale, normalised to ~[0,1] across 1e6..1.4e9
    pop_term = (math.log10(max(f.population, 1.0)) - 6.0) / (math.log10(1.4e9) - 6.0)
    pop_term = min(max(pop_term, 0.0), 1.0)
    # FIFA points normalised against a strong-team ceiling (~2100)
    fifa_term = min(f.fifa_points / 2100.0, 1.0)
    culture_term = min(max(f.football_culture, 0.0), 1.0)
    # climate fit: closer to host temperature => better adapted
    climate_term = math.exp(-((f.avg_temp_c - host_temp_c) ** 2) / (2 * 8.0 ** 2))
    host_term = 1.0 if f.is_host else 0.0

    score = (w.gdp * gdp_term + w.population * pop_term + w.fifa * fifa_term
             + w.culture * culture_term + w.climate * climate_term
             + w.host_bonus * host_term)
    total_w = w.gdp + w.population + w.fifa + w.culture + w.climate + w.host_bonus
    return score / total_w if total_w else 0.0


def klement_match_probs(s_home: float, s_away: float, draw_base: float = 0.26
                        ) -> tuple[float, float, float]:
    """Turn two Klement scores into a 1X2 distribution (logistic on the gap)."""
    e = 1.0 / (1.0 + 10.0 ** (-(s_home - s_away) * 4.0))  # scale factor tunable
    gap = abs(e - 0.5)
    p_draw = max(0.05, draw_base * (1.0 - gap * 2.0))
    rest = 1.0 - p_draw
    return rest * e, p_draw, rest * (1.0 - e)
