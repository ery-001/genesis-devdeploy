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


@lru_cache
def get_settings() -> Settings:
    return Settings()
