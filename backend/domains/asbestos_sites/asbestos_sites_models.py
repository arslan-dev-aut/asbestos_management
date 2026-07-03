"""Pydantic schemas for the asbestos_sites domain."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from backend.core.responses import ApiResponse


class SiteDetail(BaseModel):
    id: str
    customerId: str
    siteId: str
    customerName: str | None = None
    siteName: str | None = None
    highestRisk: str
    totalAcm: int
    activeAcm: int
    ampExpiryDate: date | None = None
    ampExpiryRag: str
    ampExpired: bool = False
    ampExpiringSoon: bool = False
    createdAt: datetime
    createdBy: str
    updatedAt: datetime
    updatedBy: str
    updatedByName: str | None = None


class SiteDetailResponse(ApiResponse):
    site: SiteDetail
