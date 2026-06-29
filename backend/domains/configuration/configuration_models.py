"""Pydantic schemas for the configuration domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.responses import ApiResponse


class ConfigType(BaseModel):
    """Shared shape for AsbestosBuildingTypes / AsbestosAcmTypes."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    isActive: bool
    createdAt: datetime
    createdBy: str
    updatedAt: datetime
    updatedBy: str


class CreateTypeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ToggleTypeRequest(BaseModel):
    isActive: bool


class BuildingTypesListResponse(ApiResponse):
    buildingTypes: list[ConfigType]
    totalCount: int


class BuildingTypeResponse(ApiResponse):
    buildingType: ConfigType


class AcmTypesListResponse(ApiResponse):
    acmTypes: list[ConfigType]
    totalCount: int


class AcmTypeResponse(ApiResponse):
    acmType: ConfigType
