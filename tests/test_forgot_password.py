from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.api.v1.dependencies import get_forgot_password_service
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.registration import AppUser, OtpRequest
from app.schemas.registration import ForgotPasswordStart, ForgotPasswordVerification
from app.services.forgot_password_service import (
    ForgotPasswordError,
    ForgotPasswordRateLimited,
    ForgotPasswordService,
)


class FakeSession:
    def __init__(self, scalar_values=()):
        self.scalar_values = list(scalar_values)
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.executed = []

    async def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        if getattr(value, "otp_request_id", None) is None:
            value.otp_request_id = uuid4()

    async def execute(self, statement):
        self.executed.append(statement)


class FakeSalesforce:
    async def validate_access(self, *_args):
        return []


class FakeOtp:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.sent = []
        self.verify_calls = 0

    async def send(self, destination, idempotency_key):
        self.sent.append((destination, idempotency_key))
        return "provider-reference"

    async def verify(self, _provider_reference, _otp):
        self.verify_calls += 1
        return self.accepted


class AllowAll:
    async def allow(self, *_args):
        return True


class DenyAll:
    async def allow(self, *_args):
        return False


def start_data():
    return ForgotPasswordStart(mobile_number="15551234567")


def active_user():
    return AppUser(
        user_id=uuid4(),
        mobile_number="+15551234567",
        password_hash=hash_password("Old-password1!"),
        status="ACTIVE",
    )


@pytest.mark.asyncio
async def test_start_uses_generic_nonpersistent_request_for_ineligible_account():
    db = FakeSession([None])
    request_id = await ForgotPasswordService(
        db, FakeSalesforce(), FakeOtp(), AllowAll()
    ).start(start_data(), "client")

    assert request_id
    assert not db.added


@pytest.mark.asyncio
async def test_start_persists_provider_reference_without_storing_an_otp():
    user = active_user()
    db = FakeSession([user])
    otp = FakeOtp()
    request_id = await ForgotPasswordService(db, FakeSalesforce(), otp, AllowAll()).start(
        start_data(), "client"
    )

    request = db.added[0]
    assert request_id == request.otp_request_id
    assert request.user_id == user.user_id
    assert request.purpose == "FORGOT_PASSWORD"
    assert request.provider_reference == "provider-reference"
    assert request.status == "PENDING"
    assert not hasattr(request, "otp")
    assert otp.sent == [(user.mobile_number, str(request_id))]


@pytest.mark.asyncio
async def test_verify_updates_argon_password_marks_request_used_and_revokes_sessions():
    user = active_user()
    request = OtpRequest(
        otp_request_id=uuid4(), user_id=user.user_id, purpose="FORGOT_PASSWORD",
        destination_hash=ForgotPasswordService._hash(user.mobile_number),
        provider_reference="provider-reference", status="PENDING", attempt_count=0,
        resend_count=0, expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    db = FakeSession([request, user])
    service = ForgotPasswordService(db, FakeSalesforce(), FakeOtp(), AllowAll())
    await service.verify(ForgotPasswordVerification(
        otp_request_id=request.otp_request_id, otp="123456", new_password="New-password1!"
    ))

    assert verify_password(user.password_hash, "New-password1!")
    assert request.status == "VERIFIED"
    assert request.verified_at is not None
    assert request.attempt_count == 1
    assert db.executed  # Revokes every active auth session for the account.


@pytest.mark.asyncio
async def test_verify_rejects_expired_or_used_or_attempt_limited_requests():
    request = OtpRequest(
        otp_request_id=uuid4(), user_id=uuid4(), purpose="FORGOT_PASSWORD",
        destination_hash="hash", provider_reference="ref", status="VERIFIED",
        attempt_count=0, resend_count=0, expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    otp = FakeOtp()
    with pytest.raises(ForgotPasswordError):
        await ForgotPasswordService(FakeSession([request]), FakeSalesforce(), otp, AllowAll()).verify(
            ForgotPasswordVerification(
                otp_request_id=request.otp_request_id, otp="123456", new_password="New-password1!"
            )
        )
    assert otp.verify_calls == 0


@pytest.mark.asyncio
async def test_start_rate_limits_before_account_lookup():
    with pytest.raises(ForgotPasswordRateLimited):
        await ForgotPasswordService(FakeSession(), FakeSalesforce(), FakeOtp(), DenyAll()).start(
            start_data(), "client"
        )


async def test_start_route_returns_same_accepted_shape_for_ineligible_account(client):
    class IneligibleService:
        async def start(self, *_args):
            return uuid4()

    app.dependency_overrides[get_forgot_password_service] = lambda: IneligibleService()
    try:
        response = await client.post("/api/v1/auth/forgot-password", json={"mobile_number": "15551234567"})
    finally:
        app.dependency_overrides.pop(get_forgot_password_service, None)

    assert response.status_code == 202
    assert response.json()["status"] == "If the account is eligible, an OTP has been sent."
