from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="SCEP Backend API", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    database_url: str = Field(
        default="postgresql+psycopg://scep:scep@localhost:5432/scep", alias="DATABASE_URL"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    jwt_secret_key: str = Field(default="change-me-in-local-development", alias="JWT_SECRET_KEY")
    jwt_access_token_expire_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    bootstrap_admin_email: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_display_name: str | None = Field(
        default=None, alias="BOOTSTRAP_ADMIN_DISPLAY_NAME"
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_sdk_disabled: bool = Field(default=False, alias="OTEL_SDK_DISABLED")
    dataset_export_max_window_days: int = Field(
        default=366, alias="DATASET_EXPORT_MAX_WINDOW_DAYS", ge=1
    )
    dataset_export_max_rows: int = Field(default=1_000_000, alias="DATASET_EXPORT_MAX_ROWS", ge=1)
    dataset_export_max_artifact_size_bytes: int = Field(
        default=1_073_741_824, alias="DATASET_EXPORT_MAX_ARTIFACT_SIZE_BYTES", ge=1
    )
    dataset_export_max_concurrent_jobs: int = Field(
        default=2, alias="DATASET_EXPORT_MAX_CONCURRENT_JOBS", ge=1
    )
    dataset_export_max_queued_jobs: int = Field(
        default=100, alias="DATASET_EXPORT_MAX_QUEUED_JOBS", ge=1
    )
    dataset_export_retention_days: int = Field(
        default=30, alias="DATASET_EXPORT_RETENTION_DAYS", ge=1
    )
    dataset_export_enabled_formats: str = Field(
        default="CSV,PARQUET", alias="DATASET_EXPORT_ENABLED_FORMATS"
    )
    dataset_export_storage_path: str = Field(
        default="var/dataset-exports", alias="DATASET_EXPORT_STORAGE_PATH"
    )
    dataset_export_processing_timeout_seconds: int = Field(
        default=900, alias="DATASET_EXPORT_PROCESSING_TIMEOUT_SECONDS", ge=1
    )
    dataset_export_abandoned_timeout_seconds: int = Field(
        default=1800, alias="DATASET_EXPORT_ABANDONED_TIMEOUT_SECONDS", ge=1
    )
    dataset_export_pseudonymization_secret: str = Field(
        default="change-me-dataset-export-local", alias="DATASET_EXPORT_PSEUDONYMIZATION_SECRET"
    )
    dataset_export_pseudonymization_key_version: str = Field(
        default="v1", alias="DATASET_EXPORT_PSEUDONYMIZATION_KEY_VERSION"
    )
    source_revision: str | None = Field(default=None, alias="SOURCE_REVISION")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
