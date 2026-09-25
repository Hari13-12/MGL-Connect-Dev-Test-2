from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass(frozen=True)
class ValidatedAccess:
    service_contract_sfid: str
    account_sfid: str


class SalesforceValidationPort(Protocol):
    async def validate_customer(
        self, bp_number: str, ca_number: str, mobile_number: str, email: str
    ) -> list[ValidatedAccess]: ...


class OtpPort(Protocol):
    async def send(self, destination: str, idempotency_key: str) -> str: ...
    async def verify(self, provider_reference: str, otp: str) -> bool: ...


class RateLimitPort(Protocol):
    async def allow(self, key: str, limit: int, window_seconds: int) -> bool: ...


class SalesforceMirrorPort:
    """Queries the Heroku Connect mirror using a deployment-supplied query."""

    def __init__(self, session_factory: async_sessionmaker, validation_query: str) -> None:
        self._session_factory = session_factory
        self._validation_query = validation_query.strip()

    async def validate_customer(
        self, bp_number: str, ca_number: str, mobile_number: str, email: str
    ) -> list[ValidatedAccess]:
        if not self._validation_query:
            raise RuntimeError("Salesforce mirror validation query is not configured")
        async with self._session_factory() as session:
            result = await session.execute(
                text(self._validation_query),
                {
                    "bp_number": bp_number,
                    "ca_number": ca_number,
                    "mobile_number": mobile_number,
                    "email": email,
                },
            )
            return [
                ValidatedAccess(
                    service_contract_sfid=row.service_contract_sfid,
                    account_sfid=row.account_sfid,
                )
                for row in result.mappings()
            ]


class HttpOtpPort:
    """Adapter for an OTP vendor's send/verify HTTP endpoints."""

    def __init__(
        self,
        base_url: str,
        token: str | None,
        send_path: str,
        verify_path: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._send_path = send_path
        self._verify_path = verify_path
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def send(self, destination: str, idempotency_key: str) -> str:
        if not self._base_url:
            raise RuntimeError("OTP provider URL is not configured")
        payload = {"destination": destination, "idempotency_key": idempotency_key}
        response = await self._request("POST", self._send_path, json=payload)
        reference = response.get("provider_reference") or response.get("reference")
        if not isinstance(reference, str) or not reference:
            raise RuntimeError("OTP provider did not return a reference")
        return reference

    async def verify(self, provider_reference: str, otp: str) -> bool:
        if not self._base_url:
            raise RuntimeError("OTP provider URL is not configured")
        response = await self._request(
            "POST", self._verify_path, json={"provider_reference": provider_reference, "otp": otp}
        )
        return response.get("verified") is True

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._client is not None:
            response = await self._client.request(method, f"{self._base_url}{path}", headers=self._headers, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, f"{self._base_url}{path}", headers=self._headers, **kwargs)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("OTP provider returned an invalid response")
        return body


class RedisRateLimitPort:
    """Atomic fixed-window limits shared by every application worker."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit < 1 or window_seconds < 1:
            return False
        bucket = f"{key}:{int(__import__('time').time() // window_seconds)}"
        count = await self._redis.incr(bucket)
        if count == 1:
            await self._redis.expire(bucket, window_seconds)
        return int(count) <= limit
