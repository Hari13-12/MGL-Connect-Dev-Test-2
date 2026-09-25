import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.registration import AppUser, OtpRequest, UserAccess
from app.schemas.registration import OtpResend, OtpVerification, RegistrationStart
from app.services.registration_ports import (
    OtpPort,
    RateLimitPort,
    SalesforceValidationPort,
    ValidatedAccess,
)


class RegistrationError(Exception):
    pass


class RegistrationRateLimited(RegistrationError):
    pass


class RegistrationService:
    def __init__(
        self,
        db: AsyncSession,
        salesforce: SalesforceValidationPort,
        otp: OtpPort,
        limiter: RateLimitPort,
    ) -> None:
        self.db, self.salesforce, self.otp, self.limiter = db, salesforce, otp, limiter

    @staticmethod
    def _destination_hash(mobile: str) -> str:
        return hashlib.sha256(mobile.encode()).hexdigest()

    async def _check_rate_limit(self, mobile: str, client_key: str) -> None:
        destination = await self.limiter.allow(
            f"registration:destination:{self._destination_hash(mobile)}",
            settings.OTP_DESTINATION_RATE_LIMIT,
            settings.OTP_RATE_WINDOW_SECONDS,
        )
        client = await self.limiter.allow(
            f"registration:client:{client_key}",
            settings.OTP_IP_RATE_LIMIT,
            settings.OTP_RATE_WINDOW_SECONDS,
        )
        if not destination or not client:
            raise RegistrationRateLimited()

    async def start(self, data: RegistrationStart, client_key: str) -> UUID:
        await self._check_rate_limit(data.mobile_number, client_key)
        existing = await self.db.scalar(
            select(AppUser.user_id).where(AppUser.mobile_number == data.mobile_number)
        )
        if existing:
            raise RegistrationError()
        try:
            validated = await self.salesforce.validate_customer(
                data.bp_number, data.ca_number, data.mobile_number, data.email
            )
        except Exception as exc:
            raise RegistrationError() from exc
        if not validated:
            raise RegistrationError()
        # Revalidate on completion; only opaque IDs and destination data are persisted pre-verification.
        try:
            provider_reference = await self.otp.send(data.mobile_number)
        except Exception as exc:
            raise RegistrationError() from exc
        request = OtpRequest(
            purpose="REGISTER",
            destination_hash=self._destination_hash(data.mobile_number),
            provider_reference=provider_reference,
            status="PENDING",
            attempt_count=0,
            resend_count=0,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
        )
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        return request.otp_request_id

    async def verify(self, data: OtpVerification, client_key: str) -> None:
        await self._check_rate_limit(data.mobile_number, client_key)
        request = await self.db.scalar(
            select(OtpRequest)
            .where(OtpRequest.otp_request_id == data.otp_request_id)
            .with_for_update()
        )
        now = datetime.now(timezone.utc)
        if (
            request is None
            or request.purpose != "REGISTER"
            or request.destination_hash != self._destination_hash(data.mobile_number)
            or request.status != "PENDING"
            or request.expires_at <= now
            or request.attempt_count >= settings.OTP_MAX_ATTEMPTS
        ):
            await self.db.rollback()
            raise RegistrationError()
        request.attempt_count += 1
        try:
            accepted = await self.otp.verify(request.provider_reference, data.otp)
        except Exception:  # noqa: BLE001 - provider failures must remain indistinguishable
            accepted = False
        if not accepted:
            await self.db.commit()  # retain failed attempt count
            raise RegistrationError()
        try:
            validated = await self.salesforce.validate_customer(
                data.bp_number, data.ca_number, data.mobile_number, data.email
            )
        except Exception as exc:
            await self.db.rollback()
            raise RegistrationError() from exc
        if not validated:
            await self.db.rollback()
            raise RegistrationError()
        try:
            existing = await self.db.scalar(
                select(AppUser.user_id).where(
                    AppUser.mobile_number == data.mobile_number
                )
            )
            if existing:
                raise RegistrationError()
            user = AppUser(
                mobile_number=data.mobile_number,
                password_hash=hash_password(data.password),
                status="ACTIVE",
            )
            self.db.add(user)
            await self.db.flush()
            for index, access in enumerate(_unique_accesses(validated)):
                self.db.add(
                    UserAccess(
                        user_id=user.user_id,
                        service_contract_sfid=access.service_contract_sfid,
                        account_sfid=access.account_sfid,
                        is_primary=index == 0,
                        is_active=True,
                        verified_at=now,
                    )
                )
            request.status = "VERIFIED"
            request.verified_at = now
            await self.db.commit()
        except (IntegrityError, ValueError) as exc:
            await self.db.rollback()
            raise RegistrationError() from exc

    async def resend(self, data: OtpResend, client_key: str) -> None:
        await self._check_rate_limit(data.mobile_number, client_key)
        request = await self.db.scalar(
            select(OtpRequest)
            .where(OtpRequest.otp_request_id == data.otp_request_id)
            .with_for_update()
        )
        now = datetime.now(timezone.utc)
        if (
            request is None
            or request.status != "PENDING"
            or request.destination_hash != self._destination_hash(data.mobile_number)
            or request.expires_at <= now
            or request.resend_count >= settings.OTP_MAX_RESENDS
        ):
            await self.db.rollback()
            raise RegistrationError()
        try:
            reference = await self.otp.send(data.mobile_number)
        except Exception as exc:
            await self.db.rollback()
            raise RegistrationError() from exc
        request.provider_reference = reference
        request.resend_count += 1
        request.expires_at = now + timedelta(seconds=settings.OTP_EXPIRY_SECONDS)
        await self.db.commit()


def _unique_accesses(accesses: list[ValidatedAccess]):
    seen: set[tuple[str, str]] = set()
    for access in accesses:
        key = (access.service_contract_sfid, access.account_sfid)
        if key not in seen:
            seen.add(key)
            yield access
