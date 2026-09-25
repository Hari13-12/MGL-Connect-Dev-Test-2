from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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
