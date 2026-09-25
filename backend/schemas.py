from pydantic import BaseModel, EmailStr, Field
class RegisterIn(BaseModel):
    bp_number: str=Field(min_length=1,max_length=64)
    ca_number: str=Field(min_length=1,max_length=64)
    mobile_number: str=Field(pattern=r"^\+[1-9]\d{7,14}$")
    email: EmailStr
    password: str=Field(min_length=1,max_length=256)
class VerifyIn(BaseModel):
    otp_request_id: str
    otp: str=Field(pattern=r"^\d{4,10}$")
class ResendIn(BaseModel): otp_request_id: str
class OtpCreated(BaseModel): otp_request_id: str
class RegistrationComplete(BaseModel): user_id: str; next_step: str="login"
