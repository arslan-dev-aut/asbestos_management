"""Asbestos sites service — look up full site detail(s) by integer site ID.

The lookup spans three external systems in sequence:
  1. SQL Server mapping table  — identifies whether a subcontractor relationship
                                  exists and which tenants/sites are involved.
  2. MainSubSys (GetSiteByIdMsg) — resolve integer site_id(s) to UniqueId GUIDs.
  3. PostgreSQL asbestos_sites  — load full site record(s) by UniqueId.

Response is a list because the sub-contractor case can return two records
(one for the sub's own site and one for the linked main-contractor site).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core import rag
from backend.database.db_models import AsbestosAcmEntries, AsbestosSites
from backend.database.exceptions import NotFoundError, UpstreamError
from backend.domains.acm_entries import acm_entries_service
from backend.domains.documents import documents_service
from backend.domains.register.register_models import SiteDetail, SiteDetailResponse
from backend.integrations.mainsubsys import MainSubSysClient
from backend.integrations.sqlserver import get_site_mapping


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_uid(jicro_tenant_id: str, site_auto_id: int) -> uuid.UUID | None:
    """Call GetSiteByIdMsg for a (tenant, integer site ID) pair.

    Returns the parsed UUID or None if not found / invalid.
    """
    async with MainSubSysClient(jicro_tenant_id) as mss:
        raw = await mss.get_site_unique_id_by_auto_id(site_auto_id)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def _fetch_site(
    session: AsyncSession,
    unique_id: uuid.UUID,
    postgres_tenant_id: str,
) -> AsbestosSites | None:
    return await session.scalar(
        select(AsbestosSites).where(
            AsbestosSites.site_id == unique_id,
            AsbestosSites.tenant_id == uuid.UUID(postgres_tenant_id),
        )
    )


async def _build_response(
    session: AsyncSession,
    site: AsbestosSites,
    jicro_tenant_id: str,
) -> SiteDetailResponse:
    """Build a full SiteDetailResponse from a PostgreSQL AsbestosSites ORM object.

    Uses jicro_tenant_id for all MainSubSys name-resolution calls (customers,
    sites, users, assets) so the correct tenant's data is returned.
    """
    entries = list(
        (
            await session.scalars(
                select(AsbestosAcmEntries)
                .where(AsbestosAcmEntries.asbestos_site_id == site.id)
                .options(
                    selectinload(AsbestosAcmEntries.building_type),
                    selectinload(AsbestosAcmEntries.acm_type),
                    selectinload(AsbestosAcmEntries.attachments),
                )
                .order_by(AsbestosAcmEntries.created_at.asc())
            )
        ).all()
    )

    documents = await documents_service.list_for_site(session, str(site.id))

    active_scores = [e.risk_score for e in entries if e.status == "ACTIVE"]
    highest = rag.highest_risk(active_scores)
    total_acm = len(entries)
    active_acm = len(active_scores)
    current_amp = await documents_service.current_amp(session, str(site.id))
    amp_expiry = current_amp.amp_expiry_date if current_amp else None

    asset_ids = {str(e.asset_id) for e in entries if e.asset_id}
    user_ids = (
        {str(site.updated_by)}
        | {str(e.updated_by) for e in entries}
        | {str(d.uploaded_by) for d in documents}
    )

    async with MainSubSysClient(jicro_tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids={str(site.customer_id)},
            site_ids={str(site.site_id)},
            asset_ids=asset_ids,
            user_ids=user_ids,
        )

    detail = SiteDetail(
        id=str(site.id),
        customerId=str(site.customer_id),
        siteId=str(site.site_id),
        customerName=resolved.customer(str(site.customer_id)),
        siteName=resolved.site(str(site.site_id)),
        highestRisk=highest.value,
        totalAcm=total_acm,
        activeAcm=active_acm,
        ampExpiryDate=amp_expiry,
        ampExpiryRag=rag.amp_expiry_rag(amp_expiry).value,
        ampExpired=rag.is_amp_expired(amp_expiry),
        ampExpiringSoon=rag.is_amp_expiring_soon(amp_expiry),
        createdAt=site.created_at,
        createdBy=str(site.created_by),
        updatedAt=site.updated_at,
        updatedBy=str(site.updated_by),
        updatedByName=resolved.user(str(site.updated_by)),
    )
    return SiteDetailResponse(
        site=detail,
        documents=[documents_service.to_schema(d, resolved) for d in documents],
        acmEntries=[acm_entries_service.to_schema(e, resolved) for e in entries],
    )


async def _lookup_single(
    session: AsyncSession,
    jicro_tenant_id: str,
    postgres_tenant_id: str,
    site_auto_id: int,
) -> SiteDetailResponse | None:
    """Resolve one (tenant, integer site ID) pair to a detail response.

    Returns None if the site cannot be resolved or is not found in PostgreSQL.
    """
    uid = await _resolve_uid(jicro_tenant_id, site_auto_id)
    if uid is None:
        return None
    site = await _fetch_site(session, uid, postgres_tenant_id)
    if site is None:
        return None
    return await _build_response(session, site, jicro_tenant_id)


# ---------------------------------------------------------------------------
# Public service entry point
# ---------------------------------------------------------------------------


async def get_site_by_site_id(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: int,
    user_id: str,
) -> list[SiteDetailResponse]:
    """Return site detail(s) for an integer site_id.

    Decision tree:
    - No mapping row found → direct lookup with calling (tenant_id, site_id).
    - Tenant is main contractor only → direct lookup with (main_tenant, site_id).
    - Tenant is sub contractor only → two lookups:
        (sub_tenant, sub_site_id) and (main_tenant, main_site_id).
        Returns up to 2 SiteDetailResponse objects.
    - Tenant is both (same GUID on both sides of the mapping) → use matched_field
        to pick which site_id to query, direct lookup.
    - Tenant not in mapping → fall back to direct lookup with calling tenant.
    """
    mapping = await get_site_mapping(site_id)

    if mapping is None:
        result = await _lookup_single(session, tenant_id, tenant_id, site_id)
        if result is None:
            raise NotFoundError(f"No asbestos site record found for site ID {site_id}.")
        return [result]

    main_tenant = str(mapping["MainContractorTenantId"])
    sub_tenant = str(mapping["SubContractorTenantId"])
    main_site_id = int(mapping["MainContractorSiteId"])
    sub_site_id = int(mapping["SubContractorSiteId"])

    is_main = tenant_id == main_tenant
    is_sub = tenant_id == sub_tenant

    if is_main and is_sub:
        # Same tenant on both sides of the mapping. Use matched_field to pick
        # which integer site_id to pass to MainSubSys (they resolve to different
        # UniqueIds even though the tenant is the same).
        effective_site_id = main_site_id if mapping["matched_field"] == "main" else sub_site_id
        result = await _lookup_single(session, tenant_id, tenant_id, effective_site_id)
        results: list[SiteDetailResponse] = [result] if result is not None else []

    elif is_main:
        # Calling tenant is the main contractor: single direct lookup.
        result = await _lookup_single(session, main_tenant, main_tenant, site_id)
        results = [result] if result is not None else []

    elif is_sub:
        # Calling tenant is a sub contractor: resolve both sides, but prefer the
        # sub contractor's own record. Only fall back to the main contractor's
        # record if the sub has no asbestos record in PostgreSQL.
        sub_result = await _lookup_single(session, sub_tenant, sub_tenant, sub_site_id)
        if sub_result is not None:
            results = [sub_result]
        else:
            main_result = await _lookup_single(session, main_tenant, main_tenant, main_site_id)
            results = [main_result] if main_result is not None else []

    else:
        # Tenant not present in this mapping row: fall back to direct lookup.
        result = await _lookup_single(session, tenant_id, tenant_id, site_id)
        results = [result] if result is not None else []

    if not results:
        raise NotFoundError(f"No asbestos site record found for site ID {site_id}.")
    return results
