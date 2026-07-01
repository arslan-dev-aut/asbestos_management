"""FastAPI application entry point for the B6 Asbestos Management backend.

Registers domain routers under the API prefix, mounts the unauthenticated
public QR view at the root, configures CORS, and maps domain exceptions to a
consistent ``{success, message, detail}`` JSON envelope.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.config import get_settings
from backend.core.storage import close_storage
from backend.database.exceptions import DomainError
from backend.database.postgres import dispose_engine, get_engine
from backend.middleware.auth_introspect import TokenIntrospectionMiddleware, close_http_session

logger = logging.getLogger("asbestos")
from backend.domains.acm_entries.acm_entries_router import router as acm_entries_router
from backend.domains.audit.audit_router import router as audit_router
from backend.domains.bulk.bulk_router import router as bulk_router
from backend.domains.configuration.configuration_router import router as configuration_router
from backend.domains.documents.documents_router import router as documents_router
from backend.domains.files.files_router import router as files_router
from backend.domains.lookup.lookup_router import router as lookup_router
from backend.domains.qrcode.qrcode_router import public_router
from backend.domains.qrcode.qrcode_router import router as qrcode_router
from backend.domains.register.register_router import router as register_router

def _load_app_config_eagerly() -> None:
    """Load Automation/<name>/* from Azure App Config into the environment BEFORE
    the app/CORS/title are built, so every setting (including CORS origins) sees
    the production values — not just lazily-read ones.

    Runs at import time when no event loop is active (the normal uvicorn case).
    If a loop is already running (e.g. under tests), this is skipped and the
    lifespan hook performs the load instead.
    """
    cfg = get_settings()
    if not cfg.app_configuration_connection_string:
        return
    try:
        asyncio.get_running_loop()
        return  # inside a running loop — defer to lifespan
    except RuntimeError:
        pass
    try:
        from joblogic_sdk.app_config import AppConfigManager

        asyncio.run(AppConfigManager.load())
        get_settings.cache_clear()
    except Exception as exc:  # noqa: BLE001 - surface but don't crash boot
        logger.warning("Eager App Config load failed: %s", exc)


_load_app_config_eagerly()
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fallback load for the in-event-loop case (eager import-time load skipped).
    cfg = get_settings()
    if cfg.app_configuration_connection_string:
        try:
            from joblogic_sdk.app_config import AppConfigManager

            await AppConfigManager.load()
            get_settings.cache_clear()
        except Exception as exc:  # noqa: BLE001 - surface but don't crash boot
            logger.warning("App Config load failed: %s", exc)

    # Pre-warm the DB connection pool so the first user request doesn't pay the
    # cold-start cost (AAD token fetch + TCP+TLS to Azure PostgreSQL, ~4-5 s).
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB pool pre-warm failed: %s", exc)

    yield
    await dispose_engine()
    await close_storage()
    await close_http_session()


app = FastAPI(
    title=settings.project_name,
    description="B6 Asbestos Management — contractor back-office register API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TokenIntrospectionMiddleware)


# ---- Exception handlers (routers stay thin) ----
@app.exception_handler(DomainError)
async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    def _safe(errors: list) -> list:
        result = []
        for e in errors:
            entry = {k: v for k, v in e.items() if k not in ("ctx", "url")}
            if "ctx" in e:
                # ctx values may contain exception objects — coerce to str
                entry["ctx"] = {
                    k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                    for k, v in e["ctx"].items()
                }
            result.append(entry)
        return result

    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Validation error.", "detail": _safe(exc.errors())},
    )


@app.exception_handler(Exception)
async def _unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Any error not modelled as a DomainError still gets the standard envelope —
    # and the internal detail is logged, never leaked to the client.
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "An unexpected error occurred.", "detail": None},
    )


# ---- Routers ----
# Order matters: bulk_router exposes the static /register/export and
# /register/bulk-upload/* paths and must be registered BEFORE register_router's
# dynamic /register/{asbestos_site_id} route.
_PREFIX = settings.api_base_prefix
app.include_router(configuration_router, prefix=_PREFIX)
app.include_router(audit_router, prefix=_PREFIX)
app.include_router(files_router, prefix=_PREFIX)
app.include_router(lookup_router, prefix=_PREFIX)
app.include_router(bulk_router, prefix=_PREFIX)
app.include_router(documents_router, prefix=_PREFIX)
app.include_router(acm_entries_router, prefix=_PREFIX)
app.include_router(qrcode_router, prefix=_PREFIX)
app.include_router(register_router, prefix=_PREFIX)

# Unauthenticated public QR view at the application root.
app.include_router(public_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "healthy"}


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Add Bearer + X-Tenant-Id security scheme so Swagger shows the Authorize button.
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste your access token. Swagger adds 'Bearer ' automatically.",
        },
        "TenantId": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Tenant-Id",
            "description": "Your tenant UUID.",
        },
    }
    # Apply both schemes globally to every operation.
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation["security"] = [{"BearerAuth": [], "TenantId": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi
