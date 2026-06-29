"""Generic file download endpoint.

Resolves a file UUID against either AsbestosSiteDocuments or
AsbestosAcmAttachments and returns a short-lived presigned download URL,
so callers don't need to know which table the file belongs to.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import storage
from backend.core.validation import validate_uuid
from backend.database.db_models import AsbestosAcmAttachments, AsbestosSiteDocuments
from backend.database.exceptions import DomainError, NotFoundError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.documents.documents_models import PresignedUrlResponse
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}/download", response_model=PresignedUrlResponse)
async def download_file(
    file_id: str,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PresignedUrlResponse:
    """Return a presigned download URL for a site document or ACM attachment.

    ``file_id`` is the UUID primary key of either record type.
    The file must belong to the authenticated tenant.
    """
    validate_uuid(file_id, "fileId")
    try:
        fid = uuid.UUID(file_id)

        doc = await session.get(AsbestosSiteDocuments, fid)
        if doc and str(doc.tenant_id) == ctx.tenant_id:
            return PresignedUrlResponse(url=await storage.presigned_url(doc.file_url))

        att = await session.get(AsbestosAcmAttachments, fid)
        if att and str(att.tenant_id) == ctx.tenant_id:
            return PresignedUrlResponse(url=await storage.presigned_url(att.file_url))

        raise NotFoundError("File not found.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to generate file download URL.", detail=str(exc)) from exc
