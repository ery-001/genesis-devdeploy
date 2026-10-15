"""Application settings loaded from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DevDeploy API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg2://devdeploy:devdeploy@127.0.0.1:5432/devdeploy"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"

    cors_origins: str = "http://127.0.0.1:43127,http://localhost:43127"
    web_origin: str = "http://127.0.0.1:43127"
    api_public_url: str = "http://127.0.0.1:8741"

    # Session cookies (FastAPI-owned; not NextAuth)
    session_secret: str = "devdeploy-local-session-secret-change-me"
    session_cookie_name: str = "devdeploy_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    session_cookie_secure: bool = False

    # When true (default in development), OAuth/SMS run without real credentials.
    auth_mock_mode: bool = True
    mock_otp_code: str = "000000"

    # Optional real OAuth credentials (unused while auth_mock_mode=true)
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    apple_client_id: str = ""
    apple_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    # GitHub App (repo authorization) — separate from user sign-in
    # When credentials are missing, github_mock_mode stays on for local demos.
    github_app_id: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_private_key: str = ""  # PEM contents or path via GITHUB_APP_PRIVATE_KEY_PATH
    github_app_private_key_path: str = ""
    github_app_webhook_secret: str = "devdeploy-local-webhook-secret"
    github_app_slug: str = "devdeploy-local"
    github_mock_mode: bool = True

    @property
    def github_app_configured(self) -> bool:
        return bool(
            self.github_app_id
            and (self.github_app_private_key or self.github_app_private_key_path)
        )

    @property
    def effective_github_mock(self) -> bool:
        return self.github_mock_mode or not self.github_app_configured


@lru_cache
def get_settings() -> Settings:
    return Settings()
