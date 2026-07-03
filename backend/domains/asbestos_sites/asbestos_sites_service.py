"""Asbestos sites service — look up full site detail(s) by integer site ID.

The lookup spans three external systems in sequence:
  1. SQL Server mapping table  — identifies whether a subcontractor relationship
                                  exists and which tenants/sites are involved.
  2. MainSubSys (GetSiteByIdMsg) — resolve integer site_id(s) to UniqueId GUIDs.
  3. PostgreSQL asbestos_sites  — load full site record(s) by UniqueId.

Response is a list because the API contract is consistent regardless of whether
one or more records are returned. In practice at most one record is returned per
call — the sub-contractor prefers its own record and falls back to the main's.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core import rag
from backend.database.db_models import AsbestosAcmEntries, AsbestosSites
from backend.database.exceptions import NotFoundError
from backend.domains.acm_entries import acm_entries_service
from backend.domains.documents import documents_service
from backend.domains.asbestos_sites.asbestos_sites_models import SiteDetail, SiteDetailResponse
from backend.integrations.mainsubsys import MainSubSysClient
from backend.integrations.sqlserver import get_site_mapping

# A candidate is (jicro_tenant_id, postgres_tenant_id, integer_site_id).
# Candidates are tried in order; the first one that resolves to a site record wins.
_Candidate = tuple[str, str, int]

_NOT_FOUND = "No asbestos site record found for site ID {}."


# ---------------------------------------------------------------------------
# Decision tree — single source of truth
# ---------------------------------------------------------------------------


def _candidate_sequence(
    mapping: dict[str, Any] | None,
    tenant_id: str,
    site_id: int,
) -> list[_Candidate]:
    """Return the ordered list of (jicro_tenant, pg_tenant, auto_id) to try.

    The first candidate that resolves to a PostgreSQL record wins. This is the
    only place the main/sub-contractor decision logic lives.
    """
    if mapping is None:
        return [(tenant_id, tenant_id, site_id)]

    main_tenant = str(mapping["MainContractorTenantId"]).lower()
    sub_tenant = str(mapping["SubContractorTenantId"]).lower()
    main_site_id = int(mapping["MainContractorSiteId"])
    sub_site_id = int(mapping["SubContractorSiteId"])
    is_main = tenant_id == main_tenant
    is_sub = tenant_id == sub_tenant

    if is_main and is_sub:
        # Same tenant on both sides: use matched_field to pick the right auto_id.
        effective_id = main_site_id if mapping["matched_field"] == "main" else sub_site_id
        return [(tenant_id, tenant_id, effective_id)]

    if is_main:
        return [(main_tenant, main_tenant, site_id)]

    if is_sub:
        # Sub's own record preferred; main is the fallback.
        return [
            (sub_tenant, sub_tenant, sub_site_id),
            (main_tenant, main_tenant, main_site_id),
        ]

    # Tenant not in this mapping row: best-effort direct lookup.
    return [(tenant_id, tenant_id, site_id)]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


async def _resolve_uid(jicro_tenant_id: str, site_auto_id: int) -> uuid.UUID | None:
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


# ---------------------------------------------------------------------------
# Public service entry points
# ---------------------------------------------------------------------------


async def resolve_primary_site(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: int,
) -> tuple[str, str]:
    """Resolve an integer site_id to ``(asbestos_site_id, postgres_tenant_id)``.

    Useful for endpoints that delegate to the documents or ACM-entries service,
    which expect the internal PostgreSQL UUID and the tenant stored on the record.
    Raises ``NotFoundError`` if no matching record can be found.
    """
    mapping = await get_site_mapping(site_id)
    for jicro_tenant, pg_tenant, auto_id in _candidate_sequence(mapping, tenant_id, site_id):
        uid = await _resolve_uid(jicro_tenant, auto_id)
        if uid is None:
            continue
        site = await _fetch_site(session, uid, pg_tenant)
        if site is not None:
            return str(site.id), pg_tenant
    raise NotFoundError(_NOT_FOUND.format(site_id))


async def get_site_by_site_id(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: int,
) -> list[SiteDetailResponse]:
    """Return full site detail for an integer site_id.

    Decision tree (see ``_candidate_sequence``):
    - No mapping → direct lookup against calling tenant.
    - Tenant = main contractor → direct lookup.
    - Tenant = sub contractor → sub's own record preferred; falls back to main's.
    - Tenant = both sides → use matched_field to pick the correct auto_id.
    - Tenant not in mapping → fallback to direct lookup.
    """
    mapping = await get_site_mapping(site_id)
    for jicro_tenant, pg_tenant, auto_id in _candidate_sequence(mapping, tenant_id, site_id):
        uid = await _resolve_uid(jicro_tenant, auto_id)
        if uid is None:
            continue
        site = await _fetch_site(session, uid, pg_tenant)
        if site is not None:
            return [await _build_response(session, site, jicro_tenant)]
    raise NotFoundError(_NOT_FOUND.format(site_id))
