from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.adapters import destination_digest
from backend.core.config import Settings
from backend.core.security import hash_password, validate_password
from backend.models import AppUser, OtpPurpose, OtpRequest, OtpStatus, UserAccess

INVALID=HTTPException(400,"Registration could not be completed")

async def start_registration(data, customer, otp, limiter, session: AsyncSession, settings: Settings):
    if not validate_password(data.password,settings.password_min_length): raise INVALID
    if not await limiter.allow("register:"+destination_digest(data.mobile_number), settings.otp_max_resends, settings.otp_resend_window_seconds): raise INVALID
    scope=await customer.validate(data.bp_number,data.ca_number,data.mobile_number,str(data.email))
    if not scope: raise INVALID
    digest=destination_digest(data.mobile_number)
    try: reference=await otp.send(digest)
    except Exception: raise HTTPException(503,"Registration could not be completed") from None
    row=OtpRequest(purpose=OtpPurpose.REGISTER,destination_hash=digest,provider_reference=reference,
        expires_at=datetime.now(timezone.utc)+timedelta(seconds=settings.otp_ttl_seconds), account_sfid=scope.account_sfid,
        service_contract_sfid=scope.service_contract_sfid,pending_password_hash=hash_password(data.password), pending_mobile_number=data.mobile_number)
    session.add(row); await session.commit(); return row.otp_request_id

async def verify_registration(data, otp, session: AsyncSession, settings: Settings):
    row=await session.get(OtpRequest,data.otp_request_id)
    now=datetime.now(timezone.utc)
    if not row or row.status != OtpStatus.PENDING or row.expires_at.replace(tzinfo=timezone.utc) < now: raise INVALID
    row.attempt_count+=1
    if row.attempt_count > settings.otp_max_attempts:
        row.status=OtpStatus.FAILED; await session.commit(); raise INVALID
    try: valid=await otp.verify(row.provider_reference,data.otp)
    except Exception: valid=False
    if not valid:
        await session.commit(); raise INVALID
    try:
        async with session.begin_nested():
            user=AppUser(mobile_number=row.pending_mobile_number)
            user.password_hash=row.pending_password_hash; session.add(user); await session.flush()
            session.add(UserAccess(user_id=user.user_id,service_contract_sfid=row.service_contract_sfid,account_sfid=row.account_sfid,verified_at=now))
            row.user_id=user.user_id; row.status=OtpStatus.VERIFIED; row.verified_at=now
        await session.commit(); return user.user_id
    except IntegrityError:
        await session.rollback(); raise INVALID

async def resend(data, otp, limiter, session: AsyncSession, settings: Settings):
    row=await session.get(OtpRequest,data.otp_request_id)
    if not row or row.status != OtpStatus.PENDING or row.resend_count >= settings.otp_max_resends or not await limiter.allow("resend:"+row.destination_hash,1,settings.otp_resend_window_seconds): raise INVALID
    try: row.provider_reference=await otp.send(row.destination_hash)
    except Exception: raise HTTPException(503,"Registration could not be completed") from None
    row.resend_count+=1; await session.commit()
