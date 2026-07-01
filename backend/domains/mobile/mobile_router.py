"""Mobile API router — subset of endpoints consumed by the Joblogic mobile app.

Mirrors four read endpoints from the web API under the /mobile prefix so the
mobile team can version and evolve their surface independently.  All business
logic lives in the original service modules; these handlers are thin delegates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import AcmStatus
from backend.core.validation import validate_uuid
from backend.database.postgres import get_session
from backend.domains.acm_entries import acm_entries_service as acm_svc
from backend.domains.acm_entries.acm_entries_models import ActiveAcmEntriesResponse
from backend.domains.documents import documents_service as doc_svc
from backend.domains.documents.documents_models import SiteDocumentsPaginatedResponse
from backend.domains.mobile.mobile_models import MobileSiteDetailResponse
from backend.domains.register import register_service as reg_svc
from backend.domains.register.register_models import SiteAsbestosStatusResponse
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/mobile/register", tags=["Mobile"])


@router.get("/{site_id}/check-site-asbestos-status", response_model=SiteAsbestosStatusResponse)
async def get_asbestos_status(
    site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteAsbestosStatusResponse:
    """Whether the site has any active ACM entries and how many.

    ``site_id`` is the external Joblogic site unique id (UUID).
    """
    validate_uuid(site_id, "siteId")
    return await reg_svc.get_asbestos_status(session, tenant_id=ctx.tenant_id, site_id=site_id)


@router.get("/{asbestos_site_id}", response_model=MobileSiteDetailResponse)
async def get_site_asbestos_detail(
    asbestos_site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> MobileSiteDetailResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await reg_svc.get_mobile_site_detail(
        session, tenant_id=ctx.tenant_id, site_id=asbestos_site_id
    )


@router.get("/{asbestos_site_id}/active-acm-entries", response_model=ActiveAcmEntriesResponse)
async def list_acm_entries(
    asbestos_site_id: str,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> ActiveAcmEntriesResponse:
    """Active ACM entries for a site."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await acm_svc.list_active_entries(
        session,
        tenant_id=ctx.tenant_id,
        site_id=asbestos_site_id,
        status_filter=AcmStatus.ACTIVE.value,
        page=page,
        page_size=pageSize,
    )


@router.get("/{asbestos_site_id}/site-documents", response_model=SiteDocumentsPaginatedResponse)
async def get_site_documents(
    asbestos_site_id: str,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentsPaginatedResponse:
    """All documents for a site (all types), paginated, with presigned download URLs."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await doc_svc.list_documents_paginated(
        session,
        tenant_id=ctx.tenant_id,
        site_id=asbestos_site_id,
        page=page,
        page_size=pageSize,
    )


@router.get("/assets/{asset_id}/acm-entries", response_model=ActiveAcmEntriesResponse)
async def get_acm_entries_by_asset(
    asset_id: str,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> ActiveAcmEntriesResponse:
    """All active ACM entries linked to a specific asset across all sites for the tenant.

    ``asset_id`` is the external joblogic asset unique id (UUID).
    """
    validate_uuid(asset_id, "assetId")
    return await acm_svc.list_acm_entries_by_asset(
        session,
        tenant_id=ctx.tenant_id,
        asset_id=asset_id,
        status_filter=AcmStatus.ACTIVE.value,
        page=page,
        page_size=pageSize,
    )
