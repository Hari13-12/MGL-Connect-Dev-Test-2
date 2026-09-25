from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings): 

    DATABASE_USER: str = Field(..., description="Database username")
    DATABASE_PASSWORD: str = Field(..., description="Database password")
    DATABASE_HOST: str = Field(default="localhost", description="Database host")
    DATABASE_PORT: int = Field(default=5432, description="Database port")
    DATABASE_NAME: str = Field(..., description="Database name")
    DATABASE_SCHEMA: str = Field(default="public", description="Database schema")
    # Application settings
    APP_NAME: str = Field(default="MGL Connect", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    VERSION: str = Field(default="1.0.0", description="API version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    PASSWORD_MIN_LENGTH: int = 12
    OTP_EXPIRY_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5
    OTP_MAX_RESENDS: int = 3
    OTP_DESTINATION_RATE_LIMIT: int = 5
    OTP_IP_RATE_LIMIT: int = 20
    OTP_RATE_WINDOW_SECONDS: int = 3600
   

    model_config = {
        "env_file": ".env",
        "extra": "allow",
        "case_sensitive": True
    }


settings = Settings()
 
