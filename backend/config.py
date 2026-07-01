"""Single application configuration via pydantic-settings.

All environment variables are read here once and exposed through the cached
``get_settings()`` singleton. No other module should read ``os.environ`` directly.

Note: ``load_dotenv()`` is called below so that ``os.environ`` is populated from
``.env`` at import time. This ensures the joblogic SDK (which reads from
``os.getenv()`` directly) sees the same values as pydantic-settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env next to this file (backend/.env) so it loads regardless of the
# process working directory.
_ENV_FILE = str(Path(__file__).resolve().parent / ".env")

# Populate os.environ from .env so the joblogic SDK (which calls os.getenv()
# directly) sees the same values as pydantic-settings. override=False means
# real env vars (e.g. set at the Container App level in production) always win.
load_dotenv(_ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- General ----
    application_environment: str = Field()
    api_base_prefix: str = Field()
    project_name: str = Field()

    # ---- Azure App Configuration (production credential source) ----
    # In production, AppConfigManager.load() reads Automation/<AUTOMATION_NAME>/*
    # at startup and injects values into the environment. These two vars are set
    # at the Container App level by the deploy pipeline.
    app_configuration_connection_string: str = Field()
    automation_name: str = Field()

    # ---- Database (Azure PostgreSQL) ----
    db_host: str = Field()
    db_port: int = Field(gt=0, le=65535)
    db_name: str = Field()
    db_user: str = Field()
    db_ssl_mode: str = Field()
    db_auth_mode: Literal["aad_token", "password"] = Field()
    aad_token_scope: str = Field()
    azure_client_id: str = Field()
    database_url: str = Field()  # optional: full URL for local password-mode dev
    db_echo: bool = Field()
    db_pool_size: int = Field(ge=1)
    db_max_overflow: int = Field(ge=0)

    # ---- Auth (OIDC / JobLogic Identity Server) ----
    idp_client_id: str = Field()
    idp_authority: str = Field()
    idp_client_secret: str = Field()
    jwt_user_claim: str = Field()
    # JWT claim carrying the tenant id; the X-Tenant-Id header must match it.
    jwt_tenant_claim: str = Field(default="tid")
    introspect_redirect_url: str = Field()
    auth_dev_fallback: bool = Field()
    dev_user_id: str = Field()

    # ---- User identity resolution ----
    user_detail_api_base_url: str = Field()

    # ---- Azure Blob Storage ----
    azure_storage_account_url: str = Field()
    azure_storage_container: str = Field()
    azure_storage_connection_string: str = Field()  # optional: local dev only
    blob_sas_expiry_seconds: int = Field()
    storage_public_base_url: str = Field()  # optional: CDN/base for QR images

    # ---- Public QR page ----
    public_base_url: str = Field()

    # ---- Business rules ----
    amp_expiry_warning_days: int = Field(ge=0)
    notes_max_length: int = Field(gt=0)
    notes_truncate_length: int = Field(gt=0)
    max_upload_bytes: int = Field(gt=0)
    default_page_size: int = Field(gt=0)
    max_page_size: int = Field(gt=0)
    # Hard cap on rows accepted in a single bulk-upload sheet.
    max_bulk_rows: int = Field(default=10_000, gt=0)
    # Public QR endpoint: per-IP rate limit (requests/minute).
    public_rate_limit_per_minute: int = Field(default=30, gt=0)

    # ---- CORS ----
    cors_allow_origins: str = Field()

    @property
    def is_production(self) -> bool:
        return self.application_environment.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _guard_production_invariants(self) -> "Settings":
        # An unsigned-token dev bypass must never be active in production.
        if self.is_production and self.auth_dev_fallback:
            raise ValueError(
                "AUTH_DEV_FALLBACK must be false in production — it bypasses IDP "
                "token validation and trusts the X-Tenant-Id header unverified."
            )
        if self.default_page_size > self.max_page_size:
            raise ValueError("DEFAULT_PAGE_SIZE cannot exceed MAX_PAGE_SIZE.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
