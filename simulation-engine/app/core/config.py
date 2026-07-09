from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
