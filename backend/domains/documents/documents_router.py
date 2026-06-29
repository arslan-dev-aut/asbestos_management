"""Site document endpoints (Section 4.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.responses import ApiResponse
from backend.core.validation import validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.documents import documents_service as svc
from backend.domains.documents.documents_models import (
    PresignedUrlResponse,
    SiteDocumentListResponse,
    SiteDocumentResponse,
    SiteDocumentsPaginatedResponse,
)
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/register", tags=["documents"])


@router.get("/{asbestos_site_id}/documents", response_model=SiteDocumentsPaginatedResponse)
async def get_site_documents(
    asbestos_site_id: str,
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=20, ge=1, le=100),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentsPaginatedResponse:
    """All documents for a site (all types), paginated, with presigned download URLs."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        return await svc.list_documents_paginated(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            page=page,
            page_size=pageSize,
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve site documents.", detail=str(exc)) from exc


@router.post("/{asbestos_site_id}/documents", response_model=SiteDocumentListResponse, status_code=201)
async def upload_documents(
    asbestos_site_id: str,
    files: list[UploadFile] = File(default=[]),
    documentsMetadata: str = Form(
        default="[]",
        description=(
            'JSON array, one object per file. '
            'Each object: {"fileIndex": 0, "docType": "AMP", "ampExpiryDate": "2026-01-01"} '
            '— ampExpiryDate required for AMP, omit or null for others.'
        ),
    ),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentListResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        doc_inputs = await svc.parse_document_inputs(files, documentsMetadata)
        documents = await svc.upload_documents(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            user_id=ctx.user_id,
            documents=doc_inputs,
        )
        return SiteDocumentListResponse(documents=documents, message="Documents uploaded.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to upload documents.", detail=str(exc)) from exc


@router.patch(
    "/{asbestos_site_id}/documents/{document_id}/amp-expiry",
    response_model=SiteDocumentResponse,
)
async def update_amp_expiry(
    asbestos_site_id: str,
    document_id: str,
    ampExpiryDate: str = Form(...),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> SiteDocumentResponse:
    """Update an AMP's expiry date without uploading a new file (Business Rule AMP-6)."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(document_id, "documentId")
    try:
        document = await svc.update_amp_expiry(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            document_id=document_id,
            amp_expiry_date=ampExpiryDate,
            user_id=ctx.user_id,
        )
        return SiteDocumentResponse(document=document, message="AMP expiry updated.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to update AMP expiry date.", detail=str(exc)) from exc


@router.delete("/{asbestos_site_id}/documents/{document_id}", response_model=ApiResponse)
async def remove_document(
    asbestos_site_id: str,
    document_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(document_id, "documentId")
    try:
        await svc.remove_document(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            document_id=document_id,
            user_id=ctx.user_id,
        )
        return ApiResponse(message="Document removed.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to remove document.", detail=str(exc)) from exc


@router.get(
    "/{asbestos_site_id}/documents/{document_id}/download",
    response_model=PresignedUrlResponse,
)
async def download_document(
    asbestos_site_id: str,
    document_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PresignedUrlResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(document_id, "documentId")
    try:
        url = await svc.download_url(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            document_id=document_id,
        )
        return PresignedUrlResponse(url=url)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to generate document download URL.", detail=str(exc)) from exc
