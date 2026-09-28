from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.dependencies import get_forgot_password_service
from app.schemas.registration import (
    ForgotPasswordOtpDispatched,
    ForgotPasswordStart,
    ForgotPasswordVerification,
    PasswordResetComplete,
)
from app.services.forgot_password_service import (
    ForgotPasswordError,
    ForgotPasswordRateLimited,
    ForgotPasswordService,
)

router = APIRouter(prefix="/auth/forgot-password")


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("", response_model=ForgotPasswordOtpDispatched, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_forgot_password_otp(
    payload: ForgotPasswordStart,
    request: Request,
    service: Annotated[ForgotPasswordService, Depends(get_forgot_password_service)],
):
    try:
        request_id = await service.start(payload, _client_key(request))
    except ForgotPasswordRateLimited as exc:
        raise HTTPException(status_code=429, detail="Request cannot be processed") from exc
    except ForgotPasswordError:
        # Keep provider and persistence failures indistinguishable from ineligible accounts.
        return ForgotPasswordOtpDispatched(otp_request_id=uuid4())
    return ForgotPasswordOtpDispatched(otp_request_id=request_id)


@router.post("/verify", response_model=PasswordResetComplete)
async def verify_forgot_password_otp(
    payload: ForgotPasswordVerification,
    service: Annotated[ForgotPasswordService, Depends(get_forgot_password_service)],
):
    try:
        await service.verify(payload)
    except ForgotPasswordError as exc:
        raise HTTPException(status_code=400, detail="Request cannot be processed") from exc
    return PasswordResetComplete()
