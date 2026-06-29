"""Bulk import / export service.

Validate is a dry run that resolves customer/site/building/ACM-type names to
IDs against MainSubSys + local config, returns a per-row status, and stashes a
resolved import plan under an ``uploadToken``. Confirm executes that plan,
auto-creating any sites not yet in the register.

The validation plan is held in a short-TTL in-process cache. For multi-replica
deployments this should move to Redis/DB; documented as a delivery limitation.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field

from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import (
    ALLOWED_BULK_EXT,
    CONDITION_BY_LABEL,
    RISK_BY_LABEL,
    AuditAction,
    AuditType,
    Condition,
    RiskScore,
)
from backend.config import get_settings
from backend.database.db_models import (
    AsbestosAcmEntries,
    AsbestosAcmTypes,
    AsbestosBuildingTypes,
    AsbestosSites,
)
from backend.database.exceptions import ValidationError
from backend.domains.audit import audit_service
from backend.domains.bulk.bulk_models import BulkUploadRow
from backend.domains.qrcode import qrcode_service
from backend.integrations.mainsubsys import MainSubSysClient

TEMPLATE_COLUMNS = [
    "Customer",
    "Customer ID",
    "Site Name",
    "Site ID",
    "Building",
    "Room/Location",
    "Asset",
    "ACM Type",
    "Condition",
    "Risk Score",
    "Notes",
]

_TOKEN_TTL_SECONDS = 1800


@dataclass
class _RowParsed:
    customer_name: str
    customer_id: str | None
    site_name: str
    site_id: str | None
    building: str
    room: str
    asset: str | None
    acm_type: str
    condition_raw: str
    risk_raw: str
    notes: str | None
    format_errors: list[str]


@dataclass
class _PlanRow:
    customer_id: str
    site_id: str
    building_type_id: str
    room_location: str
    asset_id: str | None
    acm_type_id: str
    condition: str
    risk_score: str
    notes: str | None


@dataclass
class _Plan:
    rows: list[_PlanRow] = field(default_factory=list)
    site_ids: set[str] = field(default_factory=set)  # distinct resolved site ids
    expires_at: float = 0.0


_PLAN_CACHE: dict[str, _Plan] = {}


def _prune_cache() -> None:
    now = time.time()
    for token in [t for t, p in _PLAN_CACHE.items() if p.expires_at < now]:
        _PLAN_CACHE.pop(token, None)


# ---- template / file helpers ----
def generate_template(fmt: str) -> tuple[bytes, str, str]:
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(TEMPLATE_COLUMNS)
        return (
            buf.getvalue().encode("utf-8-sig"),
            "text/csv",
            "asbestos-bulk-template.csv",
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "ACM Entries"
    ws.append(TEMPLATE_COLUMNS)
    out = io.BytesIO()
    wb.save(out)
    return (
        out.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "asbestos-bulk-template.xlsx",
    )


def _ext(file_name: str) -> str:
    return os.path.splitext(file_name or "")[1].lower()


def _read_rows(file_name: str, data: bytes) -> list[dict[str, str]]:
    ext = _ext(file_name)
    if ext not in ALLOWED_BULK_EXT:
        raise ValidationError("Only CSV and XLSX files are accepted.")

    if ext == ".csv":
        text = data.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
    except StopIteration:
        return []
    out: list[dict[str, str]] = []
    for raw in rows_iter:
        if raw is None or all(c is None or str(c).strip() == "" for c in raw):
            continue
        row = {header[i]: ("" if v is None else str(v).strip()) for i, v in enumerate(raw) if i < len(header)}
        out.append(row)
    return out


def _parse_condition(value: str) -> str | None:
    v = value.strip()
    if v in Condition.__members__.values():
        return v
    return CONDITION_BY_LABEL.get(v.lower())


def _parse_risk(value: str) -> str | None:
    v = value.strip()
    if v in RiskScore.__members__.values():
        return v
    return RISK_BY_LABEL.get(v.lower())


# ---- validate ----
async def validate(
    session: AsyncSession, *, tenant_id: str, file_name: str, data: bytes
) -> tuple[list[BulkUploadRow], int, int, list[str], str]:
    raw_rows = _read_rows(file_name, data)

    # Local active config lookups by lowercased name (tenant-scoped).
    building_rows = (
        await session.scalars(
            select(AsbestosBuildingTypes).where(
                AsbestosBuildingTypes.tenant_id == uuid.UUID(tenant_id),
                AsbestosBuildingTypes.is_active.is_(True),
            )
        )
    ).all()
    acm_rows = (
        await session.scalars(
            select(AsbestosAcmTypes).where(
                AsbestosAcmTypes.tenant_id == uuid.UUID(tenant_id),
                AsbestosAcmTypes.is_active.is_(True),
            )
        )
    ).all()
    building_by_name = {b.name.strip().lower(): str(b.id) for b in building_rows}
    acm_by_name = {a.name.strip().lower(): str(a.id) for a in acm_rows}

    # Phase 1: parse each row and validate UUID format — no upstream calls yet.
    parsed_rows: list[_RowParsed] = []
    for row in raw_rows:
        customer_name = row.get("Customer", "")
        customer_id_raw = row.get("Customer ID", "").strip()
        site_name = row.get("Site Name", "")
        site_id_raw = row.get("Site ID", "").strip()
        building = row.get("Building", "")
        room = row.get("Room/Location", "")
        asset = row.get("Asset", "") or None
        acm_type = row.get("ACM Type", "")
        condition_raw = row.get("Condition", "")
        risk_raw = row.get("Risk Score", "")
        notes = row.get("Notes", "") or None

        fmt_errors: list[str] = []

        customer_id: str | None = None
        if not customer_id_raw:
            fmt_errors.append("Customer ID is required")
        else:
            try:
                uuid.UUID(customer_id_raw)
                customer_id = customer_id_raw
            except ValueError:
                fmt_errors.append("Customer ID is not a valid UUID")

        site_id: str | None = None
        if not site_id_raw:
            fmt_errors.append("Site ID is required")
        else:
            try:
                uuid.UUID(site_id_raw)
                site_id = site_id_raw
            except ValueError:
                fmt_errors.append("Site ID is not a valid UUID")

        parsed_rows.append(
            _RowParsed(
                customer_name=customer_name,
                customer_id=customer_id,
                site_name=site_name,
                site_id=site_id,
                building=building,
                room=room,
                asset=asset,
                acm_type=acm_type,
                condition_raw=condition_raw,
                risk_raw=risk_raw,
                notes=notes,
                format_errors=fmt_errors,
            )
        )

    # Phase 2: batch-resolve all unique customer/site IDs against MainSubSys;
    # asset names are still resolved one at a time (optional field, low volume).
    all_customer_ids = {p.customer_id for p in parsed_rows if p.customer_id}
    all_site_ids = {p.site_id for p in parsed_rows if p.site_id}
    unique_asset_names = {p.asset for p in parsed_rows if p.asset}

    async with MainSubSysClient(tenant_id) as mss:
        resolved_customers, resolved_sites = await asyncio.gather(
            mss.resolve_customers(all_customer_ids),
            mss.resolve_sites(all_site_ids),
        )
        asset_cache: dict[str, str | None] = {}
        for name in unique_asset_names:
            asset_cache[name] = await mss.find_asset_by_name(name)

    # Phase 3: apply remaining validation and build output rows + plan.
    out_rows: list[BulkUploadRow] = []
    plan = _Plan(expires_at=time.time() + _TOKEN_TTL_SECONDS)
    sites_to_create_names: dict[str, str] = {}  # site_id -> display name

    for idx, p in enumerate(parsed_rows):
        errors: list[str] = list(p.format_errors)

        customer_id = p.customer_id
        site_id = p.site_id

        if customer_id and customer_id not in resolved_customers:
            errors.append("Customer ID not found in system")
        if site_id and site_id not in resolved_sites:
            errors.append("Site ID not found in system")

        # Prefer the name resolved from the ID; fall back to file text columns.
        display_customer = resolved_customers.get(customer_id, p.customer_name) if customer_id else p.customer_name
        display_site = resolved_sites.get(site_id, p.site_name) if site_id else p.site_name

        building_id = building_by_name.get(p.building.strip().lower())
        if not building_id:
            errors.append("Building type not found")

        acm_type_id = acm_by_name.get(p.acm_type.strip().lower())
        if not acm_type_id:
            errors.append("ACM Type not found")

        condition = _parse_condition(p.condition_raw)
        if condition is None:
            errors.append("Invalid Condition")

        risk = _parse_risk(p.risk_raw)
        if risk is None:
            errors.append("Invalid Risk Score")

        if p.notes and len(p.notes) > get_settings().notes_max_length:
            errors.append("Notes exceed 250 characters")

        # Asset is optional and best-effort (not an error if unresolved).
        asset_id: str | None = asset_cache.get(p.asset) if p.asset else None

        status = "ERROR" if errors else "VALID"
        out_rows.append(
            BulkUploadRow(
                rowIndex=idx,
                status=status,
                errorDetail="; ".join(errors) if errors else None,
                customerName=display_customer,
                siteName=display_site,
                building=p.building,
                roomLocation=p.room,
                asset=p.asset,
                acmType=p.acm_type,
                condition=p.condition_raw,
                riskScore=p.risk_raw,
                notes=p.notes,
            )
        )

        if status == "VALID":
            plan.rows.append(
                _PlanRow(
                    customer_id=customer_id,
                    site_id=site_id,
                    building_type_id=building_id,
                    room_location=p.room,
                    asset_id=asset_id,
                    acm_type_id=acm_type_id,
                    condition=condition,
                    risk_score=risk,
                    notes=p.notes,
                )
            )
            plan.site_ids.add(site_id)
            sites_to_create_names.setdefault(site_id, display_site)

    # Which valid sites are not yet in the register?
    sites_to_create: list[str] = []
    if plan.site_ids:
        existing = set(
            str(s)
            for s in (
                await session.scalars(
                    select(AsbestosSites.site_id).where(
                        AsbestosSites.tenant_id == uuid.UUID(tenant_id),
                        AsbestosSites.site_id.in_([uuid.UUID(s) for s in plan.site_ids]),
                    )
                )
            ).all()
        )
        sites_to_create = [
            sites_to_create_names[sid] for sid in plan.site_ids if sid not in existing
        ]

    valid_count = sum(1 for r in out_rows if r.status == "VALID")
    error_count = len(out_rows) - valid_count

    token = secrets.token_urlsafe(32)
    _prune_cache()
    _PLAN_CACHE[token] = plan
    return out_rows, valid_count, error_count, sites_to_create, token


# ---- confirm ----
async def confirm(
    session: AsyncSession, *, tenant_id: str, token: str, user_id: str
) -> tuple[int, int]:
    _prune_cache()
    plan = _PLAN_CACHE.pop(token, None)
    if plan is None or plan.expires_at < time.time():
        raise ValidationError("Upload token is invalid or has expired. Please re-validate.")

    uid = uuid.UUID(str(user_id))

    # Ensure all referenced sites exist; create the missing ones.
    existing_rows = (
        await session.scalars(
            select(AsbestosSites).where(
                AsbestosSites.tenant_id == uuid.UUID(tenant_id),
                AsbestosSites.site_id.in_([uuid.UUID(s) for s in plan.site_ids]),
            )
        )
    ).all()
    site_pk_by_site_id = {str(s.site_id): s.id for s in existing_rows}

    created_sites = 0
    for plan_row in plan.rows:
        if plan_row.site_id in site_pk_by_site_id:
            continue
        site = AsbestosSites(
            tenant_id=uuid.UUID(tenant_id),
            site_id=uuid.UUID(plan_row.site_id),
            customer_id=uuid.UUID(plan_row.customer_id),
            created_by=uid,
            updated_by=uid,
        )
        session.add(site)
        await session.flush()
        site_pk_by_site_id[plan_row.site_id] = site.id
        created_sites += 1
        await audit_service.record(
            session,
            site_id=str(site.id),
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type=AuditType.ASBESTOS_SITE,
            action=AuditAction.SITE_CREATED,
            details={"siteId": plan_row.site_id, "customerId": plan_row.customer_id, "source": "bulk"},
        )
        await qrcode_service.create_for_new_site(
            session, tenant_id=tenant_id, site_id=str(site.id), user_id=user_id
        )

    imported = 0
    for plan_row in plan.rows:
        site_pk = site_pk_by_site_id[plan_row.site_id]
        entry = AsbestosAcmEntries(
            tenant_id=uuid.UUID(tenant_id),
            asbestos_site_id=site_pk,
            building_type_id=uuid.UUID(plan_row.building_type_id),
            room_location=plan_row.room_location,
            asset_id=uuid.UUID(plan_row.asset_id) if plan_row.asset_id else None,
            acm_type_id=uuid.UUID(plan_row.acm_type_id),
            condition=plan_row.condition,
            risk_score=plan_row.risk_score,
            notes=plan_row.notes,
            status="ACTIVE",
            created_by=uid,
            updated_by=uid,
        )
        session.add(entry)
        await session.flush()
        imported += 1
        await audit_service.record(
            session,
            site_id=str(site_pk),
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type=AuditType.ASBESTOS_ACM,
            action=AuditAction.ACM_ENTRY_CREATED,
            details={
                "acmEntryId": str(entry.id),
                "buildingTypeId": plan_row.building_type_id,
                "roomLocation": plan_row.room_location,
                "acmTypeId": plan_row.acm_type_id,
                "riskScore": plan_row.risk_score,
                "condition": plan_row.condition,
                "source": "bulk",
            },
        )

    await session.commit()
    return imported, created_sites


# ---- export ----
EXPORT_COLUMNS = [
    "Customer",
    "Customer ID",
    "Site Name",
    "Site ID",
    "Building",
    "Room/Location",
    "Asset",
    "ACM Type",
    "Condition",
    "Risk Score",
    "Status",
    "Last Updated",
    "Updated By",
]


def build_export(rows: list[list[str]], fmt: str) -> tuple[bytes, str, str]:
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8-sig"), "text/csv", "asbestos-register.csv"
    wb = Workbook()
    ws = wb.active
    ws.title = "Register"
    ws.append(EXPORT_COLUMNS)
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return (
        out.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "asbestos-register.xlsx",
    )
