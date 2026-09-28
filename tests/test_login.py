from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.api.v1.dependencies import get_login_service
from app.core.security import hash_password, hash_session_token
from app.main import app
from app.models.registration import AppUser, UserAccess
from app.schemas.registration import LoginRequest
from app.services.login_service import LoginError, LoginRateLimited, LoginService
from app.services.registration_ports import ValidatedAccess


class FakeSession:
    def __init__(self, scalar_values=()):
        self.scalar_values = list(scalar_values)
        self.added = []
        self.commits = 0

    async def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    async def refresh(self, value):
        if getattr(value, "session_id", None) is None:
            value.session_id = uuid4()


class FakeSalesforce:
    def __init__(self, accesses=None):
        self.accesses = accesses if accesses is not None else [ValidatedAccess("BP-SFID", "CA-SFID")]
        self.calls = []

    async def validate_access(self, bp_number, ca_number):
        self.calls.append((bp_number, ca_number))
        return self.accesses


class AllowAll:
    async def allow(self, *_args):
        return True


class DenyAll:
    async def allow(self, *_args):
        return False


def login_data(password="Valid-password1!"):
    return LoginRequest(bp_number="bp1", ca_number="ca1", password=password)


def active_user():
    return AppUser(
        user_id=uuid4(),
        mobile_number="+15551234567",
        password_hash=hash_password("Valid-password1!"),
        status="ACTIVE",
    )


@pytest.mark.asyncio
async def test_login_validates_current_access_resolves_user_and_stores_only_token_hashes():
    user = active_user()
    access = UserAccess(
        user_id=user.user_id,
        service_contract_sfid="BP-SFID",
        account_sfid="CA-SFID",
        is_primary=True,
        is_active=True,
        verified_at=datetime.now(timezone.utc),
    )
    db = FakeSession([user, access])
    salesforce = FakeSalesforce()

    result = await LoginService(db, salesforce, AllowAll()).authenticate(login_data(), "127.0.0.1")

    assert salesforce.calls == [("BP1", "CA1")]
    assert db.commits == 1
    session = db.added[0]
    assert session.user_id == user.user_id
    assert session.session_type == "REGISTERED"
    assert session.access_token_hash == hash_session_token(result.access_token)
    assert session.refresh_token_hash == hash_session_token(result.refresh_token)
    assert "access_token" not in vars(session)
    assert "refresh_token" not in vars(session)
    assert result.access_expires_at < result.refresh_expires_at


@pytest.mark.asyncio
async def test_login_rejects_invalid_bp_ca_without_resolving_a_user():
    db = FakeSession()
    with pytest.raises(LoginError):
        await LoginService(db, FakeSalesforce([]), AllowAll()).authenticate(login_data(), "client")
    assert not db.added


@pytest.mark.asyncio
async def test_login_returns_generic_failure_for_wrong_password():
    user = active_user()
    db = FakeSession([user])
    with pytest.raises(LoginError):
        await LoginService(db, FakeSalesforce(), AllowAll()).authenticate(
            login_data("wrong-password"), "client"
        )
    assert not db.added


@pytest.mark.asyncio
async def test_login_rate_limits_before_salesforce_lookup():
    salesforce = FakeSalesforce()
    with pytest.raises(LoginRateLimited):
        await LoginService(FakeSession(), salesforce, DenyAll()).authenticate(login_data(), "client")
    assert not salesforce.calls


async def test_login_route_returns_generic_invalid_credentials(client):
    class RejectingService:
        async def authenticate(self, *_args):
            raise LoginError()

    app.dependency_overrides[get_login_service] = lambda: RejectingService()
    try:
        response = await client.post(
            "/api/v1/auth/login",
            json={"bp_number": "BP1", "ca_number": "CA1", "password": "wrong"},
        )
    finally:
        app.dependency_overrides.pop(get_login_service, None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
