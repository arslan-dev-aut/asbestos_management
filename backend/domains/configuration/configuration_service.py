"""Configuration service — Building Types & ACM Types.

Add-and-toggle only (no edit, no delete) per the integrity model. The two
lookups are structurally identical, so behaviour is parametrised by a small
descriptor binding the ORM model to its audit actions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import AuditAction, AuditType
from backend.database.db_models import AsbestosAcmTypes, AsbestosBuildingTypes
from backend.database.exceptions import DuplicateError, NotFoundError, ValidationError
from backend.domains.audit import audit_service
from backend.domains.configuration.configuration_models import ConfigType


@dataclass(frozen=True)
class _Kind:
    model: type
    added: AuditAction
    deactivated: AuditAction
    reactivated: AuditAction


BUILDING = _Kind(
    model=AsbestosBuildingTypes,
    added=AuditAction.BUILDING_TYPE_ADDED,
    deactivated=AuditAction.BUILDING_TYPE_DEACTIVATED,
    reactivated=AuditAction.BUILDING_TYPE_REACTIVATED,
)
ACM = _Kind(
    model=AsbestosAcmTypes,
    added=AuditAction.ACM_TYPE_ADDED,
    deactivated=AuditAction.ACM_TYPE_DEACTIVATED,
    reactivated=AuditAction.ACM_TYPE_REACTIVATED,
)


def _to_schema(row) -> ConfigType:
    return ConfigType(
        id=str(row.id),
        name=row.name,
        isActive=row.is_active,
        createdAt=row.created_at,
        createdBy=str(row.created_by),
        updatedAt=row.updated_at,
        updatedBy=str(row.updated_by),
    )


async def type_exists(
    session: AsyncSession, kind: _Kind, *, name: str, tenant_id: str
) -> bool:
    """Return True if any type (active or inactive) with this name already
    exists for the tenant.

    Checked at the application layer before insert so the caller receives a
    clean DuplicateError rather than a DB constraint violation.
    """
    row = await session.scalar(
        select(kind.model).where(
            kind.model.name == name.strip(),
            kind.model.tenant_id == uuid.UUID(tenant_id),
        )
    )
    return row is not None


async def list_types(
    session: AsyncSession,
    kind: _Kind,
    *,
    tenant_id: str,
    active_only: bool | None,
    search: str | None = None,
    page_index: int = 0,
    page_size: int = 10,
) -> tuple[list[ConfigType], int]:
    base = select(kind.model).where(kind.model.tenant_id == uuid.UUID(tenant_id))
    if active_only is True:
        base = base.where(kind.model.is_active.is_(True))
    elif active_only is False:
        base = base.where(kind.model.is_active.is_(False))
    if search:
        base = base.where(kind.model.name.ilike(f"%{search.strip()}%"))

    total: int = (await session.scalar(select(func.count()).select_from(base.subquery()))) or 0

    rows = (
        await session.scalars(
            base.order_by(kind.model.name.asc())
            .offset(page_index * page_size)
            .limit(page_size)
        )
    ).all()
    return [_to_schema(r) for r in rows], total


async def create_type(
    session: AsyncSession, kind: _Kind, *, name: str, tenant_id: str, user_id: str
) -> ConfigType:
    name = name.strip()
    if not name:
        raise ValidationError("Name is required.")

    if await type_exists(session, kind, name=name, tenant_id=tenant_id):
        raise DuplicateError(f"A type named '{name}' already exists.")

    row = kind.model(
        tenant_id=uuid.UUID(tenant_id),
        name=name,
        is_active=True,
        created_by=uuid.UUID(str(user_id)),
        updated_by=uuid.UUID(str(user_id)),
    )
    session.add(row)
    await session.flush()

    await audit_service.record(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_CONFIGURATION,
        action=kind.added,
        details={"name": name, "typeId": str(row.id)},
    )
    await session.commit()
    return _to_schema(row)


async def toggle_type(
    session: AsyncSession, kind: _Kind, *, type_id: str, tenant_id: str, is_active: bool, user_id: str
) -> ConfigType:
    row = (
        await session.scalars(
            select(kind.model).where(
                kind.model.id == uuid.UUID(type_id),
                kind.model.tenant_id == uuid.UUID(tenant_id),
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Type not found.")

    row.is_active = is_active
    row.updated_by = uuid.UUID(str(user_id))

    await audit_service.record(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=AuditType.ASBESTOS_CONFIGURATION,
        action=kind.reactivated if is_active else kind.deactivated,
        details={"name": row.name, "typeId": str(row.id), "isActive": is_active},
    )
    await session.commit()
    return _to_schema(row)
