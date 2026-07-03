"""FastAPI application entry point for the Asbestos Sites backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.config import get_settings
from backend.database.exceptions import DomainError
from backend.database.postgres import dispose_engine, get_engine
from backend.domains.asbestos_sites.asbestos_sites_router import router as asbestos_sites_router

logger = logging.getLogger("asbestos")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB pool pre-warm failed: %s", exc)

    yield
    await dispose_engine()


app = FastAPI(
    title=settings.project_name,
    description="Asbestos Sites API.",
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
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "An unexpected error occurred.", "detail": None},
    )


_PREFIX = settings.api_base_prefix
app.include_router(asbestos_sites_router, prefix=_PREFIX)


@app.get("/health", tags=["health"], include_in_schema=False)
async def health() -> dict:
    return {"status": "healthy"}
