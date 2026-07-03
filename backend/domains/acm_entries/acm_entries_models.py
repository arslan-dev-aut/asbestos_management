"""Pydantic schemas for ACM entries and their attachments."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.responses import ApiResponse


class AcmAttachment(BaseModel):
    id: str
    acmEntryId: str
    fileName: str
    fileUrl: str
    uploadedAt: datetime
    uploadedBy: str


class AcmEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asbestosSiteId: str
    buildingTypeId: str
    roomLocation: str
    assetId: str | None = None
    assetDiscrepancy: bool = False
    acmTypeId: str
    condition: str
    riskScore: str
    riskRag: str
    notes: str | None = None
    status: str
    createdAt: datetime
    createdBy: str
    updatedAt: datetime
    updatedBy: str
    buildingTypeName: str | None = None
    assetName: str | None = None
    acmTypeName: str | None = None
    updatedByName: str | None = None
    attachments: list[AcmAttachment] = Field(default_factory=list)


class ActiveAcmAttachmentView(BaseModel):
    id: str
    fileName: str
    downloadUrl: str


class ActiveAcmEntryView(BaseModel):
    id: str
    building: str | None = None
    roomLocation: str
    assetId: str | None = None
    assetName: str | None = None
    assetDiscrepancy: bool = False
    acmType: str | None = None
    condition: str
    riskScore: str
    riskRag: str
    notes: str | None = None
    status: str
    updatedAt: datetime
    updatedBy: str
    updatedByName: str | None = None
    attachments: list[ActiveAcmAttachmentView] = Field(default_factory=list)


class ActiveAcmEntriesResponse(ApiResponse):
    acmEntries: list[ActiveAcmEntryView]
    totalCount: int
    page: int
    pageSize: int
