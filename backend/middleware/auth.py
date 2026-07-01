"""Authentication context dependency.

``get_context()`` is used as ``Depends(get_context)`` in every route handler.

Mobile routes:
  ``TokenIntrospectionMiddleware`` validates the token against the IDP and
  writes ``auth_user_id`` / ``auth_tenant_id`` onto ``request.state``.
  We just read them here.

Non-mobile routes (middleware skipped):
  User ID is expected directly in the ``X-User-Id`` header — no token parsing.
  ``X-Tenant-Id`` is still required.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, Request

from backend.config import get_settings
from backend.database.exceptions import UnauthorizedError


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    user_id: str


async def get_context(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AuthContext:
    # ── Mobile path: identity resolved + verified by the middleware ───────
    auth_user_id = getattr(request.state, "auth_user_id", None)
    auth_tenant_id = getattr(request.state, "auth_tenant_id", None)
    if auth_user_id and auth_tenant_id:
        return AuthContext(tenant_id=auth_tenant_id, user_id=auth_user_id)

    # ── Non-mobile path: trust X-Tenant-Id + X-User-Id headers directly ──
    if not x_tenant_id:
        raise UnauthorizedError("X-Tenant-Id header is required.")

    # Dev fallback (tests / local without headers)
    if not x_user_id:
        settings = get_settings()
        if settings.auth_dev_fallback:
            return AuthContext(tenant_id=str(x_tenant_id), user_id=settings.dev_user_id)
        raise UnauthorizedError("X-User-Id header is required.")

    return AuthContext(tenant_id=str(x_tenant_id), user_id=str(x_user_id))


async def get_tenant_id(ctx: AuthContext = Depends(get_context)) -> str:
    return ctx.tenant_id
