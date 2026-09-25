import enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass
class UserStatus(str, enum.Enum): ACTIVE = "ACTIVE"
class OtpStatus(str, enum.Enum): PENDING="PENDING"; VERIFIED="VERIFIED"; EXPIRED="EXPIRED"; FAILED="FAILED"
class OtpPurpose(str, enum.Enum): REGISTER="REGISTER"
class AppUser(Base):
    __tablename__="app_user"
    user_id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid4()))
    mobile_number: Mapped[str]=mapped_column(String(32), unique=True, nullable=False, index=True)
    password_hash: Mapped[str]=mapped_column(String(512), nullable=False)
    status: Mapped[UserStatus]=mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
    preferred_language: Mapped[str]=mapped_column(String(10), default="en")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class OtpRequest(Base):
    __tablename__="otp_request"
    otp_request_id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid4()))
    user_id: Mapped[str|None]=mapped_column(String(36), nullable=True) # logical until user creation
    purpose: Mapped[OtpPurpose]=mapped_column(Enum(OtpPurpose), nullable=False)
    destination_hash: Mapped[str]=mapped_column(String(64), nullable=False, index=True)
    provider_reference: Mapped[str]=mapped_column(String(128), nullable=False)
    status: Mapped[OtpStatus]=mapped_column(Enum(OtpStatus), default=OtpStatus.PENDING, nullable=False)
    attempt_count: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    resend_count: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), nullable=False, index=True)
    verified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now())
    # validated scope and pending secret are application data, never Salesforce FKs
    account_sfid: Mapped[str]=mapped_column(String(64), nullable=False)
    service_contract_sfid: Mapped[str]=mapped_column(String(64), nullable=False)
    pending_password_hash: Mapped[str]=mapped_column(String(512), nullable=False)
    pending_mobile_number: Mapped[str]=mapped_column(String(32), nullable=False)
class UserAccess(Base):
    __tablename__="user_access"; __table_args__=(UniqueConstraint("user_id","service_contract_sfid","account_sfid"), Index("ix_user_access_contract_account","service_contract_sfid","account_sfid"))
    user_access_id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid4()))
    user_id: Mapped[str]=mapped_column(String(36), ForeignKey("app_user.user_id"), nullable=False, index=True)
    service_contract_sfid: Mapped[str]=mapped_column(String(64), nullable=False)
    account_sfid: Mapped[str]=mapped_column(String(64), nullable=False)
    is_primary: Mapped[bool]=mapped_column(Boolean, default=True)
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    verified_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), nullable=False)
