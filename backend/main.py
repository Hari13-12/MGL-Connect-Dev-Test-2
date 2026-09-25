from fastapi import Depends, FastAPI

from backend.core.config import Settings, get_settings
from backend.core.database import get_session
from backend.dependencies import customer_adapter, otp_adapter, rate_limiter
from backend.schemas import OtpCreated, RegisterIn, RegistrationComplete, ResendIn, VerifyIn
from backend.services import resend, start_registration, verify_registration

app = FastAPI(title="MGL Connect", version="1.0.0")


@app.on_event("startup")
async def startup():
    get_settings().validate_live()


@app.post("/api/v1/registration", response_model=OtpCreated, status_code=202)
async def register(
    data: RegisterIn,
    customer=Depends(customer_adapter),
    otp=Depends(otp_adapter),
    limiter=Depends(rate_limiter),
    session=Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return OtpCreated(
        otp_request_id=await start_registration(data, customer, otp, limiter, session, settings)
    )


@app.post("/api/v1/registration/verify", response_model=RegistrationComplete)
async def verify(
    data: VerifyIn,
    otp=Depends(otp_adapter),
    session=Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return RegistrationComplete(user_id=await verify_registration(data, otp, session, settings))


@app.post("/api/v1/registration/resend", status_code=204)
async def resend_otp(
    data: ResendIn,
    otp=Depends(otp_adapter),
    limiter=Depends(rate_limiter),
    session=Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    await resend(data, otp, limiter, session, settings)
