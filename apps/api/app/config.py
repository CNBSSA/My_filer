"""Typed application settings loaded from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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

    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket: str = "mai-filer-dev"
    storage_region: str = "ng-lagos-1"

    nrs_base_url: str = "https://api.nrs.gov.ng/v1"
    nrs_client_id: str = ""
    nrs_client_secret: str = ""
    nrs_business_id: str = ""

    identity_aggregator: Literal["dojah", "seamfix", "prembly"] = "dojah"
    dojah_api_key: str = ""
    dojah_app_id: str = ""
    seamfix_api_key: str = ""
    prembly_api_key: str = ""

    nin_vault_key: str = ""
    nin_hash_salt: str = ""

    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_issuer: str = "mai-filer"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
