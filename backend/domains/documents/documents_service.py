"""Site document service — upload (with AMP supersede), remove, download."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from fastapi import UploadFile

from backend.config import get_settings
from backend.core import rag, storage
from backend.core.enums import AuditAction, AuditType, DocType
from backend.database.db_models import AsbestosSiteDocuments, AsbestosSites
from backend.database.exceptions import NotFoundError, ValidationError
from backend.domains.audit import audit_service
from backend.domains.documents.documents_models import DocumentMeta, SiteDocument
from backend.integrations.mainsubsys import ResolvedNames


@dataclass
class DocumentInput:
    """One file + its metadata for the atomic site-create flow."""
    file_name: str
    content_type: str | None
    data: bytes
    doc_type: str
    amp_expiry_date: str | None


def to_schema(doc: AsbestosSiteDocuments, resolved: ResolvedNames) -> SiteDocument:
    amp_rag = (
        rag.amp_expiry_rag(doc.amp_expiry_date).value
        if doc.doc_type == DocType.AMP and doc.amp_expiry_date is not None
        else None
    )
    return SiteDocument(
        id=str(doc.id),
        asbestosSiteId=str(doc.asbestos_site_id),
        docType=doc.doc_type,
        fileName=doc.file_name,
        fileUrl=doc.file_url,
        ampExpiryDate=doc.amp_expiry_date,
        ampExpiryRag=amp_rag,
        isCurrentAmp=doc.is_current_amp,
        uploadedAt=doc.uploaded_at,
        uploadedBy=str(doc.uploaded_by),
        uploadedByName=resolved.user(str(doc.uploaded_by)),
    )


async def list_for_site(session: AsyncSession, site_id: str) -> list[AsbestosSiteDocuments]:
    """Non-removed documents; current AMP first, then most-recent first."""
    rows = (
        await session.scalars(
            select(AsbestosSiteDocuments)
            .where(
                AsbestosSiteDocuments.asbestos_site_id == uuid.UUID(site_id),
            )
            .order_by(
                AsbestosSiteDocuments.is_current_amp.desc(),
                AsbestosSiteDocuments.uploaded_at.desc(),
            )
        )
    ).all()
    return list(rows)


async def current_amp(session: AsyncSession, site_id: str) -> AsbestosSiteDocuments | None:
    return (
        await session.scalars(
            select(AsbestosSiteDocuments).where(
                AsbestosSiteDocuments.asbestos_site_id == uuid.UUID(site_id),
                AsbestosSiteDocuments.doc_type == DocType.AMP.value,
                AsbestosSiteDocuments.is_current_amp.is_(True),
            )
        )
    ).first()


async def _require_site(session: AsyncSession, site_id: str, tenant_id: str) -> AsbestosSites:
    site = (
        await session.scalars(
            select(AsbestosSites).where(
                AsbestosSites.id == uuid.UUID(site_id),
                AsbestosSites.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).first()
    if site is None:
        raise NotFoundError("Site not found in register.")
    return site


def _parse_expiry(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("ampExpiryDate must be an ISO date (YYYY-MM-DD).") from exc


async def _save_document(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    file_name: str,
    content_type: str | None,
    data: bytes,
    doc_type: str,
    amp_expiry_date: str | None,
    user_id: str,
    uploaded_keys: list[str],
) -> AsbestosSiteDocuments:
    """Upload blob + stage DB record + audit entry. Does NOT commit.

    Appends the blob key to *uploaded_keys* so the caller can clean up on failure.
    """
    if doc_type not in DocType.__members__.values():
        raise ValidationError(f"Unknown docType '{doc_type}'.")
    storage.validate_upload(file_name, content_type)

    expiry: date | None = None
    is_amp = doc_type == DocType.AMP.value
    if is_amp:
        expiry = _parse_expiry(amp_expiry_date)
        if expiry is None:
            raise ValidationError("AMP Expiry Date is required when docType is AMP.")

    # Supersede ALL non-removed AMP docs when uploading a new AMP.
    # Captures the current-flag holder for the audit trail.
    previous_amp: AsbestosSiteDocuments | None = None
    if is_amp:
        existing_amps = list(
            (
                await session.scalars(
                    select(AsbestosSiteDocuments).where(
                        AsbestosSiteDocuments.asbestos_site_id == uuid.UUID(site_id),
                        AsbestosSiteDocuments.doc_type == DocType.AMP.value,
                    )
                )
            ).all()
        )
        for amp in existing_amps:
            if amp.is_current_amp:
                previous_amp = amp  # used below for audit details
            amp.is_current_amp = False

    key = storage.build_object_key(tenant_id, "sites", site_id, doc_type.lower(), file_name=file_name)
    await storage.put_object(key, data, content_type)
    uploaded_keys.append(key)

    uid = uuid.UUID(str(user_id))
    doc = AsbestosSiteDocuments(
        tenant_id=uuid.UUID(tenant_id),
        asbestos_site_id=uuid.UUID(site_id),
        doc_type=doc_type,
        file_name=file_name,
        file_url=key,
        amp_expiry_date=expiry,
        is_current_amp=is_amp,
        uploaded_by=uid,
    )
    session.add(doc)
    await session.flush()

    if is_amp and previous_amp is not None:
        action = AuditAction.AMP_REPLACED
        details = {
            "previousDocId": str(previous_amp.id),
            "previousFileName": previous_amp.file_name,
            "previousExpiryDate": previous_amp.amp_expiry_date.isoformat()
            if previous_amp.amp_expiry_date
            else None,
            "newDocId": str(doc.id),
            "newFileName": doc.file_name,
            "newExpiryDate": expiry.isoformat() if expiry else None,
        }
    else:
        action = AuditAction.SITE_DOCUMENT_UPLOADED
        details = {
            "documentId": str(doc.id),
            "fileName": doc.file_name,
            "docType": doc.doc_type,
            "fileSize": len(data),
            "ampExpiryDate": expiry.isoformat() if expiry else None,
        }

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=action,
        details=details,
    )
    return doc


async def parse_document_inputs(
    files: list[UploadFile],
    documents_metadata_json: str,
) -> list[DocumentInput]:
    """Parse and validate the multipart document payload shared by both upload endpoints.

    Validates:
    - documentsMetadata is valid JSON and matches the number of files.
    - fileIndex values cover exactly 0..N-1 with no duplicates or gaps.
    - At most one AMP document per request.
    - No empty files and no files exceeding the configured size limit.

    Returns DocumentInput list ordered by fileIndex.
    """
    try:
        meta_list: list[DocumentMeta] = [DocumentMeta(**m) for m in json.loads(documents_metadata_json)]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValidationError("documentsMetadata must be a valid JSON array of document objects.") from exc

    if len(files) != len(meta_list):
        raise ValidationError(
            f"Received {len(files)} file(s) but {len(meta_list)} documentsMetadata "
            "entry/entries — counts must match."
        )

    expected = set(range(len(files)))
    provided = {m.fileIndex for m in meta_list}
    if provided != expected:
        raise ValidationError(
            f"documentsMetadata fileIndex values must be exactly {sorted(expected)}, "
            f"got {sorted(provided)}."
        )

    amp_count = sum(1 for m in meta_list if m.docType == "AMP")
    if amp_count > 1:
        raise ValidationError("Only one AMP document is allowed per upload.")

    settings = get_settings()
    meta_by_index = {m.fileIndex: m for m in meta_list}
    inputs: list[DocumentInput] = []
    for i, file in enumerate(files):
        meta = meta_by_index[i]
        data = await file.read()
        if not data:
            raise ValidationError(f"File at index {i} ('{file.filename}') is empty.")
        if len(data) > settings.max_upload_bytes:
            raise ValidationError(
                f"File at index {i} ('{file.filename}') exceeds the maximum allowed size."
            )
        inputs.append(DocumentInput(
            file_name=file.filename or "upload",
            content_type=file.content_type,
            data=data,
            doc_type=meta.docType,
            amp_expiry_date=meta.ampExpiryDate,
        ))
    return inputs


async def upload_documents(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    user_id: str,
    documents: list[DocumentInput],
) -> list[SiteDocument]:
    """Upload multiple documents for an existing site in a single commit."""
    from backend.integrations.mainsubsys import MainSubSysClient

    await _require_site(session, site_id, tenant_id)
    uploaded_keys: list[str] = []
    docs: list[AsbestosSiteDocuments] = []
    try:
        for doc_input in documents:
            doc = await _save_document(
                session,
                tenant_id=tenant_id,
                site_id=site_id,
                file_name=doc_input.file_name,
                content_type=doc_input.content_type,
                data=doc_input.data,
                doc_type=doc_input.doc_type,
                amp_expiry_date=doc_input.amp_expiry_date,
                user_id=user_id,
                uploaded_keys=uploaded_keys,
            )
            docs.append(doc)
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise

    for doc in docs:
        await session.refresh(doc)

    user_ids = {str(d.uploaded_by) for d in docs}
    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(user_ids=user_ids)
    return [to_schema(doc, resolved) for doc in docs]


async def upload_document(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    file_name: str,
    content_type: str | None,
    data: bytes,
    doc_type: str,
    amp_expiry_date: str | None,
    user_id: str,
) -> SiteDocument:
    await _require_site(session, site_id, tenant_id)
    uploaded_keys: list[str] = []
    try:
        doc = await _save_document(
            session,
            tenant_id=tenant_id,
            site_id=site_id,
            file_name=file_name,
            content_type=content_type,
            data=data,
            doc_type=doc_type,
            amp_expiry_date=amp_expiry_date,
            user_id=user_id,
            uploaded_keys=uploaded_keys,
        )
        await session.commit()
    except Exception:
        for key in uploaded_keys:
            await storage.delete_object(key)
        raise
    await session.refresh(doc)

    from backend.integrations.mainsubsys import MainSubSysClient

    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(user_ids={str(doc.uploaded_by)})
    return to_schema(doc, resolved)


async def update_amp_expiry(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    document_id: str,
    amp_expiry_date: str,
    user_id: str,
) -> SiteDocument:
    """Update an AMP's expiry date without uploading a new file."""
    doc = await session.get(AsbestosSiteDocuments, uuid.UUID(document_id))
    if (
        doc is None
        or str(doc.asbestos_site_id) != site_id
        or doc.doc_type != DocType.AMP.value
    ):
        raise NotFoundError("AMP document not found.")

    new_expiry = _parse_expiry(amp_expiry_date)
    if new_expiry is None:
        raise ValidationError("ampExpiryDate is required.")
    previous = doc.amp_expiry_date
    doc.amp_expiry_date = new_expiry

    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=AuditAction.AMP_EXPIRY_DATE_UPDATED,
        details={
            "documentId": str(doc.id),
            "previousExpiryDate": previous.isoformat() if previous else None,
            "newExpiryDate": new_expiry.isoformat(),
        },
    )
    await session.commit()
    await session.refresh(doc)

    from backend.integrations.mainsubsys import MainSubSysClient

    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(user_ids={str(doc.uploaded_by)})
    return to_schema(doc, resolved)


