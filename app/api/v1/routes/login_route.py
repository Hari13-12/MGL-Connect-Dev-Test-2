from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.dependencies import get_login_service
from app.schemas.registration import LoginRequest, LoginSuccess
from app.services.login_service import LoginError, LoginRateLimited, LoginService

router = APIRouter(prefix="/auth")


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginSuccess)
async def login(
    payload: LoginRequest,
    request: Request,
    service: Annotated[LoginService, Depends(get_login_service)],
):
    try:
        return await service.authenticate(payload, _client_key(request))
    except LoginRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Request cannot be processed",
        ) from exc
    except LoginError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        ) from exc
