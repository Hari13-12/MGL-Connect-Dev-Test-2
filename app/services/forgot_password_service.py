import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.registration import AppUser, AuthSession, OtpRequest, UserAccess
from app.schemas.registration import ForgotPasswordStart, ForgotPasswordVerification
from app.services.registration_ports import (
    OtpPort,
    RateLimitPort,
    SalesforceAccessValidationPort,
    ValidatedAccess,
)


class ForgotPasswordError(Exception):
    pass


class ForgotPasswordRateLimited(ForgotPasswordError):
    pass


class ForgotPasswordService:
    def __init__(
        self,
        db: AsyncSession,
        salesforce: SalesforceAccessValidationPort,
        otp: OtpPort,
        limiter: RateLimitPort,
    ) -> None:
        self.db, self.salesforce, self.otp, self.limiter = db, salesforce, otp, limiter

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @classmethod
    def _principal_key(cls, data: ForgotPasswordStart) -> str:
        if data.mobile_number:
            return cls._hash(data.mobile_number)
        return cls._hash(f"{data.bp_number}:{data.ca_number}")

    async def _check_rate_limit(self, data: ForgotPasswordStart, client_key: str) -> None:
        principal = await self.limiter.allow(
            f"forgot-password:principal:{self._principal_key(data)}",
            settings.OTP_DESTINATION_RATE_LIMIT,
            settings.OTP_RATE_WINDOW_SECONDS,
        )
        client = await self.limiter.allow(
            f"forgot-password:client:{client_key}",
            settings.OTP_IP_RATE_LIMIT,
            settings.OTP_RATE_WINDOW_SECONDS,
        )
        if not principal or not client:
            raise ForgotPasswordRateLimited()

    async def start(self, data: ForgotPasswordStart, client_key: str) -> UUID:
        await self._check_rate_limit(data, client_key)
        user = await self._resolve_user(data)
        # A random, non-persisted request id makes ineligible accounts indistinguishable.
        if user is None:
            return uuid4()

        request = OtpRequest(
            user_id=user.user_id,
            purpose="FORGOT_PASSWORD",
            destination_hash=self._hash(user.mobile_number),
            provider_reference="",
            status="DISPATCHING",
            attempt_count=0,
            resend_count=0,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
        )
        self.db.add(request)
        try:
            await self.db.commit()
            await self.db.refresh(request)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ForgotPasswordError() from exc
        try:
            request.provider_reference = await self.otp.send(
                user.mobile_number, str(request.otp_request_id)
            )
            request.status = "PENDING"
            await self.db.commit()
        except Exception as exc:
            request.status = "FAILED"
            await self.db.commit()
            raise ForgotPasswordError() from exc
        return request.otp_request_id

    async def verify(self, data: ForgotPasswordVerification) -> None:
        request = await self.db.scalar(
            select(OtpRequest)
            .where(OtpRequest.otp_request_id == data.otp_request_id)
            .with_for_update()
        )
        now = datetime.now(timezone.utc)
        if (
            request is None
            or request.user_id is None
            or request.purpose != "FORGOT_PASSWORD"
            or request.status != "PENDING"
            or request.expires_at <= now
            or request.attempt_count >= settings.OTP_MAX_ATTEMPTS
        ):
            await self.db.rollback()
            raise ForgotPasswordError()

        request.attempt_count += 1
        try:
            accepted = await self.otp.verify(request.provider_reference, data.otp)
        except Exception:
            accepted = False
        if not accepted:
            await self.db.commit()
            raise ForgotPasswordError()

        try:
            user = await self.db.scalar(
                select(AppUser)
                .where(AppUser.user_id == request.user_id, AppUser.status == "ACTIVE")
                .with_for_update()
            )
            if user is None:
                raise ForgotPasswordError()
            user.password_hash = hash_password(data.new_password)
            request.status = "VERIFIED"
            request.verified_at = now
            await self.db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user.user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await self.db.commit()
        except ForgotPasswordError:
            await self.db.rollback()
            raise
        except (IntegrityError, ValueError) as exc:
            await self.db.rollback()
            raise ForgotPasswordError() from exc

    async def _resolve_user(self, data: ForgotPasswordStart) -> AppUser | None:
        if data.mobile_number:
            return await self.db.scalar(
                select(AppUser).where(
                    AppUser.mobile_number == data.mobile_number, AppUser.status == "ACTIVE"
                )
            )
        try:
            accesses = await self.salesforce.validate_access(data.bp_number or "", data.ca_number or "")
        except Exception:
            return None
        for access in accesses:
            user = await self._user_for_access(access)
            if user is not None:
                return user
        return None

    async def _user_for_access(self, access: ValidatedAccess) -> AppUser | None:
        return await self.db.scalar(
            select(AppUser)
            .join(UserAccess, UserAccess.user_id == AppUser.user_id)
            .where(
                AppUser.status == "ACTIVE",
                UserAccess.service_contract_sfid == access.service_contract_sfid,
                UserAccess.account_sfid == access.account_sfid,
                UserAccess.is_active.is_(True),
            )
        )
