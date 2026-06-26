"""Core utilities — competition registry, team resolution."""
from app.core.competition_registry import (
    get_competition_teams,
    get_team_names,
    get_competition_groups,
    list_competitions,
    get_team_type,
    RegistryTeam,
    TeamType,
)

__all__ = [
    "get_competition_teams",
    "get_team_names",
    "get_competition_groups",
    "list_competitions",
    "get_team_type",
    "RegistryTeam",
    "TeamType",
]
