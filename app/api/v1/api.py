from fastapi import APIRouter

from app.api.v1.routes.health_route import router as health_router
from app.api.v1.routes.registration_route import router as registration_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(registration_router, tags=["Registration"])