async def _promote_next_amp(
    session: AsyncSession,
    *,
    site_id: str,
    exclude_id: uuid.UUID,
    tenant_id: str,
    user_id: str,
) -> None:
    """Promote the most recently uploaded remaining AMP to current after a deletion.

    No-op when no other AMPs exist for the site.
    """
    remaining_amps = list(
        (
            await session.scalars(
                select(AsbestosSiteDocuments)
                .where(
                    AsbestosSiteDocuments.asbestos_site_id == uuid.UUID(site_id),
                    AsbestosSiteDocuments.doc_type == DocType.AMP.value,
                    AsbestosSiteDocuments.id != exclude_id,
                )
                .order_by(AsbestosSiteDocuments.uploaded_at.desc())
            )
        ).all()
    )
    if not remaining_amps:
        return

    promoted = remaining_amps[0]
    promoted.is_current_amp = True
    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=AuditAction.AMP_PROMOTED,
        details={
            "promotedDocId": str(promoted.id),
            "promotedFileName": promoted.file_name,
            "reason": "Previous current AMP was deleted.",
        },
    )


async def remove_document(
    session: AsyncSession, *, tenant_id: str, site_id: str, document_id: str, user_id: str
) -> None:
    doc = await session.get(AsbestosSiteDocuments, uuid.UUID(document_id))
    if doc is None or str(doc.asbestos_site_id) != site_id or str(doc.tenant_id) != tenant_id:
        raise NotFoundError("Document not found.")

    blob_key = doc.file_url
    await audit_service.record(
        session,
        site_id=site_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_DOCUMENT,
        action=AuditAction.SITE_DOCUMENT_REMOVED,
        details={"documentId": str(doc.id), "fileName": doc.file_name, "docType": doc.doc_type},
    )
    await session.delete(doc)

    if doc.doc_type == DocType.AMP.value:
        await _promote_next_amp(
            session,
            site_id=site_id,
            exclude_id=doc.id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    await session.commit()
    await storage.delete_object(blob_key)


async def download_url(session: AsyncSession, *, tenant_id: str, site_id: str, document_id: str) -> str:
    doc = await session.get(AsbestosSiteDocuments, uuid.UUID(document_id))
    if doc is None or str(doc.asbestos_site_id) != site_id or str(doc.tenant_id) != tenant_id:
        raise NotFoundError("Document not found.")
    return await storage.presigned_url(doc.file_url)


async def list_documents_paginated(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    page: int = 0,
    page_size: int = 20,
) -> "SiteDocumentsPaginatedResponse":
    """Return all documents for a site (all types), paginated, with presigned download URLs."""
    from backend.integrations.mainsubsys import MainSubSysClient
    from backend.domains.documents.documents_models import SiteDocumentsPaginatedResponse

    await _require_site(session, site_id, tenant_id)

    page = max(0, page)
    page_size = max(1, min(page_size, 50))

    all_docs = await list_for_site(session, site_id=site_id)
    total = len(all_docs)
    page_docs = all_docs[page * page_size : (page + 1) * page_size]

    user_ids = {str(d.uploaded_by) for d in page_docs}
    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(user_ids=user_ids)

    documents = []
    for doc in page_docs:
        schema = to_schema(doc, resolved)
        schema.downloadUrl = await storage.presigned_url(doc.file_url)
        documents.append(schema)

    return SiteDocumentsPaginatedResponse(
        documents=documents,
        total=total,
        page=page,
        pageSize=page_size,
    )
