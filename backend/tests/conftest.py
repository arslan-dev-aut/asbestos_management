"""Test configuration and fixtures.

Sets a complete env BEFORE Settings is constructed, runs the app against an
in-memory SQLite database (with a JSONB->JSON shim so the Postgres models
compile), and stubs the two external dependencies — MainSubSys (JicroClient)
and Azure Blob Storage — so every endpoint can be exercised offline.
"""

from __future__ import annotations

import os
import uuid

# ── 1. Environment — every required Setting, before backend.config imports ───
_TEST_ENV = {
    "APPLICATION_ENVIRONMENT": "test",
    "API_BASE_PREFIX": "/api/v1/asbestos",
    "PROJECT_NAME": "Asbestos Test",
    "APP_CONFIGURATION_CONNECTION_STRING": "",
    "AUTOMATION_NAME": "asbestos-management",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "test",
    "DB_USER": "test",
    "DB_SSL_MODE": "disable",
    "DB_AUTH_MODE": "password",
    "AAD_TOKEN_SCOPE": "https://example/.default",
    "AZURE_CLIENT_ID": "",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "DB_ECHO": "false",
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "10",
    "IDP_CLIENT_ID": "",
    "IDP_AUTHORITY": "",
    "IDP_CLIENT_SECRET": "",
    "JWT_USER_CLAIM": "sub",
    "JWT_TENANT_CLAIM": "tid",
    "INTROSPECT_REDIRECT_URL": "",
    "AUTH_DEV_FALLBACK": "true",
    "DEV_USER_ID": "00000000-0000-0000-0000-0000000000aa",
    "USER_DETAIL_API_BASE_URL": "http://user-detail.test",
    "AZURE_STORAGE_ACCOUNT_URL": "",
    "AZURE_STORAGE_CONTAINER": "asbestos-documents",
    "AZURE_STORAGE_CONNECTION_STRING": "",
    "BLOB_SAS_EXPIRY_SECONDS": "900",
    "STORAGE_PUBLIC_BASE_URL": "",
    "PUBLIC_BASE_URL": "http://localhost:8000",
    "AMP_EXPIRY_WARNING_DAYS": "30",
    "NOTES_MAX_LENGTH": "250",
    "NOTES_TRUNCATE_LENGTH": "100",
    "MAX_UPLOAD_BYTES": "26214400",
    "DEFAULT_PAGE_SIZE": "10",
    "MAX_PAGE_SIZE": "50",
    "MAX_BULK_ROWS": "10000",
    "QR_TOKEN_TTL_DAYS": "0",
    "PUBLIC_RATE_LIMIT_PER_MINUTE": "30",
    "CORS_ALLOW_ORIGINS": "http://localhost:5173",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)

# ── 2. Postgres-type shims so the models create + round-trip on SQLite ───────
# JSONB has no SQLite compiler; render it as JSON.
# UUID renders its bare type name "UUID" which gives SQLite NUMERIC affinity —
# an all-digit UUID (e.g. 1111...) is then silently coerced to a float. Render
# it as CHAR(36) so the column keeps TEXT affinity (prod still uses native PG UUID).
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(JSONB, "sqlite")
def _render_jsonb_as_json(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


@compiles(UUID, "sqlite")
def _render_uuid_as_char(element, compiler, **kw):  # noqa: ANN001
    return "CHAR(36)"


import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database.postgres import Base, get_session  # noqa: E402
import backend.database.db_models  # noqa: E402,F401  (register tables)
from backend.integrations.mainsubsys import ResolvedNames  # noqa: E402
from backend.main import app  # noqa: E402

TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT_ID = "22222222-2222-2222-2222-222222222222"


# ── 3. Shared in-memory engine + session override ────────────────────────────
@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def client(session_factory, monkeypatch):
    # Override the request-scoped DB session with the in-memory one.
    async def _override_get_session():
        async with session_factory() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_get_session

    # ── Stub MainSubSys (no real JicroClient / network) ──────────────────────
    from backend.integrations import mainsubsys

    def _name(prefix, _id):
        return f"{prefix} {str(_id)[:8]}"

    async def _aenter(self):
        return self

    async def _aexit(self, *a):
        return None

    async def _resolve_all(self, *, customer_ids=None, site_ids=None, asset_ids=None, user_ids=None):
        return ResolvedNames(
            customers={str(c): _name("Customer", c) for c in (customer_ids or set())},
            sites={str(s): _name("Site", s) for s in (site_ids or set())},
            assets={str(a): _name("Asset", a) for a in (asset_ids or set())},
            users={str(u): _name("User", u) for u in (user_ids or set())},
        )

    async def _resolve_customers(self, ids):
        return {str(c): _name("Customer", c) for c in ids}

    async def _resolve_sites(self, ids):
        return {str(s): _name("Site", s) for s in ids}

    async def _resolve_users(self, ids):
        return {str(u): _name("User", u) for u in ids}

    async def _search_customer_ids(self, text):
        return []

    async def _search_site_ids(self, text):
        return []

    async def _find_asset_by_name(self, name):
        return None

    async def _list_customers(self, search=None, page_size=20):
        return [{"id": 1, "uniqueId": str(uuid.uuid4()), "name": "Acme"}]

    async def _list_sites_for_customer(self, customer_unique_id, search=None, page_size=500):
        return [{"Id": 1, "UniqueId": str(uuid.uuid4()), "Name": "HQ"}]

    async def _list_assets_for_site(self, site_unique_id, search=None, page_size=500):
        return [{"Id": 1, "UniqueId": str(uuid.uuid4()), "Description": "Boiler"}]

    for name, fn in {
        "__aenter__": _aenter,
        "__aexit__": _aexit,
        "resolve_all": _resolve_all,
        "resolve_customers": _resolve_customers,
        "resolve_sites": _resolve_sites,
        "resolve_users": _resolve_users,
        "search_customer_ids": _search_customer_ids,
        "search_site_ids": _search_site_ids,
        "find_asset_by_name": _find_asset_by_name,
        "list_customers": _list_customers,
        "list_sites_for_customer": _list_sites_for_customer,
        "list_assets_for_site": _list_assets_for_site,
    }.items():
        monkeypatch.setattr(mainsubsys.MainSubSysClient, name, fn, raising=False)

    # ── Stub blob storage ────────────────────────────────────────────────────
    from backend.core import storage

    async def _put_object(key, data, content_type):
        return key

    async def _presigned_url(key):
        return f"https://blob.test/{key}?sig=x"

    async def _public_url(key):
        return f"https://blob.test/{key}"

    async def _delete_object(key):
        return None

    monkeypatch.setattr(storage, "put_object", _put_object)
    monkeypatch.setattr(storage, "presigned_url", _presigned_url)
    monkeypatch.setattr(storage, "public_url", _public_url)
    monkeypatch.setattr(storage, "delete_object", _delete_object)

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Tenant-Id": TENANT_ID},
    ) as c:
        yield c

    app.dependency_overrides.clear()
