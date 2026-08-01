from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")
    backend_health_retries: int = Field(default=12, alias="BACKEND_HEALTH_RETRIES")
    backend_health_retry_delay_seconds: float = Field(
        default=5.0,
        alias="BACKEND_HEALTH_RETRY_DELAY_SECONDS",
    )
    scenario_path: str | None = Field(default=None, alias="SIMULATION_SCENARIO_PATH")
    bootstrap_path: str | None = Field(default=None, alias="SIMULATION_BOOTSTRAP_PATH")
    checkpoint_path: str = Field(
        default="simulation-checkpoint.json", alias="SIMULATION_CHECKPOINT_PATH"
    )
    report_path: str = Field(
        default="simulation-report.json", alias="SIMULATION_REPORT_PATH"
    )
    run_token: str | None = Field(default=None, alias="SIMULATION_RUN_TOKEN")
    driver_tokens_json: str | None = Field(
        default=None, alias="SIMULATION_DRIVER_TOKENS_JSON"
    )
    registered_scenario_sha256: str | None = Field(
        default=None, alias="SIMULATION_REGISTERED_SCENARIO_SHA256"
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
