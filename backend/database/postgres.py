"""Async SQLAlchemy engine + session factory for Azure PostgreSQL.

Authentication is Entra (token-based) by default — no passwords stored anywhere.

Credential selection is explicit:
- Azure (IDENTITY_ENDPOINT env var present): User-Assigned Managed Identity
- Local dev (no IDENTITY_ENDPOINT): AzureCliCredential (az login)

In aad_token mode the Postgres username is taken from DB_USER in config.
Locally, if DB_USER is not set, it is inferred automatically from the az login
token's JWT claims (preferred_username / upn) — no manual config needed for
developers; they only need to run 'az login' once.

A ``password`` mode is available for fully local dev without Azure credentials.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import AsyncGenerator
from urllib.parse import quote

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_credential = None  # azure.identity.aio credential (created lazily)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models in ``db_models.py``."""


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def _in_azure() -> bool:
    """True when running inside an Azure-managed environment.

    Azure (Container Apps, App Service, VMs) automatically injects the
    IDENTITY_ENDPOINT environment variable when a managed identity is attached.
    """
    return bool(os.environ.get("IDENTITY_ENDPOINT"))


def _make_credential():
    """Explicit credential selection — avoids DefaultAzureCredential's long
    fallback chain, giving faster startup and clearer error messages.

    Azure  → ManagedIdentityCredential (UAMI if azure_client_id is set)
    Local  → AzureCliCredential (az login)
    """
    settings = get_settings()
    if _in_azure():
        from azure.identity.aio import ManagedIdentityCredential

        client_id = settings.azure_client_id or None
        return (
            ManagedIdentityCredential(client_id=client_id)
            if client_id
            else ManagedIdentityCredential()
        )
    from azure.identity.aio import AzureCliCredential

    return AzureCliCredential()


# ---------------------------------------------------------------------------
# Local DB username inference
# ---------------------------------------------------------------------------

def _infer_local_db_user() -> str | None:
    """Decode the az login token and extract the Postgres-compatible username.

    Postgres Flexible Server with Entra auth expects the Entra UPN or display
    name as the login. On local dev we fetch a one-off sync token from the
    AzureCliCredential and read the UPN claim rather than requiring every
    developer to manually set DB_USER.
    """
    try:
        from azure.identity import AzureCliCredential as _SyncCli

        token = _SyncCli().get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        ).token
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        claims = json.loads(base64.urlsafe_b64decode(part))
        for key in ("preferred_username", "upn", "unique_name", "email"):
            val = claims.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# URL and connect-args construction
# ---------------------------------------------------------------------------

def _build_db_url() -> str:
    """Build the async SQLAlchemy connection URL.

    password mode  → DATABASE_URL env var (full URL, local dev only)
    aad_token mode → constructed from discrete parts; no password in the URL
                     (token supplied per-connection via _build_connect_args)
    """
    settings = get_settings()

    if settings.db_auth_mode == "password":
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL must be set when DB_AUTH_MODE=password.")
        return settings.database_url

    if not (settings.db_host and settings.db_name):
        raise RuntimeError("DB_HOST and DB_NAME are required for Entra (aad_token) auth.")

    user = settings.db_user
    if not user:
        if _in_azure():
            raise RuntimeError(
                "DB_USER (UAMI display name) must be set in App Config for production."
            )
        user = _infer_local_db_user()
        if not user:
            raise RuntimeError(
                "Could not infer Postgres username from az login token. "
                "Run 'az login' or set DB_USER in .env."
            )

    return (
        f"postgresql+asyncpg://{quote(user)}@"
        f"{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )


def _build_connect_args() -> dict:
    """asyncpg connect args.

    In aad_token mode the password is an async callable that fetches a fresh
    Entra token at connect time. SSL is always required for Azure PostgreSQL.
    """
    global _credential
    settings = get_settings()
    connect_args: dict = {"ssl": settings.db_ssl_mode}

    if settings.db_auth_mode == "aad_token":
        if _credential is None:
            _credential = _make_credential()

        async def _token_password() -> str:
            token = await _credential.get_token(settings.aad_token_scope)
            return token.token

        connect_args["password"] = _token_password

    return connect_args


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            _build_db_url(),
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            future=True,
            connect_args=_build_connect_args(),
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped session; rollback on error, always close."""
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    global _engine, _credential
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    if _credential is not None:
        await _credential.close()
        _credential = None
