"""Audit service.

``record`` is the single write path used by every other domain to append an
immutable audit entry inside the caller's transaction. ``list_for_site`` backs
the site Audit Trail tab.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import AuditAction, AuditType
from backend.database.db_models import AsbestosAuditLog
from backend.database.exceptions import ValidationError
from backend.domains.audit.audit_models import AuditLogEntry
from backend.integrations.mainsubsys import MainSubSysClient


async def record(
    session: AsyncSession,
    *,
    user_id: str,
    audit_type: AuditType,
    action: AuditAction,
    details: dict | None = None,
    site_id: str | uuid.UUID | None = None,
    tenant_id: str | None = None,
) -> AsbestosAuditLog:
    """Append an audit entry inside the caller's transaction. Does NOT commit.

    site_id is optional — configuration-level actions (building/ACM type
    add/toggle) have no associated site and are stored with
    asbestos_site_id = NULL. Site-scoped actions (ACM entries, documents, etc.)
    must pass a site_id.
    """
    entry = AsbestosAuditLog(
        tenant_id=uuid.UUID(str(tenant_id)) if tenant_id else uuid.uuid4(),
        asbestos_site_id=uuid.UUID(str(site_id)) if site_id else None,
        user_id=uuid.UUID(str(user_id)),
        audit_type=audit_type.value,
        action=action.value,
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry


def _build_base_query(
    tenant_id: str,
    site_id: str | None,
    audit_type: str | None,
    action: str | None,
):
    """Shared WHERE clause builder for both list functions."""
    if audit_type is not None and audit_type not in AuditType.__members__.values():
        raise ValidationError(f"Unknown auditType '{audit_type}'.")

    base = select(AsbestosAuditLog).where(
        AsbestosAuditLog.tenant_id == uuid.UUID(tenant_id),
    )
    if site_id is not None:
        base = base.where(AsbestosAuditLog.asbestos_site_id == uuid.UUID(site_id))
    if audit_type:
        base = base.where(AsbestosAuditLog.audit_type == audit_type)
    if action:
        base = base.where(AsbestosAuditLog.action == action)
    return base


def _to_entry(
    row: AsbestosAuditLog,
    names: dict,
    site_names: dict,
    customer_names: dict,
) -> AuditLogEntry:
    details = dict(row.details) if row.details else {}
    if "siteId" in details:
        details["siteName"] = site_names.get(details.pop("siteId"))
    if "customerId" in details:
        details["customerName"] = customer_names.get(details.pop("customerId"))
    return AuditLogEntry(
        id=str(row.id),
        asbestosSiteId=str(row.asbestos_site_id) if row.asbestos_site_id else None,
        userId=str(row.user_id),
        userName=names.get(str(row.user_id)),
        auditType=row.audit_type,
        action=row.action,
        details=details,
        occurredAt=row.occurred_at,
    )


async def _paginate(
    session: AsyncSession,
    tenant_id: str,
    base,
    page_index: int,
    page_size: int,
) -> tuple[list[AuditLogEntry], int]:
    page_size = max(1, min(page_size, 50))
    page_index = max(0, page_index)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await session.scalars(
            base.order_by(AsbestosAuditLog.occurred_at.desc())
            .offset(page_index * page_size)
            .limit(page_size)
        )
    ).all()

    user_ids = {str(r.user_id) for r in rows}
    site_ids = {r.details["siteId"] for r in rows if r.details and "siteId" in r.details}
    customer_ids = {r.details["customerId"] for r in rows if r.details and "customerId" in r.details}

    names: dict[str, str] = {}
    site_names: dict[str, str] = {}
    customer_names: dict[str, str] = {}
    if user_ids or site_ids or customer_ids:
        async with MainSubSysClient(tenant_id) as mss:
            resolved = await mss.resolve_all(
                user_ids=user_ids,
                site_ids=site_ids,
                customer_ids=customer_ids,
            )
        names = {uid: resolved.user(uid) for uid in user_ids if resolved.user(uid)}
        site_names = {sid: resolved.site(sid) for sid in site_ids if resolved.site(sid)}
        customer_names = {cid: resolved.customer(cid) for cid in customer_ids if resolved.customer(cid)}

    return [_to_entry(r, names, site_names, customer_names) for r in rows], int(total or 0)


async def list_for_site(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    audit_type: str | None,
    action: str | None,
    page_index: int,
    page_size: int,
) -> tuple[list[AuditLogEntry], int]:
    """Paginated audit trail for a single site (most recent first)."""
    base = _build_base_query(tenant_id, site_id, audit_type, action)
    return await _paginate(session, tenant_id, base, page_index, page_size)


async def list_config_logs(
    session: AsyncSession,
    *,
    tenant_id: str,
    action: str | None = None,
    page_index: int = 0,
    page_size: int = 50,
) -> tuple[list[AuditLogEntry], int]:
    """Paginated configuration audit trail for the tenant (most recent first).

    Returns only ASBESTOS_CONFIGURATION records (building type / ACM type
    add, deactivate, reactivate). These records have no associated site.
    """
    base = select(AsbestosAuditLog).where(
        AsbestosAuditLog.tenant_id == uuid.UUID(tenant_id),
        AsbestosAuditLog.audit_type == AuditType.ASBESTOS_CONFIGURATION.value,
        AsbestosAuditLog.asbestos_site_id.is_(None),
    )
    if action:
        base = base.where(AsbestosAuditLog.action == action)
    return await _paginate(session, tenant_id, base, page_index, page_size)


