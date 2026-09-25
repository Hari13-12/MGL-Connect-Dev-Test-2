from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ValidatedAccess:
    service_contract_sfid: str
    account_sfid: str


class SalesforceValidationPort(Protocol):
    async def validate_customer(self, bp_number: str, ca_number: str, mobile_number: str, email: str) -> list[ValidatedAccess]: ...


class OtpPort(Protocol):
    async def send(self, destination: str) -> str: ...
    async def verify(self, provider_reference: str, otp: str) -> bool: ...


class RateLimitPort(Protocol):
    async def allow(self, key: str, limit: int, window_seconds: int) -> bool: ...


class UnavailableSalesforcePort:
    async def validate_customer(self, bp_number: str, ca_number: str, mobile_number: str, email: str) -> list[ValidatedAccess]:
        raise RuntimeError("Salesforce validation is not configured")


class UnavailableOtpPort:
    async def send(self, destination: str) -> str:
        raise RuntimeError("OTP provider is not configured")

    async def verify(self, provider_reference: str, otp: str) -> bool:
        raise RuntimeError("OTP provider is not configured")


class InMemoryRateLimitPort:
    """Safe process-local fallback; production should inject a shared rate-limit backend."""
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        return count <= limit
