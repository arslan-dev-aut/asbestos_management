"""Audit Trail endpoints (Section 4.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.validation import validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.audit import audit_service
from backend.domains.audit.audit_models import (
    AuditListResponse,
    AuditTaxonomyResponse,
)
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(tags=["audit"])


@router.get("/audit/taxonomy", response_model=AuditTaxonomyResponse)
async def get_audit_taxonomy(
    _ctx: AuthContext = Depends(get_context),
) -> AuditTaxonomyResponse:
    """Audit Type + dependent Action options for the Audit Trail filters."""
    try:
        return AuditTaxonomyResponse(taxonomy=audit_service.taxonomy())
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve audit taxonomy.", detail=str(exc)) from exc


@router.get("/audit/config", response_model=AuditListResponse)
async def get_config_audit(
    action: str | None = Query(default=None),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AuditListResponse:
    """Configuration audit trail for this tenant.

    Returns building type and ACM type add/deactivate/reactivate events.
    Optionally filter by ``action`` (e.g. BUILDING_TYPE_ADDED).
    """
    try:
        entries, total = await audit_service.list_config_logs(
            session,
            tenant_id=ctx.tenant_id,
            action=action,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return AuditListResponse(entries=entries, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve configuration audit logs.", detail=str(exc)) from exc


@router.get("/register/{asbestos_site_id}/audit", response_model=AuditListResponse)
async def get_site_audit(
    asbestos_site_id: str,
    auditType: str | None = Query(default=None),
    action: str | None = Query(default=None),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AuditListResponse:
    """Site audit trail for this tenant.

    Returns all non-configuration events (ACM entries, documents, QR codes,
    site creation) for the given site. Configuration logs are excluded by
    design — use GET /audit/config for those.
    """
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        entries, total = await audit_service.list_for_site(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            audit_type=auditType,
            action=action,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return AuditListResponse(entries=entries, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site audit logs.", detail=str(exc)) from exc
