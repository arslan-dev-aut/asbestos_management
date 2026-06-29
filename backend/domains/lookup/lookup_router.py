"""Lookup endpoints — customer and site lists sourced from MainSubSys.

These endpoints are used to populate dropdowns / pickers in the frontend
when registering a new asbestos site or filtering the register.

  GET /lookup/customers                        — search/list customers
  GET /lookup/customers/{customerId}/sites     — list sites for a customer
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.validation import validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.domains.lookup.lookup_models import (
    AssetItem,
    AssetListResponse,
    CustomerItem,
    CustomerListResponse,
    SiteItem,
    SiteListResponse,
)
from backend.integrations.mainsubsys import MainSubSysClient
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/lookup", tags=["lookup"])


def _build_address(raw: dict) -> str | None:
    parts = [
        raw.get("Address1") or raw.get("address1"),
        raw.get("Address2") or raw.get("address2"),
        raw.get("Postcode") or raw.get("postcode"),
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


@router.get("/customers", response_model=CustomerListResponse)
async def list_customers(
    search: str | None = Query(default=None, description="Free-text search"),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
) -> CustomerListResponse:
    """List customers for this tenant from MainSubSys.

    Returns ``id`` (integer — use for the sites endpoint) and
    ``uniqueId`` (GUID — use when creating a register entry).
    """
    try:
        async with MainSubSysClient(ctx.tenant_id) as mss:
            raw = await mss.list_customers(search=search, page_size=pageSize)

        items = [
            CustomerItem(
                id=c["id"],
                uniqueId=str(c.get("uniqueId") or ""),
                name=c.get("name") or "",
            )
            for c in raw
            if c.get("id") is not None
        ]
        return CustomerListResponse(customers=items, totalCount=len(items))
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve customers from MainSubSys.", detail=str(exc)) from exc


@router.get("/customers/{customerId}/sites", response_model=SiteListResponse)
async def list_sites_for_customer(
    customerId: str,
    search: str | None = Query(default=None, description="Free-text search"),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
) -> SiteListResponse:
    """List sites for a specific customer from MainSubSys.

    ``customerId`` is the ``uniqueId`` (GUID) returned by GET /lookup/customers.
    Returns ``uniqueId`` (GUID) which is what should be stored when
    creating a register entry.
    """
    validate_uuid(customerId, "customerId")
    try:
        async with MainSubSysClient(ctx.tenant_id) as mss:
            raw = await mss.list_sites_for_customer(
                customer_unique_id=customerId, search=search, page_size=pageSize
            )

        items = [
            SiteItem(
                id=s.get("Id") or s.get("id") or 0,
                uniqueId=str(s.get("UniqueId") or s.get("uniqueId") or ""),
                name=s.get("Name") or s.get("name") or "",
                address=_build_address(s),
                customerName=s.get("CustomerName") or s.get("customerName"),
            )
            for s in raw
            if (s.get("UniqueId") or s.get("uniqueId"))
        ]
        return SiteListResponse(sites=items, totalCount=len(items))
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError(
            f"Failed to retrieve sites for customer '{customerId}' from MainSubSys.",
            detail=str(exc),
        ) from exc


@router.get("/sites/{siteId}/assets", response_model=AssetListResponse)
async def list_assets_for_site(
    siteId: str,
    search: str | None = Query(default=None, description="Free-text search"),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
) -> AssetListResponse:
    """List assets for a specific site from MainSubSys.

    ``siteId`` is the ``uniqueId`` (GUID) returned by GET /lookup/customers/{customerId}/sites.
    Returns ``uniqueId`` (GUID) which is what should be stored when creating a register entry.
    """
    validate_uuid(siteId, "siteId")
    try:
        async with MainSubSysClient(ctx.tenant_id) as mss:
            raw = await mss.list_assets_for_site(
                site_unique_id=siteId, search=search, page_size=pageSize
            )

        items = [
            AssetItem(
                id=a.get("Id") or a.get("id") or 0,
                uniqueId=str(a.get("UniqueId") or a.get("uniqueId") or ""),
                name=a.get("Description") or a.get("description") or "",
            )
            for a in raw
            if (a.get("UniqueId") or a.get("uniqueId"))
        ]
        return AssetListResponse(assets=items, totalCount=len(items))
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError(
            f"Failed to retrieve assets for site '{siteId}' from MainSubSys.",
            detail=str(exc),
        ) from exc
