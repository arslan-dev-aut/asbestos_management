"""Pydantic schemas for the register domain."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.core.responses import ApiResponse


class SiteListItem(BaseModel):
    id: str
    customerId: str
    siteId: str
    customerName: str | None = None
    siteName: str | None = None
    totalAcm: int
    activeAcm: int
    highestRisk: str
    ampExpiryDate: date | None = None
    ampExpiryRag: str
    lastUpdated: datetime
    updatedBy: str
    updatedByName: str | None = None


class SiteListResponse(ApiResponse):
    sites: list[SiteListItem]
    totalCount: int


class CreateSiteRequest(BaseModel):
    customerId: str = Field(min_length=1)
    siteId: str = Field(min_length=1)


class CreateSiteResponse(ApiResponse):
    asbestosSiteId: str


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


class RegisterCustomerItem(BaseModel):
    customerId: str
    customerName: str | None = None


class RegisterCustomerListResponse(ApiResponse):
    customers: list[RegisterCustomerItem]
    totalCount: int


class RegisterSiteItem(BaseModel):
    siteId: str
    siteName: str | None = None


class RegisterSiteListResponse(ApiResponse):
    sites: list[RegisterSiteItem]
    totalCount: int


class SiteExistsResponse(ApiResponse):
    exists: bool
    asbestosSiteId: str | None = None


class SiteAsbestosStatusResponse(ApiResponse):
    hasActiveAcm: bool
    activeAcmCount: int
