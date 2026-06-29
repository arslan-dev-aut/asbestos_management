"""Shared enums / constant value sets for the asbestos domain.

Mirrors Section 5.2 (Constants) and 5.3 (Audit Action Taxonomy) of the TSD.
"""

from enum import StrEnum


class Condition(StrEnum):
    GOOD = "GOOD"
    LOW_DAMAGE = "LOW_DAMAGE"
    MEDIUM_DAMAGE = "MEDIUM_DAMAGE"
    HIGH_DAMAGE = "HIGH_DAMAGE"


class RiskScore(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AcmStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REMEDIATED = "REMEDIATED"


class DocType(StrEnum):
    AMP = "AMP"
    SURVEY_REPORT = "SURVEY_REPORT"
    AIR_MONITORING = "AIR_MONITORING"
    OTHER = "OTHER"


class Rag(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    NONE = "NONE"


class HighestRisk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class AuditType(StrEnum):
    ASBESTOS_SITE = "ASBESTOS_SITE"
    ASBESTOS_ACM = "ASBESTOS_ACM"
    ASBESTOS_DOCUMENT = "ASBESTOS_DOCUMENT"
    ASBESTOS_CONFIGURATION = "ASBESTOS_CONFIGURATION"


class AuditAction(StrEnum):
    # Site management
    SITE_CREATED = "Site Created"
    SITE_DEACTIVATED = "Site Deactivated"
    SITE_REACTIVATED = "Site Reactivated"
    # ACM management
    ACM_ENTRY_CREATED = "ACM Entry Created"
    ACM_ENTRY_EDITED = "ACM Entry Edited"
    ACM_ENTRY_MARKED_REMEDIATED = "ACM Entry Marked Remediated"
    ACM_ENTRY_REACTIVATED = "ACM Entry Reactivated"
    # Document management
    SITE_DOCUMENT_UPLOADED = "Site Document Uploaded"
    SITE_DOCUMENT_REMOVED = "Site Document Removed"
    AMP_REPLACED = "AMP Replaced"
    AMP_EXPIRY_DATE_UPDATED = "AMP Expiry Date Updated"
    AMP_PROMOTED = "AMP Promoted to Current"
    ACM_DOCUMENT_UPLOADED = "ACM Document Uploaded"
    ACM_DOCUMENT_REMOVED = "ACM Document Removed"
    # Configuration
    BUILDING_TYPE_ADDED = "Building Type Added"
    BUILDING_TYPE_DEACTIVATED = "Building Type Deactivated"
    BUILDING_TYPE_REACTIVATED = "Building Type Reactivated"
    ACM_TYPE_ADDED = "ACM Type Added"
    ACM_TYPE_DEACTIVATED = "ACM Type Deactivated"
    ACM_TYPE_REACTIVATED = "ACM Type Reactivated"


# Valid (auditType -> allowed actions) mapping for the dependent Action dropdown.
AUDIT_ACTIONS_BY_TYPE: dict[AuditType, tuple[AuditAction, ...]] = {
    AuditType.ASBESTOS_SITE: (
        AuditAction.SITE_CREATED,
        AuditAction.SITE_DEACTIVATED,
        AuditAction.SITE_REACTIVATED,
    ),
    AuditType.ASBESTOS_ACM: (
        AuditAction.ACM_ENTRY_CREATED,
        AuditAction.ACM_ENTRY_EDITED,
        AuditAction.ACM_ENTRY_MARKED_REMEDIATED,
        AuditAction.ACM_ENTRY_REACTIVATED,
    ),
    AuditType.ASBESTOS_DOCUMENT: (
        AuditAction.SITE_DOCUMENT_UPLOADED,
        AuditAction.SITE_DOCUMENT_REMOVED,
        AuditAction.AMP_REPLACED,
        AuditAction.AMP_EXPIRY_DATE_UPDATED,
        AuditAction.AMP_PROMOTED,
        AuditAction.ACM_DOCUMENT_UPLOADED,
        AuditAction.ACM_DOCUMENT_REMOVED,
    ),
    AuditType.ASBESTOS_CONFIGURATION: (
        AuditAction.BUILDING_TYPE_ADDED,
        AuditAction.BUILDING_TYPE_DEACTIVATED,
        AuditAction.BUILDING_TYPE_REACTIVATED,
        AuditAction.ACM_TYPE_ADDED,
        AuditAction.ACM_TYPE_DEACTIVATED,
        AuditAction.ACM_TYPE_REACTIVATED,
    ),
}

# Risk ordering for "highest risk" computation.
RISK_ORDER: dict[str, int] = {RiskScore.LOW: 1, RiskScore.MEDIUM: 2, RiskScore.HIGH: 3}

# Risk -> RAG mapping (Section 5.2).
RISK_TO_RAG: dict[str, Rag] = {
    RiskScore.LOW: Rag.GREEN,
    RiskScore.MEDIUM: Rag.AMBER,
    RiskScore.HIGH: Rag.RED,
}

# Human labels for export / template files.
CONDITION_LABELS = {
    Condition.GOOD: "Good",
    Condition.LOW_DAMAGE: "Low Damage",
    Condition.MEDIUM_DAMAGE: "Medium Damage",
    Condition.HIGH_DAMAGE: "High Damage",
}
RISK_LABELS = {RiskScore.LOW: "Low", RiskScore.MEDIUM: "Medium", RiskScore.HIGH: "High"}
DOC_TYPE_LABELS = {
    DocType.AMP: "AMP",
    DocType.SURVEY_REPORT: "Survey Report",
    DocType.AIR_MONITORING: "Air Monitoring",
    DocType.OTHER: "Other",
}

# Reverse label -> value lookups for bulk import parsing (case-insensitive).
CONDITION_BY_LABEL = {v.lower(): k for k, v in CONDITION_LABELS.items()}
RISK_BY_LABEL = {v.lower(): k for k, v in RISK_LABELS.items()}

# Allowed upload MIME types and extensions for documents/attachments.
ALLOWED_FILE_MIME = {"application/pdf", "image/jpeg", "image/png"}
ALLOWED_FILE_EXT = {".pdf", ".jpeg", ".jpg", ".png"}

# Allowed bulk-upload file types.
ALLOWED_BULK_MIME = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}
ALLOWED_BULK_EXT = {".csv", ".xlsx"}
