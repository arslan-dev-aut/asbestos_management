"""Authentication context dependency.

``get_context()`` is used as ``Depends(get_context)`` in every route handler.
It reads the verified tenant + user identity that ``TokenIntrospectionMiddleware``
(auth_introspect.py) has already placed on ``request.state`` before the handler
runs.  No token parsing happens here — the middleware owns that responsibility.

If the middleware is not registered (e.g. in unit tests) the dependency falls
back to the legacy unverified-decode path so existing tests keep working.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from fastapi import Depends, Header, Request

from backend.config import get_settings
from backend.database.exceptions import UnauthorizedError


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    user_id: str


# ------------------------------------------------------------------ #
# Internal helpers (kept for the no-middleware fallback path only)
# ------------------------------------------------------------------ #

def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _unverified_claims(token: str) -> dict:
    try:
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, binascii.Error):
        return {}


# ------------------------------------------------------------------ #
# Primary dependency
# ------------------------------------------------------------------ #

async def get_context(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    """Return the verified ``AuthContext`` for the current request.

    Normal path (middleware active):
      ``TokenIntrospectionMiddleware`` has already validated the token against
      the IDP and written ``auth_user_id`` / ``auth_tenant_id`` onto
      ``request.state``.  We just read them here.

    Fallback path (middleware not registered, e.g. unit tests):
      Performs the legacy unverified-decode + dev-fallback logic so the app
      still starts without the middleware in place.
    """

    # ── Primary: read identity verified by the middleware ─────────────────
    auth_user_id = getattr(request.state, "auth_user_id", None)
    auth_tenant_id = getattr(request.state, "auth_tenant_id", None)

    if auth_user_id and auth_tenant_id:
        return AuthContext(tenant_id=auth_tenant_id, user_id=auth_user_id)

    # ── Fallback: middleware not active ───────────────────────────────────
    if not x_tenant_id:
        raise UnauthorizedError("X-Tenant-Id header is required.")

    settings = get_settings()
    token = _bearer_token(authorization)

    if token:
        claims = _unverified_claims(token)
        jwt_tenant = claims.get("tid")
        if jwt_tenant and str(jwt_tenant).lower() != str(x_tenant_id).lower():
            raise UnauthorizedError("Tenant mismatch: X-Tenant-Id does not match token.")
        user_id = claims.get(settings.jwt_user_claim)
        if not user_id:
            raise UnauthorizedError("User id (sub) missing from token.")
        return AuthContext(tenant_id=str(x_tenant_id), user_id=str(user_id))

    if settings.auth_dev_fallback:
        return AuthContext(tenant_id=str(x_tenant_id), user_id=settings.dev_user_id)

    raise UnauthorizedError("Missing bearer token.")


async def get_tenant_id(ctx: AuthContext = Depends(get_context)) -> str:
    return ctx.tenant_id
