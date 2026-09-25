from fastapi import APIRouter

from app.api.v1.routes.health_route import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
