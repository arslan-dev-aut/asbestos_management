"""SQLAlchemy ORM models — all asbestos register tables.

Table names are snake_case; ORM classes are PascalCase derived from the same
name. Names of customer/site/asset/user are NEVER stored locally — only IDs.
Display names are resolved at read time from MainSubSys.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.postgres import Base

# Enum value sets (kept in sync with backend.core.enums).
CONDITION_VALUES = ("GOOD", "LOW_DAMAGE", "MEDIUM_DAMAGE", "HIGH_DAMAGE")
RISK_VALUES = ("LOW", "MEDIUM", "HIGH")
STATUS_VALUES = ("ACTIVE", "REMEDIATED")
DOC_TYPE_VALUES = ("AMP", "SURVEY_REPORT", "AIR_MONITORING", "OTHER")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# Column sets aligned to the ACTUAL Azure schema (introspected). Config lookups,
# sites and ACM entries carry created_*/updated_*; file/audit/QR tables do not.
class TimestampMixin:
    """created_*/updated_* (config lookups, sites, ACM entries)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class UploadedMixin:
    """uploaded_at/uploaded_by for file-bearing tables (no updated_* in the DB)."""

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AsbestosBuildingTypes(Base, TimestampMixin):
    __tablename__ = "asbestos_building_types"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # Names are unique PER TENANT, not globally.
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_building_types_tenant_name"),
    )


class AsbestosAcmTypes(Base, TimestampMixin):
    __tablename__ = "asbestos_acm_types"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # Names are unique PER TENANT, not globally.
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_acm_types_tenant_name"),
    )


class AsbestosSites(Base, TimestampMixin):
    __tablename__ = "asbestos_sites"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    documents: Mapped[list[AsbestosSiteDocuments]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    acm_entries: Mapped[list[AsbestosAcmEntries]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )

    # A JobLogic site is registered at most once PER TENANT (not globally).
    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", name="uq_asbestos_sites_tenant_site"),
        Index("idx_asbestos_sites_customer", "customer_id"),
    )


class AsbestosSiteDocuments(Base, UploadedMixin):
    __tablename__ = "asbestos_site_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    asbestos_site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_sites.id"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    amp_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current_amp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    site: Mapped[AsbestosSites] = relationship(back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('AMP','SURVEY_REPORT','AIR_MONITORING','OTHER')",
            name="ck_site_documents_doc_type",
        ),
        Index("idx_site_docs_amp", "asbestos_site_id", "doc_type", "is_current_amp"),
    )


class AsbestosAcmEntries(Base, TimestampMixin):
    __tablename__ = "asbestos_acm_entries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    asbestos_site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_sites.id"), nullable=False
    )
    building_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_building_types.id"), nullable=False
    )
    room_location: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    asset_discrepancy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    acm_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_acm_types.id"), nullable=False
    )
    condition: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_score: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(250), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )

    site: Mapped[AsbestosSites] = relationship(back_populates="acm_entries")
    building_type: Mapped[AsbestosBuildingTypes] = relationship()
    acm_type: Mapped[AsbestosAcmTypes] = relationship()
    attachments: Mapped[list[AsbestosAcmAttachments]] = relationship(
        back_populates="acm_entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "condition IN ('GOOD','LOW_DAMAGE','MEDIUM_DAMAGE','HIGH_DAMAGE')",
            name="ck_acm_entries_condition",
        ),
        CheckConstraint("risk_score IN ('LOW','MEDIUM','HIGH')", name="ck_acm_entries_risk"),
        CheckConstraint("status IN ('ACTIVE','REMEDIATED')", name="ck_acm_entries_status"),
        Index("idx_acm_entries_site_status", "asbestos_site_id", "status"),
        Index("idx_acm_entries_risk", "risk_score"),
        Index("idx_acm_entries_asset", "asset_id"),
    )


class AsbestosAcmAttachments(Base, UploadedMixin):
    __tablename__ = "asbestos_acm_attachments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    acm_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_acm_entries.id"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)

    acm_entry: Mapped[AsbestosAcmEntries] = relationship(back_populates="attachments")


class AsbestosAuditLog(Base):
    __tablename__ = "asbestos_audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Nullable — configuration actions (building/ACM type add/toggle) have no
    # associated site and are recorded with asbestos_site_id = NULL.
    asbestos_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_sites.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Plain b-tree on (site, occurred_at); Postgres scans backward for DESC ordering.
    __table_args__ = (Index("idx_audit_site_time", "asbestos_site_id", "occurred_at"),)


class AsbestosQrCodes(Base):
    __tablename__ = "asbestos_qr_codes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asbestos_sites.id"), nullable=False, unique=True
    )
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_qr_token", "token"),)
