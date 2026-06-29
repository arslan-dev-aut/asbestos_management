"""Configuration endpoints (Section 4.1) — Building Types & ACM Types."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.validation import validate_nonempty, validate_uuid
from backend.database.exceptions import DomainError, UpstreamError
from backend.database.postgres import get_session
from backend.domains.configuration import configuration_service as svc
from backend.domains.configuration.configuration_models import (
    AcmTypeResponse,
    AcmTypesListResponse,
    BuildingTypeResponse,
    BuildingTypesListResponse,
    CreateTypeRequest,
    ToggleTypeRequest,
)
from backend.middleware.auth import AuthContext, get_context

router = APIRouter(prefix="/config", tags=["configuration"])


# ---- Building Types ----
@router.get("/building-types", response_model=BuildingTypesListResponse)
async def list_building_types(
    activeOnly: bool | None = Query(default=None, description="true = active only, false = inactive only, omit = all"),
    search: str | None = Query(default=None, description="Filter by name (case-insensitive)"),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BuildingTypesListResponse:
    try:
        items, total = await svc.list_types(
            session, svc.BUILDING,
            tenant_id=ctx.tenant_id,
            active_only=activeOnly,
            search=search,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return BuildingTypesListResponse(buildingTypes=items, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve building types.", detail=str(exc)) from exc


@router.post("/building-types", response_model=BuildingTypeResponse, status_code=201)
async def add_building_type(
    body: CreateTypeRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BuildingTypeResponse:
    validate_nonempty(body.name, "name")
    try:
        item = await svc.create_type(
            session, svc.BUILDING, name=body.name, tenant_id=ctx.tenant_id, user_id=ctx.user_id
        )
        return BuildingTypeResponse(buildingType=item, message="Building type added.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to create building type.", detail=str(exc)) from exc


@router.patch("/building-types/{type_id}", response_model=BuildingTypeResponse)
async def toggle_building_type(
    type_id: str,
    body: ToggleTypeRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BuildingTypeResponse:
    validate_uuid(type_id, "typeId")
    try:
        item = await svc.toggle_type(
            session, svc.BUILDING,
            type_id=type_id,
            tenant_id=ctx.tenant_id,
            is_active=body.isActive,
            user_id=ctx.user_id,
        )
        return BuildingTypeResponse(buildingType=item)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to update building type.", detail=str(exc)) from exc


# ---- ACM Types ----
@router.get("/acm-types", response_model=AcmTypesListResponse)
async def list_acm_types(
    activeOnly: bool | None = Query(default=None, description="true = active only, false = inactive only, omit = all"),
    search: str | None = Query(default=None, description="Filter by name (case-insensitive)"),
    pageIndex: int = Query(default=0, ge=0),
    pageSize: int = Query(default=10, ge=1, le=50),
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmTypesListResponse:
    try:
        items, total = await svc.list_types(
            session, svc.ACM,
            tenant_id=ctx.tenant_id,
            active_only=activeOnly,
            search=search,
            page_index=pageIndex,
            page_size=pageSize,
        )
        return AcmTypesListResponse(acmTypes=items, totalCount=total)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to retrieve ACM types.", detail=str(exc)) from exc


@router.post("/acm-types", response_model=AcmTypeResponse, status_code=201)
async def add_acm_type(
    body: CreateTypeRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmTypeResponse:
    validate_nonempty(body.name, "name")
    try:
        item = await svc.create_type(
            session, svc.ACM, name=body.name, tenant_id=ctx.tenant_id, user_id=ctx.user_id
        )
        return AcmTypeResponse(acmType=item, message="ACM type added.")
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to create ACM type.", detail=str(exc)) from exc


@router.patch("/acm-types/{type_id}", response_model=AcmTypeResponse)
async def toggle_acm_type(
    type_id: str,
    body: ToggleTypeRequest,
    ctx: AuthContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> AcmTypeResponse:
    validate_uuid(type_id, "typeId")
    try:
        item = await svc.toggle_type(
            session, svc.ACM,
            type_id=type_id,
            tenant_id=ctx.tenant_id,
            is_active=body.isActive,
            user_id=ctx.user_id,
        )
        return AcmTypeResponse(acmType=item)
    except DomainError:
        raise
    except Exception as exc:
        raise UpstreamError("Failed to update ACM type.", detail=str(exc)) from exc
