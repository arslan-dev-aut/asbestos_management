"""Register service — site list (computed columns), create, and full detail.

All customer/site/asset/user names are resolved from MainSubSys at read time;
the register persists IDs only. Free-text search is resolved to IDs first.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, and_, case, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core import rag, storage
from backend.core.enums import (
    CONDITION_LABELS,
    RISK_LABELS,
    AcmStatus,
    AuditAction,
    AuditType,
    DocType,
    HighestRisk,
)
from backend.database.db_models import (
    AsbestosAcmEntries,
    AsbestosSiteDocuments,
    AsbestosSites,
)
from backend.database.exceptions import DuplicateError, NotFoundError, ValidationError
from backend.domains.audit import audit_service
from backend.domains.documents import documents_service
from backend.domains.documents.documents_service import DocumentInput, _save_document
from backend.domains.mobile.mobile_models import MobileSiteDetail, MobileSiteDetailResponse
from backend.domains.register.register_models import (
    RegisterCustomerItem,
    RegisterSiteItem,
    SiteAsbestosStatusResponse,
    SiteDetail,
    SiteDetailResponse,
    SiteExistsResponse,
    SiteListItem,
)
from backend.domains.qrcode import qrcode_service
from backend.integrations.mainsubsys import MainSubSysClient

_RANK_TO_HIGHEST = {0: HighestRisk.NONE, 1: HighestRisk.LOW, 2: HighestRisk.MEDIUM, 3: HighestRisk.HIGH}
_RISK_FILTER_TO_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
# Sort keys the router accepts → the column they sort on. Customer/site *names*
# live upstream (not in the DB) so they cannot be SQL-sorted; those keys fall
# back to last-updated rather than silently pretending to sort by name.
_SORT_DIR_DEFAULT = "desc"


def _acm_agg_subquery():
    active = AsbestosAcmEntries.status == AcmStatus.ACTIVE.value
    return (
        select(
            AsbestosAcmEntries.asbestos_site_id.label("site_id"),
            func.count().label("total_acm"),
            func.coalesce(func.sum(case((active, 1), else_=0)), 0).label("active_acm"),
            func.coalesce(
                func.max(
                    case(
                        (and_(active, AsbestosAcmEntries.risk_score == "HIGH"), 3),
                        (and_(active, AsbestosAcmEntries.risk_score == "MEDIUM"), 2),
                        (and_(active, AsbestosAcmEntries.risk_score == "LOW"), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("risk_rank"),
        )
        .group_by(AsbestosAcmEntries.asbestos_site_id)
        .subquery()
    )


def _amp_subquery():
    return (
        select(
            AsbestosSiteDocuments.asbestos_site_id.label("site_id"),
            AsbestosSiteDocuments.amp_expiry_date.label("amp_expiry"),
        )
        .where(
            AsbestosSiteDocuments.doc_type == DocType.AMP.value,
            AsbestosSiteDocuments.is_current_amp.is_(True),
        )
        .subquery()
    )


def _apply_filters(
    stmt: Select,
    *,
    acm_agg,
    customer_ids: list[str] | None,
    site_ids: list[str] | None,
    risk_levels: list[str] | None,
    search_customer_ids: set[str] | None,
    search_site_ids: set[str] | None,
) -> Select:
    if customer_ids:
        stmt = stmt.where(AsbestosSites.customer_id.in_([uuid.UUID(c) for c in customer_ids]))
    if site_ids:
        stmt = stmt.where(AsbestosSites.site_id.in_([uuid.UUID(s) for s in site_ids]))
    if search_customer_ids is not None or search_site_ids is not None:
        conds = []
        if search_customer_ids:
            conds.append(
                AsbestosSites.customer_id.in_([uuid.UUID(c) for c in search_customer_ids])
            )
        if search_site_ids:
            conds.append(AsbestosSites.site_id.in_([uuid.UUID(s) for s in search_site_ids]))
        # A search that resolved to nothing must return nothing.
        stmt = stmt.where(or_(*conds) if conds else false())
    if risk_levels:
        ranks = [_RISK_FILTER_TO_RANK[r.upper()] for r in risk_levels if r.upper() in _RISK_FILTER_TO_RANK]
        if ranks:
            stmt = stmt.where(func.coalesce(acm_agg.c.risk_rank, 0).in_(ranks))
    return stmt


async def list_sites(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None,
    customer_ids: list[str] | None,
    site_ids: list[str] | None,
    risk_levels: list[str] | None,
    sort_by: str,
    sort_dir: str,
    page_index: int,
    page_size: int,
) -> tuple[list[SiteListItem], int]:
    descending = sort_dir.lower() != "asc"
    page_size = max(1, min(page_size, 50))
    page_index = max(0, page_index)

    # Resolve search text -> customer/site IDs via MainSubSys first.
    search_customer_ids: set[str] | None = None
    search_site_ids: set[str] | None = None
    if search and search.strip():
        async with MainSubSysClient(tenant_id) as mss:
            search_customer_ids = set(await mss.search_customer_ids(search.strip()))
            search_site_ids = set(await mss.search_site_ids(search.strip()))

    acm_agg = _acm_agg_subquery()
    amp_sq = _amp_subquery()

    total_col = func.coalesce(acm_agg.c.total_acm, 0)
    active_col = func.coalesce(acm_agg.c.active_acm, 0)
    rank_col = func.coalesce(acm_agg.c.risk_rank, 0)

    base = (
        select(AsbestosSites, total_col, active_col, rank_col, amp_sq.c.amp_expiry)
        .where(AsbestosSites.tenant_id == uuid.UUID(tenant_id))
        .outerjoin(acm_agg, acm_agg.c.site_id == AsbestosSites.id)
        .outerjoin(amp_sq, amp_sq.c.site_id == AsbestosSites.id)
    )
    base = _apply_filters(
        base,
        acm_agg=acm_agg,
        customer_ids=customer_ids,
        site_ids=site_ids,
        risk_levels=risk_levels,
        search_customer_ids=search_customer_ids,
        search_site_ids=search_site_ids,
    )

    # Total count over the same filters.
    total_count = await session.scalar(select(func.count()).select_from(base.subquery()))

    # Ordering. name/customerName can't be SQL-sorted (names are upstream) and
    # fall back to last-updated; every router-allowed key is handled explicitly.
    sort_target = {
        "ampExpiry": amp_sq.c.amp_expiry,
        "riskScore": rank_col,
        "highestRisk": rank_col,
        "lastUpdated": AsbestosSites.updated_at,
        "name": AsbestosSites.updated_at,
        "customerName": AsbestosSites.updated_at,
    }.get(sort_by, AsbestosSites.updated_at)
    base = base.order_by(sort_target.desc() if descending else sort_target.asc())
    base = base.offset(page_index * page_size).limit(page_size)

    rows = (await session.execute(base)).all()

    # Resolve display names for this page.
    customer_id_set = {str(r[0].customer_id) for r in rows}
    site_id_set = {str(r[0].site_id) for r in rows}
    user_id_set = {str(r[0].updated_by) for r in rows}
    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids=customer_id_set, site_ids=site_id_set, user_ids=user_id_set
        )

    items: list[SiteListItem] = []
    for site, total_acm, active_acm, risk_rank, amp_expiry in rows:
        items.append(
            SiteListItem(
                id=str(site.id),
                customerId=str(site.customer_id),
                siteId=str(site.site_id),
                customerName=resolved.customer(str(site.customer_id)),
                siteName=resolved.site(str(site.site_id)),
                totalAcm=int(total_acm),
                activeAcm=int(active_acm),
                highestRisk=_RANK_TO_HIGHEST[int(risk_rank)].value,
                ampExpiryDate=amp_expiry,
                ampExpiryRag=rag.amp_expiry_rag(amp_expiry).value,
                lastUpdated=site.updated_at,
                updatedBy=str(site.updated_by),
                updatedByName=resolved.user(str(site.updated_by)),
            )
        )
    return items, int(total_count or 0)


async def export_rows(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None,
    customer_ids: list[str] | None,
    site_ids: list[str] | None,
    risk_levels: list[str] | None,
) -> list[list[str]]:
    """Flat one-row-per-ACM-entry export honouring the list-view filters."""
    search_customer_ids: set[str] | None = None
    search_site_ids: set[str] | None = None
    if search and search.strip():
        async with MainSubSysClient(tenant_id) as mss:
            search_customer_ids = set(await mss.search_customer_ids(search.strip()))
            search_site_ids = set(await mss.search_site_ids(search.strip()))

    acm_agg = _acm_agg_subquery()
    site_select = (
        select(AsbestosSites.id)
        .where(AsbestosSites.tenant_id == uuid.UUID(tenant_id))
        .outerjoin(acm_agg, acm_agg.c.site_id == AsbestosSites.id)
    )
    site_select = _apply_filters(
        site_select,
        acm_agg=acm_agg,
        customer_ids=customer_ids,
        site_ids=site_ids,
        risk_levels=risk_levels,
        search_customer_ids=search_customer_ids,
        search_site_ids=search_site_ids,
    )
    site_pks = (await session.scalars(site_select)).all()
    if not site_pks:
        return []

    sites = (
        await session.scalars(
            select(AsbestosSites).where(AsbestosSites.id.in_(site_pks))
        )
    ).all()
    sites_by_pk = {s.id: s for s in sites}

    entries = (
        await session.scalars(
            select(AsbestosAcmEntries)
            .where(AsbestosAcmEntries.asbestos_site_id.in_(site_pks))
            .options(
                selectinload(AsbestosAcmEntries.site),
                selectinload(AsbestosAcmEntries.building_type),
                selectinload(AsbestosAcmEntries.acm_type),
            )
            .order_by(AsbestosAcmEntries.asbestos_site_id, AsbestosAcmEntries.created_at)
        )
    ).all()

    # Track which sites have at least one ACM entry
    sites_with_acm = {e.asbestos_site_id for e in entries}

    customer_id_set = {str(s.customer_id) for s in sites}
    site_id_set = {str(s.site_id) for s in sites}
    asset_id_set = {str(e.asset_id) for e in entries if e.asset_id}
    user_id_set = {str(e.updated_by) for e in entries}
    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids=customer_id_set,
            site_ids=site_id_set,
            asset_ids=asset_id_set,
            user_ids=user_id_set,
        )

    rows: list[list[str]] = []

    # Sites with no ACM entries get a single row with site columns only
    for site_pk in site_pks:
        if site_pk not in sites_with_acm:
            s = sites_by_pk.get(site_pk)
            if s is None:
                continue
            rows.append(
                [
                    resolved.customer(str(s.customer_id)) or "",
                    str(s.customer_id),
                    resolved.site(str(s.site_id)) or "",
                    str(s.site_id),
                    "", "", "", "", "", "", "", "", "",
                ]
            )

    for e in entries:
        rows.append(
            [
                resolved.customer(str(e.site.customer_id)) or "",
                str(e.site.customer_id),
                resolved.site(str(e.site.site_id)) or "",
                str(e.site.site_id),
                e.building_type.name if e.building_type else "",
                e.room_location,
                (resolved.asset(str(e.asset_id)) or "") if e.asset_id else "",
                e.acm_type.name if e.acm_type else "",
                CONDITION_LABELS.get(e.condition, e.condition),
                RISK_LABELS.get(e.risk_score, e.risk_score),
                "Active" if e.status == AcmStatus.ACTIVE.value else "Remediated",
                e.updated_at.isoformat(),
                resolved.user(str(e.updated_by)) or str(e.updated_by),
            ]
        )
    return rows


async def list_register_customers(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None,
    page_index: int,
    page_size: int,
) -> tuple[list[RegisterCustomerItem], int]:
    """Return a paginated, searchable list of distinct customers in the register.

    Paginates the distinct IDs in SQL and resolves names for the current page
    only — never the whole tenant (which would be one upstream call per row).
    """
    page_index = max(0, page_index)
    page_size = max(1, min(page_size, 50))

    base = (
        select(AsbestosSites.customer_id)
        .where(AsbestosSites.tenant_id == uuid.UUID(tenant_id))
        .distinct()
    )
    # Search is by name → resolve to IDs upstream, then filter in SQL.
    if search and search.strip():
        async with MainSubSysClient(tenant_id) as mss:
            match_ids = set(await mss.search_customer_ids(search.strip()))
        if not match_ids:
            return [], 0
        base = base.where(AsbestosSites.customer_id.in_([uuid.UUID(c) for c in match_ids]))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    page_ids = (
        await session.scalars(
            base.order_by(AsbestosSites.customer_id)
            .offset(page_index * page_size)
            .limit(page_size)
        )
    ).all()
    if not page_ids:
        return [], int(total or 0)

    id_set = {str(c) for c in page_ids}
    async with MainSubSysClient(tenant_id) as mss:
        name_map = await mss.resolve_customers(id_set)
    items = [
        RegisterCustomerItem(customerId=str(c), customerName=name_map.get(str(c)))
        for c in page_ids
    ]
    return items, int(total or 0)


async def list_register_sites(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None,
    page_index: int,
    page_size: int,
) -> tuple[list[RegisterSiteItem], int]:
    """Return a paginated, searchable list of distinct sites in the register.

    Paginates the distinct IDs in SQL and resolves names for the current page
    only — never the whole tenant.
    """
    page_index = max(0, page_index)
    page_size = max(1, min(page_size, 50))

    base = (
        select(AsbestosSites.site_id)
        .where(AsbestosSites.tenant_id == uuid.UUID(tenant_id))
        .distinct()
    )
    if search and search.strip():
        async with MainSubSysClient(tenant_id) as mss:
            match_ids = set(await mss.search_site_ids(search.strip()))
        if not match_ids:
            return [], 0
        base = base.where(AsbestosSites.site_id.in_([uuid.UUID(s) for s in match_ids]))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    page_ids = (
        await session.scalars(
            base.order_by(AsbestosSites.site_id)
            .offset(page_index * page_size)
            .limit(page_size)
        )
    ).all()
    if not page_ids:
        return [], int(total or 0)

    id_set = {str(s) for s in page_ids}
    async with MainSubSysClient(tenant_id) as mss:
        name_map = await mss.resolve_sites(id_set)
    items = [
        RegisterSiteItem(siteId=str(s), siteName=name_map.get(str(s)))
        for s in page_ids
    ]
    return items, int(total or 0)


async def check_site_exists(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
) -> SiteExistsResponse:
    try:
        site_uuid = uuid.UUID(site_id)
    except ValueError:
        return SiteExistsResponse(exists=False)

    row = await session.scalar(
        select(AsbestosSites).where(
            AsbestosSites.site_id == site_uuid,
            AsbestosSites.tenant_id == uuid.UUID(tenant_id),
        )
    )
    if row is None:
        return SiteExistsResponse(exists=False)
    return SiteExistsResponse(exists=True, asbestosSiteId=str(row.id))


async def create_site_with_documents(
    session: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
    site_id: str,
    user_id: str,
    documents: list[DocumentInput],
) -> str:
    """Atomically create a site and upload all documents in a single transaction.

    Strategy:
    1. Validate inputs (duplicate check, MainSubSys existence).
    2. Insert the site row and flush to get site.id.
    3. Upload each blob and stage each DB record (no commit yet).
    4. If any step fails: delete already-uploaded blobs, DB rolls back automatically.
    5. Single commit at the end.
    """
    try:
        customer_uuid = uuid.UUID(customer_id)
        site_uuid = uuid.UUID(site_id)
    except ValueError as exc:
        raise ValidationError("customerId and siteId must be valid UUIDs.") from exc

    existing = await session.scalar(
        select(AsbestosSites).where(
            AsbestosSites.site_id == site_uuid,
            AsbestosSites.tenant_id == uuid.UUID(tenant_id),
        )
    )
    if existing is not None:
        raise DuplicateError("This site is already in the asbestos register.")

    async with MainSubSysClient(tenant_id) as mss:
        sites = await mss.resolve_sites({site_id})
    if site_id not in sites:
        raise ValidationError("Site not found in MainSubSys.")

    uid = uuid.UUID(str(user_id))
    site = AsbestosSites(
        tenant_id=uuid.UUID(tenant_id),
        site_id=site_uuid,
        customer_id=customer_uuid,
        created_by=uid,
        updated_by=uid,
    )
    session.add(site)
    await session.flush()  # get site.id before document inserts

    await audit_service.record(
        session,
        site_id=str(site.id),
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_SITE,
        action=AuditAction.SITE_CREATED,
        details={"siteId": site_id, "customerId": customer_id},
    )

    uploaded_keys: list[str] = []
    try:
        for doc_input in documents:
            await _save_document(
                session,
                tenant_id=tenant_id,
                site_id=str(site.id),
                file_name=doc_input.file_name,
                content_type=doc_input.content_type,
                data=doc_input.data,
                doc_type=doc_input.doc_type,
                amp_expiry_date=doc_input.amp_expiry_date,
                user_id=user_id,
                uploaded_keys=uploaded_keys,
            )
        await qrcode_service.create_for_new_site(
            session, tenant_id=tenant_id, site_id=str(site.id), user_id=user_id
        )
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise

    return str(site.id)


async def create_site(
    session: AsyncSession, *, tenant_id: str, customer_id: str, site_id: str, user_id: str
) -> str:
    try:
        customer_uuid = uuid.UUID(customer_id)
        site_uuid = uuid.UUID(site_id)
    except ValueError as exc:
        raise ValidationError("customerId and siteId must be valid UUIDs.") from exc

    # Duplicate guard.
    existing = await session.scalar(
        select(AsbestosSites).where(
            AsbestosSites.site_id == site_uuid,
            AsbestosSites.tenant_id == uuid.UUID(tenant_id),
        )
    )
    if existing is not None:
        raise DuplicateError("This site is already in the asbestos register.")

    # Validate customer/site exist in MainSubSys before insert.
    async with MainSubSysClient(tenant_id) as mss:
        sites = await mss.resolve_sites({site_id})
    if site_id not in sites:
        raise ValidationError("Site not found in MainSubSys.")

    uid = uuid.UUID(str(user_id))
    site = AsbestosSites(
        tenant_id=uuid.UUID(tenant_id),
        site_id=site_uuid,
        customer_id=customer_uuid,
        created_by=uid,
        updated_by=uid,
    )
    session.add(site)
    await session.flush()

    await audit_service.record(
        session,
        site_id=str(site.id),
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_SITE,
        action=AuditAction.SITE_CREATED,
        details={"siteId": site_id, "customerId": customer_id},
    )
    await qrcode_service.create_for_new_site(
        session, tenant_id=tenant_id, site_id=str(site.id), user_id=user_id
    )
    await session.commit()
    return str(site.id)


async def _load_site(session: AsyncSession, site_id: str, tenant_id: str) -> AsbestosSites:
    try:
        site = (
            await session.scalars(
                select(AsbestosSites).where(
                    AsbestosSites.id == uuid.UUID(site_id),
                    AsbestosSites.tenant_id == uuid.UUID(tenant_id),
                )
            )
        ).one_or_none()
    except ValueError as exc:
        raise NotFoundError("Site not found.") from exc
    if site is None:
        raise NotFoundError("Site not found.")
    return site


async def get_detail(
    session: AsyncSession, *, tenant_id: str, site_id: str, user_id: str
) -> SiteDetailResponse:
    site = await _load_site(session, site_id, tenant_id)

    # Aggregate ACM counts and highest risk via a single DB query.
    acm_agg = _acm_agg_subquery()
    agg_row = (
        await session.execute(
            select(
                func.coalesce(acm_agg.c.total_acm, 0),
                func.coalesce(acm_agg.c.active_acm, 0),
                func.coalesce(acm_agg.c.risk_rank, 0),
            ).where(acm_agg.c.site_id == site.id)
        )
    ).one_or_none()

    if agg_row:
        total_acm, active_acm, risk_rank = int(agg_row[0]), int(agg_row[1]), int(agg_row[2])
    else:
        total_acm, active_acm, risk_rank = 0, 0, 0

    highest = _RANK_TO_HIGHEST[risk_rank]

    current = await documents_service.current_amp(session, site_id)
    amp_expiry = current.amp_expiry_date if current else None

    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids={str(site.customer_id)},
            site_ids={str(site.site_id)},
            user_ids={str(site.updated_by)},
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
    return SiteDetailResponse(site=detail)


async def get_mobile_site_detail(
    session: AsyncSession, *, tenant_id: str, site_id: str
) -> MobileSiteDetailResponse:
    """Slim site detail for the mobile surface: 5 fields only."""
    site = await _load_site(session, site_id, tenant_id)

    acm_agg = _acm_agg_subquery()
    agg_row = (
        await session.execute(
            select(
                func.coalesce(acm_agg.c.active_acm, 0),
                func.coalesce(acm_agg.c.risk_rank, 0),
            ).where(acm_agg.c.site_id == site.id)
        )
    ).one_or_none()
    active_acm = int(agg_row[0]) if agg_row else 0
    risk_rank = int(agg_row[1]) if agg_row else 0

    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids={str(site.customer_id)},
            site_ids={str(site.site_id)},
        )

    return MobileSiteDetailResponse(
        site=MobileSiteDetail(
            asbestosSiteId=str(site.id),
            siteName=resolved.site(str(site.site_id)),
            customerName=resolved.customer(str(site.customer_id)),
            highestRisk=_RANK_TO_HIGHEST[risk_rank].value,
            activeAcmEntriesCount=active_acm,
        )
    )


async def get_asbestos_status(
    session: AsyncSession, *, tenant_id: str, site_id: str
) -> SiteAsbestosStatusResponse:
    """Return whether a site has active ACM entries and the count.

    ``site_id`` is the external Joblogic site UUID (AsbestosSites.site_id).
    """
    site = (
        await session.scalars(
            select(AsbestosSites).where(
                AsbestosSites.site_id == uuid.UUID(site_id),
                AsbestosSites.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).one_or_none()
    if site is None:
        return SiteAsbestosStatusResponse(hasActiveAcm=False, activeAcmCount=0)
    count = await session.scalar(
        select(func.count()).where(
            AsbestosAcmEntries.asbestos_site_id == site.id,
            AsbestosAcmEntries.status == AcmStatus.ACTIVE.value,
        )
    )
    active_count = count or 0
    return SiteAsbestosStatusResponse(
        asbestosSiteId=str(site.id),
        hasActiveAcm=active_count > 0,
        activeAcmCount=active_count,
    )
