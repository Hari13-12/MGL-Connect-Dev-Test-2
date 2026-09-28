from fastapi import APIRouter

from app.api.v1.routes.health_route import router as health_router
from app.api.v1.routes.login_route import router as login_router
from app.api.v1.routes.forgot_password_route import router as forgot_password_router
from app.api.v1.routes.registration_route import router as registration_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(registration_router, tags=["Registration"])
api_router.include_router(login_router, tags=["Authentication"])
api_router.include_router(forgot_password_router, tags=["Authentication"])
