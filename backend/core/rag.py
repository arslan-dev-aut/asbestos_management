"""RAG / computed-field helpers (Section 8 — Register & Computed Field Rules).

Pure functions, no I/O, so they are trivially unit-testable.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone

from backend.config import get_settings
from backend.core.enums import RISK_ORDER, RISK_TO_RAG, HighestRisk, Rag


def _utc_today() -> date:
    """Today's date in UTC — stored timestamps are timezone-aware, so the
    compliance RAG must not flip a day early/late on a non-UTC host."""
    return datetime.now(timezone.utc).date()

_RANK_TO_HIGHEST = {
    0: HighestRisk.NONE,
    1: HighestRisk.LOW,
    2: HighestRisk.MEDIUM,
    3: HighestRisk.HIGH,
}


def highest_risk(active_risk_scores: Iterable[str]) -> HighestRisk:
    """Maximum risk (HIGH > MEDIUM > LOW) across ACTIVE entries; NONE if empty."""
    best = 0
    for score in active_risk_scores:
        best = max(best, RISK_ORDER.get(score, 0))
    return _RANK_TO_HIGHEST[best]


def risk_rag(risk_score: str) -> Rag:
    """RAG badge for a single ACM risk score."""
    return RISK_TO_RAG.get(risk_score, Rag.NONE)


def amp_expiry_rag(expiry: date | None, *, today: date | None = None) -> Rag:
    """AMP expiry RAG: Green > N days away, Amber within N days, Red if expired,
    NONE if no AMP/expiry. Threshold fixed (settings.amp_expiry_warning_days).
    """
    if expiry is None:
        return Rag.NONE
    today = today or _utc_today()
    threshold = get_settings().amp_expiry_warning_days
    days_left = (expiry - today).days
    if days_left < 0:
        return Rag.RED
    if days_left <= threshold:
        return Rag.AMBER
    return Rag.GREEN


def is_amp_expired(expiry: date | None, *, today: date | None = None) -> bool:
    if expiry is None:
        return False
    today = today or _utc_today()
    return (expiry - today).days < 0


def is_amp_expiring_soon(expiry: date | None, *, today: date | None = None) -> bool:
    if expiry is None:
        return False
    today = today or _utc_today()
    days_left = (expiry - today).days
    return 0 <= days_left <= get_settings().amp_expiry_warning_days
