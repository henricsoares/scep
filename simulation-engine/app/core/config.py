from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")
    backend_health_retries: int = Field(default=12, alias="BACKEND_HEALTH_RETRIES")
    backend_health_retry_delay_seconds: float = Field(
        default=5.0,
        alias="BACKEND_HEALTH_RETRY_DELAY_SECONDS",
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
