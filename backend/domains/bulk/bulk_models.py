"""Pydantic schemas for the bulk import / export domain."""

from __future__ import annotations

from pydantic import BaseModel

from backend.core.responses import ApiResponse


class BulkUploadRow(BaseModel):
    rowIndex: int
    status: str  # VALID | ERROR
    errorDetail: str | None = None
    customerName: str
    siteName: str
    building: str
    roomLocation: str
    asset: str | None = None
    acmType: str
    condition: str
    riskScore: str
    notes: str | None = None


class BulkValidateResponse(ApiResponse):
    rows: list[BulkUploadRow]
    validCount: int
    errorCount: int
    sitesToCreate: list[str]
    uploadToken: str


class BulkConfirmRequest(BaseModel):
    uploadToken: str


class BulkConfirmResponse(ApiResponse):
    importedEntries: int
    createdSites: int
