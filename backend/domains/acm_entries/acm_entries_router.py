"""ACM entry endpoints (Section 4.4)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.enums import Condition, RiskScore
from backend.core.validation import validate_uuid
from backend.database.exceptions import DomainError, UpstreamError, ValidationError
from backend.database.postgres import get_session
from backend.domains.acm_entries import acm_entries_service as svc
from backend.domains.acm_entries.acm_entries_models import (
    AcmEntryResponse,
    AcmStatusRequest,
    ActiveAcmEntriesResponse,
    AssetAcmMappingResponse,
    CreateAcmRequest,
    UpdateAcmRequest,
)
from backend.domains.documents.documents_models import PresignedUrlResponse
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/register", tags=["acm-entries"])


async def _read_upload(file: UploadFile, index: int) -> bytes:
    data = await file.read()
    if not data:
        raise ValidationError(f"File at index {index} ('{file.filename}') is empty.")
    if len(data) > get_settings().max_upload_bytes:
        raise ValidationError(f"File at index {index} ('{file.filename}') exceeds the maximum allowed size.")
    return data


@router.post("/{asbestos_site_id}/acm", response_model=AcmEntryResponse, status_code=201)
async def create_acm(
    asbestos_site_id: str,
    buildingTypeId: str = Form(...),
    roomLocation: str = Form(...),
    assetId: str | None = Form(default=None),
    acmTypeId: str = Form(...),
    condition: str = Form(...),
    riskScore: str = Form(...),
    notes: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmEntryResponse:
    """Create an ACM entry, optionally with attachments in one atomic operation."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(buildingTypeId, "buildingTypeId")
    validate_uuid(acmTypeId, "acmTypeId")
    # Drop empty-string parts (curl -F 'files=' sends a blank entry instead of a real file).
    files = [f for f in files if hasattr(f, "read") and f.filename]
    try:
        body = CreateAcmRequest(
            buildingTypeId=buildingTypeId,
            roomLocation=roomLocation,
            assetId=assetId or None,
            acmTypeId=acmTypeId,
            condition=Condition(condition),
            riskScore=RiskScore(riskScore),
            notes=notes or None,
        )
    except (ValueError, Exception) as exc:
        raise ValidationError(str(exc)) from exc

    try:
        file_data: list[tuple[str, str | None, bytes]] = []
        for i, file in enumerate(files):
            data = await _read_upload(file, i)
            file_data.append((file.filename or "upload", file.content_type, data))

        entry = await svc.create_entry_with_attachments(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            body=body,
            user_id=ctx.user_id,
            files=file_data,
        )
        return AcmEntryResponse(acmEntry=entry, message="ACM entry created.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to create ACM entry.", detail=str(exc)) from exc


@router.put("/{asbestos_site_id}/acm/{acm_entry_id}", response_model=AcmEntryResponse)
async def update_acm(
    asbestos_site_id: str,
    acm_entry_id: str,
    buildingTypeId: str = Form(...),
    roomLocation: str = Form(...),
    assetId: str | None = Form(default=None),
    acmTypeId: str = Form(...),
    condition: str = Form(...),
    riskScore: str = Form(...),
    notes: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    removeAttachmentIds: str = Form(
        default="[]",
        description="JSON array of attachment IDs to remove, e.g. [\"uuid1\", \"uuid2\"]",
    ),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmEntryResponse:
    """Update ACM fields, remove attachments, and add new attachments in one atomic operation."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(acm_entry_id, "acmEntryId")
    validate_uuid(buildingTypeId, "buildingTypeId")
    validate_uuid(acmTypeId, "acmTypeId")
    files = [f for f in files if hasattr(f, "read") and f.filename]

    try:
        body = UpdateAcmRequest(
            buildingTypeId=buildingTypeId,
            roomLocation=roomLocation,
            assetId=assetId or None,
            acmTypeId=acmTypeId,
            condition=Condition(condition),
            riskScore=RiskScore(riskScore),
            notes=notes or None,
        )
    except (ValueError, Exception) as exc:
        raise ValidationError(str(exc)) from exc

    try:
        remove_ids: list[str] = json.loads(removeAttachmentIds)
        if not isinstance(remove_ids, list):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValidationError("removeAttachmentIds must be a JSON array of ID strings.") from exc

    try:
        file_data: list[tuple[str, str | None, bytes]] = []
        for i, file in enumerate(files):
            data = await _read_upload(file, i)
            file_data.append((file.filename or "upload", file.content_type, data))

        entry = await svc.update_entry_with_attachments(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            acm_id=acm_entry_id,
            body=body,
            user_id=ctx.user_id,
            files=file_data,
            remove_attachment_ids=remove_ids,
        )
        return AcmEntryResponse(acmEntry=entry)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to update ACM entry.", detail=str(exc)) from exc


@router.patch("/{asbestos_site_id}/acm/{acm_entry_id}/status", response_model=AcmEntryResponse)
async def set_acm_status(
    asbestos_site_id: str,
    acm_entry_id: str,
    body: AcmStatusRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmEntryResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(acm_entry_id, "acmEntryId")
    try:
        entry = await svc.set_status(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            acm_id=acm_entry_id,
            status=body.status,
            user_id=ctx.user_id,
        )
        return AcmEntryResponse(acmEntry=entry)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to update ACM entry status.", detail=str(exc)) from exc


@router.get("/{asbestos_site_id}/acm", response_model=ActiveAcmEntriesResponse)
async def list_active_acm_entries(
    asbestos_site_id: str,
    statusFilter: str = Query(default="active", pattern="^(active|all)$"),
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=20, ge=1, le=100),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> ActiveAcmEntriesResponse:
    """ACM entries for a site. statusFilter: ``active`` (default) or ``all``."""
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    try:
        return await svc.list_active_entries(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            status_filter=statusFilter,
            page=page,
            page_size=pageSize,
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve ACM entries.", detail=str(exc)) from exc


@router.get("/{site_id}/asset-acm-mapping", response_model=AssetAcmMappingResponse)
async def get_asset_acm_mapping(
    site_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AssetAcmMappingResponse:
    """Active ACM entries grouped by asset for a site.

    ``site_id`` is the external MainSubSys site UUID (not the internal asbestosSiteId).
    Only entries with a linked asset are included.
    """
    validate_uuid(site_id, "siteId")
    try:
        return await svc.get_asset_acm_mapping(
            session, tenant_id=ctx.tenant_id, site_id=site_id
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve asset-ACM mapping.", detail=str(exc)) from exc


@router.get(
    "/{asbestos_site_id}/acm/{acm_entry_id}/attachments/{attachment_id}/download",
    response_model=PresignedUrlResponse,
)
async def download_attachment(
    asbestos_site_id: str,
    acm_entry_id: str,
    attachment_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PresignedUrlResponse:
    validate_uuid(asbestos_site_id, "asbestosSiteId")
    validate_uuid(acm_entry_id, "acmEntryId")
    validate_uuid(attachment_id, "attachmentId")
    try:
        url = await svc.attachment_download_url(
            session,
            tenant_id=ctx.tenant_id,
            site_id=asbestos_site_id,
            acm_id=acm_entry_id,
            attachment_id=attachment_id,
        )
        return PresignedUrlResponse(url=url)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to generate attachment download URL.", detail=str(exc)) from exc
