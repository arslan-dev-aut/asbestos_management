"""Bulk import / export endpoints (Section 4.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.validation import validate_nonempty
from backend.database.exceptions import DomainError, UpstreamError, ValidationError
from backend.database.postgres import get_session
from backend.domains.bulk import bulk_service
from backend.domains.bulk.bulk_models import (
    BulkConfirmRequest,
    BulkConfirmResponse,
    BulkValidateResponse,
)
from backend.domains.register import register_service
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/register", tags=["bulk"])


def _file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/bulk-upload/template")
async def download_template(
    format: str = Query(default="xlsx", pattern="^(csv|xlsx)$"),
    _ctx: AuthContext = Depends(get_context),
) -> Response:
    try:
        content, media_type, filename = bulk_service.generate_template(format)
        return _file_response(content, media_type, filename)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to generate bulk upload template.", detail=str(exc)) from exc


@router.post("/bulk-upload/validate", response_model=BulkValidateResponse)
async def validate_bulk(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BulkValidateResponse:
    data = await file.read()
    if not data:
        raise ValidationError("Uploaded file is empty.")
    if len(data) > get_settings().max_upload_bytes:
        raise ValidationError("File exceeds the maximum allowed size.")
    try:
        rows, valid_count, error_count, sites_to_create, token = await bulk_service.validate(
            session, tenant_id=ctx.tenant_id, file_name=file.filename or "upload", data=data
        )
        return BulkValidateResponse(
            rows=rows,
            validCount=valid_count,
            errorCount=error_count,
            sitesToCreate=sites_to_create,
            uploadToken=token,
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to validate bulk upload file.", detail=str(exc)) from exc


@router.post("/bulk-upload/confirm", response_model=BulkConfirmResponse)
async def confirm_bulk(
    body: BulkConfirmRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BulkConfirmResponse:
    validate_nonempty(body.uploadToken, "uploadToken")
    try:
        created_entries, not_created, created_sites, skipped = await bulk_service.confirm(
            session, tenant_id=ctx.tenant_id, token=body.uploadToken, user_id=ctx.user_id
        )
        return BulkConfirmResponse(
            createdEntries=created_entries,
            notCreatedEntries=not_created,
            skippedEntries=skipped,
            createdSites=created_sites,
            message=f"Created {created_entries} ACM entries and {created_sites} new site(s)."
            + (f" {not_created} entry/entries could not be created." if not_created else ""),
        )
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to confirm bulk import.", detail=str(exc)) from exc


@router.get("/export")
async def export_register(
    format: str = Query(default="xlsx", pattern="^(csv|xlsx)$"),
    search: str | None = Query(default=None),
    customerIds: list[str] = Query(default=[]),
    siteIds: list[str] = Query(default=[]),
    riskLevel: list[str] = Query(default=[]),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        rows = await register_service.export_rows(
            session,
            tenant_id=ctx.tenant_id,
            search=search,
            customer_ids=customerIds or None,
            site_ids=siteIds or None,
            risk_levels=riskLevel or None,
        )
        content, media_type, filename = bulk_service.build_export(rows, format)
        return _file_response(content, media_type, filename)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to export register.", detail=str(exc)) from exc
