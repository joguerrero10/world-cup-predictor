"""Router principal de la API v1."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.simulation import router as sim_router
from app.api.v1.endpoints.predictions import router as pred_router
from app.api.v1.endpoints.analytics import router as analytics_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(sim_router)
v1_router.include_router(pred_router)
v1_router.include_router(analytics_router)
