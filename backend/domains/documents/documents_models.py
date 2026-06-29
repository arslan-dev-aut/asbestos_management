"""Pydantic schemas for site documents."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from backend.core.responses import ApiResponse


class SiteDocument(BaseModel):
    id: str
    asbestosSiteId: str
    docType: str
    fileName: str
    fileUrl: str
    downloadUrl: str | None = None
    ampExpiryDate: date | None = None
    ampExpiryRag: str | None = None
    isCurrentAmp: bool
    uploadedAt: datetime
    uploadedBy: str
    uploadedByName: str | None = None


class SiteDocumentResponse(ApiResponse):
    document: SiteDocument


class SiteDocumentListResponse(ApiResponse):
    documents: list[SiteDocument]


class DocumentMeta(BaseModel):
    """Per-document metadata paired to a binary file by fileIndex."""
    fileIndex: int
    docType: str
    ampExpiryDate: str | None = None


class PresignedUrlResponse(BaseModel):
    url: str
    success: bool = True


class SiteDocumentsPaginatedResponse(ApiResponse):
    documents: list[SiteDocument]
    total: int
    page: int
    pageSize: int
