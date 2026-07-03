"""Site document service — read operations only."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import rag, storage
from backend.core.enums import DocType
from backend.database.db_models import AsbestosSiteDocuments, AsbestosSites
from backend.database.exceptions import NotFoundError
from backend.domains.documents.documents_models import SiteDocument, SiteDocumentsPaginatedResponse
from backend.integrations.mainsubsys import MainSubSysClient, ResolvedNames


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
            .where(AsbestosSiteDocuments.asbestos_site_id == uuid.UUID(site_id))
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
    ).one_or_none()


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


async def list_documents_paginated(
    session: AsyncSession,
    *,
    tenant_id: str,
    site_id: str,
    page: int = 0,
    page_size: int = 20,
) -> SiteDocumentsPaginatedResponse:
    """Return all documents for a site (all types), paginated, with presigned download URLs."""
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
