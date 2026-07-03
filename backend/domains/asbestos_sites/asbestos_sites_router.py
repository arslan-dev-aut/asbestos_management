"""Asbestos sites endpoints — look up a site by its integer site ID."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.validation import validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.acm_entries import acm_entries_service as acm_svc
from backend.domains.acm_entries.acm_entries_models import ActiveAcmEntriesResponse
from backend.domains.asbestos_sites import asbestos_sites_service as svc
from backend.domains.documents import documents_service as doc_svc
from backend.domains.documents.documents_models import SiteDocumentsPaginatedResponse
from backend.domains.asbestos_sites.asbestos_sites_models import SiteDetailResponse

router = APIRouter(prefix="/asbestos-sites", tags=["asbestos-sites"])


async def _tenant_id(x_tenant_id: str = Header(..., alias="X-Tenant-Id")) -> str:
    return x_tenant_id.lower()


@router.get("/by-site-id/{site_id}", response_model=list[SiteDetailResponse])
async def get_site_by_site_id(
    site_id: int,
    tenant_id: str = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> list[SiteDetailResponse]:
    """Fetch asbestos site record(s) by integer site ID."""
    try:
        return await svc.get_site_by_site_id(
            session, tenant_id=tenant_id, site_id=site_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site by site ID.", detail=str(exc)) from exc


@router.get("/by-site-id/{site_id}/documents", response_model=SiteDocumentsPaginatedResponse)
async def get_site_documents_by_site_id(
    site_id: int,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    tenant_id: str = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentsPaginatedResponse:
    """All documents for a site looked up by integer site ID, paginated."""
    try:
        asbestos_site_id, postgres_tenant_id = await svc.resolve_primary_site(
            session, tenant_id=tenant_id, site_id=site_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to resolve site by site ID.", detail=str(exc)) from exc
    return await doc_svc.list_documents_paginated(
        session,
        tenant_id=postgres_tenant_id,
        site_id=asbestos_site_id,
        page=page,
        page_size=pageSize,
    )


@router.get("/by-site-id/{site_id}/acm", response_model=ActiveAcmEntriesResponse)
async def list_acm_entries_by_site_id(
    site_id: int,
    statusFilter: str = Query(default="active", pattern="^(active|all)$"),
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    tenant_id: str = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ActiveAcmEntriesResponse:
    """ACM entries for a site looked up by integer site ID. statusFilter: ``active`` (default) or ``all``."""
    try:
        asbestos_site_id, postgres_tenant_id = await svc.resolve_primary_site(
            session, tenant_id=tenant_id, site_id=site_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to resolve site by site ID.", detail=str(exc)) from exc
    return await acm_svc.list_active_entries(
        session,
        tenant_id=postgres_tenant_id,
        site_id=asbestos_site_id,
        status_filter=statusFilter,
        page=page,
        page_size=pageSize,
    )


@router.get("/{asbestos_site_id}/documents", response_model=SiteDocumentsPaginatedResponse)
async def get_documents_by_asbestos_site_id(
    asbestos_site_id: str,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    tenant_id: str = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentsPaginatedResponse:
    """Paginated documents for a known asbestos site UUID (use for pages 2+)."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await doc_svc.list_documents_paginated(
        session,
        tenant_id=tenant_id,
        site_id=asbestos_site_id,
        page=page,
        page_size=pageSize,
    )


@router.get("/{asbestos_site_id}/acm", response_model=ActiveAcmEntriesResponse)
async def list_acm_by_asbestos_site_id(
    asbestos_site_id: str,
    statusFilter: str = Query(default="active", pattern="^(active|all)$"),
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    tenant_id: str = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ActiveAcmEntriesResponse:
    """Paginated ACM entries for a known asbestos site UUID (use for pages 2+). statusFilter: ``active`` or ``all``."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    return await acm_svc.list_active_entries(
        session,
        tenant_id=tenant_id,
        site_id=asbestos_site_id,
        status_filter=statusFilter,
        page=page,
        page_size=pageSize,
    )
