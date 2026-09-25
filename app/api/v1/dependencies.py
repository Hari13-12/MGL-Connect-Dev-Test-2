from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.registration_ports import (
    InMemoryRateLimitPort,
    OtpPort,
    RateLimitPort,
    SalesforceValidationPort,
    UnavailableOtpPort,
    UnavailableSalesforcePort,
)
from app.services.registration_service import RegistrationService

_salesforce: SalesforceValidationPort = UnavailableSalesforcePort()
_otp: OtpPort = UnavailableOtpPort()
_limiter: RateLimitPort = InMemoryRateLimitPort()


def get_salesforce_port() -> SalesforceValidationPort:
    return _salesforce


def get_otp_port() -> OtpPort:
    return _otp


def get_rate_limit_port() -> RateLimitPort:
    return _limiter


def get_registration_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    salesforce: Annotated[SalesforceValidationPort, Depends(get_salesforce_port)],
    otp: Annotated[OtpPort, Depends(get_otp_port)],
    limiter: Annotated[RateLimitPort, Depends(get_rate_limit_port)],
) -> RegistrationService:
    return RegistrationService(db, salesforce, otp, limiter)
