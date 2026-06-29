"""Token validation middleware — validates every bearer token by calling the
Identity Provider's UserInfo endpoint on each request.

Why UserInfo for HS256 tokens?
  Joblogic IdentityServer signs tokens with HS256 (HMAC / symmetric algorithm).
  JWKS-based local verification only works for asymmetric algorithms (RS256 etc).
  The HS256 shared secret is private to the IDP, so we cannot verify locally.
  Instead we send the token to the IDP's UserInfo endpoint — the IDP validates
  it internally and returns the user claims if valid, or 401 if not.

Flow per request:
  1. Skip unauthenticated paths (/health, /docs, /public/*).
  2. Extract the bearer token from the ``Authorization`` header.
  3. GET {IDP_AUTHORITY}/connect/userinfo with the token as a Bearer token.
       200  → token is valid; extract ``sub`` (identity user ID).
       401  → token is expired, revoked, or fake → reject with 401.
       other → IDP error → reject with 401 and include detail.
  4. Resolve identity user ID → actual DB user ID via the user detail API.
       GET {USER_DETAIL_API_BASE_URL}/api/tenantless/UK/companies/
           get-web-user-detail-by-identity?IdentityUserId={sub}
       Response UniqueId is the user ID stored in our database.
  5. No token + AUTH_DEV_FALLBACK  → skip IDP call; if a token is present
       decode sub unverified and resolve it; otherwise use DEV_USER_ID.
  6. No token (production)         → 401 JSON immediately.

Required env vars (production):
  IDP_AUTHORITY              e.g. https://uatidentityserver.joblogic.com
  USER_DETAIL_API_BASE_URL   e.g. https://jllivemarketappinternalapi.azurewebsites.net

Optional:
  AUTH_DEV_FALLBACK   Set to true in local .env to bypass IDP (dev only).
  DEV_USER_ID         Actual DB user ID used only when AUTH_DEV_FALLBACK is
                      True and no bearer token is present.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from collections import OrderedDict

import aiohttp
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import get_settings

logger = logging.getLogger(__name__)

# ── Shared HTTP session ───────────────────────────────────────────────────────
# One ClientSession for the process lifetime — reuses TCP+TLS connections to
# the IDP and user-detail API instead of opening a new handshake every request.
# Initialised on first use; call close_http_session() at app shutdown.
_http_session: aiohttp.ClientSession | None = None


def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(limit=20)
        _http_session = aiohttp.ClientSession(connector=connector)
    return _http_session


async def close_http_session() -> None:
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None


# ── Cache 1: token → user_id ─────────────────────────────────────────────────
# Skips BOTH external calls on repeat requests with the same token.
# TTL = token's own exp claim minus a 30 s safety buffer, so a 1-hour token is
# cached for ~59.5 minutes. Falls back to 60 s if exp cannot be decoded.
# Capped at 500 entries (LRU eviction).
_TOKEN_CACHE_FALLBACK_TTL = 60
_TOKEN_CACHE_SAFETY_BUFFER = 30
_TOKEN_CACHE_MAX = 500
_token_cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

# ── Cache 2: identity_user_id (sub) → db_user_id ─────────────────────────────
# sub is a permanent identity claim — it always maps to the same DB user.
# Caching it means _resolve_db_user_id (~2 s) is only ever called ONCE per user
# per process lifetime, even when the token rotates on refresh. TTL = 24 h.
# Capped at 1000 entries.
_SUB_CACHE_TTL = 86_400  # 24 hours
_SUB_CACHE_MAX = 1000
_sub_cache: OrderedDict[str, tuple[str, float]] = OrderedDict()


def _token_ttl(token: str) -> float:
    try:
        claims = _decode_claims_unverified(token)
        exp = claims.get("exp")
        if exp:
            remaining = float(exp) - time.time() - _TOKEN_CACHE_SAFETY_BUFFER
            return max(remaining, 0)
    except Exception:
        pass
    return _TOKEN_CACHE_FALLBACK_TTL


def _cache_get(token: str) -> str | None:
    entry = _token_cache.get(token)
    if entry is None:
        return None
    user_id, expires_at = entry
    if time.monotonic() > expires_at:
        _token_cache.pop(token, None)
        return None
    _token_cache.move_to_end(token)
    return user_id


def _cache_set(token: str, user_id: str) -> None:
    ttl = _token_ttl(token)
    if ttl <= 0:
        return
    if token in _token_cache:
        _token_cache.move_to_end(token)
    _token_cache[token] = (user_id, time.monotonic() + ttl)
    if len(_token_cache) > _TOKEN_CACHE_MAX:
        _token_cache.popitem(last=False)


def _sub_cache_get(identity_user_id: str) -> str | None:
    entry = _sub_cache.get(identity_user_id)
    if entry is None:
        return None
    user_id, expires_at = entry
    if time.monotonic() > expires_at:
        _sub_cache.pop(identity_user_id, None)
        return None
    _sub_cache.move_to_end(identity_user_id)
    return user_id


def _sub_cache_set(identity_user_id: str, user_id: str) -> None:
    if identity_user_id in _sub_cache:
        _sub_cache.move_to_end(identity_user_id)
    _sub_cache[identity_user_id] = (user_id, time.monotonic() + _SUB_CACHE_TTL)
    if len(_sub_cache) > _SUB_CACHE_MAX:
        _sub_cache.popitem(last=False)

_SKIP_PATHS: frozenset[str] = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})

_SKIP_PREFIXES: tuple[str, ...] = ("/public/",)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _decode_claims_unverified(token: str) -> dict:
    """Read JWT payload without verification — used only for dev fallback."""
    try:
        segment = token.split(".")[1]
        padded = segment + "=" * (-len(segment) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, binascii.Error):
        return {}


def _userinfo_url(authority: str) -> str:
    return f"{authority.rstrip('/')}/connect/userinfo"


def _unauthorized(message: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"success": False, "message": message, "detail": detail},
    )


async def _call_userinfo(token: str, authority: str) -> dict:
    """Call the IDP UserInfo endpoint using the shared HTTP session.

    Returns the claims dict on 200.
    Raises ``PermissionError`` with a descriptive message on any failure.
    """
    url = _userinfo_url(authority)
    logger.debug("Calling UserInfo endpoint: %s", url)
    try:
        http = get_http_session()
        async with http.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            body = await resp.text()
            logger.debug("UserInfo response: status=%s body=%s", resp.status, body[:200])

            if resp.status == 200:
                return await resp.json(content_type=None)

            if resp.status == 401:
                raise PermissionError("Token rejected by identity provider (401) — expired or invalid.")

            raise PermissionError(
                f"UserInfo endpoint returned HTTP {resp.status}: {body[:300]}"
            )

    except aiohttp.ClientConnectorError as exc:
        raise PermissionError(
            f"Cannot reach identity provider at {url}. "
            f"Check IDP_AUTHORITY and network connectivity. Detail: {exc}"
        ) from exc
    except aiohttp.ClientError as exc:
        raise PermissionError(f"Network error calling UserInfo endpoint: {exc}") from exc


_USER_DETAIL_PATH = "/api/tenantless/UK/companies/get-web-user-detail-by-identity"


async def _resolve_db_user_id(identity_user_id: str, api_base_url: str) -> str | None:
    """Map an IDP identity user ID (sub claim) to the actual DB user UniqueId.

    Calls the JobLogic internal user detail API.  Returns ``None`` if the user
    cannot be resolved (API error, unknown identity, or empty response).
    """
    url = f"{api_base_url.rstrip('/')}{_USER_DETAIL_PATH}"
    logger.debug("Resolving DB user ID for identity=%s via %s", identity_user_id, url)
    try:
        http = get_http_session()
        async with http.get(
            url,
            params={"IdentityUserId": identity_user_id},
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "User detail API returned HTTP %s for identity_user_id=%s body=%s",
                    resp.status, identity_user_id, body[:200],
                )
                return None

        # The API may return:
        #   - a JSON-quoted string  → e.g. "673ae391-..."  (json.loads → str)
        #   - a JSON object         → {"UniqueId": "..."}  (json.loads → dict)
        #   - a plain-text UUID     → 673ae391-...         (json.loads raises)
        try:
            data = json.loads(body)
            if isinstance(data, str):
                return data.strip() or None
            if isinstance(data, list):
                data = data[0] if data else None
            if not data:
                return None
            uid = data.get("GuidId") or data.get("UniqueId") or data.get("uniqueId")
            return str(uid) if uid else None
        except json.JSONDecodeError:
            return body.strip() or None

    except aiohttp.ClientConnectorError as exc:
        logger.warning("Cannot reach user detail API at %s: %s", url, exc)
        return None
    except aiohttp.ClientError as exc:
        logger.warning("Network error calling user detail API: %s", exc)
        return None


# ------------------------------------------------------------------ #
# Middleware
# ------------------------------------------------------------------ #

class TokenIntrospectionMiddleware(BaseHTTPMiddleware):
    """Validates bearer tokens via the IDP UserInfo endpoint, then resolves the
    identity user ID to the actual DB user UniqueId.

    On success sets on ``request.state``:
      auth_user_id   — DB UniqueId resolved from the ``sub`` claim
      auth_tenant_id — value of the ``X-Tenant-Id`` header

    Every route using ``Depends(get_context)`` is automatically protected.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # ── 1. Skip public / infra paths ─────────────────────────────────
        if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        settings = get_settings()
        authorization = request.headers.get("Authorization")
        x_tenant_id = request.headers.get("X-Tenant-Id")
        token = _bearer_token(authorization)

        # ── 2. Dev fallback ───────────────────────────────────────────────
        if settings.auth_dev_fallback:
            if token:
                # Decode sub without verifying signature, then resolve to DB ID.
                claims = _decode_claims_unverified(token)
                identity_user_id = claims.get(settings.jwt_user_claim)
                if identity_user_id and settings.user_detail_api_base_url:
                    resolved = await _resolve_db_user_id(
                        identity_user_id, settings.user_detail_api_base_url
                    )
                    user_id = resolved or settings.dev_user_id
                else:
                    user_id = settings.dev_user_id
            else:
                user_id = settings.dev_user_id
            request.state.auth_user_id = str(user_id)
            request.state.auth_tenant_id = str(x_tenant_id or "")
            logger.debug("Dev fallback — user=%s tenant=%s", user_id, x_tenant_id)
            return await call_next(request)

        # ── 3. Require bearer token ───────────────────────────────────────
        if not token:
            return _unauthorized("Missing bearer token.")

        # ── 4. Require IDP authority configured ───────────────────────────
        if not settings.idp_authority:
            logger.error("IDP_AUTHORITY is not configured.")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Auth service is not configured.", "detail": None},
            )

        # ── 5. Cache hit — skip both external calls ───────────────────────
        cached_user_id = _cache_get(token)
        if cached_user_id:
            if not x_tenant_id:
                return _unauthorized("X-Tenant-Id header is required.")
            request.state.auth_user_id = cached_user_id
            request.state.auth_tenant_id = str(x_tenant_id)
            return await call_next(request)

        # ── 6. Require X-Tenant-Id ────────────────────────────────────────
        if not x_tenant_id:
            return _unauthorized("X-Tenant-Id header is required.")

        # ── 7. Decode sub unverified — needed to check sub-cache and for parallel calls
        pre_sub = _decode_claims_unverified(token).get(settings.jwt_user_claim)

        # ── 8. Sub-cache hit — sub→db_user_id already resolved for this user ─
        # Only UserInfo (token validation) still needs to run.
        cached_db_user_id = _sub_cache_get(pre_sub) if pre_sub else None

        try:
            if cached_db_user_id:
                # sub is known — just validate the token, skip user-detail call
                userinfo = await _call_userinfo(token, settings.idp_authority)
                user_id = cached_db_user_id
            elif pre_sub and settings.user_detail_api_base_url:
                # Cold path — fire both calls concurrently
                userinfo, user_id = await asyncio.gather(
                    _call_userinfo(token, settings.idp_authority),
                    _resolve_db_user_id(pre_sub, settings.user_detail_api_base_url),
                )
            else:
                userinfo = await _call_userinfo(token, settings.idp_authority)
                user_id = None
        except PermissionError as exc:
            logger.warning("Auth failed on %s: %s", path, exc)
            return _unauthorized(str(exc))

        # ── 9. Confirm sub from the verified UserInfo response ────────────
        identity_user_id = userinfo.get("sub")
        if not identity_user_id:
            logger.warning("UserInfo response has no sub claim: %s", userinfo)
            return _unauthorized("User identity (sub) is missing from the token.")

        # ── 10. Resolve DB user ID if still unknown (no pre_sub) ─────────
        if user_id is None:
            user_id = await _resolve_db_user_id(identity_user_id, settings.user_detail_api_base_url)
        if not user_id:
            logger.warning("Could not resolve DB user ID for identity=%s", identity_user_id)
            return _unauthorized("Could not resolve user identity to a system user.")

        # ── 11. Populate both caches and store verified identity ──────────
        _sub_cache_set(identity_user_id, str(user_id))
        _cache_set(token, str(user_id))
        request.state.auth_user_id = str(user_id)
        request.state.auth_tenant_id = str(x_tenant_id)
        logger.debug("Auth OK — identity=%s user=%s tenant=%s path=%s", identity_user_id, user_id, x_tenant_id, path)

        return await call_next(request)
