"""QR code service — generate/retrieve per-site token and serve the public view."""

from __future__ import annotations

import io
import secrets
import uuid

import qrcode
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.core import rag, storage
from backend.core.enums import AcmStatus, DocType
from backend.database.db_models import (
    AsbestosAcmEntries,
    AsbestosQrCodes,
    AsbestosSiteDocuments,
    AsbestosSites,
)
from backend.database.exceptions import NotFoundError
from backend.domains.qrcode.qrcode_models import (
    PublicAcmEntry,
    PublicAttachment,
    PublicDocument,
    PublicViewResponse,
    QrCodeResponse,
)
from backend.integrations.mainsubsys import MainSubSysClient

_PUBLIC_DOC_TYPES = (DocType.AMP.value, DocType.SURVEY_REPORT.value, DocType.AIR_MONITORING.value)


def _preview_url(token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/public/{token}"


async def _render_qr_png(preview_url: str, site_id: str) -> str:
    img = qrcode.make(preview_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    key = f"qr/{site_id}.png"
    await storage.put_object(key, buf.getvalue(), "image/png")
    return await storage.public_url(key)


async def _to_response(
    session: AsyncSession, tenant_id: str, qr: AsbestosQrCodes
) -> QrCodeResponse:
    preview = _preview_url(qr.token)
    image_url = await _render_qr_png(preview, str(qr.site_id))
    async with MainSubSysClient(tenant_id) as mss:
        users = await mss.resolve_users({str(qr.generated_by)})
    return QrCodeResponse(
        token=qr.token,
        qrImageUrl=image_url,
        previewUrl=preview,
        generatedAt=qr.generated_at,
        generatedBy=users.get(str(qr.generated_by)) or str(qr.generated_by),
    )


async def create_for_new_site(
    session: AsyncSession, *, tenant_id: str, site_id: str, user_id: str
) -> None:
    """Stage a QR record for a newly created site. No-op if one already exists.

    Does NOT commit — the caller controls the transaction.
    site_id must be the internal AsbestosSites.id (UUID string).
    """
    existing = (
        await session.scalars(
            select(AsbestosQrCodes).where(
                AsbestosQrCodes.site_id == uuid.UUID(site_id),
                AsbestosQrCodes.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).one_or_none()
    if existing is not None:
        return

    qr = AsbestosQrCodes(
        tenant_id=uuid.UUID(tenant_id),
        site_id=uuid.UUID(site_id),
        token=secrets.token_urlsafe(32),
        generated_by=uuid.UUID(str(user_id)),
    )
    session.add(qr)


async def get(session: AsyncSession, *, tenant_id: str, site_id: str) -> QrCodeResponse:
    qr = (
        await session.scalars(
            select(AsbestosQrCodes).where(
                AsbestosQrCodes.site_id == uuid.UUID(site_id),
                AsbestosQrCodes.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).one_or_none()
    if qr is None:
        raise NotFoundError("No QR code has been generated for this site yet.")
    return await _to_response(session, tenant_id, qr)


async def public_view(
    session: AsyncSession,
    *,
    token: str,
    acm_page: int = 0,
    acm_page_size: int = 10,
    docs_page: int = 0,
    docs_page_size: int = 10,
) -> PublicViewResponse:
    """Unauthenticated read-only view: active ACM entries + current documents."""
    qr = (
        await session.scalars(select(AsbestosQrCodes).where(AsbestosQrCodes.token == token))
    ).one_or_none()
    if qr is None:
        raise NotFoundError("This QR code is no longer valid.")

    site = await session.get(AsbestosSites, qr.site_id)
    if site is None:
        raise NotFoundError("This QR code is no longer valid.")

    acm_where = (
        AsbestosAcmEntries.asbestos_site_id == site.id,
        AsbestosAcmEntries.status == AcmStatus.ACTIVE.value,
    )
    acm_total = await session.scalar(select(func.count()).where(*acm_where)) or 0
    entries = (
        await session.scalars(
            select(AsbestosAcmEntries)
            .where(*acm_where)
            .options(
                selectinload(AsbestosAcmEntries.building_type),
                selectinload(AsbestosAcmEntries.acm_type),
                selectinload(AsbestosAcmEntries.attachments),
            )
            .order_by(AsbestosAcmEntries.created_at)
            .offset(acm_page * acm_page_size)
            .limit(acm_page_size)
        )
    ).all()

    # Filter out superseded AMPs in SQL so the count is accurate for pagination.
    docs_where = (
        AsbestosSiteDocuments.asbestos_site_id == site.id,
        AsbestosSiteDocuments.doc_type.in_(_PUBLIC_DOC_TYPES),
        or_(
            AsbestosSiteDocuments.doc_type != DocType.AMP.value,
            AsbestosSiteDocuments.is_current_amp.is_(True),
        ),
    )
    docs_total = await session.scalar(select(func.count()).where(*docs_where)) or 0
    docs = (
        await session.scalars(
            select(AsbestosSiteDocuments)
            .where(*docs_where)
            .order_by(AsbestosSiteDocuments.uploaded_at)
            .offset(docs_page * docs_page_size)
            .limit(docs_page_size)
        )
    ).all()

    public_entries: list[PublicAcmEntry] = []
    for e in entries:
        attachments = [
            PublicAttachment(fileName=a.file_name, url=await storage.presigned_url(a.file_url))
            for a in e.attachments
        ]
        public_entries.append(
            PublicAcmEntry(
                building=e.building_type.name if e.building_type else None,
                roomLocation=e.room_location,
                acmType=e.acm_type.name if e.acm_type else None,
                condition=e.condition,
                riskScore=e.risk_score,
                riskRag=rag.risk_rag(e.risk_score).value,
                notes=e.notes,
                status=e.status,
                attachments=attachments,
            )
        )

    public_docs: list[PublicDocument] = []
    for d in docs:
        amp_rag = (
            rag.amp_expiry_rag(d.amp_expiry_date).value
            if d.doc_type == DocType.AMP.value and d.amp_expiry_date
            else None
        )
        public_docs.append(
            PublicDocument(
                docType=d.doc_type,
                fileName=d.file_name,
                ampExpiryDate=d.amp_expiry_date,
                ampExpiryRag=amp_rag,
                url=await storage.presigned_url(d.file_url),
            )
        )

    # Use the tenant stored on the QR record to resolve display names.
    # JICRO_AUTH_TOKEN must belong to a service account with read access across
    # all tenant workspaces — one token per environment, set in config.
    tenant_id = str(qr.tenant_id)
    async with MainSubSysClient(tenant_id) as mss:
        resolved = await mss.resolve_all(
            customer_ids={str(site.customer_id)},
            site_ids={str(site.site_id)},
        )

    return PublicViewResponse(
        siteName=resolved.site(str(site.site_id)),
        customerName=resolved.customer(str(site.customer_id)),
        acmEntries=public_entries,
        acmTotal=acm_total,
        acmPage=acm_page,
        acmPageSize=acm_page_size,
        documents=public_docs,
        docsTotal=docs_total,
        docsPage=docs_page,
        docsPageSize=docs_page_size,
    )
