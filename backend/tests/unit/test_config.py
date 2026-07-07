from app.core.config import Settings


def test_settings_load_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "SCEP Backend API"
    assert settings.app_env == "local"
