"""Pydantic schemas for the mobile API surface."""

from __future__ import annotations

from pydantic import BaseModel

from backend.core.responses import ApiResponse


class MobileSiteDetail(BaseModel):
    asbestosSiteId: str
    siteName: str | None = None
    customerName: str | None = None
    highestRisk: str
    activeAcmEntriesCount: int


class MobileSiteDetailResponse(ApiResponse):
    site: MobileSiteDetail
