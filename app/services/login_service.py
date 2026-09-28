import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_session_token, hash_session_token, verify_password
from app.models.registration import AppUser, AuthSession, UserAccess
from app.schemas.registration import LoginRequest, LoginSuccess
from app.services.registration_ports import (
    RateLimitPort,
    SalesforceAccessValidationPort,
    ValidatedAccess,
)

logger = logging.getLogger(__name__)


class LoginError(Exception):
    pass


class LoginRateLimited(LoginError):
    pass


class LoginService:
    def __init__(
        self,
        db: AsyncSession,
        salesforce: SalesforceAccessValidationPort,
        limiter: RateLimitPort,
    ) -> None:
        self.db, self.salesforce, self.limiter = db, salesforce, limiter

    @staticmethod
    def _principal_hash(data: LoginRequest) -> str:
        return hashlib.sha256(f"{data.bp_number}:{data.ca_number}".encode()).hexdigest()

    async def _check_rate_limit(self, data: LoginRequest, client_key: str) -> None:
        principal = await self.limiter.allow(
            f"login:principal:{self._principal_hash(data)}",
            settings.LOGIN_PRINCIPAL_RATE_LIMIT,
            settings.LOGIN_RATE_WINDOW_SECONDS,
        )
        client = await self.limiter.allow(
            f"login:client:{client_key}",
            settings.LOGIN_IP_RATE_LIMIT,
            settings.LOGIN_RATE_WINDOW_SECONDS,
        )
        if not principal or not client:
            raise LoginRateLimited()

    async def authenticate(self, data: LoginRequest, client_key: str) -> LoginSuccess:
        await self._check_rate_limit(data, client_key)
        try:
            current_access = await self.salesforce.validate_access(
                data.bp_number, data.ca_number
            )
        except Exception as exc:
            logger.warning("Login validation failed")
            raise LoginError() from exc
        if not current_access:
            logger.info("Invalid login attempt")
            raise LoginError()

        user = await self._resolve_user(current_access)
        if user is None or not verify_password(user.password_hash, data.password):
            logger.info("Invalid login attempt")
            raise LoginError()

        now = datetime.now(timezone.utc)
        access_token = generate_session_token()
        refresh_token = generate_session_token()
        access_expires_at = now + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRY_SECONDS)
        refresh_expires_at = now + timedelta(seconds=settings.REFRESH_TOKEN_EXPIRY_SECONDS)
        try:
            await self._refresh_access(user.user_id, current_access, now)
            user.last_login_at = now
            session = AuthSession(
                user_id=user.user_id,
                session_type="REGISTERED",
                access_token_hash=hash_session_token(access_token),
                refresh_token_hash=hash_session_token(refresh_token),
                expires_at=access_expires_at,
                refresh_expires_at=refresh_expires_at,
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
        except IntegrityError as exc:
            await self.db.rollback()
            raise LoginError() from exc
        return LoginSuccess(
            session_id=session.session_id,
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    async def _resolve_user(self, accesses: list[ValidatedAccess]) -> AppUser | None:
        for access in accesses:
            user = await self.db.scalar(
                select(AppUser)
                .join(UserAccess, UserAccess.user_id == AppUser.user_id)
                .where(
                    AppUser.status == "ACTIVE",
                    UserAccess.service_contract_sfid == access.service_contract_sfid,
                    UserAccess.account_sfid == access.account_sfid,
                    UserAccess.is_active.is_(True),
                )
                .with_for_update()
            )
            if user is not None:
                return user
        return None

    async def _refresh_access(
        self, user_id, accesses: list[ValidatedAccess], now: datetime
    ) -> None:
        for access in _unique_accesses(accesses):
            existing = await self.db.scalar(
                select(UserAccess).where(
                    UserAccess.user_id == user_id,
                    UserAccess.service_contract_sfid == access.service_contract_sfid,
                    UserAccess.account_sfid == access.account_sfid,
                )
            )
            if existing is None:
                self.db.add(
                    UserAccess(
                        user_id=user_id,
                        service_contract_sfid=access.service_contract_sfid,
                        account_sfid=access.account_sfid,
                        is_primary=False,
                        is_active=True,
                        verified_at=now,
                    )
                )
            else:
                existing.is_active = True
                existing.verified_at = now


def _unique_accesses(accesses: list[ValidatedAccess]):
    seen: set[tuple[str, str]] = set()
    for access in accesses:
        key = (access.service_contract_sfid, access.account_sfid)
        if key not in seen:
            seen.add(key)
            yield access
