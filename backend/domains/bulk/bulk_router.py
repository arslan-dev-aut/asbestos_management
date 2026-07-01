"""Bulk import / export endpoints (Section 4.5).

Handlers are thin — expected failures are raised as ``DomainError`` subclasses
by the service layer; unexpected ones are handled centrally in ``backend.main``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.validation import validate_nonempty
from backend.database.exceptions import ValidationError
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
    content, media_type, filename = bulk_service.generate_template(format)
    return _file_response(content, media_type, filename)


@router.post("/bulk-upload/validate", response_model=BulkValidateResponse)
async def validate_bulk(
    request: Request,
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BulkValidateResponse:
    max_bytes = get_settings().max_upload_bytes
    # Reject oversized uploads from the declared Content-Length before buffering
    # the whole body into memory.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ValidationError("File exceeds the maximum allowed size.")
    data = await file.read()
    if not data:
        raise ValidationError("Uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValidationError("File exceeds the maximum allowed size.")

    rows, valid_count, error_count, sites_to_create, token = await bulk_service.validate(
        session,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        file_name=file.filename or "upload",
        data=data,
    )
    return BulkValidateResponse(
        rows=rows,
        validCount=valid_count,
        errorCount=error_count,
        sitesToCreate=sites_to_create,
        uploadToken=token,
    )


@router.post("/bulk-upload/confirm", response_model=BulkConfirmResponse)
async def confirm_bulk(
    body: BulkConfirmRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BulkConfirmResponse:
    validate_nonempty(body.uploadToken, "uploadToken")
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
