from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def normalize_mobile(value: str) -> str:
    value = value.strip().replace(" ", "").replace("-", "")
    if value.startswith("00"):
        value = "+" + value[2:]
    if not value.startswith("+"):
        value = "+" + value
    if not value[1:].isdigit() or not 8 <= len(value[1:]) <= 15:
        raise ValueError("mobile number must be an international number")
    return value


class RegistrationStart(BaseModel):
    bp_number: str = Field(min_length=1, max_length=64)
    ca_number: str = Field(min_length=1, max_length=64)
    mobile_number: str
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("bp_number", "ca_number")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("mobile_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_mobile(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class OtpVerification(BaseModel):
    otp_request_id: UUID
    bp_number: str = Field(min_length=1, max_length=64)
    ca_number: str = Field(min_length=1, max_length=64)
    mobile_number: str
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    otp: str = Field(min_length=4, max_length=16)

    @field_validator("mobile_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_mobile(value)

    @field_validator("bp_number", "ca_number")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class OtpResend(BaseModel):
    otp_request_id: UUID
    mobile_number: str

    @field_validator("mobile_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_mobile(value)


class OtpDispatched(BaseModel):
    otp_request_id: UUID
    status: str = "OTP_DISPATCHED"


class RegistrationComplete(BaseModel):
    status: str = "REGISTRATION_COMPLETE"


class LoginRequest(BaseModel):
    bp_number: str = Field(min_length=1, max_length=64)
    ca_number: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("bp_number", "ca_number")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().upper()


class LoginSuccess(BaseModel):
    session_id: UUID
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    token_type: str = "Bearer"


class ForgotPasswordStart(BaseModel):
    bp_number: str | None = Field(default=None, min_length=1, max_length=64)
    ca_number: str | None = Field(default=None, min_length=1, max_length=64)
    mobile_number: str | None = None

    @field_validator("bp_number", "ca_number")
    @classmethod
    def normalize_optional_identifier(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("mobile_number")
    @classmethod
    def normalize_optional_mobile(cls, value: str | None) -> str | None:
        return normalize_mobile(value) if value else value

    @model_validator(mode="after")
    def require_one_identifier(self):
        has_mobile = self.mobile_number is not None
        has_bp_ca = self.bp_number is not None and self.ca_number is not None
        has_partial_bp_ca = (self.bp_number is None) != (self.ca_number is None)
        if has_partial_bp_ca or has_mobile == has_bp_ca:
            raise ValueError("provide either mobile_number or both bp_number and ca_number")
        return self


class ForgotPasswordVerification(BaseModel):
    otp_request_id: UUID
    otp: str = Field(min_length=4, max_length=16)
    new_password: str = Field(min_length=1, max_length=256)


class ForgotPasswordOtpDispatched(BaseModel):
    otp_request_id: UUID
    status: str = "If the account is eligible, an OTP has been sent."


class PasswordResetComplete(BaseModel):
    status: str = "PASSWORD_UPDATED"
