from functools import lru_cache

from fastapi import Depends

from backend.adapters import FakeOtpAdapter, FakeSalesforceAdapter, MirrorSalesforceAdapter
from backend.core.config import Settings, get_settings
from backend.core.database import get_session
from backend.core.rate_limit import MemoryRateLimiter


@lru_cache
def otp_adapter():
    return FakeOtpAdapter()


@lru_cache
def salesforce_fake():
    return FakeSalesforceAdapter()


@lru_cache
def rate_limiter():
    return MemoryRateLimiter()


async def customer_adapter(
    settings: Settings = Depends(get_settings), session=Depends(get_session)
):
    return salesforce_fake() if settings.use_fakes else MirrorSalesforceAdapter(session, settings)
