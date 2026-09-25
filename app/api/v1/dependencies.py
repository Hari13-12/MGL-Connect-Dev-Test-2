from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.base import AsyncSessionLocal
from app.core.config import settings
from redis.asyncio import Redis
from app.services.registration_ports import (
    HttpOtpPort,
    OtpPort,
    RateLimitPort,
    RedisRateLimitPort,
    SalesforceMirrorPort,
    SalesforceValidationPort,
)
from app.services.registration_service import RegistrationService

_salesforce: SalesforceValidationPort = SalesforceMirrorPort(
    AsyncSessionLocal, settings.SALESFORCE_MIRROR_VALIDATION_QUERY
)
_otp: OtpPort = HttpOtpPort(
    settings.OTP_PROVIDER_BASE_URL,
    settings.OTP_PROVIDER_TOKEN,
    settings.OTP_PROVIDER_SEND_PATH,
    settings.OTP_PROVIDER_VERIFY_PATH,
)
_limiter: RateLimitPort = RedisRateLimitPort(
    Redis.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True)
)


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
