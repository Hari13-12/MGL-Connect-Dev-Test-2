from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.adapters import FakeOtpAdapter, FakeSalesforceAdapter
from backend.core.config import Settings
from backend.core.rate_limit import MemoryRateLimiter
from backend.models import AppUser, Base, OtpRequest, UserAccess
from backend.schemas import RegisterIn, VerifyIn
from backend.services import start_registration, verify_registration

@pytest.fixture
async def session():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine,expire_on_commit=False)() as value: yield value
    await engine.dispose()

def registration(): return RegisterIn(bp_number="BP-1",ca_number="CA-1",mobile_number="+15555550100",email="customer@example.test",password="Secure-Pass1!")

@pytest.mark.asyncio
async def test_valid_registration_creates_only_validated_access(session):
    otp=FakeOtpAdapter(); settings=Settings(); request_id=await start_registration(registration(),FakeSalesforceAdapter(),otp,MemoryRateLimiter(),session,settings)
    result=await verify_registration(VerifyIn(otp_request_id=request_id,otp="123456"),otp,session,settings)
    user=await session.get(AppUser,result); access=(await session.execute(select(UserAccess))).scalar_one()
    assert user.mobile_number=="+15555550100" and user.password_hash.startswith("$argon2id$")
    assert (access.service_contract_sfid,access.account_sfid)==("SC-1","AC-1")
    assert "Secure-Pass1!" not in user.password_hash

@pytest.mark.asyncio
async def test_invalid_customer_and_otp_never_create_user(session):
    with pytest.raises(Exception): await start_registration(registration().model_copy(update={"ca_number":"wrong"}),FakeSalesforceAdapter(),FakeOtpAdapter(),MemoryRateLimiter(),session,Settings())
    otp=FakeOtpAdapter(); request_id=await start_registration(registration(),FakeSalesforceAdapter(),otp,MemoryRateLimiter(),session,Settings())
    with pytest.raises(Exception): await verify_registration(VerifyIn(otp_request_id=request_id,otp="000000"),otp,session,Settings())
    assert not (await session.execute(select(AppUser))).scalars().all()

@pytest.mark.asyncio
async def test_expired_otp_is_rejected(session):
    otp=FakeOtpAdapter(); request_id=await start_registration(registration(),FakeSalesforceAdapter(),otp,MemoryRateLimiter(),session,Settings())
    row=await session.get(OtpRequest,request_id); row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1); await session.commit()
    with pytest.raises(Exception): await verify_registration(VerifyIn(otp_request_id=request_id,otp="123456"),otp,session,Settings())
