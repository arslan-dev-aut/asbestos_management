"""QR code endpoints (Section 4.7).

``router`` holds the authenticated retrieve endpoint (mounted under the API
prefix). ``public_router`` holds the unauthenticated public view and is mounted
at the application root. Handlers are thin — errors are converted to the
standard envelope by the app-level exception handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.validation import validate_nonempty, validate_uuid
from backend.database.postgres import get_session
from backend.domains.qrcode import qrcode_service
from backend.domains.qrcode.qrcode_models import PublicViewResponse, QrCodeResponse
from backend.middleware.auth import AuthContext, get_context
from backend.middleware.rate_limit import public_rate_limit

router = APIRouter(prefix="/register", tags=["qrcode"])
public_router = APIRouter(tags=["public"])


@router.get("/{asbestos_site_id}/qr-code", response_model=QrCodeResponse)
async def get_qr(
    asbestos_site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> QrCodeResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await qrcode_service.get(
        session, tenant_id=ctx.tenant_id, site_id=asbestos_site_id
    )


@public_router.get("/public/{token}", response_model=PublicViewResponse)
async def public_view(
    token: str,
    acmPage: int = Query(default=0, ge=0),
    acmPageSize: int = Query(default=10, ge=1, le=50),
    docsPage: int = Query(default=0, ge=0),
    docsPageSize: int = Query(default=10, ge=1, le=50),
    _rl: None = Depends(public_rate_limit),
    session: AsyncSession = Depends(get_session),
) -> PublicViewResponse:
    """No authentication — strictly read-only active ACM data + current documents."""
    validate_nonempty(token, "token")
    return await qrcode_service.public_view(
        session,
        token=token,
        acm_page=acmPage,
        acm_page_size=acmPageSize,
        docs_page=docsPage,
        docs_page_size=docsPageSize,
    )
