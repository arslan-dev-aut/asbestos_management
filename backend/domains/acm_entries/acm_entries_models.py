"""Pydantic schemas for ACM entries and their attachments."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.config import get_settings
from backend.core.enums import Condition, RiskScore
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
    # resolved at read time
    buildingTypeName: str | None = None
    assetName: str | None = None
    acmTypeName: str | None = None
    updatedByName: str | None = None
    attachments: list[AcmAttachment] = Field(default_factory=list)


class _AcmWriteBase(BaseModel):
    buildingTypeId: str
    roomLocation: str = Field(min_length=1, max_length=500)
    assetId: str | None = None
    acmTypeId: str
    condition: Condition
    riskScore: RiskScore
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def _notes_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > get_settings().notes_max_length:
            raise ValueError(
                f"Notes must be {get_settings().notes_max_length} characters or fewer."
            )
        return v


class CreateAcmRequest(_AcmWriteBase):
    pass


class UpdateAcmRequest(_AcmWriteBase):
    pass


class AcmStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid(cls, v: str) -> str:
        if v not in ("ACTIVE", "REMEDIATED"):
            raise ValueError("status must be ACTIVE or REMEDIATED.")
        return v


class AcmEntryResponse(ApiResponse):
    acmEntry: AcmEntry


class AcmAttachmentResponse(ApiResponse):
    attachment: AcmAttachment


# ---- read-optimised view models (presigned URLs, resolved names) ----

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
    acmType: str | None = None
    condition: str
    riskScore: str
    riskRag: str
    notes: str | None = None
    status: str
    attachments: list[ActiveAcmAttachmentView] = Field(default_factory=list)


class ActiveAcmEntriesResponse(ApiResponse):
    acmEntries: list[ActiveAcmEntryView]
    totalCount: int
    page: int
    pageSize: int


class AssetAcmItem(BaseModel):
    assetId: str
    assetName: str | None = None
    acmEntries: list[ActiveAcmEntryView]


class AssetAcmMappingResponse(ApiResponse):
    mapping: list[AssetAcmItem]
