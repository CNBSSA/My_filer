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

    @field_validator("storage_access_key", "storage_secret_key")
    @classmethod
    def _reject_default_storage_credentials(cls, v: str, info: object) -> str:
        """Reject MinIO's well-known default credentials in production / staging."""
        data = getattr(info, "data", {}) or {}
        env = data.get("app_env", "development")
        if env in ("production", "staging") and v == "minioadmin":
            raise ValueError(
                f"{info.field_name.upper()} must not use the default 'minioadmin' value in "
                f"app_env={env!r}. Set a strong random credential."
            )
        return v

    @field_validator("nin_vault_key")
    @classmethod
    def _require_nin_vault_key(cls, v: str, info: object) -> str:
        """Require a non-empty NIN vault key in production / staging."""
        data = getattr(info, "data", {}) or {}
        env = data.get("app_env", "development")
        if env in ("production", "staging") and not v:
            raise ValueError(
                f"NIN_VAULT_KEY must be set to a 32-byte base64 Fernet key in app_env={env!r}."
            )
        return v

    @field_validator("nin_hash_salt")
    @classmethod
    def _require_strong_nin_hash_salt(cls, v: str, info: object) -> str:
        """Require a minimum-entropy NIN hash salt in production / staging."""
        data = getattr(info, "data", {}) or {}
        env = data.get("app_env", "development")
        if env in ("production", "staging") and len(v) < 16:
            raise ValueError(
                f"NIN_HASH_SALT must be at least 16 characters long in app_env={env!r}. "
                f"Current length: {len(v)}."
            )
        return v

    @field_validator("cors_allow_origins")
    @classmethod
    def _require_https_cors_origins_in_prod(cls, v: str, info: object) -> str:
        """Reject plain-http CORS origins in production / staging."""
        data = getattr(info, "data", {}) or {}
        env = data.get("app_env", "development")
        if env in ("production", "staging"):
            insecure = [
                o.strip()
                for o in v.split(",")
                if o.strip().startswith("http://") and "localhost" not in o and "127.0.0.1" not in o
            ]
            if insecure:
                raise ValueError(
                    f"CORS_ALLOW_ORIGINS contains insecure http:// origins in app_env={env!r}: "
                    f"{insecure}. Use https:// for all production origins."
                )
        return v

    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def validate_for_env(self) -> None:
        """Collect all environment misconfigurations and raise at startup.

        Called once from the FastAPI lifespan so every problem is reported
        together rather than the app failing silently or returning 503 on the
        first request.
        """
        errors: list[str] = []

        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is not set — Claude calls will fail.")

        if self.app_env in ("production", "staging"):
            if not self.api_token:
                errors.append(
                    "API_TOKEN is not set — all protected endpoints will return 401."
                )
            if not self.nrs_client_secret:
                errors.append(
                    "NRS_CLIENT_SECRET is not set — NRS submission will fail in production."
                )
            if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
                errors.append(
                    "DATABASE_URL still points to localhost — use the production database URL."
                )
            if "localhost" in self.storage_endpoint:
                errors.append(
                    "STORAGE_ENDPOINT still points to localhost — use the production object-store URL."
                )

        if errors:
            bullet_list = "\n  - ".join(errors)
            raise RuntimeError(
                f"Mai Filer startup failed — {len(errors)} configuration error(s):\n  - {bullet_list}"
            )

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
