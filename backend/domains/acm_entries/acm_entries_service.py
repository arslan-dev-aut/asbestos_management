"""ACM entry service — CRUD, status toggle, and entry-level attachments."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func

from backend.core import rag, storage
from backend.core.enums import AcmStatus, AuditAction, AuditType
from backend.database.db_models import (
    AsbestosAcmAttachments,
    AsbestosAcmEntries,
    AsbestosAcmTypes,
    AsbestosBuildingTypes,
    AsbestosSites,
)
from backend.database.exceptions import NotFoundError, ValidationError
from backend.domains.acm_entries.acm_entries_models import (
    AcmAttachment,
    AcmEntry,
    ActiveAcmAttachmentView,
    ActiveAcmEntriesResponse,
    ActiveAcmEntryView,
    AssetAcmItem,
    AssetAcmLinkResponse,
    AssetAcmMappingResponse,
    CreateAcmRequest,
    UpdateAcmRequest,
)
from backend.domains.audit import audit_service
from backend.integrations.mainsubsys import MainSubSysClient, ResolvedNames


# ---- serialization ----
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
        attachments=[
            attachment_to_schema(a) for a in entry.attachments
        ],
    )


# ---- helpers ----
async def _load_entry(
    session: AsyncSession, site_id: str, acm_id: str, tenant_id: str
) -> AsbestosAcmEntries:
    entry = (
        await session.scalars(
            select(AsbestosAcmEntries)
            .where(
                AsbestosAcmEntries.id == uuid.UUID(acm_id),
                AsbestosAcmEntries.asbestos_site_id == uuid.UUID(site_id),
                AsbestosAcmEntries.tenant_id == uuid.UUID(tenant_id),
            )
            .options(
                selectinload(AsbestosAcmEntries.building_type),
                selectinload(AsbestosAcmEntries.acm_type),
                selectinload(AsbestosAcmEntries.attachments),
            )
        )
    ).one_or_none()
    if entry is None:
        raise NotFoundError("ACM entry not found.")
    return entry


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


async def _require_site_by_external_id(
    session: AsyncSession, site_id: str, tenant_id: str
) -> AsbestosSites:
    """Look up an asbestos site by its external MainSubSys site UUID (AsbestosSites.site_id)."""
    site = (
        await session.scalars(
            select(AsbestosSites).where(
                AsbestosSites.site_id == uuid.UUID(site_id),
                AsbestosSites.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).one_or_none()
    if site is None:
        raise NotFoundError(f"No asbestos register entry found for site '{site_id}'.")
    return site


async def _validate_active_type(session: AsyncSession, model, type_id: str, label: str) -> None:
    row = await session.get(model, uuid.UUID(type_id))
    if row is None or not row.is_active:
        raise ValidationError(f"{label} must be an existing, active type.")


async def _resolve_for_entry(tenant_id: str, entry: AsbestosAcmEntries) -> ResolvedNames:

    async with MainSubSysClient(tenant_id) as mss:
        return await mss.resolve_all(
            asset_ids={str(entry.asset_id)} if entry.asset_id else set(),
            user_ids={str(entry.updated_by)},
        )


# ---- operations ----
async def create_entry(
    session: AsyncSession, *, tenant_id: str, site_id: str, body: CreateAcmRequest, user_id: str
) -> AcmEntry:
    await _require_site(session, site_id, tenant_id)
    await _validate_active_type(session, AsbestosBuildingTypes, body.buildingTypeId, "Building")
    await _validate_active_type(session, AsbestosAcmTypes, body.acmTypeId, "ACM Type")

    uid = uuid.UUID(str(user_id))
    entry = AsbestosAcmEntries(
        tenant_id=uuid.UUID(tenant_id),
        asbestos_site_id=uuid.UUID(site_id),
        building_type_id=uuid.UUID(body.buildingTypeId),
        room_location=body.roomLocation.strip(),
        asset_id=uuid.UUID(body.assetId) if body.assetId else None,
        acm_type_id=uuid.UUID(body.acmTypeId),
        condition=body.condition.value,
        risk_score=body.riskScore.value,
        notes=body.notes,
        status=AcmStatus.ACTIVE.value,
        created_by=uid,
        updated_by=uid,
    )
    session.add(entry)
    await session.flush()

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_ACM,
        action=AuditAction.ACM_ENTRY_CREATED,
        details={
            "acmEntryId": str(entry.id),
            "buildingTypeId": body.buildingTypeId,
            "roomLocation": entry.room_location,
            "acmTypeId": body.acmTypeId,
            "riskScore": entry.risk_score,
            "condition": entry.condition,
        },
    )
    await session.commit()
    entry = await _load_entry(session, site_id, str(entry.id), tenant_id)
    return to_schema(entry, await _resolve_for_entry(tenant_id, entry))


async def create_entry_with_attachments(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    body: CreateAcmRequest,
    user_id: str,
    files: list[tuple[str, str | None, bytes]],
) -> AcmEntry:
    """Create an ACM entry and upload attachments atomically.

    All DB writes and blob uploads succeed or fail together.
    ``files`` is a list of (file_name, content_type, data) tuples.
    """
    await _require_site(session, site_id, tenant_id)
    await _validate_active_type(session, AsbestosBuildingTypes, body.buildingTypeId, "Building")
    await _validate_active_type(session, AsbestosAcmTypes, body.acmTypeId, "ACM Type")

    uid = uuid.UUID(str(user_id))
    entry = AsbestosAcmEntries(
        tenant_id=uuid.UUID(tenant_id),
        asbestos_site_id=uuid.UUID(site_id),
        building_type_id=uuid.UUID(body.buildingTypeId),
        room_location=body.roomLocation.strip(),
        asset_id=uuid.UUID(body.assetId) if body.assetId else None,
        acm_type_id=uuid.UUID(body.acmTypeId),
        condition=body.condition.value,
        risk_score=body.riskScore.value,
        notes=body.notes,
        status=AcmStatus.ACTIVE.value,
        created_by=uid,
        updated_by=uid,
    )
    session.add(entry)
    await session.flush()

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_ACM,
        action=AuditAction.ACM_ENTRY_CREATED,
        details={
            "acmEntryId": str(entry.id),
            "buildingTypeId": body.buildingTypeId,
            "roomLocation": entry.room_location,
            "acmTypeId": body.acmTypeId,
            "riskScore": entry.risk_score,
            "condition": entry.condition,
            "attachmentCount": len(files),
        },
    )

    # Need building_type loaded for attachment audit details before we have a full load.
    await session.refresh(entry, ["building_type", "acm_type"])

    uploaded_keys: list[str] = []
    try:
        for file_name, content_type, data in files:
            await _save_attachment(
                session,
                tenant_id=tenant_id,
                site_id=site_id,
                entry=entry,
                file_name=file_name,
                content_type=content_type,
                data=data,
                user_id=user_id,
                uploaded_keys=uploaded_keys,
            )
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise

    entry = await _load_entry(session, site_id, str(entry.id), tenant_id)
    return to_schema(entry, await _resolve_for_entry(tenant_id, entry))


async def update_entry(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    acm_id: str,
    body: UpdateAcmRequest,
    user_id: str,
) -> AcmEntry:
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    await _validate_active_type(session, AsbestosBuildingTypes, body.buildingTypeId, "Building")
    await _validate_active_type(session, AsbestosAcmTypes, body.acmTypeId, "ACM Type")

    # Build a field-level diff for the audit entry.
    new_values = {
        "buildingTypeId": body.buildingTypeId,
        "roomLocation": body.roomLocation.strip(),
        "assetId": body.assetId,
        "acmTypeId": body.acmTypeId,
        "condition": body.condition.value,
        "riskScore": body.riskScore.value,
        "notes": body.notes,
    }
    old_values = {
        "buildingTypeId": str(entry.building_type_id),
        "roomLocation": entry.room_location,
        "assetId": str(entry.asset_id) if entry.asset_id else None,
        "acmTypeId": str(entry.acm_type_id),
        "condition": entry.condition,
        "riskScore": entry.risk_score,
        "notes": entry.notes,
    }
    changes = {
        k: {"from": old_values[k], "to": new_values[k]}
        for k in new_values
        if old_values[k] != new_values[k]
    }

    entry.building_type_id = uuid.UUID(body.buildingTypeId)
    entry.room_location = new_values["roomLocation"]
    entry.asset_id = uuid.UUID(body.assetId) if body.assetId else None
    # Asset relink clears any prior discrepancy; re-checked on next detail load.
    entry.asset_discrepancy = False
    entry.acm_type_id = uuid.UUID(body.acmTypeId)
    entry.condition = body.condition.value
    entry.risk_score = body.riskScore.value
    entry.notes = body.notes
    entry.updated_by = uuid.UUID(str(user_id))

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_ACM,
        action=AuditAction.ACM_ENTRY_EDITED,
        details={"acmEntryId": str(entry.id), "changes": changes},
    )
    await session.commit()
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    return to_schema(entry, await _resolve_for_entry(tenant_id, entry))


async def update_entry_with_attachments(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    acm_id: str,
    body: UpdateAcmRequest,
    user_id: str,
    files: list[tuple[str, str | None, bytes]],
    remove_attachment_ids: list[str],
) -> AcmEntry:
    """Update ACM fields, remove specified attachments, and add new attachments atomically."""
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    await _validate_active_type(session, AsbestosBuildingTypes, body.buildingTypeId, "Building")
    await _validate_active_type(session, AsbestosAcmTypes, body.acmTypeId, "ACM Type")

    # Validate all removals upfront before touching anything.
    atts_to_remove: list[AsbestosAcmAttachments] = []
    for att_id in remove_attachment_ids:
        att = await session.get(AsbestosAcmAttachments, uuid.UUID(att_id))
        if att is None or att.acm_entry_id != entry.id:
            raise NotFoundError(f"Attachment '{att_id}' not found.")
        atts_to_remove.append(att)

    # Field-level diff for audit.
    new_values = {
        "buildingTypeId": body.buildingTypeId,
        "roomLocation": body.roomLocation.strip(),
        "assetId": body.assetId,
        "acmTypeId": body.acmTypeId,
        "condition": body.condition.value,
        "riskScore": body.riskScore.value,
        "notes": body.notes,
    }
    old_values = {
        "buildingTypeId": str(entry.building_type_id),
        "roomLocation": entry.room_location,
        "assetId": str(entry.asset_id) if entry.asset_id else None,
        "acmTypeId": str(entry.acm_type_id),
        "condition": entry.condition,
        "riskScore": entry.risk_score,
        "notes": entry.notes,
    }
    changes = {
        k: {"from": old_values[k], "to": new_values[k]}
        for k in new_values
        if old_values[k] != new_values[k]
    }

    entry.building_type_id = uuid.UUID(body.buildingTypeId)
    entry.room_location = new_values["roomLocation"]
    entry.asset_id = uuid.UUID(body.assetId) if body.assetId else None
    entry.asset_discrepancy = False
    entry.acm_type_id = uuid.UUID(body.acmTypeId)
    entry.condition = body.condition.value
    entry.risk_score = body.riskScore.value
    entry.notes = body.notes
    entry.updated_by = uuid.UUID(str(user_id))

    if changes:
        await audit_service.record(
            session,
            site_id=site_id,
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type=AuditType.ASBESTOS_ACM,
            action=AuditAction.ACM_ENTRY_EDITED,
            details={"acmEntryId": str(entry.id), "changes": changes},
        )

    # Hard-delete requested attachments — capture blob keys before commit.
    removed_blob_keys = [att.file_url for att in atts_to_remove]
    for att in atts_to_remove:
        await audit_service.record(
            session,
            site_id=site_id,
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type=AuditType.ASBESTOS_DOCUMENT,
            action=AuditAction.ACM_DOCUMENT_REMOVED,
            details={"fileName": att.file_name, "acmEntryId": str(entry.id)},
        )
        await session.delete(att)

    # Upload new attachments — flush field changes first so the entry is consistent.
    await session.flush()
    uploaded_keys: list[str] = []
    try:
        for file_name, content_type, data in files:
            await _save_attachment(
                session,
                tenant_id=tenant_id,
                site_id=site_id,
                entry=entry,
                file_name=file_name,
                content_type=content_type,
                data=data,
                user_id=user_id,
                uploaded_keys=uploaded_keys,
            )
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise

    # Post-commit: delete blobs for soft-deleted attachments (best-effort).
    for key in removed_blob_keys:
        await storage.delete_object(key)

    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    return to_schema(entry, await _resolve_for_entry(tenant_id, entry))


async def set_status(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    acm_id: str,
    status: str,
    user_id: str,
) -> AcmEntry:
    # Defense in depth: never persist a status outside the allowed set, even if a
    # future caller bypasses the router's request-model validation.
    if status not in (AcmStatus.ACTIVE.value, AcmStatus.REMEDIATED.value):
        raise ValidationError(f"Invalid ACM status '{status}'.")
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    previous = entry.status
    entry.status = status
    entry.updated_by = uuid.UUID(str(user_id))

    action = (
        AuditAction.ACM_ENTRY_REACTIVATED
        if status == AcmStatus.ACTIVE.value
        else AuditAction.ACM_ENTRY_MARKED_REMEDIATED
    )
    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_ACM,
        action=action,
        details={
            "acmEntryId": str(entry.id),
            "fromStatus": previous,
            "toStatus": status,
            "building": entry.building_type.name if entry.building_type else None,
            "room": entry.room_location,
        },
    )
    await session.commit()
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    return to_schema(entry, await _resolve_for_entry(tenant_id, entry))


async def _save_attachment(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    entry: AsbestosAcmEntries,
    file_name: str,
    content_type: str | None,
    data: bytes,
    user_id: str,
    uploaded_keys: list[str],
) -> AsbestosAcmAttachments:
    """Upload blob + stage attachment record + audit entry. Does NOT commit.

    Appends the blob key to *uploaded_keys* so the caller can clean up on failure.
    """
    storage.validate_upload(file_name, content_type)
    key = storage.build_object_key(tenant_id, "acm", str(entry.id), file_name=file_name)
    await storage.put_object(key, data, content_type)
    uploaded_keys.append(key)

    att = AsbestosAcmAttachments(
        tenant_id=uuid.UUID(tenant_id),
        acm_entry_id=entry.id,
        file_name=file_name,
        file_url=key,
        uploaded_by=uuid.UUID(str(user_id)),
    )
    session.add(att)
    await session.flush()

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=AuditAction.ACM_DOCUMENT_UPLOADED,
        details={
            "fileName": file_name,
            "acmEntryId": str(entry.id),
            "building": entry.building_type.name if entry.building_type else None,
            "room": entry.room_location,
        },
    )
    return att


async def add_attachment(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    acm_id: str,
    file_name: str,
    content_type: str | None,
    data: bytes,
    user_id: str,
) -> AcmAttachment:
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    uploaded_keys: list[str] = []
    try:
        att = await _save_attachment(
            session,
            tenant_id=tenant_id,
            site_id=site_id,
            entry=entry,
            file_name=file_name,
            content_type=content_type,
            data=data,
            user_id=user_id,
            uploaded_keys=uploaded_keys,
        )
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise
    await session.refresh(att)
    return attachment_to_schema(att)


async def remove_attachment(
    session: AsyncSession, *, tenant_id: str, site_id: str, acm_id: str, attachment_id: str, user_id: str
) -> None:
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    att = await session.get(AsbestosAcmAttachments, uuid.UUID(attachment_id))
    if att is None or att.acm_entry_id != entry.id:
        raise NotFoundError("Attachment not found.")

    blob_key = att.file_url
    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=AuditAction.ACM_DOCUMENT_REMOVED,
        details={"fileName": att.file_name, "acmEntryId": str(entry.id)},
    )
    await session.delete(att)
    await session.commit()
    await storage.delete_object(blob_key)


async def attachment_download_url(
    session: AsyncSession, *, tenant_id: str, site_id: str, acm_id: str, attachment_id: str
) -> str:
    entry = await _load_entry(session, site_id, acm_id, tenant_id)
    att = await session.get(AsbestosAcmAttachments, uuid.UUID(attachment_id))
    if att is None or att.acm_entry_id != entry.id:
        raise NotFoundError("Attachment not found.")
    return await storage.presigned_url(att.file_url)


def _compute_discrepancy(entry: AsbestosAcmEntries, resolved: ResolvedNames) -> bool:
    """An ACM's asset is discrepant when it is removed (None) OR suspended upstream."""
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
        # Computed live at read time; reads never write to the DB.
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

    total_count = await session.scalar(
        select(func.count()).where(*base_where)
    )

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

    # Discrepancy is computed live for the response — a GET never mutates the DB.
    # (Persisting the flag is the job of the write paths / a scheduled job.)
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


