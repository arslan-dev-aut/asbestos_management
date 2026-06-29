"""Asbestos sites endpoint — look up a site by its integer site ID."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.asbestos_sites import asbestos_sites_service as svc
from backend.domains.register.register_models import SiteDetailResponse
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/asbestos-sites", tags=["asbestos-sites"])


@router.get("/by-site-id/{site_id}", response_model=list[SiteDetailResponse])
async def get_site_by_site_id(
    site_id: int,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[SiteDetailResponse]:
    """Fetch asbestos site record(s) by integer site ID.

    Returns a list because the sub-contractor case resolves two sites:
    the sub contractor's own record and the linked main-contractor record.
    The main-contractor and no-mapping cases always return a single-item list.
    """
    try:
        return await svc.get_site_by_site_id(
            session, tenant_id=ctx.tenant_id, site_id=site_id, user_id=ctx.user_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site by site ID.", detail=str(exc)) from exc
