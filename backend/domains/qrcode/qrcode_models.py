"""Pydantic schemas for the QR code domain."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from backend.core.responses import ApiResponse


class QrCodeResponse(ApiResponse):
    token: str
    qrImageUrl: str
    previewUrl: str
    generatedAt: datetime
    generatedBy: str


# ---- Public view (no auth) ----
class PublicAttachment(BaseModel):
    fileName: str
    url: str


class PublicAcmEntry(BaseModel):
    building: str | None = None
    roomLocation: str
    acmType: str | None = None
    condition: str
    riskScore: str
    riskRag: str
    notes: str | None = None
    status: str
    attachments: list[PublicAttachment] = []


class PublicDocument(BaseModel):
    docType: str
    fileName: str
    ampExpiryDate: date | None = None
    ampExpiryRag: str | None = None
    url: str


class PublicViewResponse(ApiResponse):
    siteName: str | None = None
    customerName: str | None = None
    acmEntries: list[PublicAcmEntry]
    acmTotal: int
    acmPage: int
    acmPageSize: int
    documents: list[PublicDocument]
    docsTotal: int
    docsPage: int
    docsPageSize: int
