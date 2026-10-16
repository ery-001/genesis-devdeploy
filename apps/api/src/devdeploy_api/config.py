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

    # Real OAuth credentials (used when AUTH_MOCK_MODE=false).
    # GitHub login falls back to GITHUB_APP_CLIENT_ID/SECRET when these are empty.
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    apple_client_id: str = ""
    apple_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"

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

    # Milestone 3–5 runtime adapters
    # Prefer real Docker/kind when available; set *_MOCK_MODE=true to force mocks.
    build_mock_mode: bool = False
    k8s_mock_mode: bool = False
    aws_mock_mode: bool = True  # never spend AWS $ unless explicitly disabled
    aws_region: str = "us-east-1"
    ecr_registry: str = ""
    eks_cluster_name: str = ""

    # Local image registry + kind
    local_registry: str = "localhost:5001"
    kind_cluster_name: str = "devdeploy"
    k8s_context: str = "kind-devdeploy"
    k8s_ingress_host_port: int = 8088
    k8s_node_port: int = 30080
    k8s_rollout_timeout_seconds: int = 120
    workload_container_port: int = 8000

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
