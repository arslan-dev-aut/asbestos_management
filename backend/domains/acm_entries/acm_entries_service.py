"""ACM entry service — read operations only."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core import rag, storage
from backend.core.enums import AcmStatus
from backend.database.db_models import AsbestosAcmAttachments, AsbestosAcmEntries, AsbestosSites
from backend.database.exceptions import NotFoundError
from backend.domains.acm_entries.acm_entries_models import (
    AcmAttachment,
    AcmEntry,
    ActiveAcmAttachmentView,
    ActiveAcmEntriesResponse,
    ActiveAcmEntryView,
)
from backend.integrations.mainsubsys import MainSubSysClient, ResolvedNames


def attachment_to_schema(att: AsbestosAcmAttachments) -> AcmAttachment:
    return AcmAttachment(
        id=str(att.id),
        acmEntryId=str(att.acm_entry_id),
        fileName=att.file_name,
        fileUrl=att.file_url,
        uploadedAt=att.uploaded_at,
        uploadedBy=str(att.uploaded_by),
    )


def to_schema(entry: AsbestosAcmEntries, resolved: ResolvedNames) -> AcmEntry:
    return AcmEntry(
        id=str(entry.id),
        asbestosSiteId=str(entry.asbestos_site_id),
        buildingTypeId=str(entry.building_type_id),
        roomLocation=entry.room_location,
        assetId=str(entry.asset_id) if entry.asset_id else None,
        assetDiscrepancy=entry.asset_discrepancy,
        acmTypeId=str(entry.acm_type_id),
        condition=entry.condition,
        riskScore=entry.risk_score,
        riskRag=rag.risk_rag(entry.risk_score).value,
        notes=entry.notes,
        status=entry.status,
        createdAt=entry.created_at,
        createdBy=str(entry.created_by),
        updatedAt=entry.updated_at,
        updatedBy=str(entry.updated_by),
        buildingTypeName=entry.building_type.name if entry.building_type else None,
        acmTypeName=entry.acm_type.name if entry.acm_type else None,
        assetName=resolved.asset(str(entry.asset_id)) if entry.asset_id else None,
        updatedByName=resolved.user(str(entry.updated_by)),
        attachments=[attachment_to_schema(a) for a in entry.attachments],
    )


async def _require_site(session: AsyncSession, site_id: str, tenant_id: str) -> AsbestosSites:
    site = (
        await session.scalars(
            select(AsbestosSites).where(
                AsbestosSites.id == uuid.UUID(site_id),
                AsbestosSites.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).one_or_none()
    if site is None:
        raise NotFoundError("Site not found in register.")
    return site


def _compute_discrepancy(entry: AsbestosAcmEntries, resolved: ResolvedNames) -> bool:
    if not entry.asset_id:
        return False
    aid = str(entry.asset_id)
    return resolved.asset(aid) is None or resolved.is_asset_suspended(aid)


async def _entry_to_active_view(
    entry: AsbestosAcmEntries,
    resolved_assets: dict[str, str | None],
    resolved_users: dict[str, str | None],
    discrepancy: bool | None = None,
) -> ActiveAcmEntryView:
    attachments = [
        ActiveAcmAttachmentView(
            id=str(a.id),
            fileName=a.file_name,
            downloadUrl=await storage.presigned_url(a.file_url),
        )
        for a in entry.attachments
    ]
    return ActiveAcmEntryView(
        id=str(entry.id),
        building=entry.building_type.name if entry.building_type else None,
        roomLocation=entry.room_location,
        assetId=str(entry.asset_id) if entry.asset_id else None,
        assetName=resolved_assets.get(str(entry.asset_id)) if entry.asset_id else None,
        assetDiscrepancy=entry.asset_discrepancy if discrepancy is None else discrepancy,
        acmType=entry.acm_type.name if entry.acm_type else None,
        condition=entry.condition,
        riskScore=entry.risk_score,
        riskRag=rag.risk_rag(entry.risk_score).value,
        notes=entry.notes,
        status=entry.status,
        updatedAt=entry.updated_at,
        updatedBy=str(entry.updated_by),
        updatedByName=resolved_users.get(str(entry.updated_by)),
        attachments=attachments,
    )


async def list_active_entries(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    status_filter: str = "active",
    page: int = 0,
    page_size: int = 20,
) -> ActiveAcmEntriesResponse:
    """Return ACM entries for a site with presigned attachment URLs.

    status_filter: ``"active"`` returns only ACTIVE entries (default);
                   ``"all"`` returns entries of every status.
    """
    page = max(0, page)
    page_size = max(1, min(page_size, 50))

    await _require_site(session, site_id, tenant_id)

    base_where = [
        AsbestosAcmEntries.asbestos_site_id == uuid.UUID(site_id),
        AsbestosAcmEntries.tenant_id == uuid.UUID(tenant_id),
    ]
    if status_filter.lower() == "active":
        base_where.append(AsbestosAcmEntries.status == AcmStatus.ACTIVE.value)

    total_count = await session.scalar(select(func.count()).where(*base_where))

    entries = list(
        (
            await session.scalars(
                select(AsbestosAcmEntries)
                .where(*base_where)
                .options(
                    selectinload(AsbestosAcmEntries.building_type),
                    selectinload(AsbestosAcmEntries.acm_type),
                    selectinload(AsbestosAcmEntries.attachments),
                )
                .order_by(AsbestosAcmEntries.created_at)
                .offset(page * page_size)
                .limit(page_size)
            )
        ).all()
    )

    asset_ids = {str(e.asset_id) for e in entries if e.asset_id}
    user_ids = {str(e.updated_by) for e in entries}
    resolved_assets: dict[str, str | None] = {}
    resolved_users: dict[str, str | None] = {}
    resolved = ResolvedNames()
    if asset_ids or user_ids:
        async with MainSubSysClient(tenant_id) as mss:
            resolved = await mss.resolve_all(asset_ids=asset_ids, user_ids=user_ids)
            resolved_assets = {aid: resolved.asset(aid) for aid in asset_ids}
            resolved_users = {uid: resolved.user(uid) for uid in user_ids}

    views = [
        await _entry_to_active_view(
            e, resolved_assets, resolved_users, _compute_discrepancy(e, resolved)
        )
        for e in entries
    ]
    return ActiveAcmEntriesResponse(
        acmEntries=views,
        totalCount=int(total_count or 0),
        page=page,
        pageSize=page_size,
    )
