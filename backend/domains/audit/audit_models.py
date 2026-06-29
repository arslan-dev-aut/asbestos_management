"""Pydantic schemas for the audit domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.core.enums import AuditType
from backend.core.responses import ApiResponse


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asbestosSiteId: str | None = None
    userId: str
    userName: str | None = None
    auditType: str
    action: str
    details: dict
    occurredAt: datetime


class AuditListResponse(ApiResponse):
    entries: list[AuditLogEntry]
    totalCount: int


class AuditTypeOption(BaseModel):
    auditType: str
    actions: list[str]


class AuditTaxonomyResponse(ApiResponse):
    """Drives the dependent Audit Type / Action dropdowns in the UI."""

    taxonomy: list[AuditTypeOption]
