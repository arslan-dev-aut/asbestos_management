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

_ENV_FILE = str(Path(__file__).resolve().parent / ".env")

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
    project_name: str = Field(default="Asbestos Sites API")

    # ---- Database (Azure PostgreSQL) ----
    db_host: str = Field(default="")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="automation-asbestos")
    db_user: str = Field(default="")
    db_ssl_mode: str = Field(default="require")
    db_auth_mode: str = Field(default="aad_token")  # aad_token | password
    aad_token_scope: str = Field(default="https://ossrdbms-aad.database.windows.net/.default")
    azure_client_id: str = Field(default="")
    database_url: str = Field(default="")
    db_echo: bool = Field(default=False)
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)

    # ---- Azure Blob Storage ----
    azure_storage_account_url: str = Field(default="")
    azure_storage_container: str = Field(default="asbestos-documents")
    azure_storage_connection_string: str = Field(default="")
    blob_sas_expiry_seconds: int = Field(default=900)
    storage_public_base_url: str = Field(default="")

    # ---- Business rules ----
    amp_expiry_warning_days: int = Field(default=30)
    notes_max_length: int = Field(default=250)
    notes_truncate_length: int = Field(default=100)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024)
    default_page_size: int = Field(default=10)
    max_page_size: int = Field(default=50)
    max_bulk_rows: int = Field(default=10_000)

    # ---- SQL Server (subcontractor mapping database) ----
    sqlserver_host: str = Field(default="")
    sqlserver_port: int = Field(default=1433)
    sqlserver_database: str = Field(default="")
    sqlserver_user: str = Field(default="")
    sqlserver_password: str = Field(default="")
    sqlserver_mapping_table: str = Field(default="SubContractor.SiteMapping")
    sqlserver_tenant_mapping_table: str = Field(default="SubContractor.TenantMapping")

    # ---- CORS ----
    cors_allow_origins: str = Field(default="*")

    @property
    def is_production(self) -> bool:
        return self.application_environment.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
