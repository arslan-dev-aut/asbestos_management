"""Response models for the MainSubSys lookup endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class CustomerItem(BaseModel):
    id: int
    uniqueId: str
    name: str


class CustomerListResponse(BaseModel):
    customers: list[CustomerItem]
    totalCount: int


class SiteItem(BaseModel):
    id: int
    uniqueId: str
    name: str
    address: str | None = None
    customerName: str | None = None


class SiteListResponse(BaseModel):
    sites: list[SiteItem]
    totalCount: int


class AssetItem(BaseModel):
    id: int
    uniqueId: str
    name: str


class AssetListResponse(BaseModel):
    assets: list[AssetItem]
    totalCount: int