async def check_asset_acm_link(
    session: AsyncSession, *, tenant_id: str, asset_id: str
):
    """Return whether a JobLogic asset is linked to any active ACM entry for this tenant."""
    count = await session.scalar(
        select(func.count()).where(
            AsbestosAcmEntries.tenant_id == uuid.UUID(tenant_id),
            AsbestosAcmEntries.asset_id == uuid.UUID(asset_id),
            AsbestosAcmEntries.status == AcmStatus.ACTIVE.value,
        )
    )
    active_count = int(count or 0)
    return AssetAcmLinkResponse(
        assetId=asset_id,
        linked=active_count > 0,
        activeEntryCount=active_count,
    )


async def get_asset_acm_mapping(
    session: AsyncSession, *, tenant_id: str, site_id: str
) -> AssetAcmMappingResponse:
    """Return a per-asset grouping of active ACM entries for a site.

    ``site_id`` is the external MainSubSys site UUID (AsbestosSites.site_id).
    The internal asbestos_site_id is resolved from the asbestos_sites table first.
    """
    asbestos_site = await _require_site_by_external_id(session, site_id, tenant_id)
    asbestos_site_id = asbestos_site.id

    entries = list(
        (
            await session.scalars(
                select(AsbestosAcmEntries)
                .where(
                    AsbestosAcmEntries.asbestos_site_id == asbestos_site_id,
                    AsbestosAcmEntries.tenant_id == uuid.UUID(tenant_id),
                    AsbestosAcmEntries.status == AcmStatus.ACTIVE.value,
                    AsbestosAcmEntries.asset_id.is_not(None),
                )
                .options(
                    selectinload(AsbestosAcmEntries.building_type),
                    selectinload(AsbestosAcmEntries.acm_type),
                    selectinload(AsbestosAcmEntries.attachments),
                )
                .order_by(AsbestosAcmEntries.asset_id, AsbestosAcmEntries.created_at)
            )
        ).all()
    )

    asset_ids = {str(e.asset_id) for e in entries}
    user_ids = {str(e.updated_by) for e in entries}
    resolved_assets: dict[str, str | None] = {}
    resolved_users: dict[str, str | None] = {}
    resolved = ResolvedNames()
    if asset_ids or user_ids:
        async with MainSubSysClient(tenant_id) as mss:
            resolved = await mss.resolve_all(asset_ids=asset_ids, user_ids=user_ids)
            resolved_assets = {aid: resolved.asset(aid) for aid in asset_ids}
            resolved_users = {uid: resolved.user(uid) for uid in user_ids}

    # Group by asset_id preserving insertion order. Discrepancy is computed live
    # for the response — a GET never mutates the DB.
    grouped: dict[str, list] = {}
    for entry in entries:
        aid = str(entry.asset_id)
        if aid not in grouped:
            grouped[aid] = []
        grouped[aid].append(
            await _entry_to_active_view(
                entry, resolved_assets, resolved_users, _compute_discrepancy(entry, resolved)
            )
        )

    mapping = [
        AssetAcmItem(
            assetId=aid,
            assetName=resolved_assets.get(aid),
            acmEntries=views,
        )
        for aid, views in grouped.items()
    ]
    return AssetAcmMappingResponse(mapping=mapping)
