"""Single application configuration via pydantic-settings.

All environment variables are read here once and exposed through the cached
``get_settings()`` singleton. No other module should read ``os.environ`` directly.

Note: ``load_dotenv()`` is called below so that ``os.environ`` is populated from
``.env`` at import time. This ensures the joblogic SDK (which reads from
``os.getenv()`` directly) sees the same values as pydantic-settings.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
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
    application_environment: str = Field(default="development")
    api_base_prefix: str = Field(default="/api/v1/asbestos")
    project_name: str = Field(default="JobLogic Asbestos Management API")

    # ---- Azure App Configuration (production credential source) ----
    # In production, AppConfigManager.load() reads Automation/<AUTOMATION_NAME>/*
    # at startup and injects values into the environment. These two vars are set
    # at the Container App level by the deploy pipeline (deploy/scripts/containerapp.sh).
    app_configuration_connection_string: str = Field(default="")
    automation_name: str = Field(default="asbestos-management")

    # ---- Database (Azure PostgreSQL) ----
    # No connection string is hardcoded. Discrete parts come from config
    # (local .env / Azure App Config). Default auth is Entra (token) — an
    # access token is fetched at connect time and used as the password.
    db_host: str = Field(default="")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="automation-asbestos")
    db_user: str = Field(default="")  # AAD principal / Postgres role name
    db_ssl_mode: str = Field(default="require")  # Azure requires SSL
    db_auth_mode: str = Field(default="aad_token")  # aad_token | password
    # Entra token settings (aad_token mode):
    aad_token_scope: str = Field(default="https://ossrdbms-aad.database.windows.net/.default")
    # User-assigned managed identity client id (set by the deploy pipeline in prod).
    azure_client_id: str = Field(default="")
    # Optional full URL for local password-mode dev only (never committed):
    database_url: str = Field(default="")
    db_echo: bool = Field(default=False)
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)

    # ---- Auth (OIDC / JobLogic Identity Server) ----
    # Multi-tenant marketplace pattern (per repo conventions): the tenant is
    # taken from the X-Tenant-Id header via joblogic_sdk.auth.get_tenant_id; the
    # acting user is the `sub` claim of the (gateway/SDK-validated) bearer token.
    idp_client_id: str = Field(default="")
    idp_authority: str = Field(default="")
    idp_client_secret: str = Field(default="")  # required for token introspection
    jwt_user_claim: str = Field(default="sub")
    # URL to redirect to when a token is missing or rejected by the IDP.
    introspect_redirect_url: str = Field(default="https://example.com/unauthorised")
    # Local dev fallback: trust the X-Tenant-Id header without a bearer token.
    auth_dev_fallback: bool = Field(default=False)
    # Actual DB user ID used as last resort when auth_dev_fallback is True and
    # no bearer token is present. Must be set explicitly — no default GUID.
    dev_user_id: str = Field(default="")

    # ---- User identity resolution ----
    # Base URL of the JobLogic internal API used to map an IDP identity user ID
    # (the `sub` claim) to the actual user UniqueId stored in the database.
    # user_detail_api_base_url: str = Field(
    #     default="https://jllivemarketappinternalapi.azurewebsites.net"
    # )
    user_detail_api_base_url: str = Field(
        default="https://uat-marketappapi.joblogicinternal.com"
    )
    

    # ---- Azure Blob Storage ----
    # Default auth is Entra/managed identity (account URL + DefaultAzureCredential),
    # consistent with the DB. A connection string may be supplied for local dev.
    azure_storage_account_url: str = Field(default="")  # https://<acct>.blob.core.windows.net
    azure_storage_container: str = Field(default="asbestos-documents")
    azure_storage_connection_string: str = Field(default="")  # optional (local dev)
    blob_sas_expiry_seconds: int = Field(default=900)
    storage_public_base_url: str = Field(default="")  # optional CDN/base for qr images

    # ---- Public QR page ----
    public_base_url: str = Field(default="http://localhost:8000")

    # ---- Business rules ----
    amp_expiry_warning_days: int = Field(default=30)
    notes_max_length: int = Field(default=250)
    notes_truncate_length: int = Field(default=100)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024)

    # ---- CORS ----
    cors_allow_origins: str = Field(default="http://localhost:5173,https://go.joblogic.com")

    @property
    def is_production(self) -> bool:
        return self.application_environment.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
