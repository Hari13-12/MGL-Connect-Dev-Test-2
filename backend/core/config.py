from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)
    environment: str = "test"
    database_url: str = "sqlite+aiosqlite:///./registration-test.db"
    redis_url: str = "redis://localhost:6379/0"
    salesforce_mirror_url: str = ""
    salesforce_contract_table: str = ""
    salesforce_bp_field: str = ""
    salesforce_ca_field: str = ""
    salesforce_mobile_field: str = ""
    salesforce_email_field: str = ""
    otp_provider_name: str = "fake"
    otp_provider_credentials: str = ""
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_max_resends: int = 3
    otp_resend_window_seconds: int = 60
    password_min_length: int = 12

    @property
    def use_fakes(self) -> bool:
        return self.environment == "test"

    def validate_live(self) -> None:
        if self.use_fakes:
            return
        required = (self.database_url, self.redis_url, self.salesforce_mirror_url,
                    self.salesforce_contract_table, self.salesforce_bp_field,
                    self.salesforce_ca_field, self.salesforce_mobile_field,
                    self.salesforce_email_field, self.otp_provider_credentials)
        if not all(required):
            raise RuntimeError("Required production registration settings are missing")


@lru_cache
def get_settings() -> Settings:
    return Settings()
