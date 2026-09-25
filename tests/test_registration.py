import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from app.models.registration import OtpRequest
from app.schemas.registration import OtpVerification, RegistrationStart
from app.services.registration_ports import (
    HttpOtpPort,
    RedisRateLimitPort,
    ValidatedAccess,
)
from app.services.registration_service import RegistrationError, RegistrationService


class FakeSession:
    def __init__(self, scalar_values=()):
        self.scalar_values = list(scalar_values)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, request):
        request.otp_request_id = uuid4()

    async def flush(self):
        for value in self.added:
            if getattr(value, "user_id", None) is None:
                value.user_id = uuid4()


class FakeSalesforce:
    def __init__(self, result=None, error=None):
        self.result = result or [ValidatedAccess("contract", "account")]
        self.error = error

    async def validate_customer(self, *_args):
        if self.error:
            raise self.error
        return self.result


class FakeOtp:
    def __init__(self, accepted=True, send_error=None):
        self.accepted = accepted
        self.send_error = send_error
        self.sent = []
        self.verify_calls = 0

    async def send(self, destination, idempotency_key):
        self.sent.append((destination, idempotency_key))
        if self.send_error:
            raise self.send_error
        return "provider-ref"

    async def verify(self, _reference, _otp):
        self.verify_calls += 1
        return self.accepted


class AllowAll:
    async def allow(self, *_args):
        return True


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        self.expiries[key] = seconds


def registration_data():
    return RegistrationStart(
        bp_number="BP1", ca_number="CA1", mobile_number="15551234567",
        email="customer@example.com", password="Valid-password1!",
    )


@pytest.mark.asyncio
async def test_start_persists_request_before_provider_send():
    db = FakeSession([None])
    otp = FakeOtp()
    service = RegistrationService(db, FakeSalesforce(), otp, AllowAll())

    request_id = await service.start(registration_data(), "client")

    assert request_id
    assert db.commits == 2
    assert otp.sent and otp.sent[0][1] == str(request_id)
    request = db.added[0]
    assert request.status == "PENDING"
    assert request.provider_reference == "provider-ref"


@pytest.mark.asyncio
async def test_start_provider_failure_is_recorded_after_durable_request():
    db = FakeSession([None])
    service = RegistrationService(db, FakeSalesforce(), FakeOtp(send_error=OSError()), AllowAll())

    with pytest.raises(RegistrationError):
        await service.start(registration_data(), "client")

    assert db.commits == 2
    assert db.added[0].status == "FAILED"


@pytest.mark.asyncio
async def test_start_salesforce_failure_does_not_create_otp_request():
    db = FakeSession([None])
    service = RegistrationService(db, FakeSalesforce(error=OSError()), FakeOtp(), AllowAll())

    with pytest.raises(RegistrationError):
        await service.start(registration_data(), "client")

    assert not db.added


@pytest.mark.asyncio
@pytest.mark.parametrize("status, expires_at, attempts", [
    ("VERIFIED", datetime.now(timezone.utc) + timedelta(minutes=1), 0),
    ("PENDING", datetime.now(timezone.utc) - timedelta(seconds=1), 0),
    ("PENDING", datetime.now(timezone.utc) + timedelta(minutes=1), 5),
])
async def test_verify_rejects_reused_expired_and_attempt_limited_otps(status, expires_at, attempts):
    request = OtpRequest(
        otp_request_id=uuid4(), purpose="REGISTER", destination_hash=RegistrationService._destination_hash("+15551234567"),
        provider_reference="ref", status=status, attempt_count=attempts, resend_count=0, expires_at=expires_at,
    )
    otp = FakeOtp()
    service = RegistrationService(FakeSession([request]), FakeSalesforce(), otp, AllowAll())
    verification = OtpVerification(
        otp_request_id=request.otp_request_id, bp_number="BP1", ca_number="CA1", mobile_number="15551234567",
        email="customer@example.com", password="Valid-password1!", otp="123456",
    )

    with pytest.raises(RegistrationError):
        await service.verify(verification, "client")

    assert otp.verify_calls == 0


@pytest.mark.asyncio
async def test_invalid_otp_increments_attempt_without_creating_user():
    request = OtpRequest(
        otp_request_id=uuid4(), purpose="REGISTER", destination_hash=RegistrationService._destination_hash("+15551234567"),
        provider_reference="ref", status="PENDING", attempt_count=0, resend_count=0,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    db = FakeSession([request])
    service = RegistrationService(db, FakeSalesforce(), FakeOtp(accepted=False), AllowAll())
    verification = OtpVerification(
        otp_request_id=request.otp_request_id, bp_number="BP1", ca_number="CA1", mobile_number="15551234567",
        email="customer@example.com", password="Valid-password1!", otp="123456",
    )

    with pytest.raises(RegistrationError):
        await service.verify(verification, "client")

    assert request.attempt_count == 1
    assert not db.added


@pytest.mark.asyncio
async def test_redis_rate_limit_uses_expiring_shared_buckets(monkeypatch):
    monkeypatch.setattr("app.services.registration_ports.time.time", lambda: 3600)
    redis = FakeRedis()
    limiter = RedisRateLimitPort(redis)

    assert await limiter.allow("destination", 2, 60)
    assert await limiter.allow("destination", 2, 60)
    assert not await limiter.allow("destination", 2, 60)
    assert redis.expiries["destination:60"] == 60


@pytest.mark.asyncio
async def test_http_otp_port_translates_provider_responses():
    async def handler(request):
        if request.url.path == "/send":
            assert json.loads(request.content) == {"destination": "+15551234567", "idempotency_key": "key"}
            return httpx.Response(200, json={"provider_reference": "ref"})
        return httpx.Response(200, json={"verified": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    port = HttpOtpPort("https://otp.example", None, "/send", "/verify", client)
    assert await port.send("+15551234567", "key") == "ref"
    assert await port.verify("ref", "123456")
    await client.aclose()
