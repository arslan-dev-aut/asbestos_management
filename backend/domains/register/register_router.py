"""Register endpoints (Section 4.2) — site list, create, detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.validation import validate_nonempty, validate_one_of, validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.documents.documents_service import parse_document_inputs
from backend.domains.register import register_service as svc
from backend.domains.register.register_models import (
    CreateSiteRequest,
    CreateSiteResponse,
    RegisterCustomerListResponse,
    RegisterSiteListResponse,
    SiteAsbestosStatusResponse,
    SiteDetailResponse,
    SiteExistsResponse,
    SiteListResponse,
)
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/register", tags=["register"])

_SORT_BY_VALUES = ("lastUpdated", "name", "customerName", "ampExpiry", "riskScore")
_SORT_DIR_VALUES = ("asc", "desc")


@router.get("/sites", response_model=RegisterSiteListResponse)
async def list_register_sites(
    search: str | None = Query(default=None, description="Filter by site name"),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> RegisterSiteListResponse:
    """Distinct sites present in the register — for populating the site filter."""
    try:
        sites, total = await svc.list_register_sites(
            session,
            tenant_id=ctx.tenant_id,
            search=search,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return RegisterSiteListResponse(sites=sites, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve register sites.", detail=str(exc)) from exc


@router.get("/customers", response_model=RegisterCustomerListResponse)
async def list_register_customers(
    search: str | None = Query(default=None, description="Filter by customer name"),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> RegisterCustomerListResponse:
    """Distinct customers present in the register — for populating the customer filter."""
    try:
        customers, total = await svc.list_register_customers(
            session,
            tenant_id=ctx.tenant_id,
            search=search,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return RegisterCustomerListResponse(customers=customers, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve register customers.", detail=str(exc)) from exc


@router.get("", response_model=SiteListResponse)
async def list_sites(
    search: str | None = Query(default=None),
    customerIds: list[str] = Query(default=[]),
    siteIds: list[str] = Query(default=[]),
    riskLevel: list[str] = Query(default=[]),
    sortBy: str = Query(default="lastUpdated"),
    sortDir: str = Query(default="desc"),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteListResponse:
    validate_one_of(sortBy, _SORT_BY_VALUES, "sortBy")
    validate_one_of(sortDir, _SORT_DIR_VALUES, "sortDir")
    try:
        sites, total = await svc.list_sites(
            session,
            tenant_id=ctx.tenant_id,
            search=search,
            customer_ids=customerIds or None,
            site_ids=siteIds or None,
            risk_levels=riskLevel or None,
            sort_by=sortBy,
            sort_dir=sortDir,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return SiteListResponse(sites=sites, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve sites.", detail=str(exc)) from exc


@router.post("/with-documents", response_model=CreateSiteResponse, status_code=201)
async def create_site_with_documents(
    customerId: str = Form(...),
    siteId: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    documentsMetadata: str = Form(
        default="[]",
        description=(
            'JSON array, one object per file, in the same order as `files`. '
            'Each object: {"docType": "AMP", "ampExpiryDate": "2026-01-01"} '
            '— ampExpiryDate is required for AMP, omit or null for others.'
        ),
    ),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CreateSiteResponse:
    """Create a site and upload its documents atomically."""
    validate_nonempty(customerId, "customerId")
    validate_nonempty(siteId, "siteId")
    try:
        doc_inputs = await parse_document_inputs(files, documentsMetadata)
        asbestos_site_id = await svc.create_site_with_documents(
            session,
            tenant_id=ctx.tenant_id,
            customer_id=customerId,
            site_id=siteId,
            user_id=ctx.user_id,
            documents=doc_inputs,
        )
        return CreateSiteResponse(asbestosSiteId=asbestos_site_id, message="Site registered.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to create site with documents.", detail=str(exc)) from exc


@router.get("/check", response_model=SiteExistsResponse)
async def check_site_exists(
    siteId: str = Query(..., description="MainSubSys site UniqueId (GUID)"),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteExistsResponse:
    """Check whether a site is already in the register for this tenant."""
    validate_nonempty(siteId, "siteId")
    try:
        return await svc.check_site_exists(session, tenant_id=ctx.tenant_id, site_id=siteId)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to check site existence.", detail=str(exc)) from exc


@router.post("", response_model=CreateSiteResponse, status_code=201)
async def create_site(
    body: CreateSiteRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CreateSiteResponse:
    validate_nonempty(body.customerId, "customerId")
    validate_nonempty(body.siteId, "siteId")
    try:
        asbestos_site_id = await svc.create_site(
            session,
            tenant_id=ctx.tenant_id,
            customer_id=body.customerId,
            site_id=body.siteId,
            user_id=ctx.user_id,
        )
        return CreateSiteResponse(asbestosSiteId=asbestos_site_id, message="Site registered.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to create site.", detail=str(exc)) from exc


@router.get("/{asbestos_site_id}/asbestos-status", response_model=SiteAsbestosStatusResponse)
async def get_asbestos_status(
    asbestos_site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteAsbestosStatusResponse:
    """Whether the site has any active ACM entries and how many."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        return await svc.get_asbestos_status(
            session, tenant_id=ctx.tenant_id, site_id=asbestos_site_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site asbestos status.", detail=str(exc)) from exc


@router.get("/{asbestos_site_id}", response_model=SiteDetailResponse)
async def get_site_detail(
    asbestos_site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteDetailResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        return await svc.get_detail(
            session, tenant_id=ctx.tenant_id, site_id=asbestos_site_id, user_id=ctx.user_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site detail.", detail=str(exc)) from exc
