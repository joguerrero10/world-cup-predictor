"""Router principal de la API v1 — plataforma enterprise multicompetición."""
from __future__ import annotations

from fastapi import APIRouter

# Endpoints originales (mantenidos para compatibilidad)
from app.api.v1.endpoints.simulation import router as sim_router
from app.api.v1.endpoints.predictions import router as pred_router
from app.api.v1.endpoints.analytics import router as analytics_router

# Nuevos endpoints enterprise
from app.api.v1.endpoints.competitions import router as competitions_router
from app.api.v1.endpoints.simulate_v2 import router as simulate_v2_router
from app.api.v1.endpoints.standings import router as standings_router
from app.api.v1.endpoints.fixtures import router as fixtures_router
from app.api.v1.endpoints.players import router as players_router
from app.api.v1.endpoints.transfers import router as transfers_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.teams import router as teams_router

v1_router = APIRouter(prefix="/api/v1")

# Legacy
v1_router.include_router(sim_router)
v1_router.include_router(pred_router)
v1_router.include_router(analytics_router)

# Enterprise v2
v1_router.include_router(competitions_router)
v1_router.include_router(simulate_v2_router)
v1_router.include_router(standings_router)
v1_router.include_router(fixtures_router)
v1_router.include_router(players_router)
v1_router.include_router(transfers_router)
v1_router.include_router(system_router)
v1_router.include_router(teams_router)
