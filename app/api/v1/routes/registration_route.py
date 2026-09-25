from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.dependencies import get_registration_service
from app.schemas.registration import (
    OtpDispatched,
    OtpResend,
    OtpVerification,
    RegistrationComplete,
    RegistrationStart,
)
from app.services.registration_service import (
    RegistrationError,
    RegistrationRateLimited,
    RegistrationService,
)

router = APIRouter(prefix="/registration")


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _failure(error: Exception) -> HTTPException:
    if isinstance(error, RegistrationRateLimited):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Request cannot be processed",
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Request cannot be processed"
    )


@router.post("", response_model=OtpDispatched, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_registration_otp(
    payload: RegistrationStart,
    request: Request,
    service: Annotated[RegistrationService, Depends(get_registration_service)],
):
    try:
        request_id = await service.start(payload, _client_key(request))
    except RegistrationError as exc:
        raise _failure(exc) from exc
    return OtpDispatched(otp_request_id=request_id)


@router.post("/verify", response_model=RegistrationComplete)
async def verify_registration_otp(
    payload: OtpVerification,
    request: Request,
    service: Annotated[RegistrationService, Depends(get_registration_service)],
):
    try:
        await service.verify(payload, _client_key(request))
    except RegistrationError as exc:
        raise _failure(exc) from exc
    return RegistrationComplete()


@router.post(
    "/resend", response_model=OtpDispatched, status_code=status.HTTP_202_ACCEPTED
)
async def resend_registration_otp(
    payload: OtpResend,
    request: Request,
    service: Annotated[RegistrationService, Depends(get_registration_service)],
):
    try:
        await service.resend(payload, _client_key(request))
    except RegistrationError as exc:
        raise _failure(exc) from exc
    return OtpDispatched(otp_request_id=payload.otp_request_id)
