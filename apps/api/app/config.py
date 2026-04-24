"""Typed application settings loaded from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "mai-filer-api"
    app_port: int = 8000
    log_level: str = "INFO"

    anthropic_api_key: str = ""
    claude_model_orchestrator: str = "claude-opus-4-7"
    claude_model_tools: str = "claude-sonnet-4-6"
    claude_model_cheap: str = "claude-haiku-4-5-20251001"

    database_url: str = "postgresql+psycopg://mai:mai@localhost:5432/mai_filer"
    redis_url: str = "redis://localhost:6379/0"

    # Celery / async submission pipeline (P6.4, P6.5). Disabled by default
    # so local dev and CI run the gateway inline; flip to true alongside
    # Redis provisioning and a running worker process.
    celery_enabled: bool = False
    celery_task_eager: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket: str = "mai-filer-dev"
    storage_region: str = "ng-lagos-1"

    nrs_base_url: str = "https://api.nrs.gov.ng/v1"
    nrs_client_id: str = ""
    nrs_client_secret: str = ""
    nrs_business_id: str = ""
    # "hmac" today; switch to "jwt" after NRS Rev360 cutover if needed.
    nrs_auth_scheme: Literal["hmac", "jwt"] = "hmac"
    nrs_jwt_algorithm: str = "HS256"
    nrs_jwt_private_key: str = ""  # PEM for RS256; shared secret for HS256

    identity_aggregator: Literal["dojah", "seamfix", "prembly"] = "dojah"
    dojah_api_key: str = ""
    dojah_app_id: str = ""
    seamfix_api_key: str = ""
    prembly_api_key: str = ""

    nin_vault_key: str = ""
    nin_hash_salt: str = ""

    # JWT secret for user-facing tokens.  MUST be set in production — the
    # validator rejects the default in production/staging so a misconfigured
    # deployment fails loudly at startup.
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_issuer: str = "mai-filer"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Bearer token that protects all PII-bearing API endpoints.
    # Set API_TOKEN to a long random string in production (min 32 chars).
    api_token: str = ""

    # Comma-separated list of origins the web app is served from.
    # Example: "https://mai-filer-web.up.railway.app,http://localhost:3000"
    cors_allow_origins: str = "http://localhost:3000"

    # Secrets backend: "env" (dev), "aws" (prod). When "aws",
    # `SECRETS_PATH_PREFIX` + `AWS_REGION` must be set; `boto3` must be
    # installed. See `app/secrets/`.
    secrets_backend: Literal["env", "aws"] = "env"
    secrets_path_prefix: str = ""

    # Observability. The correlation-ID header is read from inbound
    # requests; if absent, the middleware generates a UUID.
    correlation_id_header: str = "X-Request-Id"

    @field_validator("jwt_secret")
    @classmethod
    def _require_strong_jwt_secret(cls, v: str, info: object) -> str:
        """Reject the default placeholder secret in production / staging."""
        data = getattr(info, "data", {}) or {}
        env = data.get("app_env", "development")
        if env in ("production", "staging") and v == "dev-only-change-me":
            raise ValueError(
                "JWT_SECRET must be changed from the default value in "
                f"app_env={env!r}. Set a strong random value."
            )
        return v

    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def resolve_secret(self, key: str) -> str:
        """Return the current value for `key`, preferring Secrets Manager
        when configured. Falls through to the Pydantic-parsed attribute
        for backward-compat with env-file-driven dev.
        """
        # Local import avoids a config <-> secrets import cycle at module load.
        from app.secret_store import secret

        value = secret(key)
        if value is not None:
            return value
        return getattr(self, key.lower(), "") or ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
